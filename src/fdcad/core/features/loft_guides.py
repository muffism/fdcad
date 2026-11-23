"""Guide curves and a centerline for Loft (TR55 items 2 to 4, DECISIONS D804).

The kernel cannot loft along guides reliably (D220), so FDCAD adds sections of
its own between each pair of profiles and lofts through all of them:

- Each added section blends the two profiles edge by edge (edge k of one with
  edge k of the next, so corners stay corners). The profiles therefore need the
  same number of edges; the next profile's edges are turned round to line up
  with the first's.
- Guides: each guide must touch every profile. Along a span, the section is
  pushed by how far each guide leaves the straight line between its touching
  points, most strongly near where that guide touches, so the sides follow the
  guides. One guide moves the whole section with it.
- Centerline: each added section is turned square to the centerline and
  centred on it. ``sections`` sets how many are added in each span.

Kernel work: call from the rebuild (CLAUDE.md rule 2).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_CompCurve, BRepAdaptor_Curve
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepTools import BRepTools_WireExplorer
from OCP.GCPnts import GCPnts_AbscissaPoint
from OCP.gp import gp_Pnt, gp_Vec
from OCP.TopAbs import TopAbs_REVERSED
from OCP.TopoDS import TopoDS_Edge, TopoDS_Wire

from fdcad.core.features.base import FeatureError
from fdcad.core.features.sweep_guides import TOUCH, Guide

#: Points per edge used to blend sections.
EDGE_POINTS = 13
#: Sections added in each span with guides (a centerline uses ``sections``).
GUIDE_SECTIONS = 8


def _edges(wire: TopoDS_Wire) -> list[TopoDS_Edge]:
    out = []
    walk = BRepTools_WireExplorer(wire)
    while walk.More():
        out.append(walk.Current())
        walk.Next()
    return out


def _edge_points(edge: TopoDS_Edge) -> np.ndarray:
    """``EDGE_POINTS`` points along ``edge`` in the wire's direction."""
    curve = BRepAdaptor_Curve(edge)
    a, b = curve.FirstParameter(), curve.LastParameter()
    us = np.linspace(a, b, EDGE_POINTS)
    if edge.Orientation() == TopAbs_REVERSED:
        us = us[::-1]
    pts = []
    for u in us:
        p = curve.Value(float(u))
        pts.append((p.X(), p.Y(), p.Z()))
    return np.array(pts, dtype=float)


def _aligned(first: list[np.ndarray], other: list[np.ndarray]) -> list[np.ndarray]:
    """``other``'s edges turned round to line up with ``first``'s (centres matched)."""
    a = np.array([e[0] for e in first])
    b = np.array([e[0] for e in other])
    a -= a.mean(axis=0)
    b -= b.mean(axis=0)
    n = len(other)
    best = min(
        range(n), key=lambda k: float(np.sum(np.linalg.norm(a - np.roll(b, -k, axis=0), axis=1)))
    )
    return other[best:] + other[:best]


def _fractions(points: list[np.ndarray]) -> np.ndarray:
    """Each sample's place along the whole outline, 0 to 1 by length."""
    flat = np.concatenate(points)
    steps = np.linalg.norm(np.diff(flat, axis=0), axis=1)
    run = np.concatenate([[0.0], np.cumsum(steps)])
    return run / run[-1] if run[-1] > 0 else run


def _touch(guide: Guide, wire: TopoDS_Wire) -> gp_Pnt | None:
    dist = BRepExtrema_DistShapeShape(guide.wire, wire)
    if not dist.IsDone() or dist.NbSolution() == 0 or dist.Value() > TOUCH:
        return None
    return dist.PointOnShape1(1)


def _along(guide: Guide, point: gp_Pnt) -> float:
    """The length along ``guide`` to the guide point nearest ``point``."""
    curve = BRepAdaptor_CompCurve(guide.wire)
    a, b = curve.FirstParameter(), curve.LastParameter()
    us = np.linspace(a, b, 400)
    best = min(us, key=lambda u: curve.Value(float(u)).Distance(point))
    lo, hi = max(a, best - (b - a) / 399), min(b, best + (b - a) / 399)
    for _ in range(50):
        m1, m2 = lo + (hi - lo) / 3, hi - (hi - lo) / 3
        if curve.Value(m1).Distance(point) < curve.Value(m2).Distance(point):
            hi = m2
        else:
            lo = m1
    return float(GCPnts_AbscissaPoint.Length_s(curve, a, (lo + hi) / 2))


def _at(guide: Guide, length: float) -> np.ndarray:
    curve = BRepAdaptor_CompCurve(guide.wire)
    u = GCPnts_AbscissaPoint(curve, length, curve.FirstParameter()).Parameter()
    p = curve.Value(u)
    return np.array([p.X(), p.Y(), p.Z()])


def _wire_through(points: list[np.ndarray]) -> TopoDS_Wire:
    """A closed wire, one smooth edge through each row of points, corners shared."""
    from OCP.collections import Array1_gp_Pnt
    from OCP.GeomAbs import GeomAbs_C2
    from OCP.GeomAPI import GeomAPI_PointsToBSpline

    maker = BRepBuilderAPI_MakeWire()
    count = len(points)
    for k, row in enumerate(points):
        row = row.copy()
        row[-1] = points[(k + 1) % count][0]  # close each corner exactly
        if float(np.max(np.linalg.norm(row - row[0], axis=1))) < 1e-9:
            continue
        array = Array1_gp_Pnt(1, len(row))
        for i, p in enumerate(row, start=1):
            array.SetValue(i, gp_Pnt(*map(float, p)))
        curve = GeomAPI_PointsToBSpline(array, 3, 8, GeomAbs_C2, 1e-6).Curve()
        maker.Add(BRepBuilderAPI_MakeEdge(curve).Edge())
    return maker.Wire()


