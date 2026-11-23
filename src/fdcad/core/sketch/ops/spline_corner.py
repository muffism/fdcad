"""Spline pieces for sketch fillets and chamfers (TUTORIAL_REVIEW_SPEC_2 TR48, D1700).

A sketch spline is a run of cubic pieces: the piece from through point ``i`` to
``i + 1`` has the poles ``P_i``, ``H_i``, ``2 P_(i+1) - H_(i+1)`` and ``P_(i+1)``
(the handle sets the leaving direction and the mirrored handle the arriving one).
A place on the spline is a number ``u`` from 0 to the piece count: the whole part
names the piece and the rest is the place inside it.

Cutting a spline at ``u`` keeps the place, the direction and the shape of the end
piece exactly when the kept piece is the spline's only piece next to the cut. When
the kept part has more pieces, the through point next to the cut keeps its handle
(it also shapes the next piece), so the cut piece bends a little between its ends;
the cut end itself and its direction are always exact.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from fdcad.core.sketch.model import Arc, Line, Point, Sketch, Spline, entity_points

Vec = tuple[float, float]
Arr = NDArray[np.float64]

#: Samples per spline piece when looking for touching points.
SAMPLES = 96


def poles(sketch: Sketch, s: Spline) -> Arr:
    """The poles of every piece, shape (pieces, 4, 2)."""
    pts = np.array([sketch.xy(p) for p in s.points], dtype=float)
    hs = np.array([sketch.xy(h) for h in s.handles], dtype=float)
    out = np.empty((len(pts) - 1, 4, 2))
    out[:, 0] = pts[:-1]
    out[:, 1] = hs[:-1]
    out[:, 2] = 2 * pts[1:] - hs[1:]
    out[:, 3] = pts[1:]
    return out


def _split(u: float, count: int) -> tuple[int, float]:
    seg = min(max(math.floor(u), 0), count - 1)
    return seg, min(max(u - seg, 0.0), 1.0)


def at(p: Arr, u: float) -> tuple[Vec, Vec]:
    """The place and the (not unit) direction at ``u``."""
    seg, t = _split(u, len(p))
    a, b, c, d = p[seg]
    m = 1 - t
    pos = m**3 * a + 3 * m * m * t * b + 3 * m * t * t * c + t**3 * d
    der = 3 * (m * m * (b - a) + 2 * m * t * (c - b) + t * t * (d - c))
    return (float(pos[0]), float(pos[1])), (float(der[0]), float(der[1]))


def samples(p: Arr, n: int = SAMPLES) -> tuple[Arr, Arr, Arr]:
    """Places ``u``, points and unit directions along the whole spline, as arrays."""
    t = np.linspace(0.0, 1.0, n + 1)[:-1]
    m = 1 - t
    w = np.stack([m**3, 3 * m * m * t, 3 * m * t * t, t**3], axis=1)  # (n, 4)
    dw = np.stack([-3 * m * m, 3 * m * m - 6 * m * t, 6 * m * t - 3 * t * t, 3 * t * t], axis=1)
    pts = np.einsum("nk,skd->snd", w, p).reshape(-1, 2)
    der = np.einsum("nk,skd->snd", dw, p).reshape(-1, 2)
    u = (np.arange(len(p))[:, None] + t[None, :]).reshape(-1)
    u = np.append(u, float(len(p)))
    pts = np.vstack([pts, p[-1, 3]])
    der = np.vstack([der, 3 * (p[-1, 3] - p[-1, 2])])
    norm = np.linalg.norm(der, axis=1)
    norm[norm < 1e-12] = 1.0
    return u, pts, der / norm[:, None]


def end_index(sketch: Sketch, s: Spline, x: Vec) -> int:
    """0 when the spline's first point is at ``x``, -1 when its last point is."""
    first = math.dist(sketch.xy(s.points[0]), x)
    last = math.dist(sketch.xy(s.points[-1]), x)
    return 0 if first <= last else -1


