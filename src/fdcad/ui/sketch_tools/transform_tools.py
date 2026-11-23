"""Move, Copy, Rotate, Scale and Stretch Entities (TUTORIAL_REVIEW_SPEC TR1, D684). No Qt.

All five work the same way:

1. Pick: click sketch entities (or start the tool with entities selected).
   Stretch picks with a box instead: drag across the ends to move, or click two
   corners.
2. Base point (centre for Rotate): click a point, a snap or empty space. The
   usual snaps apply.
3. The preview follows the cursor, and the panel values (Delta X and Y, the
   angle) follow it too, so they show in the view as value labels (T15.5).
   A click places it. A value typed in a label or the panel holds while the
   cursor moves; Enter then applies it without a click.

Each change is one undo step; the tool keeps its picks so it can go again.
"""

from __future__ import annotations

import copy as _copy
import itertools
import math

from fdcad.core.sketch.freeform import sample
from fdcad.core.sketch.model import Ellipse, EllipseArc, Point, Spline
from fdcad.core.sketch.ops.geom import Vec, dist
from fdcad.core.sketch.ops.transform import (
    Step,
    TransformError,
    TransformReport,
    copy,
    describe,
    move,
    points_in_box,
    stretch,
)
from fdcad.ui.sketch_tools.edit import SketchEdit
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.pick_tools import RELATION_LABELS, PickTool, add_curve_preview
from fdcad.ui.sketch_tools.tool_options import Option
from fdcad.ui.sketch_tools.tools import Preview

#: Snaps that name a place (a click there sets the base point, not a pick).
_PLACES = ("point", "center", "midpoint", "quadrant", "intersection")
_KEEP = Option(
    "keep_relations",
    "Keep relations",
    "bool",
    tip="Off removes every relation and dimension of the moved entities.",
)


def add_entity_preview(out: Preview, sketch: object, eid: str) -> None:
    """Draw any sketch entity into a preview: curves, freeform curves as short lines, points."""
    from fdcad.core.sketch.model import Sketch

    assert isinstance(sketch, Sketch)
    ent = sketch.entities.get(eid)
    if ent is None:
        return
    if isinstance(ent, Point):
        out.points.append((ent.x, ent.y))
    elif isinstance(ent, Ellipse | EllipseArc | Spline):
        pts = sample(sketch, ent, 48)
        out.lines += list(itertools.pairwise(pts))
    else:
        add_curve_preview(out, sketch, eid)


