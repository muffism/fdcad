"""Baseline and Ordinate dimensions, and Chamfer dimensions (TUTORIAL_REVIEW_SPEC_2 TR45,
D1307). Pure Python, no Qt.

* Baseline Dimension: click a base point or line, then each item to measure from
  it. Each click adds one driving dimension; their texts stack, each row one step
  further out.
* Ordinate Dimension: click the zero point, then points. Each adds a horizontal
  (or vertical) distance from the zero point drawn as a short leader with its
  number (``display`` style ``ordinate``). The texts of one group move together.
* Chamfer dimensions: ``chamfer_dimensions`` adds a length and an angle, or two
  lengths, to a chamfer line between two lines.

All are ordinary sketch dimensions: driving by default, and they can be made
reference like any other.
"""

from __future__ import annotations

import math

from fdcad.core.sketch.model import Dimension, Line, Point, Sketch
from fdcad.core.sketch.ops.geom import nearest_curve
from fdcad.ui.sketch_tools.edit import SketchEdit, label_anchor
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.tool_options import Option
from fdcad.ui.sketch_tools.tools import Preview, Tool

AXES = (("horizontal", "Horizontal"), ("vertical", "Vertical"))
#: Space between stacked rows and between a group and its points, in mm per pixel scale
#: (the canvas sets ``tolerance`` from the zoom; rows are this many pick distances apart).
_ROW = 8.0


def _item_at(edit: SketchEdit, snap: Snap, tolerance: float, lines: bool) -> str | None:
    """The point under the snap, else (with ``lines``) the line under it."""
    sk = edit.sketch
    if snap.target is not None and isinstance(sk.entities.get(snap.target), Point):
        return snap.target
    if lines:
        return nearest_curve(sk, snap.xy, tolerance, (Line,))
    return None


class BaselineDimensionTool(Tool):
    """Base item first, then each item measured from it."""

    name, label = "baseline_dimension", "Baseline Dimension"
    options = (Option("axis", "Direction from a base point", "choice", choices=AXES),)

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.axis = "horizontal"
        self.base: str | None = None
        self.made: list[str] = []
        self.message = ""

    @property
    def prompt(self) -> str:
        """What to click next."""
        if self.base is None:
            return "Click the base point or line."
        return "Click each point or line to measure from the base. Press Escape to finish."

    @property
    def busy(self) -> bool:
        """True once the base is picked."""
        return self.base is not None

    def cancel(self) -> bool:
        """Escape starts again with a new base, then ends the tool."""
        if self.base is not None:
            self.base, self.made = None, []
            return False
        return True

    def click(self, snap: Snap) -> bool:
        """Pick the base, then add a dimension per item."""
        item = _item_at(self.edit, snap, self.tolerance, lines=True)
        if item is None:
            self.message = "Click a point or a line."
            return False
        if self.base is None:
            self.base = item
            return False
        if item == self.base:
            return False
        return self._add(item)

    def _dtype(self, item: str) -> str:
        sk = self.edit.sketch
        if isinstance(sk.entities[self.base or ""], Line) or isinstance(sk.entities[item], Line):
            return "distance"
        return f"{self.axis}_distance"

    def _add(self, item: str) -> bool:
        assert self.base is not None
        edit = self.edit
        edit.checkpoint()
        try:
            dim = edit.add_dimension(self._dtype(item), [self.base, item], None)
        except (ValueError, KeyError, TypeError) as exc:
            edit.discard_checkpoint()
            self.message = f"Baseline Dimension failed: {exc}"
            return False
        self.made.append(dim.id)
        _stack(edit, dim, len(self.made), self.tolerance * _ROW)
        if edit.over_defines(dim.id):
            dim.driving = False
            self.message = "That size is already set, so it was added as a reference dimension."
        return True

    def take_message(self) -> str:
        """The status note, cleared once read."""
        msg, self.message = self.message, ""
        return msg

    def preview(self) -> Preview:
        """A mark on the base."""
        out = Preview()
        sk = self.edit.sketch
        base = sk.entities.get(self.base or "")
        if isinstance(base, Point):
            out.points.append((base.x, base.y))
        elif isinstance(base, Line):
            out.lines.append((sk.xy(base.p1), sk.xy(base.p2)))
        return out


