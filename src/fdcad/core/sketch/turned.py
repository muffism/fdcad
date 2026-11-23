"""Turned outline of the part (TUTORIAL_REVIEW_SPEC_2 TR319, DECISIONS D888).

The part seen as it would look spun about the sketch's X axis: at each station
along the axis, the largest distance of the part from the axis. The result is the
half profile above the axis, closed along the axis, as sketch lines: the outline of
a turned part for a lathe drawing, or a profile to revolve.

The part is meshed; the largest distance over a slice of the surface is found
where the mesh's edges cross the slice (the distance from an axis is convex, so a
triangle's largest value in a slice is on its edges), all in numpy. No Qt.
"""

from __future__ import annotations

import numpy as np
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.sketch.curve_convert import CurvePiece, ProjectedCurve
from fdcad.core.sketch.profiles import SketchPlane

TURNED = "turned"
#: Stations along the axis.
STATIONS = 400
#: Outline points closer than this to the line through their neighbours are dropped (mm).
FLAT = 0.005


def _envelope(
    tris: np.ndarray, origin: np.ndarray, axis: np.ndarray, count: int
) -> tuple[np.ndarray, np.ndarray]:
    """Stations along the axis and the largest radius at each."""
    pts = tris.reshape(-1, 3).astype(np.float64) - origin
    t = pts @ axis
    r = np.sqrt(np.maximum((pts * pts).sum(axis=1) - t * t, 0.0))
    t0, t1 = float(t.min()), float(t.max())
    stations = np.linspace(t0, t1, count)
    best = np.zeros(count)
    # Vertices: each lands on its nearest station.
    k = np.clip(
        np.rint((t - t0) / max(t1 - t0, 1e-12) * (count - 1)).astype(np.int64), 0, count - 1
    )
    np.maximum.at(best, k, r)
    # Edges crossing stations: the point where each edge meets each station it spans.
    tri_pts = pts.reshape(-1, 3, 3)
    a = tri_pts.reshape(-1, 3)
    b = np.roll(tri_pts, -1, axis=1).reshape(-1, 3)
    ta, tb = a @ axis, b @ axis
    lo, hi = np.minimum(ta, tb), np.maximum(ta, tb)
    step = (t1 - t0) / (count - 1) if count > 1 else 1.0
    first = np.ceil((lo - t0) / step - 1e-9).astype(np.int64)
    last = np.floor((hi - t0) / step + 1e-9).astype(np.int64)
    spans = np.clip(last - first + 1, 0, None)
    keep = (spans > 0) & (hi - lo > 1e-12)
    if keep.any():
        a, b, ta, tb = a[keep], b[keep], ta[keep], tb[keep]
        first, spans = first[keep], spans[keep]
        edge = np.repeat(np.arange(len(a)), spans)
        offsets = np.arange(spans.sum()) - np.repeat(np.cumsum(spans) - spans, spans)
        station = np.clip(first[edge] + offsets, 0, count - 1)
        s = (stations[station] - ta[edge]) / (tb[edge] - ta[edge])
        p = a[edge] + (b[edge] - a[edge]) * s[:, None]
        tp = p @ axis
        rp = np.sqrt(np.maximum((p * p).sum(axis=1) - tp * tp, 0.0))
        np.maximum.at(best, station, rp)
    return stations, best


def _simplify(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Drop points that lie on the line through their neighbours."""
    out = [points[0]]
    for i in range(1, len(points) - 1):
        (x0, y0), (x1, y1), (x2, y2) = out[-1], points[i], points[i + 1]
        dx, dy = x2 - x0, y2 - y0
        length = (dx * dx + dy * dy) ** 0.5
        off = abs(dx * (y0 - y1) - (x0 - x1) * dy) / length if length > 1e-12 else 0.0
        if off > FLAT:
            out.append(points[i])
    out.append(points[-1])
    return out


def turned_outline(shape: TopoDS_Shape, plane: SketchPlane) -> ProjectedCurve:
    """The closed half profile of ``shape`` spun about the sketch's X axis, in sketch
    coordinates. Never raises: an empty result on any failure."""
    from fdcad.core.features.solids import bounding_size
    from fdcad.core.io.export import MeshSettings, triangles

    out = ProjectedCurve(TURNED, "Turned outline")
    try:
        size = bounding_size(shape)
        tris = triangles(shape, MeshSettings(deviation=max(0.02, size * 0.001)))
        if len(tris) == 0:
            return out
        stations, radius = _envelope(
            tris,
            np.array(plane.origin, dtype=np.float64),
            np.array(plane.x_dir, dtype=np.float64),
            STATIONS,
        )
        outline = _simplify([(float(t), float(r)) for t, r in zip(stations, radius, strict=True)])
        first, last = outline[0], outline[-1]
        loop = [(first[0], 0.0), *outline, (last[0], 0.0)]
        loop = [
            p
            for i, p in enumerate(loop)
            if i == 0 or abs(p[0] - loop[i - 1][0]) + abs(p[1] - loop[i - 1][1]) > 1e-9
        ]
        pieces = [CurvePiece("line", (loop[i], loop[i + 1])) for i in range(len(loop) - 1)]
        pieces.append(CurvePiece("line", (loop[-1], loop[0])))  # along the axis
        out.pieces = pieces
    except Exception:  # reference only: an empty result, never a crash (CLAUDE.md 5.7)
        out.pieces = []
    return out