class _TransformTool(PickTool):
    """Shared picking, base point and applying (see the module notes)."""

    raw_cursor = False  # the base and target points use the usual snaps
    #: What the base point is called in the prompts.
    base_name = "base point"

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.picks: list[str] = []
        self.base: Vec | None = None
        self.keep_relations = True
        #: Values the user typed: they hold while the cursor moves.
        self.typed: set[str] = set()

    # Picking -------------------------------------------------------------------------

    def take_selection(self, ids: list[str]) -> None:
        """Start with the entities selected before the tool (TR1.1)."""
        sk = self.edit.sketch
        self.picks = [i for i in ids if i in sk.entities]

    @property
    def busy(self) -> bool:
        """True while something is picked."""
        return bool(self.picks)

    @property
    def prompt(self) -> str:  # type: ignore[override]
        """What to do next."""
        if not self.picks:
            return "Click the sketch entities to change, or select them first."
        if self.base is None:
            return f"Click more entities, or click the {self.base_name}."
        return "Click to place it, or type a value and press Enter."

    def cancel(self) -> bool:
        """Escape steps back: the base point, then the picks, then ends the tool."""
        if self.base is not None:
            self.base = None
            return False
        if self.picks:
            self.picks, self.typed = [], set()
            return False
        return True

    def entity_at(self, p: Vec) -> str | None:
        """The curve or point under ``p``."""
        cid = self.curve_at(p)
        if cid is not None:
            return cid
        for e in self.edit.sketch.entities.values():
            if isinstance(e, Point) and dist((e.x, e.y), p) <= self.tolerance:
                return e.id
        return None

    def hover(self, snap: Snap) -> Snap:
        """Track the entity under the cursor, and the values while placing."""
        self.cursor = snap
        self.hot = self.entity_at(snap.xy) if self.base is None else None
        if self.base is not None:
            self.follow(snap.xy)
        return snap

    def follow(self, at: Vec) -> None:
        """Set the values from the cursor (unless typed)."""

    def click(self, snap: Snap) -> bool:
        """Pick, set the base point, or place."""
        self.hover(snap)
        if self.base is not None:
            self.follow(snap.xy)
            return self.place()
        hit = self.entity_at(snap.xy)
        if self.picks and (snap.kind in _PLACES or hit is None):
            self.set_base(snap.xy)
            return False
        if hit is None:
            return False
        if hit in self.picks:
            self.picks.remove(hit)
        else:
            self.picks.append(hit)
        return False

    def set_base(self, at: Vec) -> None:
        """The base point is set: placing starts."""
        self.base = at

    # Applying -------------------------------------------------------------------------

    def option_changed(self, key: str) -> bool:
        """A typed value holds while the cursor moves."""
        self.typed.add(key)
        return False

    def enter(self) -> bool | None:
        """Enter with no value box open: apply the typed values. None when not used."""
        if not self.picks or not self.ready():
            return None
        return self.place()

    def ready(self) -> bool:
        """True when the values say what to do without a click."""
        return False

    def enter_ready(self) -> bool:
        """True when Enter would apply something (the canvas then takes the key)."""
        return bool(self.picks) and self.ready()

    def change(self, sketch: object) -> TransformReport:
        """Make the change on ``sketch``."""
        raise NotImplementedError

    def place(self) -> bool:
        """Make the change as one undo step; the picks stay for another go."""
        self.edit.checkpoint()
        try:
            report = self.change(self.edit.sketch)
        except (TransformError, KeyError, TypeError, ZeroDivisionError) as exc:
            self.edit.discard_checkpoint()
            self.message = str(exc) if isinstance(exc, TransformError) else ""
            return False
        self.message = describe(report, RELATION_LABELS)
        self.drawn = list(report.entities)
        self.after_place(report)
        return True

    def after_place(self, report: TransformReport) -> None:
        """Ready for the next go: the base point is asked again."""
        self.base = None
        self.typed.discard("dx")
        self.typed.discard("dy")
        self.typed.discard("angle")
        self.picks = [p for p in self.picks if p in self.edit.sketch.entities]

    # Preview --------------------------------------------------------------------------

    def preview(self) -> Preview:
        """The picks, and the result on a copy of the sketch."""
        out = super().preview()
        sk = self.edit.sketch
        for eid in self.picks:
            add_entity_preview(out, sk, eid)
        if self.hot is not None and self.hot not in self.picks:
            add_entity_preview(out, sk, self.hot)
        if self.base is not None:
            out.points.append(self.base)
        if not self.picks or not (self.base is not None or self.ready()):
            return out
        trial = _copy.deepcopy(sk)
        try:
            report = self.change(trial)
        except (TransformError, KeyError, TypeError, ZeroDivisionError):
            return out
        for eid in self.shown(report):
            add_entity_preview(out, trial, eid)
        return out

    def shown(self, report: TransformReport) -> list[str]:
        """The entities of the trial result to draw."""
        return report.entities or list(self.picks)


class MoveEntitiesTool(_TransformTool):
    """Move Entities: from a base point to a target, or by Delta X and Delta Y."""

    name, label = "move_entities", "Move Entities"
    options: tuple[Option, ...] = (
        Option("dx", "Delta X", "length"),
        Option("dy", "Delta Y", "length"),
        _KEEP,
    )

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.dx = 0.0
        self.dy = 0.0

    def follow(self, at: Vec) -> None:
        """Delta X and Y follow the cursor from the base point."""
        if self.base is None:
            return
        if "dx" not in self.typed:
            self.dx = at[0] - self.base[0]
        if "dy" not in self.typed:
            self.dy = at[1] - self.base[1]

    def ready(self) -> bool:
        """Typed deltas can be applied with Enter."""
        return bool({"dx", "dy"} & self.typed) and math.hypot(self.dx, self.dy) > 1e-9

    def step(self) -> Step:
        """The move."""
        return Step("move", self.dx, self.dy)

    def change(self, sketch: object) -> TransformReport:
        """Move the picks."""
        from fdcad.core.sketch.model import Sketch

        assert isinstance(sketch, Sketch)
        if math.hypot(self.dx, self.dy) <= 1e-9:
            raise TransformError("Type a distance to move by, or click a target point.")
        return move(sketch, self.picks, self.step(), self.keep_relations)