def _stack(edit: SketchEdit, dim: Dimension, row: int, step: float) -> None:
    """Put the text of the row-th baseline dimension ``row`` steps out."""
    sk = edit.sketch
    anchor = label_anchor(sk, dim)
    if dim.type == "horizontal_distance":
        edit.set_label(dim.id, (anchor[0], _base_y(sk, dim) - step * row))
    elif dim.type == "vertical_distance":
        edit.set_label(dim.id, (_base_x(sk, dim) + step * row, anchor[1]))
    else:
        a, b = _ends(sk, dim)
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1.0
        edit.set_label(dim.id, (anchor[0] + dy / n * step * row, anchor[1] - dx / n * step * row))


def _ends(sk: Sketch, dim: Dimension) -> tuple[tuple[float, float], tuple[float, float]]:
    from fdcad.ui.sketch_tools.edit import distance_ends

    return distance_ends(sk, dim)


def _base_y(sk: Sketch, dim: Dimension) -> float:
    a, b = _ends(sk, dim)
    return min(a[1], b[1])


def _base_x(sk: Sketch, dim: Dimension) -> float:
    a, b = _ends(sk, dim)
    return max(a[0], b[0])


# Ordinate ---------------------------------------------------------------------------------


def is_ordinate(dim: Dimension) -> bool:
    """True for a dimension drawn as an ordinate (TR45)."""
    return bool(dim.display) and dim.display.get("style") == "ordinate"  # type: ignore[union-attr]


class OrdinateDimensionTool(Tool):
    """Zero point first, then points."""

    name, label = "ordinate_dimension", "Ordinate Dimension"
    options = (Option("axis", "Measure along", "choice", choices=AXES),)

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.axis = "horizontal"
        self.zero: str | None = None
        self.message = ""

    @property
    def prompt(self) -> str:
        """What to click next."""
        if self.zero is None:
            return "Click the zero point."
        return "Click each point to measure from the zero point. Press Escape to finish."

    @property
    def busy(self) -> bool:
        """True once the zero point is picked."""
        return self.zero is not None

    def cancel(self) -> bool:
        """Escape starts a new group, then ends the tool."""
        if self.zero is not None:
            self.zero = None
            return False
        return True

    def option_changed(self, key: str) -> bool:
        """A new direction starts a new group from the same zero point."""
        return False

    def click(self, snap: Snap) -> bool:
        """Pick the zero point, then add an ordinate per point."""
        item = _item_at(self.edit, snap, self.tolerance, lines=False)
        if item is None:
            self.message = "Click a point."
            return False
        if self.zero is None:
            self.zero = item
            return False
        if item == self.zero:
            return False
        edit = self.edit
        edit.checkpoint()
        dim = edit.add_dimension(f"{self.axis}_distance", [self.zero, item], None)
        group = f"{self.zero}:{self.axis}"
        dim.display = {"style": "ordinate", "group": group}
        mates = [
            d
            for d in edit.sketch.dimensions
            if is_ordinate(d) and (d.display or {}).get("group") == group
        ]
        first = mates[0]
        if first.label is not None and first is not dim:
            place = label_anchor(edit.sketch, first)
            edit.set_label(dim.id, (place[0] + first.label[0], place[1] + first.label[1]))
        else:
            zx, zy = edit.sketch.xy(self.zero)
            step = self.tolerance * _ROW
            px, py = edit.sketch.xy(item)
            at = (px, zy - step) if self.axis == "horizontal" else (zx - step, py)
            edit.set_label(dim.id, at)
        if edit.over_defines(dim.id):
            dim.driving = False
            self.message = "That size is already set, so it was added as a reference dimension."
        return True

    def take_message(self) -> str:
        """The status note, cleared once read."""
        msg, self.message = self.message, ""
        return msg

    def preview(self) -> Preview:
        """A mark on the zero point."""
        out = Preview()
        if self.zero is not None and self.zero in self.edit.sketch.entities:
            out.points.append(self.edit.sketch.xy(self.zero))
        return out


