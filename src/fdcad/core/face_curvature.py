"""Curvature colours on faces and the curvature at a point (TUTORIAL_REVIEW_SPEC_2
TR199 item 1, DECISIONS D2503).

Each face gets one value: exact for planes, cylinders and spheres, and for other
faces the most curved of a small grid of sample points (a fixed number per face,
never per triangle). A value is one of three kinds:

- ``largest``: the larger principal curvature by size, 1/mm (one over the
  tightest radius at that point),
- ``mean``: the average of the two principal curvatures, 1/mm,
- ``gaussian``: their product, 1/mm squared (zero on flat and singly curved faces).

Colours run from blue (the smallest value shown) through green to red (the
largest). Kernel work: run ``face_values`` on a worker. Nothing here changes the
part. No Qt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepLProp import BRepLProp_SLProps
from OCP.BRepTools import BRepTools
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Sphere
from OCP.gp import gp_Pnt
from OCP.ShapeAnalysis import ShapeAnalysis_Surface
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

KINDS = ("largest", "mean", "gaussian")
#: Sample points along each side of a face's parameter grid (faces that are not
#: planes, cylinders or spheres).
SAMPLES = 5
#: The colour ramp, smallest to largest.
RAMP = ("#2B6CD9", "#2BB3D9", "#3DBF4A", "#E6C229", "#D93B2B")


@dataclass(frozen=True)
class PointCurvature:
    """Principal curvatures at a point (1/mm, signed), and the values derived from them."""

    k1: float
    k2: float

    @property
    def largest(self) -> float:
        """The principal curvature of the larger size, as a size (1/mm)."""
        return max(abs(self.k1), abs(self.k2))

    @property
    def mean(self) -> float:
        """The mean curvature (1/mm)."""
        return (self.k1 + self.k2) / 2

    @property
    def gaussian(self) -> float:
        """The Gaussian curvature (1/mm squared)."""
        return self.k1 * self.k2

    @property
    def radius(self) -> float | None:
        """The tightest radius at the point (mm), or None where it is flat."""
        k = self.largest
        return 1.0 / k if k > 1e-12 else None

    def value(self, kind: str) -> float:
        """The value of ``kind``."""
        return float(getattr(self, kind))


def _faces(shape: TopoDS_Shape) -> list[TopoDS_Face]:
    out: list[TopoDS_Face] = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        out.append(TopoDS.Face(explorer.Current()))
        explorer.Next()
    return out


def _at_uv(face: TopoDS_Face, u: float, v: float) -> PointCurvature | None:
    props = BRepLProp_SLProps(BRepAdaptor_Surface(face), u, v, 2, 1e-7)
    if not props.IsCurvatureDefined():
        return None
    return PointCurvature(props.MaxCurvature(), props.MinCurvature())


def _analytic(face: TopoDS_Face) -> PointCurvature | None:
    """The curvature of a plane, cylinder or sphere (the same everywhere), or None."""
    surface = BRepAdaptor_Surface(face)
    kind = surface.GetType()
    sign = -1.0 if face.Orientation() == 1 else 1.0  # reversed faces curve the other way
    if kind == GeomAbs_Plane:
        return PointCurvature(0.0, 0.0)
    if kind == GeomAbs_Cylinder:
        return PointCurvature(sign / surface.Cylinder().Radius(), 0.0)
    if kind == GeomAbs_Sphere:
        k = sign / surface.Sphere().Radius()
        return PointCurvature(k, k)
    return None


def face_curvature(face: TopoDS_Face, kind: str, samples: int = SAMPLES) -> float:
    """One value for ``face``: exact for planes, cylinders and spheres, else the sample
    of the largest size on a ``samples`` by ``samples`` parameter grid."""
    exact = _analytic(face)
    if exact is not None:
        return exact.value(kind)
    u0, u1, v0, v1 = BRepTools.UVBounds_s(face)
    best = 0.0
    n = max(2, samples)
    for i in range(n):  # a fixed grid per face, not a loop over mesh points (D2503)
        for j in range(n):
            u = u0 + (u1 - u0) * (i + 0.5) / n
            v = v0 + (v1 - v0) * (j + 0.5) / n
            found = _at_uv(face, u, v)
            if found is not None:
                value = found.value(kind)
                if math.isfinite(value) and abs(value) > abs(best):
                    best = value
    return best


def face_values(shape: TopoDS_Shape, kind: str = "largest") -> list[tuple[TopoDS_Face, float]]:
    """Every face of ``shape`` with its value of ``kind``."""
    if kind not in KINDS:
        raise ValueError(f"unknown curvature kind {kind!r}")
    return [(f, face_curvature(f, kind)) for f in _faces(shape)]


def value_range(values: list[float]) -> tuple[float, float]:
    """The smallest and largest value to colour; a single value gives a range around it."""
    if not values:
        return 0.0, 1.0
    lo, hi = min(values), max(values)
    if hi - lo < 1e-12:
        return lo - 0.5 if lo != 0 else 0.0, hi + 0.5 if hi != 0 else 1.0
    return lo, hi


def color_for(value: float, lo: float, hi: float) -> str:
    """The ramp colour of ``value`` between ``lo`` (blue) and ``hi`` (red)."""
    t = 0.0 if hi <= lo else min(max((value - lo) / (hi - lo), 0.0), 1.0)
    x = t * (len(RAMP) - 1)
    i = min(int(x), len(RAMP) - 2)
    f = x - i
    a, b = RAMP[i], RAMP[i + 1]
    mixed = [round(int(a[k : k + 2], 16) * (1 - f) + int(b[k : k + 2], 16) * f) for k in (1, 3, 5)]
    return "#" + "".join(f"{c:02X}" for c in mixed)


def curvature_at(face: TopoDS_Face, point: tuple[float, float, float]) -> PointCurvature | None:
    """The curvature of ``face`` at the point nearest ``point`` (a hover readout:
    one projection and one evaluation), or None when it is not defined there."""
    exact = _analytic(face)
    if exact is not None:
        return exact
    try:
        surface = BRepAdaptor_Surface(face).Surface().Surface()
        uv = ShapeAnalysis_Surface(surface).ValueOfUV(gp_Pnt(*point), 1e-6)
        return _at_uv(face, uv.X(), uv.Y())
    except Exception:
        return None
