"""Sketch fillet and sketch chamfer tools (PHASE2_SPEC P2.8 items 6 and 7). No Qt."""

from __future__ import annotations

import math
from typing import Any

from fdcad.core.sketch.model import Arc, Line, Point, Spline
from fdcad.core.sketch.ops.corner import (
    CHAMFER_KINDS,
    CornerError,
    CornerResult,
    NeedsConfirmError,
    chamfer,
    fillet,
    lines_at,
)
from fdcad.core.sketch.ops.geom import Vec, dist
from fdcad.core.sketch.ops.trim import describe
from fdcad.ui.sketch_tools.edit import SketchEdit
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.pick_tools import RELATION_LABELS, PickTool, add_curve_preview
from fdcad.ui.sketch_tools.tool_options import Option
from fdcad.ui.sketch_tools.tools import Preview


def _ends(c: object) -> tuple[str, ...]:
    if isinstance(c, Line):
        return (c.p1, c.p2)
    if isinstance(c, Arc):
        return (c.start, c.end)
    if isinstance(c, Spline):
        return (c.points[0], c.points[-1])
    return ()


class CornerTool(PickTool):
    """Shared picking: a corner point where two lines meet, or two lines."""

    pickable: tuple[type[Any], ...] = (Line,)

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.first: tuple[str, Vec] | None = None
        #: A corner whose deletion of relations the next click on it confirms.
        self.confirm: tuple[str, str] | None = None

    @property
    def prompt(self) -> str:  # type: ignore[override]
        """What to click next."""
        if self.first is None:
            return "Click a corner point, or the first of two lines."
        return "Click the second curve."

    @property
    def busy(self) -> bool:
        """True after the first line."""
        return self.first is not None

    def cancel(self) -> bool:
        """Escape drops the first pick, then ends the tool."""
        if self.first is not None:
            self.first = None
            return False
        return True

    def _corner_point(self, at: Vec) -> tuple[str, str, Vec] | None:
        sk = self.edit.sketch
        for e in sk.entities.values():
            if isinstance(e, Point) and dist((e.x, e.y), at) <= self.tolerance:
                lines = lines_at(sk, e.id)
                if len(lines) == 2:
                    return lines[0], lines[1], (e.x, e.y)
        if self.pickable == (Line,):
            return None
        for e in sk.entities.values():
            if isinstance(e, Point) and dist((e.x, e.y), at) <= self.tolerance:
                curves = [
                    c.id
                    for c in sk.curves()
                    if isinstance(c, self.pickable)
                    and any(dist(sk.xy(p), (e.x, e.y)) < 1e-6 for p in _ends(c))
                ]
                if len(curves) == 2:
                    return curves[0], curves[1], (e.x, e.y)
        return None

    def click(self, snap: Snap) -> bool:
        """A corner point acts at once; lines are picked one by one."""
        self.hover(snap)
        at = snap.xy
        if self.first is None:
            corner = self._corner_point(at)
            if corner is not None:
                a, b, x = corner
                return self._run(a, x, b, x)
        cid = self.hot
        if cid is None:
            return False
        if self.first is None:
            self.first = (cid, at)
            return False
        first, self.first = self.first, None
        if first[0] == cid:
            return False
        return self._run(first[0], first[1], cid, at)

    def _run(self, a: str, pa: Vec, b: str, pb: Vec) -> bool:
        force = self.confirm == (a, b)
        #: The undo depth before this corner, for sizing it by dragging (TR48, D1702).
        self.depth_before = self.edit.undo_depth
        self.edit.checkpoint()
        try:
            result = self.make(a, pa, b, pb, force)
        except NeedsConfirmError as exc:
            self.edit.discard_checkpoint()
            self.confirm = (a, b)
            self.message = str(exc)
            return False
        except CornerError as exc:
            self.edit.discard_checkpoint()
            self.message = str(exc)
            return False
        self.confirm = None
        self.drawn = [result.curve]
        self.message = describe(result.report, RELATION_LABELS)
        return True

    def make(self, a: str, pa: Vec, b: str, pb: Vec, force: bool) -> CornerResult:
        """Make the corner shape."""
        raise NotImplementedError

    def preview(self) -> Preview:
        """The first line and the line under the cursor."""
        out = super().preview()
        if self.first is not None and self.first[0] in self.edit.sketch.entities:
            add_curve_preview(out, self.edit.sketch, self.first[0])
        return out


