"""Fast lookup of projected part geometry under the cursor (WP14, D250).

Built once when the projection arrives (never per mouse move); each query is a
few whole array numpy operations (CLAUDE.md 5A item 2), so a part with
thousands of edges still snaps smoothly. Pure Python and numpy, no Qt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from fdcad.core.sketch.links import ModelCircle, ModelGeometry, ModelLine, ModelPoint

Vec = tuple[float, float]


@dataclass(frozen=True)
class ModelHit:
    """One model snap candidate: where, which kind, and the part item it came from."""

    kind: str  # "point", "midpoint" or "on_curve"
    xy: Vec
    distance: float
    point: ModelPoint | None = None
    curve: ModelLine | ModelCircle | None = None


class ModelSnapIndex:
    """Part vertices, the origin, straight and round edges as arrays."""

    def __init__(self, geometry: ModelGeometry) -> None:
        self.geometry = geometry
        #: Vertices and the origin snap at once; round edge centres are revealed by
        #: hovering their edge (W3.2), so they are looked up separately.
        self.points = [p for p in geometry.points if p.source is None or p.source[0] != "edge"]
        self.centres = [
            p for p in geometry.points if p.source is not None and p.source[0] == "edge"
        ]
        self._p = np.array([p.xy for p in self.points], dtype=float).reshape(-1, 2)
        self.lines = list(geometry.lines)
        ends = np.array([(*ln.a, *ln.b) for ln in self.lines], dtype=float).reshape(-1, 4)
        self._a, self._b = ends[:, :2], ends[:, 2:]
        self.circles = list(geometry.circles)
        self._c = np.array([c.centre for c in self.circles], dtype=float).reshape(-1, 2)
        self._r = np.array([c.radius for c in self.circles], dtype=float)

    def query(self, cursor: Vec, tol: float) -> list[ModelHit]:
        """The nearest vertex, line midpoint and edge point within ``tol`` of ``cursor``."""
        q = np.array(cursor, dtype=float)
        hits: list[ModelHit] = []
        if len(self._p):
            d = np.hypot(*(self._p - q).T)
            i = int(np.argmin(d))
            if d[i] <= tol:
                hits.append(ModelHit("point", self.points[i].xy, float(d[i]), point=self.points[i]))
        if len(self.lines):
            mids = (self._a + self._b) / 2
            d = np.hypot(*(mids - q).T)
            i = int(np.argmin(d))
            if d[i] <= tol:
                xy = (float(mids[i, 0]), float(mids[i, 1]))
                hits.append(ModelHit("midpoint", xy, float(d[i]), curve=self.lines[i]))
            ab = self._b - self._a
            length2 = np.maximum(np.einsum("ij,ij->i", ab, ab), 1e-24)
            t = np.clip(np.einsum("ij,ij->i", q - self._a, ab) / length2, 0.0, 1.0)
            foot = self._a + ab * t[:, None]
            d = np.hypot(*(foot - q).T)
            i = int(np.argmin(d))
            if d[i] <= tol:
                xy = (float(foot[i, 0]), float(foot[i, 1]))
                hits.append(ModelHit("on_curve", xy, float(d[i]), curve=self.lines[i]))
        if len(self.circles):
            off = q - self._c
            r = np.hypot(*off.T)
            d = np.abs(r - self._r)
            for i in np.argsort(d)[:4]:
                if d[i] > tol:
                    break
                c = self.circles[int(i)]
                angle = math.atan2(float(off[i, 1]), float(off[i, 0])) if r[i] > 1e-12 else 0.0
                if c.arc is not None and not _in_arc(angle, c.arc):
                    continue
                xy = (
                    c.centre[0] + c.radius * math.cos(angle),
                    c.centre[1] + c.radius * math.sin(angle),
                )
                hits.append(ModelHit("on_curve", xy, float(d[i]), curve=c))
                break
        return hits

    def centre_at(self, xy: Vec) -> ModelPoint | None:
        """The round edge centre at ``xy`` (a revealed centre), if the projection has one."""
        for p in self.centres:
            if math.dist(p.xy, xy) < 1e-6:
                return p
        return None

    def ring_circles(self) -> list[tuple[Vec, float]]:
        """Round edges as (centre, radius), for revealing their centres by hover."""
        return [(c.centre, c.radius) for c in self.circles]

    def line_at(self, cursor: Vec, tol: float) -> ModelLine | None:
        """The straight edge under the cursor (Smart Dimension picks, D113)."""
        for hit in self.query(cursor, tol):
            if hit.kind == "on_curve" and isinstance(hit.curve, ModelLine):
                return hit.curve
        return None


def _in_arc(angle: float, arc: tuple[float, float]) -> bool:
    a0, a1 = arc
    span = (a1 - a0) % (2 * math.pi)
    return (angle - a0) % (2 * math.pi) <= span + 1e-9
