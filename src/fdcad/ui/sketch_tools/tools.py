"""Sketch drawing tools as small click driven state machines.

The canvas turns mouse input into snaps (sketch millimetres) and calls
``click`` and ``hover``. A tool adds entities to the :class:`SketchEdit`
when it has enough clicks, and describes what to draw meanwhile through
``preview``. Pure Python, no Qt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Arc, Line, Point
from fdcad.ui.sketch_tools.edit import SketchEdit
from fdcad.ui.sketch_tools.geometry import Vec, arc_through, ccw_turn, dist
from fdcad.ui.sketch_tools.inference import Snap, line_relation
from fdcad.ui.sketch_tools.tool_options import Option
from fdcad.ui.sketch_tools.typed_size import add_dimensions, constrain

#: Shorter than this (mm) counts as no movement.
_MIN = 1e-6
#: Leaving the end point closer than this to the end direction (cosine) gives a
#: tangent arc; further to the side gives a normal arc (T2.5.2).
_ALONG = math.cos(math.radians(45.0))
#: Construction lines a rectangle can get (TR114, D1313).
RECTANGLE_LINES = (
    ("none", "None"),
    ("diagonals", "Corner to corner"),
    ("midlines", "Midpoint to midpoint"),
)
#: Line orientations offered in the Line panel (T2.1.4).
ORIENTATIONS = ("as_drawn", "horizontal", "vertical", "angle")


@dataclass
class Preview:
    """Rubber band geometry in sketch millimetres."""

    lines: list[tuple[Vec, Vec]] = field(default_factory=list)
    circles: list[tuple[Vec, float]] = field(default_factory=list)
    arcs: list[tuple[Vec, float, float, float]] = field(default_factory=list)  # c, r, a0, a1 ccw
    points: list[Vec] = field(default_factory=list)
    #: Direction arrows (TR341 item 2, D1705): a tail point and a unit direction, in
    #: sketch millimetres; drawn at a fixed size on screen.
    arrows: list[tuple[Vec, Vec]] = field(default_factory=list)


def _point_snap(pid: str, xy: Vec) -> Snap:
    return Snap("point", xy[0], xy[1], [("coincident", [pid])], target=pid)


class Tool:
    """Base class. ``finished`` turns True when the tool wants to end."""

    name = ""
    label = ""

    def __init__(self, edit: SketchEdit) -> None:
        self.edit = edit
        self.clicks: list[Snap] = []
        self.cursor: Snap | None = None
        self.finished = False
        #: False while snapping is off (preference, or Ctrl held, T1.2.7).
        self.snapping = True
        #: Shift is held (square rectangles, T2.3.2).
        self.shift = False
        #: Pick distance in mm at the current zoom; the canvas keeps it up to date.
        self.tolerance = 0.5
        #: New shapes are construction geometry (panel option, T2.7, T7.2).
        self.construction = False
        #: Entities of the shape drawn last, for the panel's values (T7.2).
        self.drawn: list[str] = []
        #: Sizes typed while drawing (T15.6): "length", "radius" and so on, as typed.
        self.locks: dict[str, Param] = {}

    def hover(self, snap: Snap) -> Snap:
        """Track the cursor. May adjust the snap (for example to horizontal)."""
        self.cursor = snap
        return snap

    def track(self, snap: Snap) -> Snap:
        """``hover``, then keep any typed size (T15.6). The canvas calls this."""
        snap = self.hover(snap)
        if self.locks:
            snap = constrain(self, snap)
            self.cursor = snap
        return snap

    def click(self, snap: Snap) -> bool:
        """Handle a click. Returns True when the sketch changed.

        A shape drawn with typed sizes gets their dimensions in the same undo step,
        and with dynamic mirror on (D514) its mirror copy too.
        """
        snap = self.track(snap)
        self.clicks.append(snap)
        if self.ready():
            self.edit.checkpoint()
            before = set(self.edit.sketch.entities) if self.edit.mirror_axis else None
            ok = self.commit()
            if ok and self.locks:
                add_dimensions(self)
                self.edit.refresh(full=False)
            if ok and before is not None:
                # Dynamic mirror (D514): the copy is part of the same undo step.
                from fdcad.ui.sketch_tools.dynamic_mirror import mirror_new

                if mirror_new(self.edit, before):
                    self.edit.refresh(full=False)
            if not ok:
                self.edit.discard_checkpoint()
            self.locks.clear()
            self.after_commit()
            return ok
        return False

    def ready(self) -> bool:
        """True when enough clicks were made."""
        return False

    def commit(self) -> bool:
        """Add the geometry. Returns False when it would be degenerate."""
        return False

    def after_commit(self) -> None:
        """Reset for the next shape."""
        self.clicks.clear()

    def cancel(self) -> bool:
        """Escape: drop the current shape. Returns True when the tool should end."""
        self.locks.clear()
        if self.clicks:
            self.clicks.clear()
            return False
        return True

    def preview(self) -> Preview:
        """What to draw for the shape in progress."""
        return Preview()

    @property
    def busy(self) -> bool:
        """True while a shape is in progress."""
        return bool(self.clicks)


class PointTool(Tool):
    """Places points."""

    name, label = "point", "Point"

    def ready(self) -> bool:
        """One click per point."""
        return len(self.clicks) == 1

    def commit(self) -> bool:
        """Add the point."""
        self.drawn = [self.edit.place_point(self.clicks[0])]
        return True


class LineTool(Tool):
    """Chained lines: each click ends a line and starts the next. Escape ends the chain.

    After a segment, moving the cursor back onto the end point and away again
    switches to a tangent arc (T2.1.3); the Switch Line and Arc command does the
    same without going back. Centerlines have no arc switch.
    """

    name, label = "line", "Line"

    def __init__(self, edit: SketchEdit, construction: bool = False) -> None:
        super().__init__(edit)
        self.construction = construction
        self.centerline = construction
        if construction:
            self.name, self.label = "centerline", "Centerline"
        #: Relation the line gets from a direction snap: (type, other line ids) or None.
        self.direction: tuple[str, list[str]] | None = None
        #: The start snap of the next segment of a chain (a shape join, T1.3.3).
        self.chain: Snap | None = None
        #: Panel option (T2.1.4): one of ORIENTATIONS, and the angle for "angle".
        self.orientation = "as_drawn"
        self.angle = 0.0
        #: The next segment is a tangent arc (T2.1.3).
        self.arc_mode = False
        #: The cursor has left the chain's end point since the last segment.
        self._left_end = False
        #: The cursor is back on the chain's end point.
        self._on_end = False

    @property
    def axis(self) -> str | None:
        """``horizontal`` or ``vertical`` when the line snapped to an axis, else None."""
        if self.direction is not None and self.direction[0] in ("horizontal", "vertical"):
            return self.direction[0]
        return None

    @property
    def chained(self) -> bool:
        """True while the next segment continues a chain."""
        return self.chain is not None and bool(self.clicks) and self.clicks[0] is self.chain

    def _end_direction(self) -> Vec | None:
        if not self.chained or self.chain is None or self.chain.target is None:
            return None
        return _end_direction(self.edit, self.chain.target)

    def toggle_arc(self) -> bool:
        """Switch the next segment between line and tangent arc. False when not possible."""
        if self.centerline or self._end_direction() is None:
            return False
        self.arc_mode = not self.arc_mode
        return True

    def _track_end(self, snap: Snap) -> None:
        """Back onto the end point and away again switches line and arc (T2.1.3)."""
        if self.centerline or not self.chained or self.chain is None:
            return
        near = dist(snap.xy, self.chain.xy) <= self.tolerance
        if not near:
            if self._on_end and self._end_direction() is not None:
                self.arc_mode = not self.arc_mode
            self._on_end = False
            self._left_end = True
        elif self._left_end:
            self._on_end = True

    def hover(self, snap: Snap) -> Snap:
        """Snap to horizontal, vertical, parallel or perpendicular near those directions.

        With snapping off (Ctrl held, T1.2.7) the line follows the cursor freely. A
        fixed orientation from the panel keeps the line on that direction.
        """
        self.direction = None
        self._track_end(snap)
        if self.clicks and not self.arc_mode:
            if self.orientation != "as_drawn":
                snap = self._oriented(self.clicks[0].xy, snap)
            elif self.snapping:
                snap, self.direction = line_relation(self.edit.sketch, self.clicks[0].xy, snap)
        self.cursor = snap
        return snap

    def _oriented(self, start: Vec, snap: Snap) -> Snap:
        """The cursor moved onto the panel's fixed direction through ``start``."""
        if self.orientation == "horizontal":
            d: Vec = (1.0, 0.0)
        elif self.orientation == "vertical":
            d = (0.0, 1.0)
        else:
            d = (math.cos(self.angle), math.sin(self.angle))
        t = (snap.x - start[0]) * d[0] + (snap.y - start[1]) * d[1]
        at = (start[0] + t * d[0], start[1] + t * d[1])
        if dist(at, snap.xy) < 1e-9:
            return snap
        return Snap("free", at[0], at[1])

    def ready(self) -> bool:
        """A line needs two clicks."""
        return len(self.clicks) == 2

    def click(self, snap: Snap) -> bool:
        """A second click within the pick distance of the first is ignored, so quick
        clicking makes no tiny segments (TR115 item 3, D1314)."""
        if len(self.clicks) == 1 and not self.locks:
            at = self.track(snap)
            if dist(at.xy, self.clicks[0].xy) <= self.tolerance:
                return False
        return super().click(snap)

    def commit(self) -> bool:
        """Add the line (or the tangent arc) and its relations."""
        start, end = self.clicks
        if dist(start.xy, end.xy) < _MIN:
            return False
        if self.arc_mode:
            return self._commit_arc(start, end)
        chained = self.chain is not None and start is self.chain
        lid = self.edit.add_line(start, end, self.construction, keep_start=chained)
        if self.orientation in ("horizontal", "vertical"):
            # A fixed orientation is part of the shape the user asked for.
            self.edit.relate(self.orientation, [lid])
        elif self.direction is not None:
            rtype, others = self.direction
            if all(o in self.edit.sketch.entities for o in others):
                self.edit.auto_relate(rtype, [lid, *others])
        self.drawn = [lid]
        return True

    def _commit_arc(self, start: Snap, end: Snap) -> bool:
        direction = self._end_direction()
        if direction is None or start.target is None:
            return False
        geo = tangent_arc(start.xy, direction, end.xy)
        if geo is None:
            return False
        center, _, ccw = geo
        curve = _curve_at(self.edit, start.target)
        aid = self.edit.add_arc(center, start, end, ccw, self.construction, keep_start=True)
        if curve is not None:
            self.edit.relate("tangent", [aid, curve])
        self.drawn = [aid]
        return True

    def after_commit(self) -> None:
        """Start the next segment at the end of this one; arcs go back to lines."""
        ent = self.edit.sketch.entities.get(self.drawn[-1]) if self.drawn else None
        end = self.clicks[-1]
        self.clicks.clear()
        self.arc_mode = False
        self._left_end = False
        self._on_end = False
        pid: str | None = None
        if isinstance(ent, Line):
            pid = ent.p2
        elif isinstance(ent, Arc):
            pid = _point_near(self.edit, [ent.start, ent.end], end.xy)
        # Ending on an existing point stops the chain, like closing a loop.
        if pid is not None and end.kind not in ("point", "center"):
            self.chain = _point_snap(pid, self.edit.sketch.xy(pid))
            self.clicks.append(self.chain)

    def cancel(self) -> bool:
        """Escape ends the chain first, then the tool."""
        self.arc_mode = False
        return super().cancel()

    def preview(self) -> Preview:
        """The line, or the tangent arc, from the last click to the cursor."""
        out = Preview()
        if not self.clicks or self.cursor is None:
            return out
        start = self.clicks[0].xy
        if self.arc_mode:
            direction = self._end_direction()
            if direction is not None:
                _add_arc_preview(out, start, direction, self.cursor.xy)
            return out
        out.lines.append((start, self.cursor.xy))
        return out


