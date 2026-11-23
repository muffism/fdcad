"""Three click shapes: turned rectangles, the parallelogram and the perimeter circle.

TOOL_SPEC T2.3 item 4 and T2.4 item 2 (DECISIONS D511, D512). Each tool takes
three clicks. The rectangles may sit at any angle, so they get Perpendicular and
Parallel relations instead of Horizontal and Vertical. Pure Python, no Qt.
"""

from __future__ import annotations

import math

from fdcad.core.sketch.model import Circle
from fdcad.ui.sketch_tools import tool_text
from fdcad.ui.sketch_tools.edit import SketchEdit
from fdcad.ui.sketch_tools.geometry import Vec, arc_through, dist
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.tools import Preview, Tool

#: Shorter than this (mm) counts as no size.
_MIN = 1e-6
#: Snap kinds whose target is an existing sketch point.
_POINT_KINDS = ("point", "center")


def _unit(a: Vec, b: Vec) -> Vec | None:
    """The unit vector from ``a`` to ``b``, or None when they meet."""
    d = dist(a, b)
    if d < _MIN:
        return None
    return (b[0] - a[0]) / d, (b[1] - a[1]) / d


def _side(a: Vec, u: Vec, p: Vec) -> float:
    """Signed distance of ``p`` from the line through ``a`` along ``u`` (left is plus)."""
    return (p[0] - a[0]) * -u[1] + (p[1] - a[1]) * u[0]


def _quad_preview(pts: list[Vec]) -> Preview:
    out = Preview()
    out.lines += [(pts[i], pts[(i + 1) % 4]) for i in range(4)]
    return out


def add_quad(edit: SketchEdit, pts: list[Vec], snaps: list[Snap], construction: bool) -> list[str]:
    """Four joined lines through ``pts``; line ``i`` starts at corner ``i``. Corners take
    their snap's relations. Returns the line ids. The caller adds the shape relations."""
    sk = edit.sketch
    lines = [edit.line(sk.add_line(*pts[i], *pts[(i + 1) % 4], construction)) for i in range(4)]
    for i in range(4):
        sk.relate("coincident", lines[i].p2, lines[(i + 1) % 4].p1)
    for line, snap in zip(lines, snaps, strict=True):
        edit.attach(line.p1, snap)
    return [ln.id for ln in lines]


class _ThreeClickTool(Tool):
    """Shared input of the three click quads: the third point follows ``third``."""

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        #: The last shape was made square with Shift (D159).
        self.square = False

    def ready(self) -> bool:
        """Three clicks."""
        return len(self.clicks) == 3

    def third(self, snap: Snap) -> Vec:
        """Where the third point goes for a cursor at ``snap``."""
        return snap.xy

    def hover(self, snap: Snap) -> Snap:
        """Move the third point where the shape allows; a moved point is free."""
        self.square = False
        if len(self.clicks) == 2:
            at = self.third(snap)
            if dist(at, snap.xy) > 1e-9:
                snap = Snap("free", at[0], at[1])
        self.cursor = snap
        return snap

    def corners(self, a: Vec, b: Vec, c: Vec) -> list[Vec] | None:
        """The four corners from the three points, or None when degenerate."""
        return None

    def preview(self) -> Preview:
        """The first side, then the whole shape to the cursor."""
        out = Preview()
        if not self.clicks or self.cursor is None:
            return out
        if len(self.clicks) == 1:
            out.lines.append((self.clicks[0].xy, self.cursor.xy))
            return out
        pts = self.corners(self.clicks[0].xy, self.clicks[1].xy, self.cursor.xy)
        if pts is None:
            out.lines.append((self.clicks[0].xy, self.clicks[1].xy))
            return out
        return _quad_preview(pts)


