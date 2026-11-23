"""Fillet methods and profiles (TR62, DECISIONS D1402).

``method``: "radius" (default), "asymmetric" (``radius`` is the first distance,
``distance2`` the second, ``reverse`` swaps the faces they are measured on) or
"chord" (``radius`` is the chord width: the straight distance between the two
lines where the round meets the faces).

``profile``: "circular" (default), "conic" (``rho``, a shape value between 0 and 1:
small is flat, large is close to the sharp corner, about 0.41 is a circle on a
square corner), "curvature" (curvature continuous: no jump in curvature where the
round meets the faces) or "elliptic" (asymmetric only; a quarter ellipse, the same
as circular when both distances are equal on a square corner).

The kernel's fillet only makes circular rounds of one radius across. So a Circular
profile with the Radius or Chord method goes to the kernel (the chord gives each
edge its radius from the angle between its faces). Every other choice is built
here, for straight edges between two flat faces: the cross section (the corner
point, the two points where the round meets the faces and the profile curve) is
extruded along the edge, and the prism is cut from a convex edge or added to a
concave one. Edges that are not straight between flat faces are named in the error.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakeWire,
)
from OCP.BRepClass import BRepClass_FaceClassifier
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.collections import Array1_double, Array1_gp_Pnt
from OCP.Geom import Geom_BezierCurve
from OCP.gp import gp_Pnt, gp_Vec
from OCP.TopAbs import TopAbs_FACE, TopAbs_IN, TopAbs_ON
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureError
from fdcad.core.features.modify import edge_faces
from fdcad.core.features.solids import compound, line_ends
from fdcad.core.naming.names import NamedFace, NamedShape
from fdcad.core.occ import shape_list
from fdcad.core.plane_normal import plane_normal

METHODS = ("radius", "asymmetric", "chord")
PROFILES = ("circular", "conic", "curvature", "elliptic")

Vec3 = tuple[float, float, float]


def method_of(feature: Feature) -> str:
    """The fillet method, "radius" when not set."""
    value = feature.params.get("method", "radius")
    return value if isinstance(value, str) and value in METHODS else "radius"


def profile_of(feature: Feature) -> str:
    """The profile, "circular" when not set."""
    value = feature.params.get("profile", "circular")
    return value if isinstance(value, str) and value in PROFILES else "circular"


def built_here(feature: Feature) -> bool:
    """True when the round is made by this module, not by the kernel's fillet."""
    return method_of(feature) == "asymmetric" or profile_of(feature) != "circular"


def _number(feature: Feature, name: str) -> float | None:
    value = feature.params.get(name)
    return value.value if isinstance(value, Param) else None


@dataclass
class Corner:
    """The cross section frame of one straight edge between two flat faces."""

    start: gp_Pnt
    along: gp_Vec  # the edge, start to end
    u_first: gp_Vec  # unit, in the first face, square to the edge, away from it
    u_second: gp_Vec
    convex: bool
    first_name: str
    second_name: str

    @property
    def angle(self) -> float:
        """The angle between the two faces across the wedge the round fills, radians."""
        return float(self.u_first.Angle(self.u_second))


def _inward(face: TopoDS_Face, middle: gp_Pnt, normal: gp_Vec, along: gp_Vec) -> gp_Vec:
    """Unit vector in ``face``, square to the edge, pointing from the edge into the face."""
    u = normal.Crossed(along)
    u.Normalize()
    step = 1e-4 * max(1.0, along.Magnitude())
    probe = gp_Pnt(middle.XYZ().Added(u.Scaled(step).XYZ()))
    state = BRepClass_FaceClassifier(face, probe, 1e-7).State()
    if state not in (TopAbs_IN, TopAbs_ON):
        u.Reverse()
    return u


def corner_of(body: NamedShape, edge: TopoDS_Edge) -> Corner | None:
    """The frame of ``edge``, or None when it is not straight between two flat faces."""
    ends = line_ends(edge)
    faces = edge_faces(body.shape, edge)
    if ends is None or len(faces) != 2:
        return None
    normals = [plane_normal(f) for f in faces]
    if normals[0] is None or normals[1] is None:
        return None
    a, b = gp_Pnt(*ends[0]), gp_Pnt(*ends[1])
    along = gp_Vec(a, b)
    if along.Magnitude() < 1e-9:
        return None
    middle = gp_Pnt((a.X() + b.X()) / 2, (a.Y() + b.Y()) / 2, (a.Z() + b.Z()) / 2)
    n1, n2 = gp_Vec(*normals[0]), gp_Vec(*normals[1])
    if n1.IsParallel(n2, 1e-6):
        return None
    names = sorted([(body.primary_name(f) or "", k) for k, f in enumerate(faces)])
    order = [k for _n, k in names]
    first, second = faces[order[0]], faces[order[1]]
    nf, ns = (n1, n2) if order[0] == 0 else (n2, n1)
    u1 = _inward(first, middle, nf, along)
    u2 = _inward(second, middle, ns, along)
    convex = nf.Dot(u2) < 0
    return Corner(a, along, u1, u2, convex, names[0][0], names[1][0])