def _point_near(edit: SketchEdit, pids: list[str], at: Vec) -> str:
    """The point of ``pids`` closest to ``at``."""
    return min(pids, key=lambda p: dist(edit.sketch.xy(p), at))


def _add_arc_preview(out: Preview, start: Vec, direction: Vec, end: Vec) -> None:
    geo = tangent_arc(start, direction, end)
    if geo is None:
        out.lines.append((start, end))
        return
    c, r, ccw = geo
    a0 = math.atan2(start[1] - c[1], start[0] - c[0])
    a1 = math.atan2(end[1] - c[1], end[0] - c[0])
    if not ccw:
        a0, a1 = a1, a0
    if a1 <= a0:
        a1 += 2 * math.pi
    out.arcs.append((c, r, a0, a1))


def squared(a: Vec, b: Vec) -> Vec:
    """``b`` moved so that the box from ``a`` to it is a square (T2.3.2)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    side = max(abs(dx), abs(dy))
    return a[0] + math.copysign(side, dx or 1.0), a[1] + math.copysign(side, dy or 1.0)


class CornerRectangleTool(Tool):
    """Rectangle from two opposite corners, sides horizontal and vertical."""

    name, label = "corner_rectangle", "Corner Rectangle"
    #: Extras made with the rectangle (TR114, D1313).
    options: tuple[Option, ...] = (
        Option("lines", "Construction lines", "choice", choices=RECTANGLE_LINES),
        Option(
            "round", "Corner radius", "length", tip="0 leaves the corners sharp.", in_sketch=False
        ),
        Option(
            "frame", "Inner frame offset", "length", tip="0 adds no inner frame.", in_sketch=False
        ),
    )

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        #: The second corner was made square with Shift.
        self.square = False
        self.lines = "none"
        self.round = 0.0
        self.frame = 0.0

    def hover(self, snap: Snap) -> Snap:
        """With Shift held the second corner makes a square (T2.3.2, T14.1.1)."""
        self.square = False
        if self.clicks and self.shift:
            at = squared(self.clicks[0].xy, snap.xy)
            if dist(at, snap.xy) > 1e-9:
                snap = Snap("free", at[0], at[1])
            self.square = True
        self.cursor = snap
        return snap

    def ready(self) -> bool:
        """Two corners."""
        return len(self.clicks) == 2

    def corners(self, a: Vec, b: Vec) -> list[Vec]:
        """The four corners, counter clockwise from ``a`` when ``b`` is up right."""
        return [a, (b[0], a[1]), b, (a[0], b[1])]

    def commit(self) -> bool:
        """Add four lines with corner, horizontal and vertical relations."""
        a, b = self.clicks
        if abs(a.x - b.x) < _MIN or abs(a.y - b.y) < _MIN:
            from fdcad.ui.sketch_tools.tool_text import FLAT_RECTANGLE

            self.edit.note = FLAT_RECTANGLE
            return False
        pts = self.corners(a.xy, b.xy)
        snaps: list[Snap] = [a, Snap("free", *pts[1]), b, Snap("free", *pts[3])]
        self.drawn = add_closed_rectangle(self.edit, pts, snaps, self.construction, self.square)
        return self.add_extras(pts)

    def add_extras(self, pts: list[Vec]) -> bool:
        """Construction lines, an inner frame and rounded corners (TR114, D1313), in
        the rectangle's undo step. False (nothing made) when one cannot be made."""
        from fdcad.core.sketch.ops.corner import CornerError, round_all
        from fdcad.core.sketch.ops.offset import OffsetError, offset

        sk = self.edit.sketch
        sides = list(self.drawn)
        corners = [self.edit.line(lid).p1 for lid in sides]
        if self.lines == "diagonals":
            for i, j in ((0, 2), (1, 3)):
                diag = self.edit.line(sk.add_line(*pts[i], *pts[j], construction=True))
                sk.relate("coincident", diag.p1, corners[i])
                sk.relate("coincident", diag.p2, corners[j])
        elif self.lines == "midlines":
            for i, j in ((0, 2), (1, 3)):
                a, b = _middle(pts[i], pts[(i + 1) % 4]), _middle(pts[j], pts[(j + 1) % 4])
                mid = self.edit.line(sk.add_line(*a, *b, construction=True))
                sk.relate("midpoint", mid.p1, sides[i])
                sk.relate("midpoint", mid.p2, sides[j])
        try:
            if float(self.frame) > 0:
                centre = _middle(pts[0], pts[2])
                offset(sk, sides, float(self.frame), centre, add_dimension=True)
            if float(self.round) > 0:
                round_all(sk, sides, float(self.round))
        except (OffsetError, CornerError) as exc:
            self.edit.note = str(exc)
            return False
        return True

    def preview(self) -> Preview:
        """The rectangle to the cursor."""
        out = Preview()
        if self.clicks and self.cursor is not None:
            pts = self.corners(self.clicks[0].xy, self.cursor.xy)
            out.lines += [(pts[i], pts[(i + 1) % 4]) for i in range(4)]
        return out


