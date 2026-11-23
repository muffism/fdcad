"""Copy curve features onto a sketch plane (IDEAS.md item 2, DECISIONS D517).

``curve_projection.project_curve`` projects a curve feature's edges onto the
sketch plane (kernel work, off the UI thread) as the pieces below. :func:`add_curve`
then adds them to a sketch as fixed curves. Pure Python, no kernel and no Qt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import cached_property

import numpy as np

from fdcad.core.sketch.freeform import default_handles
from fdcad.core.sketch.model import Arc, Circle, Curve, Line, Point, Sketch, Spline

Vec = tuple[float, float]
#: Pieces shorter than this (mm) project to a point and are skipped.
MIN_SIZE = 1e-4


@dataclass(frozen=True)
class CurvePiece:
    """One projected edge.

    ``kind`` is ``line`` (``points`` holds both ends), ``circle``, ``arc`` (with
    ``centre``, ``radius``, and for an arc the counter clockwise ``angles`` and
    its ends in ``points``) or ``spline`` (``points`` along the curve).
    """

    kind: str
    points: tuple[Vec, ...]
    centre: Vec = (0.0, 0.0)
    radius: float = 0.0
    angles: tuple[float, float] = (0.0, 0.0)

    def polyline(self, steps: int = 48) -> list[Vec]:
        """Points along the piece, for drawing and picking."""
        if self.kind in ("circle", "arc"):
            a0, a1 = (0.0, math.tau) if self.kind == "circle" else self.angles
            if a1 <= a0:
                a1 += math.tau
            cx, cy = self.centre
            return [
                (
                    cx + self.radius * math.cos(a0 + (a1 - a0) * i / steps),
                    cy + self.radius * math.sin(a0 + (a1 - a0) * i / steps),
                )
                for i in range(steps + 1)
            ]
        return list(self.points)


@dataclass
class ProjectedCurve:
    """A curve feature seen on the sketch plane."""

    feature: str
    name: str
    pieces: list[CurvePiece] = field(default_factory=list)
    #: Edges that projected to a point or to almost nothing.
    skipped: int = 0
    #: Why the curve could not be worked out, as a message to show; empty when it was
    #: (D2635).
    problem: str = ""

    @cached_property
    def polylines(self) -> list[list[Vec]]:
        """Every piece as a polyline (worked out once, for drawing and picking)."""
        return [p.polyline() for p in self.pieces]

    @cached_property
    def bounds(self) -> tuple[float, float, float, float]:
        """Smallest and largest x and y of the projected curve."""
        pts = np.array([p for poly in self.polylines for p in poly] or [(0.0, 0.0)])
        lo, hi = pts.min(axis=0), pts.max(axis=0)
        return float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1])

    def near(self, at: Vec, tol: float) -> bool:
        """True when ``at`` lies within ``tol`` of the projected curve."""
        from fdcad.core.sketch.ops.convert import near

        x0, y0, x1, y1 = self.bounds
        if not (x0 - tol <= at[0] <= x1 + tol and y0 - tol <= at[1] <= y1 + tol):
            return False
        return any(near(poly, at, tol) for poly in self.polylines)


def spline_handles(pts: list[Vec]) -> list[Vec]:
    """Tangent handles for a spline through ``pts``; a closed one stays smooth where it
    closes."""
    hs = default_handles(pts)
    if len(pts) > 3 and math.dist(pts[0], pts[-1]) < 1e-9:
        a, b = pts[-2], pts[1]
        h = (pts[0][0] + (b[0] - a[0]) / 6, pts[0][1] + (b[1] - a[1]) / 6)
        hs[0] = h
        hs[-1] = (pts[-1][0] + h[0] - pts[0][0], pts[-1][1] + h[1] - pts[0][1])
    return hs


def add_piece(sketch: Sketch, piece: CurvePiece, construction: bool = False) -> str:
    """Add one projected piece to ``sketch`` as a fixed curve. Returns its id."""
    if piece.kind == "line":
        (x1, y1), (x2, y2) = piece.points
        cid = sketch.add_line(x1, y1, x2, y2, construction)
    elif piece.kind == "circle":
        cid = sketch.add_circle(*piece.centre, piece.radius, construction)
    elif piece.kind == "arc":
        cid = sketch.add_arc(*piece.centre, piece.radius, *piece.angles, construction)
        arc = sketch.entities[cid]
        assert isinstance(arc, Arc)
        # Exact end coordinates, so neighbouring pieces join.
        for pid, xy in zip((arc.start, arc.end), piece.points, strict=True):
            p = sketch.point(pid)
            p.x, p.y = xy
    else:
        pts = list(piece.points)
        ids = [sketch.add_point(x, y, construction) for x, y in pts]
        handles = [sketch.add_point(hx, hy, True) for hx, hy in spline_handles(pts)]
        cid = sketch.new_id()
        sketch.entities[cid] = Spline(cid, ids, handles, construction)
    sketch.relate("fixed", cid)
    return cid


def _fixed_curves(sketch: Sketch) -> list[Curve]:
    fixed = {e for r in sketch.relations if r.type == "fixed" for e in r.entities}
    return [c for c in sketch.curves(True) if c.id in fixed]


def _near(a: Vec, b: Vec) -> bool:
    return math.dist(a, b) < MIN_SIZE


def _same(sketch: Sketch, curve: Curve, piece: CurvePiece) -> bool:
    """True when ``curve`` already lies on ``piece``."""
    if piece.kind == "circle":
        return (
            isinstance(curve, Circle)
            and _near(sketch.xy(curve.center), piece.centre)
            and abs(curve.radius - piece.radius) < MIN_SIZE
        )
    if piece.kind == "line" and isinstance(curve, Line):
        ends = (sketch.xy(curve.p1), sketch.xy(curve.p2))
    elif piece.kind == "arc" and isinstance(curve, Arc):
        if not _near(sketch.xy(curve.center), piece.centre):
            return False
        ends = (sketch.xy(curve.start), sketch.xy(curve.end))
    elif piece.kind == "spline" and isinstance(curve, Spline):
        pts = [sketch.xy(p) for p in curve.points]
        return len(pts) == len(piece.points) and (
            all(_near(a, b) for a, b in zip(pts, piece.points, strict=True))
            or all(_near(a, b) for a, b in zip(pts[::-1], piece.points, strict=True))
        )
    else:
        return False
    a, b = piece.points
    return (_near(ends[0], a) and _near(ends[1], b)) or (_near(ends[0], b) and _near(ends[1], a))


def add_curve(
    sketch: Sketch, curve: ProjectedCurve, construction: bool = False
) -> tuple[list[str], int]:
    """Add every piece of ``curve`` not in the sketch yet as a fixed curve.

    Returns the new curve ids and how many pieces were already there (stacked
    contour loops seen from above land on one another and are copied once).
    """
    made: list[str] = []
    already = 0
    fixed = _fixed_curves(sketch)
    for piece in curve.pieces:
        if any(_same(sketch, c, piece) for c in fixed):
            already += 1
            continue
        cid = add_piece(sketch, piece, construction)
        made.append(cid)
        new = sketch.entities[cid]
        assert not isinstance(new, Point)
        fixed.append(new)
    return made, already