class SketchFilletTool(CornerTool):
    """Round corners with tangent arcs (P2.8 item 6)."""

    name, label = "fillet", "Sketch Fillet"
    pickable = (Line, Arc, Spline)  # TR48: arcs (D1317) and splines (D1700)
    options = (
        Option("radius", "Radius", "length"),
        Option("keep_corner", "Keep constrained corners", "bool"),
        Option("dimension_each", "Dimension each fillet", "bool"),
    )

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.radius = 5.0
        self.keep_corner = True
        self.dimension_each = True
        #: The first fillet made since the tool started; later ones may get Equal to it.
        self.first_fillet: str | None = None
        #: A corner just rounded from its point, which dragging resizes (TR48, D1702):
        #: the two curves, the corner, and the undo depth before it.
        self.sizing: tuple[str, str, Vec, int] | None = None
        #: The fillet being sized gets its own radius dimension.
        self._own_dimension = False

    @property
    def busy(self) -> bool:
        """True after the first curve, and while a new fillet can be sized by dragging."""
        return self.first is not None or self.sizing is not None

    def cancel(self) -> bool:
        """Escape stops sizing, drops the first pick, then ends the tool."""
        self.sizing = None
        return super().cancel()

    def click(self, snap: Snap) -> bool:
        """A corner point rounds it at once; holding the button and dragging then sizes
        the fillet (TR48, D1702)."""
        self.sizing = None
        corner = self._corner_point(snap.xy) if self.first is None else None
        made = super().click(snap)
        if made and corner is not None:
            a, b, x = corner
            self.sizing = (a, b, x, self.depth_before)
        return made

    def hover(self, snap: Snap) -> Snap:
        """While sizing, the radius is the distance from the corner to the cursor."""
        out = super().hover(snap)
        if self.sizing is not None:
            _a, _b, x, _depth = self.sizing
            r = dist(x, snap.xy)
            if r > self.tolerance:
                self.resize(r)
        return out

    def resize(self, radius: float) -> bool:
        """Make the fillet being sized again with ``radius``; on a radius that does not
        fit, keep the last one that did. True when it changed."""
        if self.sizing is None:
            return False
        a, b, x, depth = self.sizing
        good = self.radius
        for r in (radius, good):
            self.edit.rollback(depth)
            if self.first_fillet is not None and self.first_fillet not in self.edit.sketch.entities:
                self.first_fillet = None
            self.edit.checkpoint()
            self._own_dimension = True
            self.radius = r
            try:
                result = self.make(a, x, b, x, True)
            except CornerError as exc:
                self.message = str(exc)
                continue
            finally:
                self._own_dimension = False
            self.drawn = [result.curve]
            return r == radius
        self.radius = good
        self.edit.rollback(depth)
        self.sizing = None
        return False

    def release(self, snap: Snap, moved: bool) -> bool:
        """The end of a press: ends sizing; a drag from the first curve picks the
        second there."""
        if self.sizing is not None:
            self.sizing = None
            return moved
        if moved:
            return self.click(snap)
        return False

    def make(self, a: str, pa: Vec, b: str, pb: Vec, force: bool) -> CornerResult:
        """A fillet with the panel's options; a corner with an arc uses the curve fillet
        (TR48, D1317)."""
        own = self.dimension_each or self._own_dimension
        equal_to = self.first_fillet if not own else None
        sk = self.edit.sketch
        if not (isinstance(sk.entities.get(a), Line) and isinstance(sk.entities.get(b), Line)):
            from fdcad.core.sketch.ops.curve_fillet import fillet_curves

            result = fillet_curves(
                sk,
                a,
                b,
                self.radius,
                dimension=own or self.first_fillet is None,
                equal_to=equal_to,
            )
            if self.first_fillet is None or self.first_fillet not in sk.entities:
                self.first_fillet = result.curve
            return result
        result = fillet(
            self.edit.sketch,
            a,
            pa,
            b,
            pb,
            self.radius,
            self.keep_corner,
            force,
            dimension=own or self.first_fillet is None,
            equal_to=equal_to,
        )
        if self.first_fillet is None or self.first_fillet not in self.edit.sketch.entities:
            self.first_fillet = result.curve
        return result


CHAMFER_LABELS = {
    "angle_distance": "Angle and distance",
    "distance_distance": "Distance and distance",
}


class SketchChamferTool(CornerTool):
    """Cut corners with a line (P2.8 item 7). Distance 1 is on the first line picked."""

    name, label = "chamfer", "Sketch Chamfer"
    pickable = (Line, Arc, Spline)  # TR48 (D1701): arcs and splines too
    options = (
        Option("kind", "Type", "choice", tuple((k, CHAMFER_LABELS[k]) for k in CHAMFER_KINDS)),
        Option("equal", "Equal distance", "bool"),
        Option("d1", "Distance 1", "length"),
        Option("d2", "Distance 2", "length"),
        Option("angle", "Angle", "angle"),
    )

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.kind = "distance_distance"
        self.equal = True
        self.d1 = 5.0
        self.d2 = 5.0
        self.angle = math.radians(45.0)

    def make(self, a: str, pa: Vec, b: str, pb: Vec, force: bool) -> CornerResult:
        """A chamfer with the panel's values."""
        d2 = self.d1 if self.equal else self.d2
        sk = self.edit.sketch
        if not (isinstance(sk.entities.get(a), Line) and isinstance(sk.entities.get(b), Line)):
            from fdcad.core.sketch.ops.curve_chamfer import chamfer_curves

            return chamfer_curves(sk, a, b, self.kind, self.d1, d2)
        return chamfer(self.edit.sketch, a, pa, b, pb, self.kind, self.d1, d2, self.angle)