class CenterRectangleTool(CornerRectangleTool):
    """Rectangle from its centre and a corner, with construction diagonals."""

    name, label = "center_rectangle", "Center Rectangle"

    def corners(self, a: Vec, b: Vec) -> list[Vec]:
        """Corners around centre ``a`` through corner ``b``."""
        dx, dy = b[0] - a[0], b[1] - a[1]
        return [
            (a[0] - dx, a[1] - dy),
            (a[0] + dx, a[1] - dy),
            (a[0] + dx, a[1] + dy),
            (a[0] - dx, a[1] + dy),
        ]

    def commit(self) -> bool:
        """Four lines, two construction diagonals and a centre point on both."""
        c, b = self.clicks
        if abs(c.x - b.x) < _MIN or abs(c.y - b.y) < _MIN:
            return False
        pts = self.corners(c.xy, b.xy)
        snaps = [Snap("free", *p) for p in pts]
        snaps[2] = b
        self.drawn = add_closed_rectangle(
            self.edit, pts, snaps, self.construction, self.square, diagonals=True
        )
        sk = self.edit.sketch
        corners = [self.edit.line(lid).p1 for lid in self.drawn]
        d1 = sk.add_line(*pts[0], *pts[2], construction=True)
        d2 = sk.add_line(*pts[1], *pts[3], construction=True)
        for diag, (i, j) in ((d1, (0, 2)), (d2, (1, 3))):
            line = self.edit.line(diag)
            sk.relate("coincident", line.p1, corners[i])
            sk.relate("coincident", line.p2, corners[j])
        center = self.edit.place_point(c, construction=True)
        sk.relate("midpoint", center, d1)
        sk.relate("midpoint", center, d2)
        if self.lines == "diagonals":
            self.lines = "none"  # a centre rectangle has its diagonals already
            try:
                return self.add_extras(pts)
            finally:
                self.lines = "diagonals"
        return self.add_extras(pts)


