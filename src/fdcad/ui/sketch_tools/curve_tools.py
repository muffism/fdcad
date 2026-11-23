"""Ellipse, partial ellipse and spline drawing tools (PHASE2_SPEC P2.8 items 10, 13).

They place points with snaps like the Phase 1 tools (TOOL_SPEC T1.2, T1.3). No Qt.
"""

from __future__ import annotations

import itertools
import math

from fdcad.core.sketch.freeform import (
    default_handles,
    ellipse_param,
    ellipse_point,
    sample,
)
from fdcad.core.sketch.model import Ellipse, EllipseArc, Line, Sketch, Spline
from fdcad.ui.sketch_tools.edit import SketchEdit
from fdcad.ui.sketch_tools.geometry import Vec, dist
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.tool_options import Option
from fdcad.ui.sketch_tools.tools import Preview, Tool

_MIN = 1e-6


def ellipse_axes(c: Vec, major: Vec, third: Vec) -> tuple[float, float, float] | None:
    """Major and minor semi axes and the major angle from the centre, the first axis
    end and a point that sets the second axis. The longer axis is the major one."""
    a = dist(c, major)
    if a < _MIN:
        return None
    phi = math.atan2(major[1] - c[1], major[0] - c[0])
    dx, dy = third[0] - c[0], third[1] - c[1]
    b = abs(-dx * math.sin(phi) + dy * math.cos(phi))
    if b < _MIN:
        return None
    if b > a:
        a, b, phi = b, a, phi + math.pi / 2
    return a, b, phi


def add_ellipse_points(
    edit: SketchEdit, centre: Snap, a: float, b: float, phi: float, construction: bool
) -> tuple[str, str, str]:
    """The centre (with its snap's relations) and construction axis end points."""
    sk = edit.sketch
    c = edit.place_point(centre, construction)
    mj = ellipse_point(centre.xy, a, b, phi, 0.0)
    mn = ellipse_point(centre.xy, a, b, phi, math.pi / 2)
    return c, sk.add_point(*mj, construction=True), sk.add_point(*mn, construction=True)


def add_axis_lines(sk: Sketch, centre: str, major: str, minor: str) -> list[str]:
    """Both axes of an ellipse as construction lines through its centre: each ends on
    an axis point and has the centre as its midpoint, so they add no freedom (TR114)."""
    cx, cy = sk.xy(centre)
    made: list[str] = []
    for end in (major, minor):
        ex, ey = sk.xy(end)
        lid = sk.add_line(2 * cx - ex, 2 * cy - ey, ex, ey, construction=True)
        line = sk.entities[lid]
        assert isinstance(line, Line)
        sk.relate("coincident", line.p2, end)
        sk.relate("midpoint", centre, lid)
        made.append(lid)
    return made


class EllipseTool(Tool):
    """Ellipse: the centre, an end of one axis, then the size of the other (P2.8 item 13)."""

    name, label = "ellipse", "Ellipse"
    prompt = "Click the center, an end of the first axis, then the size of the second axis."
    options = (  # TR114 (D967)
        Option(
            "axes",
            "Construction axes",
            "bool",
            tip="Add both axes as construction lines through the centre, to dimension and "
            "turn the ellipse by.",
        ),
    )

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.axes = True

    def ready(self) -> bool:
        """Three clicks."""
        return len(self.clicks) == 3

    def commit(self) -> bool:
        """Add the ellipse."""
        c, m, t = self.clicks
        axes = ellipse_axes(c.xy, m.xy, t.xy)
        if axes is None:
            return False
        sk = self.edit.sketch
        centre, major, minor = add_ellipse_points(self.edit, c, *axes, self.construction)
        eid = sk.new_id()
        sk.entities[eid] = Ellipse(eid, centre, major, minor, self.construction)
        self.drawn = [eid]
        if self.axes:
            add_axis_lines(sk, centre, major, minor)
        return True

    def preview(self) -> Preview:
        """The first axis, then the ellipse."""
        out = Preview()
        if not self.clicks or self.cursor is None:
            return out
        if len(self.clicks) == 1:
            out.lines.append((self.clicks[0].xy, self.cursor.xy))
            return out
        axes = ellipse_axes(self.clicks[0].xy, self.clicks[1].xy, self.cursor.xy)
        if axes is not None:
            pts = [ellipse_point(self.clicks[0].xy, *axes, t / 48 * math.tau) for t in range(49)]
            out.lines += list(itertools.pairwise(pts))
        return out