class CopyEntitiesTool(MoveEntitiesTool):
    """Copy Entities: like Move, leaving the originals; each copy one more step away."""

    name, label = "copy_entities", "Copy Entities"
    options: tuple[Option, ...] = (
        Option("dx", "Delta X", "length"),
        Option("dy", "Delta Y", "length"),
        Option("count", "Copies", "int", low=1, high=500),
        _KEEP,
        Option("linked", "Linked", "bool", tip="Copied dimensions follow the originals."),
    )

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.count = 1
        #: Copied dimensions share a value link with their originals (TR122, D1315).
        self.linked = False

    def change(self, sketch: object) -> TransformReport:
        """Add the copies."""
        from fdcad.core.sketch.model import Sketch

        assert isinstance(sketch, Sketch)
        if math.hypot(self.dx, self.dy) <= 1e-9:
            raise TransformError("Type a distance to copy by, or click a target point.")
        return copy(
            sketch, self.picks, self.step(), self.count, self.keep_relations, bool(self.linked)
        )


class RotateEntitiesTool(_TransformTool):
    """Rotate Entities about a centre by an angle."""

    name, label = "rotate_entities", "Rotate Entities"
    base_name = "center of rotation"
    options: tuple[Option, ...] = (
        Option("cx", "Center X", "length"),
        Option("cy", "Center Y", "length"),
        Option("angle", "Angle", "angle"),
        _KEEP,
    )

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.cx = 0.0
        self.cy = 0.0
        self.angle = 0.0

    def set_base(self, at: Vec) -> None:
        """The centre is set: the angle follows the cursor from here."""
        super().set_base(at)
        self.cx, self.cy = at
        self.typed -= {"cx", "cy"}

    def option_changed(self, key: str) -> bool:
        """A typed centre sets the centre."""
        super().option_changed(key)
        if key in ("cx", "cy") and self.picks:
            self.base = (self.cx, self.cy)
        return False

    def follow(self, at: Vec) -> None:
        """The angle follows the cursor, measured from the X direction."""
        if self.base is None or "angle" in self.typed:
            return
        if dist(at, self.base) > 1e-9:
            self.angle = math.atan2(at[1] - self.base[1], at[0] - self.base[0])

    def ready(self) -> bool:
        """A typed angle can be applied with Enter, about the typed or clicked centre."""
        return "angle" in self.typed and abs(self.angle) > 1e-12

    def change(self, sketch: object) -> TransformReport:
        """Turn the picks."""
        from fdcad.core.sketch.model import Sketch

        assert isinstance(sketch, Sketch)
        if abs(math.remainder(self.angle, 2 * math.pi)) <= 1e-12:
            raise TransformError("Type an angle, or click where the picks should turn to.")
        step = Step("rotate", centre=(self.cx, self.cy), angle=self.angle)
        return move(sketch, self.picks, step, self.keep_relations)


class ScaleEntitiesTool(_TransformTool):
    """Scale Entities about a base point by a factor, with Copy and a number of copies."""

    name, label = "scale_entities", "Scale Entities"
    options: tuple[Option, ...] = (
        Option("cx", "Base X", "length"),
        Option("cy", "Base Y", "length"),
        Option("factor", "Scale factor", "number"),
        Option("make_copy", "Copy", "bool", tip="Leave the originals and add scaled copies."),
        Option("count", "Copies", "int", low=1, high=500),
        _KEEP,
    )

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.cx = 0.0
        self.cy = 0.0
        self.factor = 2.0
        self.make_copy = False
        self.count = 1

    @property
    def prompt(self) -> str:  # type: ignore[override]
        """What to do next."""
        if self.picks and self.base is not None:
            return "Click to scale, or type the factor and press Enter."
        return super().prompt

    def set_base(self, at: Vec) -> None:
        """The base point is set; the preview shows the scaled picks."""
        super().set_base(at)
        self.cx, self.cy = at

    def option_changed(self, key: str) -> bool:
        """A typed base point sets the base point."""
        super().option_changed(key)
        if key in ("cx", "cy") and self.picks:
            self.base = (self.cx, self.cy)
        return False

    def ready(self) -> bool:
        """Enter applies once there is a base point."""
        return self.base is not None

    def change(self, sketch: object) -> TransformReport:
        """Scale the picks, or add scaled copies."""
        from fdcad.core.sketch.model import Sketch

        assert isinstance(sketch, Sketch)
        if abs(self.factor - 1.0) <= 1e-12:
            raise TransformError("Type a scale factor other than 1.")
        step = Step("scale", centre=(self.cx, self.cy), factor=self.factor)
        if self.make_copy:
            return copy(sketch, self.picks, step, self.count, self.keep_relations)
        return move(sketch, self.picks, step, self.keep_relations)