def add_closed_rectangle(
    edit: SketchEdit,
    pts: list[Vec],
    snaps: list[Snap],
    construction: bool = False,
    square: bool = False,
    diagonals: bool = False,
) -> list[str]:
    """Four joined lines through ``pts`` with H and V relations, and Equal sides for a
    square. Returns the line ids; line ``i`` starts at corner ``i``.

    With ``diagonals`` the caller adds diagonals that halve each other, which already
    make the opposite sides parallel, so only one side of each pair gets H or V;
    a second would be a redundant relation and over define the sketch.
    """
    sk = edit.sketch
    lines = [edit.line(sk.add_line(*pts[i], *pts[(i + 1) % 4], construction)) for i in range(4)]
    for i in range(4):
        sk.relate("coincident", lines[i].p2, lines[(i + 1) % 4].p1)
    sk.relate("horizontal", lines[0].id)
    sk.relate("vertical", lines[1].id)
    if not diagonals:
        sk.relate("horizontal", lines[2].id)
        sk.relate("vertical", lines[3].id)
    if square:
        sk.relate("equal", lines[0].id, lines[1].id)
    corners = [ln.p1 for ln in lines]
    for pid, snap in zip(corners, snaps, strict=True):
        edit.attach(pid, snap)
    return [ln.id for ln in lines]