def _square_to(
    points: list[np.ndarray], centre: np.ndarray, tangent: np.ndarray
) -> list[np.ndarray]:
    """``points`` turned so their best fit plane is square to ``tangent``, centred on
    ``centre`` (the centerline, TR55 item 3)."""
    flat = np.concatenate(points)
    middle = flat.mean(axis=0)
    _u, _s, vt = np.linalg.svd(flat - middle)
    normal = vt[2]
    t = tangent / np.linalg.norm(tangent)
    if float(normal @ t) < 0:
        normal = -normal
    axis = np.cross(normal, t)
    s, c = float(np.linalg.norm(axis)), float(normal @ t)
    if s < 1e-12:
        rot = np.eye(3)
    else:
        k = axis / s
        kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
        rot = np.eye(3) + s * kx + (1 - c) * (kx @ kx)
    return [(row - middle) @ rot.T + centre for row in points]


def added_sections(
    owner: str,
    wires: Sequence[TopoDS_Wire],
    guides: Sequence[Guide],
    centerline: TopoDS_Wire | None,
    count: int,
) -> list[TopoDS_Wire]:
    """The profiles with blended sections added between them (see the module notes)."""
    edge_rows = [[_edge_points(e) for e in _edges(w)] for w in wires]
    sizes = {len(r) for r in edge_rows}
    if len(sizes) != 1:
        raise FeatureError(
            f"{owner}: with guide curves or a centerline every profile needs the same number "
            "of edges. Split edges so the profiles match, or remove the guides."
        )
    for k in range(1, len(edge_rows)):
        edge_rows[k] = _aligned(edge_rows[k - 1], edge_rows[k])
    touches: list[list[gp_Pnt]] = []
    for guide in guides:
        row = []
        for k, wire in enumerate(wires, start=1):
            point = _touch(guide, wire)
            if point is None:
                raise FeatureError(
                    f"{owner}: {guide.label} does not touch profile {k}. Move the guide onto "
                    "that profile's outline."
                )
            row.append(point)
        touches.append(row)
    lengths = [[_along(g, p) for p in row] for g, row in zip(guides, touches, strict=True)]
    fractions = _fractions(edge_rows[0])
    anchors = []
    flat0 = np.concatenate(edge_rows[0])
    for row in touches:
        c = np.array([row[0].X(), row[0].Y(), row[0].Z()])
        anchors.append(float(fractions[int(np.argmin(np.linalg.norm(flat0 - c, axis=1)))]))
    line = BRepAdaptor_CompCurve(centerline) if centerline is not None else None
    added = count if centerline is not None else GUIDE_SECTIONS
    out: list[TopoDS_Wire] = [wires[0]]
    for i in range(len(wires) - 1):
        a, b = edge_rows[i], edge_rows[i + 1]
        if line is not None:
            ca, cb = (np.concatenate(a).mean(axis=0), np.concatenate(b).mean(axis=0))
            ua, ub = _nearest(line, ca), _nearest(line, cb)
        for step in range(1, added + 1):
            t = step / (added + 1)
            rows = [(1 - t) * ea + t * eb for ea, eb in zip(a, b, strict=True)]
            if guides:
                flat = np.concatenate(rows)
                shift = np.zeros_like(flat)
                weights = np.zeros(len(flat))
                pushes = []
                for g, guide in enumerate(guides):
                    on_guide = _at(guide, (1 - t) * lengths[g][i] + t * lengths[g][i + 1])
                    pa, pb = touches[g][i], touches[g][i + 1]
                    straight = (1 - t) * np.array([pa.X(), pa.Y(), pa.Z()]) + t * np.array(
                        [pb.X(), pb.Y(), pb.Z()]
                    )
                    pushes.append(on_guide - straight)
                for g, push in enumerate(pushes):
                    d = np.abs(fractions - anchors[g])
                    d = np.minimum(d, 1 - d)
                    w = 1.0 / (d * d + 1e-6) if len(guides) > 1 else np.ones(len(flat))
                    shift += w[:, None] * push
                    weights += w
                flat = flat + shift / weights[:, None]
                rows = list(np.split(flat, len(rows)))
            if line is not None:
                u = (1 - t) * ua + t * ub
                p, d = gp_Pnt(), gp_Vec()
                line.D1(u, p, d)
                rows = _square_to(
                    rows, np.array([p.X(), p.Y(), p.Z()]), np.array([d.X(), d.Y(), d.Z()])
                )
            out.append(_wire_through(rows))
        out.append(wires[i + 1])
    return out


def _nearest(curve: BRepAdaptor_CompCurve, point: np.ndarray) -> float:
    a, b = curve.FirstParameter(), curve.LastParameter()
    us = np.linspace(a, b, 400)
    target = gp_Pnt(*map(float, point))
    return float(min(us, key=lambda u: curve.Value(float(u)).Distance(target)))


def check_count(value: float) -> int:
    """The number of centerline sections per span, 1 to 50."""
    if math.isnan(value) or math.isinf(value):
        raise FeatureError("The number of sections must be from 1 to 50. Type another number.")
    n = round(value)
    if not 1 <= n <= 50:
        raise FeatureError("The number of sections must be from 1 to 50. Type another number.")
    return n