def ordinate_place(sk: Sketch, dim: Dimension, place: tuple[float, float]) -> tuple[float, float]:
    """Where an ordinate's text goes for a dragged ``place``: in line with its point
    across the axis, at the dragged height along it."""
    px, py = sk.xy(dim.entities[1])
    if dim.type == "horizontal_distance":
        return px, place[1]
    return place[0], py


def move_group(edit: SketchEdit, did: str, place: tuple[float, float]) -> None:
    """Move every ordinate of ``did``'s group to the row of ``place`` (TR45)."""
    sk = edit.sketch
    dim = next((d for d in sk.dimensions if d.id == did), None)
    if dim is None or not is_ordinate(dim):
        return
    group = dim.display["group"]  # type: ignore[index]
    for other in sk.dimensions:
        if is_ordinate(other) and other.display["group"] == group:  # type: ignore[index]
            at = ordinate_place(sk, other, place)
            anchor = label_anchor(sk, other)
            other.label = (round(at[0] - anchor[0], 6), round(at[1] - anchor[1], 6))


# Chamfer ----------------------------------------------------------------------------------


def _neighbour(sk: Sketch, line: Line, pid: str) -> Line | None:
    """The other line that ends at point ``pid`` (shared or coincident)."""
    tied = {pid}
    for r in sk.relations:
        if r.type == "coincident" and pid in r.entities:
            tied |= set(r.entities)
    for e in sk.entities.values():
        if isinstance(e, Line) and e.id != line.id and ({e.p1, e.p2} & tied):
            return e
    return None


def chamfer_problem(sk: Sketch, lid: str) -> str | None:
    """Why ``lid`` cannot take chamfer dimensions, or None."""
    line = sk.entities.get(lid)
    if not isinstance(line, Line):
        return "Pick a chamfer line."
    if _neighbour(sk, line, line.p1) is None or _neighbour(sk, line, line.p2) is None:
        return "A chamfer line needs a line at each end. Pick the chamfer line between two lines."
    return None


def chamfer_dimensions(edit: SketchEdit, lid: str, mode: str) -> list[str]:
    """Add chamfer dimensions to line ``lid`` (the caller checkpoints): ``angle`` adds
    its length and its angle to the line at its first end; ``lengths`` adds the two
    distances from the corner the chamfer cut off, at a construction point held where
    the two lines meet. Returns the new dimension ids."""
    sk = edit.sketch
    problem = chamfer_problem(sk, lid)
    if problem is not None:
        raise ValueError(problem)
    line = sk.entities[lid]
    assert isinstance(line, Line)
    a = _neighbour(sk, line, line.p1)
    b = _neighbour(sk, line, line.p2)
    assert a is not None and b is not None
    if mode == "angle":
        length = edit.add_dimension("distance", [lid], None)
        angle = edit.add_dimension("angle", [lid, a.id], None)
        return [length.id, angle.id]
    corner = _corner(sk, a, b)
    if corner is None:
        raise ValueError("The two lines are parallel, so there is no corner. Use length and angle.")
    pid = sk.add_point(corner[0], corner[1], construction=True)
    sk.relate("intersection", pid, a.id, b.id)
    first = edit.add_dimension("distance", [pid, line.p1], None)
    second = edit.add_dimension("distance", [pid, line.p2], None)
    return [first.id, second.id]


def _corner(sk: Sketch, a: Line, b: Line) -> tuple[float, float] | None:
    (x1, y1), (x2, y2) = sk.xy(a.p1), sk.xy(a.p2)
    (x3, y3), (x4, y4) = sk.xy(b.p1), sk.xy(b.p2)
    d = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(d) < 1e-12:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / d
    return x1 + t * (x2 - x1), y1 + t * (y2 - y1)