class PartialEllipseTool(Tool):
    """Partial ellipse: centre, first axis, second axis (which also sets the start),
    then move along the outline and click to end (P2.8 item 13)."""

    name, label = "partial_ellipse", "Partial Ellipse"
    prompt = (
        "Click the center, an end of the first axis and the second axis, then move along "
        "the outline and click to end."
    )

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.sweep = 0.0
        self._last: float | None = None

    def _axes(self) -> tuple[float, float, float] | None:
        return ellipse_axes(self.clicks[0].xy, self.clicks[1].xy, self.clicks[2].xy)

    def hover(self, snap: Snap) -> Snap:
        """Track how far the cursor turned around the ellipse."""
        if len(self.clicks) == 3:
            axes = self._axes()
            if axes is not None:
                t = ellipse_param(self.clicks[0].xy, *axes, snap.xy)
                if self._last is not None:
                    self.sweep += math.remainder(t - self._last, math.tau)
                self._last = t
        self.cursor = snap
        return snap

    def click(self, snap: Snap) -> bool:
        """After the second axis the sweep starts at that click."""
        changed = super().click(snap)
        if len(self.clicks) == 3:
            axes = self._axes()
            if axes is None:
                self.clicks.pop()
                return changed
            self._last = ellipse_param(self.clicks[0].xy, *axes, self.clicks[2].xy)
            self.sweep = 0.0
        return changed

    def ready(self) -> bool:
        """Four clicks."""
        return len(self.clicks) == 4

    def _span(self) -> tuple[float, float, float, float, float] | None:
        axes = self._axes()
        if axes is None or abs(self.sweep) < 1e-6:
            return None
        a, b, phi = axes
        t0 = ellipse_param(self.clicks[0].xy, a, b, phi, self.clicks[2].xy)
        return a, b, phi, t0, t0 + self.sweep

    def commit(self) -> bool:
        """Add the partial ellipse, counter clockwise from its first end."""
        span = self._span()
        if span is None:
            return False
        a, b, phi, t0, t1 = span
        if t1 < t0:
            t0, t1 = t1, t0
        c = self.clicks[0]
        sk = self.edit.sketch
        centre, major, minor = add_ellipse_points(self.edit, c, a, b, phi, True)
        s = sk.add_point(*ellipse_point(c.xy, a, b, phi, t0), construction=self.construction)
        e = sk.add_point(*ellipse_point(c.xy, a, b, phi, t1), construction=self.construction)
        eid = sk.new_id()
        sk.entities[eid] = EllipseArc(eid, centre, major, minor, s, e, self.construction)
        self.drawn = [eid]
        return True

    def preview(self) -> Preview:
        """Axes, the ellipse, then the swept part."""
        out = Preview()
        if not self.clicks or self.cursor is None:
            return out
        c = self.clicks[0].xy
        if len(self.clicks) == 1:
            out.lines.append((c, self.cursor.xy))
            return out
        third = self.cursor.xy if len(self.clicks) == 2 else self.clicks[2].xy
        axes = ellipse_axes(c, self.clicks[1].xy, third)
        if axes is None:
            return out
        if len(self.clicks) == 2:
            pts = [ellipse_point(c, *axes, t / 48 * math.tau) for t in range(49)]
        else:
            t0 = ellipse_param(c, *axes, self.clicks[2].xy)
            pts = [ellipse_point(c, *axes, t0 + self.sweep * k / 48) for k in range(49)]
        out.lines += list(itertools.pairwise(pts))
        return out


class SplineTool(Tool):
    """Spline through clicked points (P2.8 item 10). A press and drag at a point sets
    its tangent handle; a double click, Escape or the right click menu finishes."""

    name, label = "spline", "Spline"
    prompt = (
        "Click points along the curve; press and drag at a point to set its tangent. "
        "Double click to finish."
    )

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        #: Handle ends set by dragging, by click index.
        self.handles: dict[int, Vec] = {}

    def ready(self) -> bool:
        """Points are collected until the spline is finished."""
        return False

    def release(self, snap: Snap, moved: bool) -> bool:
        """The end of a press: a drag sets the last point's tangent handle."""
        if moved and self.clicks:
            self.handles[len(self.clicks) - 1] = snap.xy
        return False

    def cancel(self) -> bool:
        """Finish the spline (two points or more), else drop it; with nothing in
        progress the tool ends."""
        if not self.clicks:
            return True
        # A double click adds its second press as a point on top of the last one.
        while (
            len(self.clicks) > 1 and dist(self.clicks[-1].xy, self.clicks[-2].xy) <= self.tolerance
        ):
            self.handles.pop(len(self.clicks) - 1, None)
            self.clicks.pop()
        if len(self.clicks) >= 2:
            self.edit.checkpoint()
            self._finish()
            self.finished_one = True
        self.clicks.clear()
        self.handles = {}
        return False

    def _repeated(self) -> bool:
        return dist(self.clicks[-1].xy, self.clicks[-2].xy) <= self.tolerance

    #: True after cancel added a spline (the canvas then refreshes).
    finished_one = False

    def _poles(self) -> tuple[list[Vec], list[Vec]]:
        pts = [c.xy for c in self.clicks]
        hs = default_handles(pts)
        for i, h in self.handles.items():
            if i < len(hs) and dist(h, pts[i]) > _MIN:
                hs[i] = h
        return pts, hs

    def _finish(self) -> None:
        sk = self.edit.sketch
        _pts, hs = self._poles()
        ids = [self.edit.place_point(c, self.construction) for c in self.clicks]
        handles = [sk.add_point(h[0], h[1], construction=True) for h in hs]
        sid = sk.new_id()
        sk.entities[sid] = Spline(sid, ids, handles, self.construction)
        self.drawn = [sid]

    def take_changed(self) -> bool:
        """True once after cancel made a spline."""
        made, self.finished_one = self.finished_one, False
        return made

    def preview(self) -> Preview:
        """The spline through the points and the cursor, and the handles."""
        out = Preview()
        if not self.clicks or self.cursor is None:
            return out
        scratch = Sketch()
        pts = [c.xy for c in self.clicks] + [self.cursor.xy]
        hs = default_handles(pts)
        for i, h in self.handles.items():
            if i < len(hs):
                hs[i] = h
        ids = [scratch.add_point(*p) for p in pts]
        hids = [scratch.add_point(*h) for h in hs]
        spline = Spline("s", ids, hids)
        samples = sample(scratch, spline)
        out.lines += list(itertools.pairwise(samples))
        for i, h in self.handles.items():
            if i < len(pts):
                out.lines.append((pts[i], h))
                out.points.append(h)
        return out