def refine(f: object, lo: float, hi: float, steps: int = 60) -> float:
    """Where the function ``f`` (of ``u``) changes sign between ``lo`` and ``hi``."""
    assert callable(f)
    flo = f(lo)
    for _ in range(steps):
        mid = (lo + hi) / 2
        fm = f(mid)
        if (fm <= 0) == (flo <= 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return (lo + hi) / 2


def cut(sketch: Sketch, s: Spline, u: float, corner_end: int) -> str:
    """Cut spline ``s`` at ``u`` and drop the part on the ``corner_end`` side (0 for
    its start, -1 for its end). Returns the id of the spline's new end point."""
    p = poles(sketch, s)
    seg, t = _split(u, len(p))
    a, b, c, d = p[seg]
    ab, bc, cd = a + (b - a) * t, b + (c - b) * t, c + (d - c) * t
    abc, bcd = ab + (bc - ab) * t, bc + (cd - bc) * t
    m = abc + (bcd - abc) * t
    old_points = list(s.points)
    old_handles = list(s.handles)
    new_pt = sketch.add_point(float(m[0]), float(m[1]), s.construction)
    if corner_end == -1:
        # Keep the start up to the cut: the cut piece runs a, ab, abc, m.
        h = 2 * m - abc
        new_h = sketch.add_point(float(h[0]), float(h[1]), True)
        s.points = [*old_points[: seg + 1], new_pt]
        s.handles = [*old_handles[: seg + 1], new_h]
        if seg == 0:
            first = sketch.point(s.handles[0])
            first.x, first.y = float(ab[0]), float(ab[1])
    else:
        # Keep from the cut to the end: the cut piece runs m, bcd, cd, d.
        new_h = sketch.add_point(float(bcd[0]), float(bcd[1]), True)
        s.points = [new_pt, *old_points[seg + 1 :]]
        s.handles = [new_h, *old_handles[seg + 1 :]]
        if seg == len(p) - 1:
            last = sketch.point(s.handles[-1])
            h = 2 * d - cd
            last.x, last.y = float(h[0]), float(h[1])
    gone = (set(old_points) | set(old_handles)) - set(s.points) - set(s.handles)
    users = {
        q for e in sketch.entities.values() if not isinstance(e, Point) for q in entity_points(e)
    }
    for pid in gone - users:
        sketch.entities.pop(pid, None)
    sketch.relations = [r for r in sketch.relations if not set(r.entities) & (gone - users)]
    sketch.dimensions = [dm for dm in sketch.dimensions if not set(dm.entities) & (gone - users)]
    return new_pt


def distance_to(sketch: Sketch, c: Line | Arc, o: Arr) -> Arr:
    """Distance from each point of ``o`` (shape (n, 2)) to the full line or circle of
    ``c``."""
    if isinstance(c, Line):
        (x1, y1), (x2, y2) = sketch.xy(c.p1), sketch.xy(c.p2)
        n = math.hypot(x2 - x1, y2 - y1) or 1.0
        out: Arr = np.abs((o[:, 0] - x1) * (y2 - y1) - (o[:, 1] - y1) * (x2 - x1)) / n
        return out
    cx, cy = sketch.xy(c.center)
    big = sketch.radius(c.id)
    out2: Arr = np.abs(np.hypot(o[:, 0] - cx, o[:, 1] - cy) - big)
    return out2


def fillet_centres(
    sketch: Sketch, s: Spline, other: Line | Arc, radius: float
) -> list[tuple[float, Vec]]:
    """Places ``u`` on the spline and fillet centres ``radius`` away from both the
    spline (on its normal at ``u``) and the full line or circle of ``other``."""
    p = poles(sketch, s)
    u, pts, tan = samples(p)
    normal = np.stack([-tan[:, 1], tan[:, 0]], axis=1)
    found: list[tuple[float, Vec]] = []
    for side in (1.0, -1.0):
        centres = pts + side * radius * normal
        f = distance_to(sketch, other, centres) - radius
        flips = np.nonzero(np.sign(f[:-1]) * np.sign(f[1:]) < 0)[0]

        def gap(v: float, side: float = side) -> float:
            (x, y), (dx, dy) = at(p, v)
            n = math.hypot(dx, dy) or 1.0
            o = np.array([[x - side * radius * dy / n, y + side * radius * dx / n]])
            return float(distance_to(sketch, other, o)[0]) - radius

        for i in flips:
            v = refine(gap, float(u[i]), float(u[i + 1]))
            (x, y), (dx, dy) = at(p, v)
            n = math.hypot(dx, dy) or 1.0
            found.append((v, (x - side * radius * dy / n, y + side * radius * dx / n)))
    return found


def point_at_distance(sketch: Sketch, s: Spline, corner_end: int, d: float) -> float | None:
    """The place ``u`` nearest the ``corner_end`` end whose straight distance from that
    end is ``d``, or None when the spline is shorter."""
    p = poles(sketch, s)
    u, pts, _tan = samples(p)
    if corner_end == -1:
        u, pts = u[::-1], pts[::-1]
    x = pts[0]
    gaps = np.hypot(pts[:, 0] - x[0], pts[:, 1] - x[1]) - d
    over = np.nonzero(gaps >= 0)[0]
    if len(over) == 0 or over[0] == 0:
        return None
    i = int(over[0])

    def f(v: float) -> float:
        q, _ = at(p, v)
        return math.dist(q, (float(x[0]), float(x[1]))) - d

    return refine(f, float(u[i - 1]), float(u[i]))