class CircleTool(Tool):
    """Circle from its centre and a point on it."""

    name, label = "circle", "Circle"

    def ready(self) -> bool:
        """Centre and radius point."""
        return len(self.clicks) == 2

    def commit(self) -> bool:
        """Add the circle. A radius point on another entity adds no relation."""
        c, p = self.clicks
        r = dist(c.xy, p.xy)
        if r < _MIN:
            return False
        self.drawn = [self.edit.add_circle(c, r, self.construction)]
        return True

    def preview(self) -> Preview:
        """The circle to the cursor."""
        out = Preview()
        if self.clicks and self.cursor is not None:
            out.circles.append((self.clicks[0].xy, dist(self.clicks[0].xy, self.cursor.xy)))
        return out


class CenterArcTool(Tool):
    """Arc from its centre, a start point and an end point. The turn follows the mouse."""

    name, label = "center_arc", "Centerpoint Arc"

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.sweep = 0.0
        self._last_angle: float | None = None

    def hover(self, snap: Snap) -> Snap:
        """Track how far the cursor has turned around the centre."""
        if len(self.clicks) == 2:
            c = self.clicks[0].xy
            angle = math.atan2(snap.y - c[1], snap.x - c[0])
            if self._last_angle is not None:
                self.sweep += math.remainder(angle - self._last_angle, 2 * math.pi)
            self._last_angle = angle
        self.cursor = snap
        return snap

    def click(self, snap: Snap) -> bool:
        """Start tracking the turn after the start point."""
        changed = super().click(snap)
        if len(self.clicks) == 2:
            c, s = self.clicks[0].xy, self.clicks[1].xy
            self._last_angle = math.atan2(s[1] - c[1], s[0] - c[0])
            self.sweep = 0.0
        return changed

    def ready(self) -> bool:
        """Centre, start and end."""
        return len(self.clicks) == 3

    def _end_on_circle(self, end: Snap) -> Snap:
        c, s = self.clicks[0].xy, self.clicks[1].xy
        r = dist(c, s)
        a = math.atan2(end.y - c[1], end.x - c[0])
        if end.kind in ("point", "center", "intersection"):
            return end
        return Snap(end.kind, c[0] + r * math.cos(a), c[1] + r * math.sin(a), end.relations)

    def commit(self) -> bool:
        """Add the arc in the direction the mouse turned."""
        c, s, e = self.clicks
        if dist(c.xy, s.xy) < _MIN:
            return False
        end = self._end_on_circle(e)
        if dist(end.xy, s.xy) < _MIN:
            return False
        self.drawn = [
            self.edit.add_arc(c.xy, s, end, self.sweep >= 0, self.construction, center_snap=c)
        ]
        return True

    def preview(self) -> Preview:
        """Radius line, then the arc so far."""
        out = Preview()
        if not self.clicks or self.cursor is None:
            return out
        c = self.clicks[0].xy
        if len(self.clicks) == 1:
            out.lines.append((c, self.cursor.xy))
        else:
            s = self.clicks[1].xy
            r = dist(c, s)
            a0 = math.atan2(s[1] - c[1], s[0] - c[0])
            a1 = a0 + self.sweep
            out.arcs.append((c, r, min(a0, a1), max(a0, a1)))
            out.points.append(c)
        return out