def chord_radius(corner_angle: float, chord: float) -> float:
    """The circular radius whose round has chord ``chord`` across a wedge of ``corner_angle``."""
    return chord / (2 * math.cos(corner_angle / 2))


def edge_angle(body: NamedShape, edge: TopoDS_Edge) -> float | None:
    """The wedge angle at the middle of any edge between two faces, radians (for Chord)."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepGProp import BRepGProp_Face
    from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf

    faces = edge_faces(body.shape, edge)
    if len(faces) != 2:
        return None
    curve = BRepAdaptor_Curve(edge)
    u = (curve.FirstParameter() + curve.LastParameter()) / 2
    p, t = gp_Pnt(), gp_Vec()
    curve.D1(u, p, t)
    if t.Magnitude() < 1e-12:
        return None
    vectors: list[gp_Vec] = []
    for face in faces:
        surface = BRep_Tool.Surface_s(face)
        project = GeomAPI_ProjectPointOnSurf(p, surface)
        if project.NbPoints() == 0:
            return None
        su, sv = project.LowerDistanceParameters()
        normal, point = gp_Vec(), gp_Pnt()
        BRepGProp_Face(face).Normal(su, sv, point, normal)
        if normal.Magnitude() < 1e-12:
            return None
        vectors.append(_inward(face, p, normal.Normalized(), t))
    return float(vectors[0].Angle(vectors[1]))


def _bezier(points: list[gp_Pnt], weights: list[float] | None = None) -> Geom_BezierCurve:
    poles = Array1_gp_Pnt(1, len(points))
    for i, p in enumerate(points, start=1):
        poles.SetValue(i, p)
    if weights is None:
        return Geom_BezierCurve(poles)
    array = Array1_double(1, len(weights))
    for i, w in enumerate(weights, start=1):
        array.SetValue(i, w)
    return Geom_BezierCurve(poles, array)


def profile_curve(
    profile: str, corner: gp_Pnt, p0: gp_Pnt, p2: gp_Pnt, wedge: float, rho: float
) -> Geom_BezierCurve:
    """The cross section curve from ``p0`` to ``p2``, tangent to the faces at both."""
    if profile == "curvature":
        k = 0.5
        q1 = gp_Pnt(p0.XYZ().Added(gp_Vec(p0, corner).Scaled(k).XYZ()))
        q3 = gp_Pnt(p2.XYZ().Added(gp_Vec(p2, corner).Scaled(k).XYZ()))
        return _bezier([p0, q1, corner, q3, p2])
    # Circular and elliptic: the conic through the tangent points of a circle.
    weight = rho / (1 - rho) if profile == "conic" else math.sin(wedge / 2)
    return _bezier([p0, corner, p2], [1.0, weight, 1.0])


@dataclass
class Sizes:
    """What the profile needs: method, profile, the two distances or the chord, rho."""

    method: str
    profile: str
    first: float
    second: float
    rho: float
    reverse: bool


def sizes(feature: Feature, radius: float) -> Sizes:
    """Read the profile sizes, with errors that say what to type."""
    method, profile = method_of(feature), profile_of(feature)
    if profile == "elliptic" and method != "asymmetric":
        raise FeatureError(
            f"{feature.name}: the Elliptic profile is for the Asymmetric method. "
            "Choose Asymmetric, or another profile."
        )
    second = radius
    if method == "asymmetric":
        value = _number(feature, "distance2")
        if value is None or value <= 0:
            raise FeatureError(
                f"{feature.name}: the second distance is missing or not above zero. "
                "Enter a second distance."
            )
        second = value
    rho = 0.5
    if profile == "conic":
        value = _number(feature, "rho")
        if value is None or not 0.05 <= value <= 0.95:
            raise FeatureError(
                f"{feature.name}: the conic shape value must be between 0.05 and 0.95. "
                "Enter a value in that range."
            )
        rho = value
    return Sizes(method, profile, radius, second, rho, feature.params.get("reverse") is True)


def section(corner: Corner, size: Sizes) -> tuple[gp_Pnt, gp_Pnt, float, float]:
    """The two tangent points at the start of the edge and the distances along each face."""
    wedge = corner.angle
    if size.method == "asymmetric":
        d1, d2 = (size.second, size.first) if size.reverse else (size.first, size.second)
    elif size.method == "chord":
        d1 = d2 = size.first / (2 * math.sin(wedge / 2))
    else:  # radius: where a circle of that radius would meet the faces
        d1 = d2 = size.first / math.tan(wedge / 2)
    p0 = gp_Pnt(corner.start.XYZ().Added(corner.u_first.Scaled(d1).XYZ()))
    p2 = gp_Pnt(corner.start.XYZ().Added(corner.u_second.Scaled(d2).XYZ()))
    return p0, p2, d1, d2


def prism(corner: Corner, size: Sizes, role: str) -> tuple[TopoDS_Shape, list[NamedFace]]:
    """The solid between the sharp corner and the round, along the whole edge."""
    p0, p2, _d1, _d2 = section(corner, size)
    curve = profile_curve(size.profile, corner.start, p0, p2, corner.angle, size.rho)
    wire = BRepBuilderAPI_MakeWire()
    round_edge = BRepBuilderAPI_MakeEdge(curve).Edge()
    wire.Add(BRepBuilderAPI_MakeEdge(corner.start, p0).Edge())
    wire.Add(round_edge)
    wire.Add(BRepBuilderAPI_MakeEdge(p2, corner.start).Edge())
    face = BRepBuilderAPI_MakeFace(wire.Wire(), True).Face()
    from OCP.GeomAbs import GeomAbs_Line

    from fdcad.core.features.modify import edges_of

    # The wire may copy its edges, so find the curved one in the face itself.
    round_edge = next(e for e in edges_of(face) if BRepAdaptor_Curve(e).GetType() != GeomAbs_Line)
    maker = BRepPrimAPI_MakePrism(face, corner.along)
    shape = maker.Shape()
    named: list[NamedFace] = []
    for made in shape_list(maker.Generated(round_edge)):
        if made.ShapeType() == TopAbs_FACE:
            named.append((role, TopoDS.Face(made)))
    return shape, named


def profile_round(
    feature: Feature,
    body: NamedShape,
    items: list[tuple[str, TopoDS_Edge, int]],
    radius: float,
) -> NamedShape:
    """Round every item with the chosen method and profile (see the module docstring)."""
    from fdcad.core.features.solids import combine

    size = sizes(feature, radius)
    corners: list[tuple[str, Corner]] = []
    bad: list[str] = []
    for position, (name, edge, index) in enumerate(items, start=1):
        corner = corner_of(body, edge)
        if corner is None:
            bad.append(f"edge {index}" if index else f"edge {position}")
        else:
            corners.append((name, corner))
    if bad:
        raise FeatureError(
            f"{feature.name}: {', '.join(bad)} cannot take this profile: the "
            f"{_label(size)} is made only on straight edges between two flat faces. "
            "Remove these edges, or use the Circular profile with the Radius method.",
            highlight=[n for n, _e, _i in items if corner_of(body, _e) is None],
        )
    cut: list[TopoDS_Shape] = []
    add: list[TopoDS_Shape] = []
    cut_names: list[NamedFace] = []
    add_names: list[NamedFace] = []
    for name, corner in corners:
        _p0, _p2, d1, d2 = section(corner, size)
        if max(d1, d2) <= 0 or not math.isfinite(d1 + d2):
            raise FeatureError(
                f"{feature.name}: the round on edge {name} has no size. Enter a larger value."
            )
        shape, named = prism(corner, size, f"{feature.id}/fillet/{name}")
        (cut if corner.convex else add).append(shape)
        (cut_names if corner.convex else add_names).extend(named)
    current = body
    try:
        if cut:
            current = combine(
                feature.id, feature.name, current, NamedShape(compound(cut), cut_names), "cut"
            )
        if add:
            current = combine(
                feature.id, feature.name, current, NamedShape(compound(add), add_names), "boss"
            )
    except FeatureError:
        raise
    except Exception as exc:  # kernel failure
        raise FeatureError(
            f"{feature.name}: the {_label(size)} could not be made. "
            "Reduce the sizes, or round fewer edges."
        ) from exc
    return current


def _label(size: Sizes) -> str:
    if size.method == "asymmetric":
        return f"asymmetric {size.profile} round"
    return f"{size.profile} round"


__all__ = [
    "METHODS",
    "PROFILES",
    "built_here",
    "chord_radius",
    "corner_of",
    "edge_angle",
    "method_of",
    "profile_of",
    "profile_round",
]
