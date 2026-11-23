"""Slot and polygon drawing tools (PHASE2_SPEC P2.8 items 11 and 12). No Qt.

They place points with snaps like the Phase 1 tools (TOOL_SPEC T1.2, T1.3): a
click on a snap ties the slot's or polygon's centre to it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from fdcad.core.sketch.model import Arc, Circle, Line, Sketch
from fdcad.core.sketch.ops.geom import Geo, Vec, dist
from fdcad.core.sketch.ops.shapes import (
    LENGTH_MODES,
    SLOT_KINDS,
    ShapeError,
    ShapeResult,
    arc_slot,
    polygon,
    straight_slot,
)
from fdcad.ui.sketch_tools.edit import SketchEdit
from fdcad.ui.sketch_tools.geometry import arc_through, ccw_turn
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.pick_tools import add_curve_preview
from fdcad.ui.sketch_tools.tool_options import Option
from fdcad.ui.sketch_tools.tools import Preview, Tool

SLOT_LABELS = {
    "straight": "Straight slot",
    "centre_straight": "Center straight slot",
    "arc3": "3 point arc slot",
    "centre_arc": "Center point arc slot",
}
LENGTH_LABELS = {"centre": "Center to center", "overall": "Overall"}
_PROMPTS = {
    "straight": [
        "Click the first end center.",
        "Click the second end center.",
        "Click to set the width.",
    ],
    "centre_straight": [
        "Click the slot center.",
        "Click an end center.",
        "Click to set the width.",
    ],
    "arc3": [
        "Click the first end center.",
        "Click the second end center.",
        "Click a point on the slot's arc.",
        "Click to set the width.",
    ],
    "centre_arc": [
        "Click the arc center.",
        "Click the first end center.",
        "Move around and click the second end center.",
        "Click to set the width.",
    ],
}


@dataclass(frozen=True)
class _SlotGeo:
    """End centres ``a`` and ``b`` and the width; arc slots add the arc centre and turn."""

    a: Vec
    b: Vec
    width: float
    mid: Vec | None = None
    centre: Vec | None = None
    ccw: bool = True


class SlotTool(Tool):
    """Four kinds of slot, chosen in the panel."""

    name, label = "slot", "Slot"
    options = (
        Option("kind", "Type", "choice", tuple((k, SLOT_LABELS[k]) for k in SLOT_KINDS)),
        Option("add_dimensions", "Add dimensions", "bool"),
        Option(
            "length_mode", "Length", "choice", tuple((m, LENGTH_LABELS[m]) for m in LENGTH_MODES)
        ),
    )

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.kind = "straight"
        self.add_dimensions = False
        self.length_mode = "centre"
        #: How far the cursor turned around the centre (centre point arc slot).
        self.sweep = 0.0
        self._last: float | None = None
        self.message = ""
        #: The centre line of the last straight slot, for a typed length (T15.6).
        self.axis: str | None = None

    @property
    def prompt(self) -> str:
        """What to click next."""
        steps = _PROMPTS[self.kind]
        return steps[min(len(self.clicks), len(steps) - 1)]

    def option_changed(self, key: str) -> bool:
        """A new kind starts over."""
        if key == "kind":
            self.clicks.clear()
        return False

    def take_message(self) -> str:
        """The status note, cleared once read."""
        msg, self.message = self.message, ""
        return msg

    def hover(self, snap: Snap) -> Snap:
        """Track the turn around the centre for the centre point arc slot."""
        if self.kind == "centre_arc" and len(self.clicks) == 2:
            c = self.clicks[0].xy
            ang = math.atan2(snap.y - c[1], snap.x - c[0])
            if self._last is not None:
                self.sweep += math.remainder(ang - self._last, 2 * math.pi)
            self._last = ang
        self.cursor = snap
        return snap

    def click(self, snap: Snap) -> bool:
        """Start tracking the turn after the first end of a centre point arc slot."""
        changed = super().click(snap)
        if self.kind == "centre_arc" and len(self.clicks) == 2:
            c, s = self.clicks[0].xy, self.clicks[1].xy
            self._last = math.atan2(s[1] - c[1], s[0] - c[0])
            self.sweep = 0.0
        return changed

    def ready(self) -> bool:
        """Straight slots take three clicks, arc slots four."""
        return len(self.clicks) == (3 if self.kind in ("straight", "centre_straight") else 4)

    def _geometry(self, pts: list[Vec]) -> _SlotGeo | None:
        """The slot from its clicks (the last one sets the width)."""
        if self.kind == "straight":
            c1, c2, w = pts
            return _SlotGeo(c1, c2, 2 * _line_gap(c1, c2, w))
        if self.kind == "centre_straight":
            m, c2, w = pts
            c1 = (2 * m[0] - c2[0], 2 * m[1] - c2[1])
            return _SlotGeo(c1, c2, 2 * _line_gap(c1, c2, w), mid=m)
        if self.kind == "arc3":
            s, e, on, w = pts
            circle = arc_through(s, on, e)
            if circle is None:
                return None
            centre, radius = circle
            width = 2 * abs(dist(centre, w) - radius)
            return _SlotGeo(s, e, width, centre=centre, ccw=ccw_turn(s, on, e))
        c, s, e, w = pts
        radius = dist(c, s)
        ang = math.atan2(e[1] - c[1], e[0] - c[0])
        end = (c[0] + radius * math.cos(ang), c[1] + radius * math.sin(ang))
        width = 2 * abs(dist(c, w) - radius)
        return _SlotGeo(s, end, width, centre=c, ccw=self.sweep >= 0)

    def _build(self, sk: Sketch, g: _SlotGeo, real: bool) -> ShapeResult:
        cons = self.construction if real else False
        dims = self.add_dimensions if real else False
        if g.centre is None:
            return straight_slot(sk, g.a, g.b, g.width, cons, g.mid, dims, self.length_mode)
        return arc_slot(sk, g.centre, g.a, g.b, g.ccw, g.width, cons, dims)

    def commit(self) -> bool:
        """Add the slot, tied to the snaps of its first clicks."""
        g = self._geometry([c.xy for c in self.clicks])
        if g is None:
            return False
        try:
            result = self._build(self.edit.sketch, g, True)
        except ShapeError as exc:
            self.message = str(exc)
            return False
        self._attach(result)
        self.drawn = result.curves
        self.axis = result.construction[0] if result.construction else None
        return True

    def _attach(self, result: ShapeResult) -> None:
        """Snaps of the clicks that placed centres add their relations (T1.3)."""
        sk = self.edit.sketch
        if self.kind in ("straight", "centre_straight"):
            axis = sk.entities[result.construction[0]]
            assert isinstance(axis, Line)
            if self.kind == "straight":
                self.edit.attach(axis.p1, self.clicks[0])
                self.edit.attach(axis.p2, self.clicks[1])
            else:
                if result.centre is not None:
                    self.edit.attach(result.centre, self.clicks[0])
                self.edit.attach(axis.p2, self.clicks[1])
            return
        axis_arc = sk.entities[result.construction[0]]
        assert isinstance(axis_arc, Arc)
        if self.kind == "centre_arc":
            self.edit.attach(axis_arc.center, self.clicks[0])

    def preview(self) -> Preview:
        """The centre line so far, then the whole slot."""
        out = Preview()
        if not self.clicks or self.cursor is None:
            return out
        pts = [c.xy for c in self.clicks] + [self.cursor.xy]
        need = 3 if self.kind in ("straight", "centre_straight") else 4
        if len(pts) < need:
            if self.kind == "centre_arc" and len(pts) == 3:
                c, s = pts[0], pts[1]
                r = dist(c, s)
                a0 = math.atan2(s[1] - c[1], s[0] - c[0])
                a1 = a0 + self.sweep
                out.arcs.append((c, r, min(a0, a1), max(a0, a1)))
            else:
                out.lines.append((pts[-2], pts[-1]))
            return out
        g = self._geometry(pts[:need])
        if g is None:
            return out
        scratch = Sketch()
        try:
            result = self._build(scratch, g, False)
        except ShapeError:
            return out
        _draw(out, scratch, result.curves)
        return out


def _line_gap(a: Vec, b: Vec, p: Vec) -> float:
    g = Geo("line", a, b)
    return dist(p, g.at(g.param(p)))


def _draw(out: Preview, sk: Sketch, ids: list[str]) -> None:
    for cid in ids:
        add_curve_preview(out, sk, cid)


class PolygonTool(Tool):
    """A regular polygon from its centre and a vertex (P2.8 item 12)."""

    name, label = "polygon", "Polygon"
    options = (
        Option("sides", "Sides", "int", low=3, high=40),
        # Spec 2 section 20 item 8 (D713): "Inscribed circle" read as the opposite.
        Option("inscribed", "Corners on the circle (off: sides touch the circle)", "bool"),
        Option("triangle", "Triangle", "button"),  # TR114 item 2 (D1709)
        Option("new", "New Polygon", "button"),
    )
    prompt = "Click the center, then a corner (or the middle of a side when the sides touch)."

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.sides = 6
        self.inscribed = True
        self.message = ""

    def option_changed(self, key: str) -> bool:
        """New Polygon starts the next one afresh; Triangle sets three sides."""
        if key == "triangle":
            self.sides = 3
        if key == "new":
            self.clicks.clear()
            self.drawn = []
        return False

    def take_message(self) -> str:
        """The status note, cleared once read."""
        msg, self.message = self.message, ""
        return msg

    def ready(self) -> bool:
        """Centre and vertex."""
        return len(self.clicks) == 2

    def commit(self) -> bool:
        """Add the polygon; the centre takes the first click's snap."""
        c, v = self.clicks
        try:
            result = polygon(
                self.edit.sketch, c.xy, v.xy, self.sides, self.inscribed, self.construction
            )
        except ShapeError as exc:
            self.message = str(exc)
            return False
        if result.centre is not None:
            self.edit.attach(result.centre, c)
        self.drawn = result.curves
        return True

    def preview(self) -> Preview:
        """The polygon and its construction circle to the cursor."""
        out = Preview()
        if not self.clicks or self.cursor is None:
            return out
        scratch = Sketch()
        try:
            result = polygon(scratch, self.clicks[0].xy, self.cursor.xy, self.sides, self.inscribed)
        except ShapeError:
            return out
        _draw(out, scratch, result.curves)
        circle = scratch.entities[result.construction[0]]
        assert isinstance(circle, Circle)
        out.circles.append((scratch.xy(circle.center), circle.radius))
        return out