class ThreePointCornerRectangleTool(_ThreeClickTool):
    """Rectangle from two corners (one side at any angle) and the other side's size."""

    name, label = "three_point_corner_rectangle", "3 Point Corner Rectangle"

    def third(self, snap: Snap) -> Vec:
        """The cursor moved square onto the line through the second corner; with Shift
        the side is as long as the first (a square)."""
        a, b = self.clicks[0].xy, self.clicks[1].xy
        u = _unit(a, b)
        if u is None:
            return snap.xy
        h = _side(a, u, snap.xy)
        if self.shift:
            h = math.copysign(dist(a, b), h or 1.0)
            self.square = True
        return b[0] - u[1] * h, b[1] + u[0] * h

    def corners(self, a: Vec, b: Vec, c: Vec) -> list[Vec] | None:
        """a, b, the third corner square to ab through b, and the fourth."""
        u = _unit(a, b)
        if u is None:
            return None
        h = _side(a, u, c)
        if abs(h) < _MIN:
            return None
        n = (-u[1] * h, u[0] * h)
        return [a, b, (b[0] + n[0], b[1] + n[1]), (a[0] + n[0], a[1] + n[1])]

    def commit(self) -> bool:
        """Four lines with Perpendicular and Parallel relations (no Horizontal or Vertical)."""
        a, b, c = self.clicks
        pts = self.corners(a.xy, b.xy, c.xy)
        if pts is None:
            return False
        third = c if dist(c.xy, pts[2]) < 1e-9 else Snap("free", *pts[2])
        ids = add_quad(self.edit, pts, [a, b, third, Snap("free", *pts[3])], self.construction)
        sk = self.edit.sketch
        sk.relate("perpendicular", ids[0], ids[1])
        sk.relate("parallel", ids[0], ids[2])
        sk.relate("parallel", ids[1], ids[3])
        if self.square:
            sk.relate("equal", ids[0], ids[1])
        self.drawn = ids
        return True


class ThreePointCenterRectangleTool(_ThreeClickTool):
    """Rectangle from its centre, the midpoint of one side and the other half size."""

    name, label = "three_point_center_rectangle", "3 Point Center Rectangle"

    def third(self, snap: Snap) -> Vec:
        """With Shift the half height is the half width (a square)."""
        if not self.shift:
            return snap.xy
        m, s = self.clicks[0].xy, self.clicks[1].xy
        u = _unit(m, s)
        if u is None:
            return snap.xy
        h = math.copysign(dist(m, s), _side(m, u, snap.xy) or 1.0)
        self.square = True
        t = (snap.x - m[0]) * u[0] + (snap.y - m[1]) * u[1]
        return m[0] + u[0] * t - u[1] * h, m[1] + u[1] * t + u[0] * h

    def corners(self, a: Vec, b: Vec, c: Vec) -> list[Vec] | None:
        """Corners around centre ``a``; ``b`` is the middle of the second side."""
        u = _unit(a, b)
        if u is None:
            return None
        hw = dist(a, b)
        hh = abs(_side(a, u, c))
        if hh < _MIN:
            return None
        ux, uy = u[0] * hw, u[1] * hw
        nx, ny = -u[1] * hh, u[0] * hh
        return [
            (a[0] - ux - nx, a[1] - uy - ny),
            (a[0] + ux - nx, a[1] + uy - ny),
            (a[0] + ux + nx, a[1] + uy + ny),
            (a[0] - ux + nx, a[1] - uy + ny),
        ]

    def commit(self) -> bool:
        """Four lines, construction diagonals halving each other at a centre point,
        and Perpendicular on two adjacent sides."""
        c, s, h = self.clicks
        pts = self.corners(c.xy, s.xy, h.xy)
        if pts is None:
            return False
        edit, sk = self.edit, self.edit.sketch
        ids = add_quad(edit, pts, [Snap("free", *p) for p in pts], self.construction)
        sk.relate("perpendicular", ids[0], ids[1])
        if self.square:
            sk.relate("equal", ids[0], ids[1])
        corners = [edit.line(lid).p1 for lid in ids]
        d1 = sk.add_line(*pts[0], *pts[2], construction=True)
        d2 = sk.add_line(*pts[1], *pts[3], construction=True)
        for diag, (i, j) in ((d1, (0, 2)), (d2, (1, 3))):
            line = edit.line(diag)
            sk.relate("coincident", line.p1, corners[i])
            sk.relate("coincident", line.p2, corners[j])
        center = edit.place_point(c, construction=True)
        sk.relate("midpoint", center, d1)
        sk.relate("midpoint", center, d2)
        if edit.auto_relations and s.kind in _POINT_KINDS and s.target in sk.entities:
            sk.relate("midpoint", s.target, ids[1])  # the side through the second click
        self.drawn = ids
        return True