class StretchEntitiesTool(MoveEntitiesTool):
    """Stretch Entities: the points inside a crossing box move, the rest stay."""

    name, label = "stretch_entities", "Stretch Entities"
    options: tuple[Option, ...] = (
        Option("dx", "Delta X", "length"),
        Option("dy", "Delta Y", "length"),
        _KEEP,
    )

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        #: The crossing box, once drawn.
        self.box: tuple[Vec, Vec] | None = None
        #: The first corner while the box is being drawn.
        self.corner: Vec | None = None

    def take_selection(self, ids: list[str]) -> None:
        """Stretch picks with a box only."""

    @property
    def busy(self) -> bool:
        """True while a box is drawn or being drawn."""
        return self.box is not None or self.corner is not None

    @property
    def prompt(self) -> str:  # type: ignore[override]
        """What to do next."""
        if self.box is None:
            if self.corner is None:
                return "Drag a box across the ends to stretch, or click its first corner."
            return "Click the other corner of the box."
        return super().prompt

    def cancel(self) -> bool:
        """Escape steps back: the base point, the box, then ends the tool."""
        if self.base is not None:
            self.base = None
            return False
        if self.box is not None or self.corner is not None:
            self.box, self.corner, self.picks, self.typed = None, None, [], set()
            return False
        return True

    def hover(self, snap: Snap) -> Snap:
        """Track the box corner, then the values while placing."""
        self.cursor = snap
        self.hot = None
        if self.base is not None:
            self.follow(snap.xy)
        return snap

    def click(self, snap: Snap) -> bool:
        """Draw the box, set the base point, or place."""
        self.hover(snap)
        if self.box is None:
            if self.corner is None:
                self.corner = snap.xy
                return False
            return self._close_box(snap.xy)
        if self.base is None:
            self.set_base(snap.xy)
            return False
        return self.place()

    def release(self, snap: Snap, moved: bool) -> bool:
        """A press, drag and release draws the whole box."""
        if self.box is None and self.corner is not None and moved:
            self._close_box(snap.xy)
        return False

    def _close_box(self, at: Vec) -> bool:
        a = self.corner
        assert a is not None
        self.corner = None
        if dist(a, at) <= 1e-9:
            return False
        inside = points_in_box(self.edit.sketch, a, at)
        if not inside:
            self.message = (
                "No sketch points are inside the box. Drag a box across the ends to stretch."
            )
            return False
        self.box = (a, at)
        self.picks = self._touched(inside)
        return False

    def _touched(self, inside: set[str]) -> list[str]:
        from fdcad.core.sketch.model import entity_points

        sk = self.edit.sketch
        return [
            e.id
            for e in sk.entities.values()
            if not isinstance(e, Point) and set(entity_points(e)) & inside
        ] or sorted(inside)

    def change(self, sketch: object) -> TransformReport:
        """Stretch the box's points."""
        from fdcad.core.sketch.model import Sketch

        assert isinstance(sketch, Sketch)
        if self.box is None:
            raise TransformError("Drag a box across the ends to stretch.")
        return stretch(sketch, *self.box, self.dx, self.dy, self.keep_relations)

    def after_place(self, report: TransformReport) -> None:
        """Ready for the next stretch: a new box."""
        super().after_place(report)
        self.box, self.picks = None, []

    def preview(self) -> Preview:
        """The box while drawing it, then the stretched curves."""
        out = super().preview()
        corners = None
        if self.box is not None:
            corners = self.box
        elif self.corner is not None and self.cursor is not None:
            corners = (self.corner, self.cursor.xy)
        if corners is not None:
            (x0, y0), (x1, y1) = corners
            ring = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            out.lines += [(ring[i], ring[(i + 1) % 4]) for i in range(4)]
        return out

    def shown(self, report: TransformReport) -> list[str]:
        """The curves the box touches."""
        return list(self.picks)


#: The five tools by name, in command order (TR1.1).
TRANSFORM_TOOLS: dict[str, type[_TransformTool]] = {
    "move_entities": MoveEntitiesTool,
    "copy_entities": CopyEntitiesTool,
    "rotate_entities": RotateEntitiesTool,
    "scale_entities": ScaleEntitiesTool,
    "stretch_entities": StretchEntitiesTool,
}