def _end_direction(edit: SketchEdit, pid: str) -> Vec | None:
    """Direction a curve leaves through its end point ``pid`` (for a tangent arc)."""
    sk = edit.sketch
    for c in sk.curves(True):
        if isinstance(c, Line) and pid in (c.p1, c.p2):
            a, b = (c.p1, c.p2) if pid == c.p2 else (c.p2, c.p1)
            (x1, y1), (x2, y2) = sk.xy(a), sk.xy(b)
            n = math.hypot(x2 - x1, y2 - y1)
            return ((x2 - x1) / n, (y2 - y1) / n) if n > 0 else None
        if isinstance(c, Arc) and pid in (c.start, c.end):
            cx, cy = sk.xy(c.center)
            px, py = sk.xy(pid)
            rx, ry = px - cx, py - cy
            n = math.hypot(rx, ry)
            if n == 0:
                return None
            # Counter clockwise tangent is (-ry, rx); leaving through the end follows the run.
            leaving_forward = (pid == c.end) == c.ccw
            sign = 1.0 if leaving_forward else -1.0
            return (-ry / n * sign, rx / n * sign)
    return None


def _curve_at(edit: SketchEdit, pid: str) -> str | None:
    for c in edit.sketch.curves(True):
        if isinstance(c, Line) and pid in (c.p1, c.p2):
            return c.id
        if isinstance(c, Arc) and pid in (c.start, c.end):
            return c.id
    return None