class ParallelogramTool(_ThreeClickTool):
    """Parallelogram from three corners; the fourth completes it."""

    name, label = "parallelogram", "Parallelogram"

    def corners(self, a: Vec, b: Vec, c: Vec) -> list[Vec] | None:
        """a, b, c and the fourth corner a + c - b."""
        u = _unit(a, b)
        if u is None or dist(b, c) < _MIN or abs(_side(a, u, c)) < _MIN:
            return None
        return [a, b, c, (a[0] + c[0] - b[0], a[1] + c[1] - b[1])]

    def commit(self) -> bool:
        """Four lines with Parallel on opposite sides only."""
        a, b, c = self.clicks
        pts = self.corners(a.xy, b.xy, c.xy)
        if pts is None:
            return False
        ids = add_quad(self.edit, pts, [a, b, c, Snap("free", *pts[3])], self.construction)
        sk = self.edit.sketch
        sk.relate("parallel", ids[0], ids[2])
        sk.relate("parallel", ids[1], ids[3])
        self.drawn = ids
        return True


class PerimeterCircleTool(Tool):
    """Circle through three clicked points (T2.4.2), stored as centre and radius."""

    name, label = "perimeter_circle", "Perimeter Circle"

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.message = ""

    def ready(self) -> bool:
        """Three points on the circle."""
        return len(self.clicks) == 3

    def take_message(self) -> str:
        """The status note left by the last click, once."""
        msg, self.message = self.message, ""
        return msg

    def commit(self) -> bool:
        """Add the circle and put each snapped click on it."""
        p1, p2, p3 = self.clicks
        circle = arc_through(p1.xy, p2.xy, p3.xy)
        if circle is None or circle[1] < _MIN:
            self.message = tool_text.PERIMETER_IN_LINE
            return False
        (cx, cy), r = circle
        edit, sk = self.edit, self.edit.sketch
        cid = sk.add_circle(cx, cy, r, self.construction)
        if edit.auto_relations:
            for snap in self.clicks:
                self._on_circle(cid, snap)
        self.drawn = [cid]
        return True

    def _on_circle(self, cid: str, snap: Snap) -> None:
        """Tie a snapped click to the circle: an existing point directly, anything else
        through a construction point that keeps the snap's relations."""
        edit, sk = self.edit, self.edit.sketch
        circle = sk.entities[cid]
        assert isinstance(circle, Circle)
        if snap.kind in _POINT_KINDS and snap.target in sk.entities:
            if snap.target != circle.center:
                sk.relate("coincident", snap.target, cid)
            return
        if not (snap.relations or snap.model is not None or snap.model_curve is not None):
            return
        pid = edit.place_point(snap, construction=True)
        sk.relate("coincident", pid, cid)

    def preview(self) -> Preview:
        """A chord to the cursor, then the circle through both clicks and the cursor."""
        out = Preview()
        if not self.clicks or self.cursor is None:
            return out
        if len(self.clicks) == 1:
            out.lines.append((self.clicks[0].xy, self.cursor.xy))
            return out
        a, b = self.clicks[0].xy, self.clicks[1].xy
        circle = arc_through(a, b, self.cursor.xy)
        if circle is None:
            out.lines.append((a, b))
        else:
            out.circles.append(circle)
        out.points += [a, b]
        return out


__all__ = [
    "ParallelogramTool",
    "PerimeterCircleTool",
    "ThreePointCenterRectangleTool",
    "ThreePointCornerRectangleTool",
    "add_quad",
]
