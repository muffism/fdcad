"""Deform a solid through its NURBS control points (PLAN Phase 4, D393).

The PLAN method: convert the body to NURBS, deform the control points, rebuild
and validate the solid.

1. ``BRepBuilderAPI_NurbsConvert`` turns every face and edge into B-splines.
2. Each surface and edge curve gets degree 3 or more and extra knots, so it has
   enough control points to follow a bent or twisted shape. The control points
   are then moved: new control points are solved so the surface passes through
   the mapped points at its Greville parameters (one per control point). For
   maps that keep straight lines straight this equals moving each control point
   by the map; for bends and twists it is far more accurate. Knots, weights and
   parameters do not change, so every face's boundary curves (pcurves) stay
   valid on the moved surface.
3. The result is compared with the exact map at sample points. When the
   largest deviation is above the tolerance the curve or surface is refined
   again, up to a limit; the deviation that remains is reported, so the
   feature can warn that the result is approximate.
4. Edges and vertices are moved the same way, tolerances are updated, the
   shape is healed and checked. An invalid result raises ``DeformError``.

Control points are read and written one at a time because the kernel binding
has no bulk transfer for them; the map itself runs on whole numpy arrays. Runs
on the rebuild worker thread, never the UI thread.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray
from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy, BRepBuilderAPI_NurbsConvert
from OCP.BRepLib import BRepLib
from OCP.Geom import Geom_BSplineCurve, Geom_BSplineSurface
from OCP.GeomConvert import GeomConvert
from OCP.gp import gp_Pnt
from OCP.ShapeFix import ShapeFix_Shape
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
from OCP.TopExp import TopExp
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

from fdcad.core.deform.maps import PointMap, Points
from fdcad.core.occ import ShapeMap

#: Most segments per direction a surface or curve is split into while refining.
MAX_SEGMENTS = 48
#: Samples per direction for the deviation check.
_SAMPLES = 7


class DeformError(Exception):
    """The deformation failed. The message says why; the feature adds what to do."""


@dataclass
class Deformed:
    """The deformed shape, what each original face became, and the largest deviation."""

    shape: TopoDS_Shape
    faces: list[tuple[TopoDS_Face, TopoDS_Face]] = field(default_factory=list)
    deviation: float = 0.0


def _array(arr: object) -> NDArray[np.float64]:
    lower, upper = arr.Lower(), arr.Upper()  # type: ignore[attr-defined]
    return np.array([arr.Value(i) for i in range(lower, upper + 1)])  # type: ignore[attr-defined]


def basis_matrix(
    knots: NDArray[np.float64], degree: int, xs: NDArray[np.float64]
) -> NDArray[np.float64]:
    """B-spline basis values: row a holds every basis function at ``xs[a]``.

    ``knots`` is the full (flat) knot sequence. Cox and de Boor's recursion on
    whole arrays.
    """
    n = len(knots) - degree - 1
    x = np.clip(xs, knots[degree], knots[n])
    last = knots[n]
    b = np.zeros((len(x), len(knots) - 1))
    for i in range(len(knots) - 1):
        lo, hi = knots[i], knots[i + 1]
        if hi > lo:
            b[:, i] = ((x >= lo) & (x < hi)) | ((x == last) & (hi == last))
    for d in range(1, degree + 1):
        nxt = np.zeros((len(x), len(knots) - d - 1))
        for i in range(len(knots) - d - 1):
            left = knots[i + d] - knots[i]
            right = knots[i + d + 1] - knots[i + 1]
            term = np.zeros(len(x))
            if left > 0:
                term += (x - knots[i]) / left * b[:, i]
            if right > 0:
                term += (knots[i + d + 1] - x) / right * b[:, i + 1]
            nxt[:, i] = term
        b = nxt
    return b[:, :n]


def greville(knots: NDArray[np.float64], degree: int) -> NDArray[np.float64]:
    """The Greville parameters: one per control point."""
    n = len(knots) - degree - 1
    return np.array([knots[i + 1 : i + degree + 1].mean() for i in range(n)])


def _poles_2d(surface: Geom_BSplineSurface) -> Points:
    nu, nv = surface.NbUPoles(), surface.NbVPoles()
    out = np.empty((nu * nv, 3))
    k = 0
    for i in range(1, nu + 1):
        for j in range(1, nv + 1):
            p = surface.Pole(i, j)
            out[k] = (p.X(), p.Y(), p.Z())
            k += 1
    return out


def _set_poles_2d(surface: Geom_BSplineSurface, pts: Points) -> None:
    nu, nv = surface.NbUPoles(), surface.NbVPoles()
    k = 0
    for i in range(1, nu + 1):
        for j in range(1, nv + 1):
            x, y, z = pts[k]
            surface.SetPole(i, j, gp_Pnt(float(x), float(y), float(z)))
            k += 1


def _poles_1d(curve: Geom_BSplineCurve) -> Points:
    n = curve.NbPoles()
    out = np.empty((n, 3))
    for i in range(1, n + 1):
        p = curve.Pole(i)
        out[i - 1] = (p.X(), p.Y(), p.Z())
    return out


def _set_poles_1d(curve: Geom_BSplineCurve, pts: Points) -> None:
    for i, (x, y, z) in enumerate(pts, start=1):
        curve.SetPole(i, gp_Pnt(float(x), float(y), float(z)))


def _apply_location(pts: Points, loc: TopLoc_Location, inverse: bool = False) -> Points:
    if loc.IsIdentity():
        return pts
    trsf = loc.Transformation()
    if inverse:
        trsf = trsf.Inverted()
    out = np.empty_like(pts)
    for k, (x, y, z) in enumerate(pts):
        p = gp_Pnt(float(x), float(y), float(z)).Transformed(trsf)
        out[k] = (p.X(), p.Y(), p.Z())
    return out


def _even(lo: float, hi: float, n: int) -> list[float]:
    return [lo + (hi - lo) * i / n for i in range(1, n)]


def refine_surface(surface: Geom_BSplineSurface, n: int) -> None:
    """Raise the degree to 3 and split each direction into ``n`` spans, in place.

    The shape and parameters do not change, so curves on the surface stay valid.
    """
    surface.IncreaseDegree(max(3, surface.UDegree()), max(3, surface.VDegree()))
    if surface.IsUPeriodic():
        surface.SetUNotPeriodic()
    if surface.IsVPeriodic():
        surface.SetVNotPeriodic()
    u1, u2, v1, v2 = surface.Bounds()
    tol = 1e-9 * max(1.0, abs(u2 - u1), abs(v2 - v1))
    for u in _even(u1, u2, n):
        surface.InsertUKnot(u, 1, tol, True)
    for v in _even(v1, v2, n):
        surface.InsertVKnot(v, 1, tol, True)


def refine_curve(curve: Geom_BSplineCurve, n: int) -> None:
    """The curve version of ``refine_surface``."""
    curve.IncreaseDegree(max(3, curve.Degree()))
    if curve.IsPeriodic():
        curve.SetNotPeriodic()
    t1, t2 = curve.FirstParameter(), curve.LastParameter()
    tol = 1e-9 * max(1.0, abs(t2 - t1))
    for t in _even(t1, t2, n):
        curve.InsertKnot(t, 1, tol, True)


def _refined_surface(base: Geom_BSplineSurface, n: int) -> Geom_BSplineSurface:
    copy = GeomConvert.SurfaceToBSplineSurface_s(base)  # a copy
    refine_surface(copy, n)
    return copy


def _refined_curve(base: Geom_BSplineCurve, n: int) -> Geom_BSplineCurve:
    copy = GeomConvert.CurveToBSplineCurve_s(base)  # a copy
    refine_curve(copy, n)
    return copy


def _weights_2d(surface: Geom_BSplineSurface) -> NDArray[np.float64]:
    nu, nv = surface.NbUPoles(), surface.NbVPoles()
    if not surface.IsURational() and not surface.IsVRational():
        return np.ones((nu, nv))
    return np.array([[surface.Weight(i, j) for j in range(1, nv + 1)] for i in range(1, nu + 1)])


def fit_surface(surface: Geom_BSplineSurface, loc: TopLoc_Location, fmap: PointMap) -> None:
    """Move the control points so the surface passes through the mapped points at its
    Greville parameters (weights kept)."""
    ku, kv = _array(surface.UKnotSequence()), _array(surface.VKnotSequence())
    du, dv = surface.UDegree(), surface.VDegree()
    gu, gv = greville(ku, du), greville(kv, dv)
    nu, nv = len(gu), len(gv)
    uv = [(float(u), float(v)) for u in gu for v in gv]
    target = fmap(_apply_location(_values_2d(surface, uv), loc))
    target = _apply_location(target, loc, inverse=True).reshape(nu, nv, 3)
    bu, bv = basis_matrix(ku, du, gu), basis_matrix(kv, dv, gv)
    w = _weights_2d(surface)
    denom = bu @ w @ bv.T  # the rational denominator at each Greville point
    q = np.empty((nu, nv, 3))
    inv_u, inv_v = np.linalg.inv(bu), np.linalg.inv(bv)
    for k in range(3):
        q[:, :, k] = inv_u @ (target[:, :, k] * denom) @ inv_v.T
    _set_poles_2d(surface, (q / w[:, :, None]).reshape(-1, 3))


def fit_curve(curve: Geom_BSplineCurve, loc: TopLoc_Location, fmap: PointMap) -> None:
    """The curve version of ``fit_surface``."""
    knots = _array(curve.KnotSequence())
    degree = curve.Degree()
    g = greville(knots, degree)
    target = fmap(_apply_location(_values_1d(curve, [float(t) for t in g]), loc))
    target = _apply_location(target, loc, inverse=True)
    n = curve.NbPoles()
    w = np.array([curve.Weight(i) for i in range(1, n + 1)]) if curve.IsRational() else np.ones(n)
    b = basis_matrix(knots, degree, g)
    denom = b @ w
    q = np.linalg.solve(b, target * denom[:, None])
    _set_poles_1d(curve, q / w[:, None])


def _surface_samples(surface: Geom_BSplineSurface) -> list[tuple[float, float]]:
    u1, u2, v1, v2 = surface.Bounds()
    steps = [(i + 0.5) / _SAMPLES for i in range(_SAMPLES)]
    return [(u1 + (u2 - u1) * a, v1 + (v2 - v1) * b) for a in steps for b in steps]


def _values_2d(surface: Geom_BSplineSurface, uv: list[tuple[float, float]]) -> Points:
    out = np.empty((len(uv), 3))
    for k, (u, v) in enumerate(uv):
        p = surface.Value(u, v)
        out[k] = (p.X(), p.Y(), p.Z())
    return out


def _values_1d(curve: Geom_BSplineCurve, ts: list[float]) -> Points:
    out = np.empty((len(ts), 3))
    for k, t in enumerate(ts):
        p = curve.Value(t)
        out[k] = (p.X(), p.Y(), p.Z())
    return out


def _segments(extent: float, region: float) -> list[int]:
    """Segment counts to try, coarse first."""
    start = max(2, min(16, math.ceil(4.0 * extent / max(region, 1e-9))))
    out = [start]
    while out[-1] < MAX_SEGMENTS:
        out.append(min(MAX_SEGMENTS, out[-1] * 2))
    return out


def _extent(pts: Points) -> float:
    return float(np.linalg.norm(pts.max(axis=0) - pts.min(axis=0))) if len(pts) else 0.0


def deform_surface(
    surface: Geom_BSplineSurface,
    loc: TopLoc_Location,
    fmap: PointMap,
    tolerance: float,
    region: float,
) -> float:
    """Deform ``surface`` in place (it keeps its location). Returns the largest deviation.

    Refinements are tried on copies, coarse first; the first that meets the
    tolerance (or the best one) is then applied to the surface itself.
    """
    uv = _surface_samples(surface)
    exact = fmap(_apply_location(_values_2d(surface, uv), loc))
    best: tuple[int, float] | None = None
    extent = _extent(_apply_location(_poles_2d(surface), loc))
    for n in _segments(extent, region):
        trial = _refined_surface(surface, n)
        fit_surface(trial, loc, fmap)
        got = _apply_location(_values_2d(trial, uv), loc)
        deviation = float(np.max(np.linalg.norm(got - exact, axis=1)))
        if best is None or deviation < best[1]:
            best = (n, deviation)
        if deviation <= tolerance:
            break
    assert best is not None
    refine_surface(surface, best[0])
    fit_surface(surface, loc, fmap)
    return best[1]


def deform_curve(
    curve: Geom_BSplineCurve,
    loc: TopLoc_Location,
    fmap: PointMap,
    tolerance: float,
    region: float,
) -> float:
    """Deform an edge curve in place, like ``deform_surface``. Returns the deviation."""
    t1, t2 = curve.FirstParameter(), curve.LastParameter()
    ts = [t1 + (t2 - t1) * (i + 0.5) / (3 * _SAMPLES) for i in range(3 * _SAMPLES)]
    exact = fmap(_apply_location(_values_1d(curve, ts), loc))
    best: tuple[int, float] | None = None
    extent = _extent(_apply_location(_poles_1d(curve), loc))
    for n in _segments(extent, region):
        trial = _refined_curve(curve, n)
        fit_curve(trial, loc, fmap)
        got = _apply_location(_values_1d(trial, ts), loc)
        deviation = float(np.max(np.linalg.norm(got - exact, axis=1)))
        if best is None or deviation < best[1]:
            best = (n, deviation)
        if deviation <= tolerance:
            break
    assert best is not None
    refine_curve(curve, best[0])
    fit_curve(curve, loc, fmap)
    return best[1]


def _unique(shape: TopoDS_Shape, kind: int) -> list[TopoDS_Shape]:
    m = ShapeMap()
    TopExp.MapShapes_s(shape, kind, m)
    return [m.FindKey(i) for i in range(1, m.Extent() + 1)]


def deform_shape(
    shape: TopoDS_Shape,
    fmap: PointMap,
    tolerance: float,
    region: float,
    cancelled: Callable[[], bool] = lambda: False,
) -> Deformed:
    """Deform ``shape`` with ``fmap`` (see the module notes). Raises DeformError."""
    if tolerance <= 0:
        raise DeformError("the tolerance must be above zero")
    originals = [TopoDS.Face(f) for f in _unique(shape, TopAbs_FACE)]
    # A full copy first: the conversion may share vertices and edges with the input,
    # and they are moved in place below. The input body is used by other features
    # and by the live preview, so it must never change.
    copier = BRepBuilderAPI_Copy(shape, True, False)
    copied = copier.Shape()
    converter = BRepBuilderAPI_NurbsConvert(copied, True)
    if not converter.IsDone():
        raise DeformError("the body could not be converted to NURBS")
    nurbs = converter.Shape()
    pairs = [(f, TopoDS.Face(converter.ModifiedShape(copier.ModifiedShape(f)))) for f in originals]
    builder = BRep_Builder()
    worst = 0.0
    for raw in _unique(nurbs, TopAbs_FACE):
        if cancelled():
            raise DeformError("cancelled")
        face = TopoDS.Face(raw)
        loc = TopLoc_Location()
        surface = BRep_Tool.Surface_s(face, loc)
        if not isinstance(surface, Geom_BSplineSurface):
            raise DeformError("a face could not be converted to NURBS")
        # The face's own surface object changes, so its edges' curves stay attached.
        deviation = deform_surface(surface, loc, fmap, tolerance, region)
        builder.UpdateFace(face, max(BRep_Tool.Tolerance_s(face), deviation))
        worst = max(worst, deviation)
    for raw in _unique(nurbs, TopAbs_EDGE):
        edge = TopoDS.Edge(raw)
        if BRep_Tool.Degenerated_s(edge):
            continue
        loc = TopLoc_Location()
        first, last = BRep_Tool.Range_s(edge)
        curve = BRep_Tool.Curve_s(edge, loc, first, last)
        if curve is None:
            continue
        if not isinstance(curve, Geom_BSplineCurve):
            raise DeformError("an edge could not be converted to NURBS")
        deviation = deform_curve(curve, loc, fmap, tolerance, region)
        builder.UpdateEdge(edge, max(BRep_Tool.Tolerance_s(edge), deviation))
        worst = max(worst, deviation)
    for raw in _unique(nurbs, TopAbs_VERTEX):
        vertex = TopoDS.Vertex(raw)
        p = BRep_Tool.Pnt_s(vertex)
        ((x, y, z),) = fmap(np.array([[p.X(), p.Y(), p.Z()]]))
        builder.UpdateVertex(
            vertex, gp_Pnt(float(x), float(y), float(z)), BRep_Tool.Tolerance_s(vertex)
        )
    BRepLib.SameParameter_s(nurbs, max(tolerance, 1e-6), True)
    BRepLib.UpdateTolerances_s(nurbs, False)
    fixer = ShapeFix_Shape(nurbs)
    fixer.SetPrecision(max(1e-7, min(tolerance, 1e-4)))
    fixer.SetMaxTolerance(max(tolerance * 10.0, worst * 2.0, 1e-3))
    fixer.Perform()
    fixed = fixer.Shape()
    context = fixer.Context()
    out_pairs = []
    for original, converted in pairs:
        image = context.Apply(converted)
        if not image.IsNull() and image.ShapeType() == TopAbs_FACE:
            out_pairs.append((original, TopoDS.Face(image)))
    return Deformed(fixed, out_pairs, worst)
