"""Two point and tangent circles (TUTORIAL_REVIEW_SPEC_2 TR317, DECISIONS D877).

``two_point_circle``: two clicks at the ends of a diameter.
``tangent_circle``: click three lines, arcs or circles and the circle touches all
three; or click two and then empty space, and the circle touches the two and passes
near that spot, with a driving radius dimension to type the size into. The solver
finds the circle from a starting guess inside the picks, on a copy first, so a
choice it cannot solve adds nothing. Pure Python, no Qt.
"""

from __future__ import annotations

import copy
import math

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Arc, Circle, Line, Sketch
from fdcad.ui.sketch_tools import tool_text
from fdcad.ui.sketch_tools.edit import SketchEdit
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.three_point_tools import PerimeterCircleTool
from fdcad.ui.sketch_tools.tools import Preview, Tool

Vec = tuple[float, float]


class TwoPointCircleTool(PerimeterCircleTool):
    """A circle from the two ends of a diameter."""

    name, label = "two_point_circle", "2 Point Circle"

    def ready(self) -> bool:
        """Both ends clicked."""
        return len(self.clicks) == 2

    def commit(self) -> bool:
        """Add the circle and put each snapped end on it."""
        a, b = self.clicks[0].xy, self.clicks[1].xy
        r = math.dist(a, b) / 2
        if r < 1e-6:
            self.message = tool_text.TWO_POINT_SAME
            return False
        edit, sk = self.edit, self.edit.sketch
        cid = sk.add_circle((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, r, self.construction)
        if edit.auto_relations:
            for snap in self.clicks:
                self._on_circle(cid, snap)
        self.drawn = [cid]
        return True

    def preview(self) -> Preview:
        """The circle on the first click and the cursor."""
        out = Preview()
        if not self.clicks or self.cursor is None:
            return out
        a, b = self.clicks[0].xy, self.cursor.xy
        r = math.dist(a, b) / 2
        if r > 1e-9:
            out.circles.append((((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), r))
        out.points.append(a)
        return out


def _curve(sketch: Sketch, snap: Snap) -> str | None:
    """The line, arc or circle a click landed on, or None."""
    eid = snap.target
    e = sketch.entities.get(eid) if eid is not None else None
    return eid if isinstance(e, (Line, Arc, Circle)) else None


def _distance_to(sketch: Sketch, eid: str, p: Vec) -> float:
    e = sketch.entities[eid]
    if isinstance(e, Line):
        (x1, y1), (x2, y2) = sketch.xy(e.p1), sketch.xy(e.p2)
        length = math.hypot(x2 - x1, y2 - y1)
        if length < 1e-12:
            return math.dist(p, (x1, y1))
        return abs((x2 - x1) * (y1 - p[1]) - (x1 - p[0]) * (y2 - y1)) / length
    assert isinstance(e, (Arc, Circle))
    centre = sketch.xy(e.center)
    return abs(math.dist(centre, p) - sketch.radius(eid))


def tangent_circle(
    sketch: Sketch, curves: list[str], guess: Vec, through: bool = False
) -> tuple[Vec, float] | None:
    """Centre and radius of a circle tangent to ``curves``, solved from a start at
    ``guess``; with ``through`` (two curves) the radius is the guess's distance to the
    curves. None when the solver finds no such circle."""
    from fdcad.core.sketch.solver import solve

    trial = copy.deepcopy(sketch)
    radius = sum(_distance_to(trial, c, guess) for c in curves) / len(curves)
    if radius < 1e-6:
        return None
    cid = trial.add_circle(guess[0], guess[1], radius)
    for c in curves:
        trial.relate("tangent", cid, c)
    if through:
        trial.dimension("radius", [cid], Param(f"{radius:.6g}", radius))
    result = solve(trial)
    if not result.solved:
        return None
    circle = trial.entities[cid]
    assert isinstance(circle, Circle)
    return trial.xy(circle.center), trial.radius(cid)


class TangentCircleTool(Tool):
    """A circle tangent to three picked curves, or to two with a radius to type."""

    name, label = "tangent_circle", "Tangent Circle"

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.message = ""

    def take_message(self) -> str:
        """The status note left by the last click, once."""
        msg, self.message = self.message, ""
        return msg

    def click(self, snap: Snap) -> bool:
        """The first two clicks must be on curves; a third off a curve uses two."""
        snap = self.track(snap)
        if len(self.clicks) < 2 and _curve(self.edit.sketch, snap) is None:
            self.message = tool_text.TANGENT_PICK_CURVE
            return False
        return super().click(snap)

    def ready(self) -> bool:
        """Three clicks: three curves, or two curves and a spot."""
        return len(self.clicks) == 3

    def commit(self) -> bool:
        """Solve on a copy, then add the circle with its tangent relations."""
        sk = self.edit.sketch
        curves = [c for c in (_curve(sk, s) for s in self.clicks) if c is not None]
        curves = list(dict.fromkeys(curves))
        through = len(curves) == 2
        if len(curves) < 2:
            self.message = tool_text.TANGENT_PICK_CURVE
            return False
        pts = [s.xy for s in self.clicks]
        guess = pts[2] if through else (sum(p[0] for p in pts) / 3, sum(p[1] for p in pts) / 3)
        found = tangent_circle(sk, curves, guess, through)
        if found is None:
            self.message = tool_text.TANGENT_NO_CIRCLE
            return False
        (cx, cy), r = found
        cid = sk.add_circle(cx, cy, r, self.construction)
        for c in curves:
            sk.relate("tangent", cid, c)
        if through:
            sk.dimension("radius", [cid], Param(f"{r:.6g}", r))
        self.drawn = [cid]
        return True

    def preview(self) -> Preview:
        """The picked spots."""
        out = Preview()
        out.points += [s.xy for s in self.clicks]
        return out


__all__ = ["TangentCircleTool", "TwoPointCircleTool", "tangent_circle"]