def tangent_arc(start: Vec, direction: Vec, end: Vec) -> tuple[Vec, float, bool] | None:
    """Centre, radius and turn (True for counter clockwise) of the tangent arc."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    nx, ny = -direction[1], direction[0]  # left normal
    dn = dx * nx + dy * ny
    if abs(dn) < 1e-9:
        return None
    r = (dx * dx + dy * dy) / (2 * dn)
    center = (start[0] + nx * r, start[1] + ny * r)
    return center, abs(r), r > 0


class TangentArcTool(Tool):
    """Arc that continues from the end of a line or arc (T2.5.2).

    Leaving the end point along the end direction gives an arc tangent to the
    curve; leaving it sideways gives an arc normal (perpendicular) to it.
    Returning to the end point and leaving in a new direction decides again.
    """

    name, label = "tangent_arc", "Tangent Arc"
    #: Flip direction (TR115 item 2, D1710): leave the end backward along the curve.
    options = (Option("flip", "Flip direction", "bool"),)

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.flip = False
        #: The arc leaves at a right angle to the curve instead of along it.
        self.normal = False
        #: Which side a normal arc leaves to: +1 left of the end direction, -1 right.
        self._side = 1.0
        #: The tangent or normal choice is made; returning to the end point clears it.
        self._decided = False

    def click(self, snap: Snap) -> bool:
        """The first click must be on the end of a line or arc."""
        if not self.clicks and (
            snap.kind != "point"
            or snap.target is None
            or _end_direction(self.edit, snap.target) is None
        ):
            return False
        if not self.clicks:
            self._decided = False
            self.normal = False
        else:
            # A click with no move away first keeps the plain tangent arc.
            self._decided = True
        return super().click(snap)

    def hover(self, snap: Snap) -> Snap:
        """Decide tangent or normal from where the cursor leaves the end point."""
        if self.clicks:
            start = self.clicks[0].xy
            gap = dist(start, snap.xy)
            if gap <= self.tolerance:
                self._decided = False
            elif not self._decided:
                direction = self._end_direction()
                if direction is not None:
                    vx, vy = (snap.x - start[0]) / gap, (snap.y - start[1]) / gap
                    along = vx * direction[0] + vy * direction[1]
                    self.normal = abs(along) < _ALONG
                    self._side = 1.0 if vy * direction[0] - vx * direction[1] >= 0 else -1.0
                    self._decided = True
        self.cursor = snap
        return snap

    def ready(self) -> bool:
        """Start (an end point) and end."""
        return len(self.clicks) == 2

    def _end_direction(self) -> Vec | None:
        start = self.clicks[0]
        assert start.target is not None
        return _end_direction(self.edit, start.target)

    def _start_direction(self) -> Vec | None:
        """The arc's direction at its start: along the curve, or square to it."""
        direction = self._end_direction()
        if direction is not None and self.flip:
            direction = (-direction[0], -direction[1])
        if direction is None or not self.normal:
            return direction
        return (-direction[1] * self._side, direction[0] * self._side)

    def _geometry(self, end: Vec) -> tuple[Vec, float, bool] | None:
        direction = self._start_direction()
        if direction is None:
            return None
        return tangent_arc(self.clicks[0].xy, direction, end)

    def commit(self) -> bool:
        """Add the arc with its join and a tangent relation, or for a normal arc on a
        line, its centre on the line."""
        start, end = self.clicks
        geo = self._geometry(end.xy)
        if geo is None or start.target is None:
            return False
        center, _, ccw = geo
        # The arc continues the curve it starts on, so that join always stays.
        aid = self.edit.add_arc(center, start, end, ccw, self.construction, keep_start=True)
        curve = _curve_at(self.edit, start.target)
        if curve is not None and not self.normal:
            self.edit.relate("tangent", [aid, curve])
        elif curve is not None and isinstance(self.edit.sketch.entities[curve], Line):
            # Square to a line: the arc's centre lies on the line (its extension).
            arc = self.edit.sketch.entities[aid]
            assert isinstance(arc, Arc)
            self.edit.relate("coincident", [arc.center, curve])
        self.drawn = [aid]
        self._decided = False
        return True

    def preview(self) -> Preview:
        """The tangent or normal arc to the cursor."""
        out = Preview()
        if self.clicks and self.cursor is not None:
            direction = self._start_direction()
            if direction is not None:
                _add_arc_preview(out, self.clicks[0].xy, direction, self.cursor.xy)
        return out


class ThreePointArcTool(Tool):
    """Arc through a start point, an end point and a third point on the arc."""

    name, label = "three_point_arc", "3 Point Arc"

    def ready(self) -> bool:
        """Start, end and a point on the arc."""
        return len(self.clicks) == 3

    def commit(self) -> bool:
        """Add the arc through the three points."""
        s, e, m = self.clicks
        circle = arc_through(s.xy, m.xy, e.xy)
        if circle is None:
            return False
        center, _ = circle
        ccw = ccw_turn(s.xy, m.xy, e.xy)
        self.drawn = [self.edit.add_arc(center, s, e, ccw, self.construction)]
        return True

    def preview(self) -> Preview:
        """Chord, then the arc through the cursor."""
        out = Preview()
        if not self.clicks or self.cursor is None:
            return out
        if len(self.clicks) == 1:
            out.lines.append((self.clicks[0].xy, self.cursor.xy))
            return out
        s, e, m = self.clicks[0].xy, self.clicks[1].xy, self.cursor.xy
        circle = arc_through(s, m, e)
        if circle is None:
            out.lines.append((s, e))
            return out
        c, r = circle
        a0 = math.atan2(s[1] - c[1], s[0] - c[0])
        a1 = math.atan2(e[1] - c[1], e[0] - c[0])
        if not ccw_turn(s, m, e):
            a0, a1 = a1, a0
        if a1 <= a0:
            a1 += 2 * math.pi
        out.arcs.append((c, r, a0, a1))
        return out


#: Tool names to classes, used by the command tab and shortcuts.
TOOLS: dict[str, type[Tool]] = {
    "line": LineTool,
    "corner_rectangle": CornerRectangleTool,
    "center_rectangle": CenterRectangleTool,
    "circle": CircleTool,
    "center_arc": CenterArcTool,
    "tangent_arc": TangentArcTool,
    "three_point_arc": ThreePointArcTool,
    "point": PointTool,
}


def make_tool(name: str, edit: SketchEdit) -> Tool:
    """Create a tool by name. ``centerline`` is a construction line tool."""
    if name == "centerline":
        return LineTool(edit, construction=True)
    if name not in TOOLS:
        from fdcad.ui.sketch_tools.registry import extra_tools

        return extra_tools()[name](edit)
    return TOOLS[name](edit)


__all__ = ["TOOLS", "Point", "Preview", "Tool", "make_tool"]


def _middle(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
