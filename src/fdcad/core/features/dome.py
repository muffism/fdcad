"""Dome (PHASE4_SPEC P4.6, DECISIONS D321).

Raises (or with Reverse sinks) flat faces into domes.

Params (FDEF_SPEC 5.3.30):

- ``distance``: length, the dome height at the middle of the face. 0 on a round
  face makes a dome tangent to the side (a half sphere or half ellipsoid).
- ``reverse``: optional boolean, a concave dome cut into the part.
- ``elliptical``: optional boolean, round faces get a half ellipsoid instead of
  a spherical cap.
- ``continuous``: optional boolean, polygon faces get one smooth spherical
  surface; off, the dome rises from each edge.

Refs: ``faces`` (flat faces to dome), optional ``profile_sketch`` (TR147, D2301: a
closed outline that sets the dome's section, see ``dome_profile``; the distance is
then not used) and optional ``direction`` (TR147, D1805: a
straight edge, flat face or plane the dome rises along, turned to leave the face).
See ``dome_direction``.

Face roles: ``dome/<k>/face#j`` for face ``k`` (counted from 1).
"""

from __future__ import annotations

import math

import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakeWire,
)
from OCP.BRepPrimAPI import (
    BRepPrimAPI_MakeCylinder,
    BRepPrimAPI_MakePrism,
    BRepPrimAPI_MakeRevol,
    BRepPrimAPI_MakeSphere,
)
from OCP.GC import GC_MakeArcOfEllipse
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Line
from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Elips, gp_Pnt, gp_Vec
from OCP.TopAbs import TopAbs_EDGE, TopAbs_WIRE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Feature
from fdcad.core.features import fastening as fx
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.modify import require_body, resolve_faces
from fdcad.core.features.sketch import face_plane
from fdcad.core.features.solids import FUZZY_TOLERANCE, check_result, combine, volume_of
from fdcad.core.naming.names import NamedShape, centroid, restrict
from fdcad.core.occ import BRepAlgoAPI_Common
from fdcad.core.units import Kind


def _edges(face: TopoDS_Face) -> list[BRepAdaptor_Curve]:
    out = []
    explorer = TopExp_Explorer(face, TopAbs_EDGE)
    while explorer.More():
        out.append(BRepAdaptor_Curve(TopoDS.Edge(explorer.Current())))
        explorer.Next()
    return out


#: Points taken along each edge of an outline to test whether it is a circle (D2621).
_ROUND_SAMPLES = 64
#: How far a point of such an outline may be from the fitted circle, as a share of
#: its radius. The spline circles that lofts and scaled sweeps leave are within 1e-7.
_ROUND_TOLERANCE = 1e-4


def _wire_count(face: TopoDS_Face) -> int:
    explorer = TopExp_Explorer(face, TopAbs_WIRE)
    count = 0
    while explorer.More():
        count += 1
        explorer.Next()
    return count


def fitted_circle(curves: list[BRepAdaptor_Curve]) -> tuple[fx.Vec3, float] | None:
    """Centre and radius when the points along ``curves`` lie on one circle, else None.

    Edges of any kind count (D2621): the round end of a loft or a scaled sweep is a
    spline that is a circle in shape. The points must lie in one plane and at one
    distance from a centre, within ``_ROUND_TOLERANCE`` of the radius.
    """
    if not curves or any(c.GetType() == GeomAbs_Line for c in curves):
        return None
    rows = []
    for curve in curves:
        for u in np.linspace(curve.FirstParameter(), curve.LastParameter(), _ROUND_SAMPLES):
            p = curve.Value(float(u))
            rows.append((p.X(), p.Y(), p.Z()))
    points = np.array(rows, dtype=float)
    mean = points.mean(axis=0)
    rel = points - mean
    _s, _v, axes = np.linalg.svd(rel, full_matrices=False)
    u_dir, v_dir, normal = axes
    x, y = rel @ u_dir, rel @ v_dir
    # x^2 + y^2 = 2 a x + 2 b y + c for a circle of centre (a, b).
    rhs = x * x + y * y
    solved = np.linalg.lstsq(np.column_stack([2 * x, 2 * y, np.ones_like(x)]), rhs, rcond=None)
    a, b, c = (float(t) for t in solved[0])
    squared = c + a * a + b * b
    if squared <= 0:
        return None
    radius = math.sqrt(squared)
    slack = _ROUND_TOLERANCE * radius
    flat = float(np.abs(rel @ normal).max())
    off = float(np.abs(np.hypot(x - a, y - b) - radius).max())
    if flat > slack or off > slack:
        return None
    centre = mean + a * u_dir + b * v_dir
    return (float(centre[0]), float(centre[1]), float(centre[2])), radius


def round_face(face: TopoDS_Face) -> tuple[fx.Vec3, float] | None:
    """Centre and radius when the face is a full disc, else None.

    The outline is tested by its shape, not its kind (D2621): a spline or several
    arcs that make one circle count as round.
    """
    curves = _edges(face)
    if len(curves) == 1 and curves[0].GetType() == GeomAbs_Circle:
        circle = curves[0].Circle()
        c = circle.Location()
        return (c.X(), c.Y(), c.Z()), circle.Radius()
    if _wire_count(face) != 1:
        return None
    return fitted_circle(curves)


#: Tolerances the dome's intersection is tried with, in turn (D1053).
_COMMON_TOLERANCES = (FUZZY_TOLERANCE, 10 * FUZZY_TOLERANCE, 0.1 * FUZZY_TOLERANCE, 0.0)


def _common(a: TopoDS_Shape, b: TopoDS_Shape) -> TopoDS_Shape:
    """What ``a`` and ``b`` share.

    The kernel can report success and return nothing for two shapes that plainly
    overlap (D1053): the pushed up end of a swept stay and the dome's sphere gave an
    empty result at this tolerance and the right one at ten times it, and which it was
    changed with the last digits of the sketch. An empty answer is asked again with
    the other tolerances. When every answer is empty the shapes do not overlap (an
    edge dome on a face that is not convex), and the empty shape is returned.
    """
    from fdcad.core.occ import ShapeList

    first: TopoDS_Shape | None = None
    for fuzzy in _COMMON_TOLERANCES:
        op = BRepAlgoAPI_Common()
        args, tools = ShapeList(), ShapeList()
        args.Append(a)
        tools.Append(b)
        op.SetArguments(args)
        op.SetTools(tools)
        if fuzzy > 0:
            op.SetFuzzyValue(fuzzy)
        op.Build()
        if not op.IsDone():
            continue
        shape = op.Shape()
        if first is None:
            first = shape
        if abs(volume_of(shape)) > 1e-9:
            return shape
    if first is None:
        raise FeatureError("the dome could not be shaped. Use a smaller distance.")
    return first


def _half_ellipsoid(centre: fx.Vec3, up: fx.Vec3, radius: float, height: float) -> TopoDS_Shape:
    """A half ellipsoid on a disc: ``radius`` across, ``height`` along ``up``."""
    f = fx.frame(centre, up)
    major, minor = max(radius, height), min(radius, height)
    # The ellipse lies in the plane of up and x; its major axis follows the longer size.
    axis_dir = f.x if radius >= height else f.up
    ax = gp_Ax2(gp_Pnt(*centre), gp_Dir(*fx.cross(f.x, f.up)), gp_Dir(*axis_dir))
    ellipse = gp_Elips(ax, major, minor)
    rim, top = gp_Pnt(*f.at(radius, 0.0, 0.0)), gp_Pnt(*f.at(0.0, 0.0, height))
    arc = GC_MakeArcOfEllipse(ellipse, rim, top, True)
    if not arc.IsDone():
        arc = GC_MakeArcOfEllipse(ellipse, top, rim, True)
    edge = BRepBuilderAPI_MakeEdge(arc.Value()).Edge()
    wire = BRepBuilderAPI_MakeWire(
        BRepBuilderAPI_MakeEdge(gp_Pnt(*centre), rim).Edge(),
        edge,
        BRepBuilderAPI_MakeEdge(top, gp_Pnt(*centre)).Edge(),
    ).Wire()
    face = BRepBuilderAPI_MakeFace(wire, True).Face()
    return BRepPrimAPI_MakeRevol(face, gp_Ax1(gp_Pnt(*centre), gp_Dir(*up)), 2 * math.pi).Shape()


def dome_solid(
    feature: Feature, face: TopoDS_Face, height: float, ctx: BuildContext | None = None
) -> TopoDS_Shape:
    """The dome over one flat face, growing out of it (before Reverse)."""
    plane = face_plane(face)
    if plane is None:
        raise FeatureError(f"{feature.name}: domes are made on flat faces. Pick a flat face.")
    up = plane.normal
    from fdcad.core.features.dome_profile import has_profile, profile_dome

    if has_profile(feature) and ctx is not None:  # TR147 (D2301)
        disc0 = round_face(face)
        return profile_dome(feature, ctx, face, disc0[0] if disc0 else centroid(face), up)
    disc = round_face(face)
    if disc is not None:
        centre, radius = disc
        h = radius if height == 0 else height
        if feature.params.get("elliptical") is True:
            return _half_ellipsoid(centre, up, radius, h)
        return _cap(face, centre, up, radius, h)
    if height <= 0:
        raise FeatureError(
            f"{feature.name}: a distance of 0 only works on a round face. Enter a distance."
        )
    mid = centroid(face)
    if feature.params.get("continuous") is True:
        reach = 0.0
        for curve in _edges(face):
            for u in (curve.FirstParameter(), curve.LastParameter()):
                p = curve.Value(u)
                reach = max(reach, math.dist((p.X(), p.Y(), p.Z()), mid))
        return _cap(face, mid, up, reach, height)
    return _edge_dome(feature, face, mid, up, height)


def _cap(
    face: TopoDS_Face, centre: fx.Vec3, up: fx.Vec3, reach: float, height: float
) -> TopoDS_Shape:
    """The face pushed up, cut by a sphere through the rim ``reach`` from ``centre``."""
    radius = (reach * reach + height * height) / (2 * height)
    middle = fx.add(centre, up, height - radius)
    sphere = BRepPrimAPI_MakeSphere(gp_Pnt(*middle), radius).Shape()
    prism = BRepPrimAPI_MakePrism(face, gp_Vec(*fx.add((0, 0, 0), up, height * 1.01))).Shape()
    return _common(prism, sphere)


def _edge_dome(
    feature: Feature, face: TopoDS_Face, mid: fx.Vec3, up: fx.Vec3, height: float
) -> TopoDS_Shape:
    """A dome that rises from every straight edge: the face pushed up and cut by one
    cylinder per edge, each through its edge and the top over the middle."""
    shape = BRepPrimAPI_MakePrism(face, gp_Vec(*fx.add((0, 0, 0), up, height * 1.01))).Shape()
    for curve in _edges(face):
        if curve.GetType() != GeomAbs_Line:
            raise FeatureError(
                f"{feature.name}: a dome that rises from each edge needs straight edges. "
                "Tick Continuous dome."
            )
        a, b = curve.Value(curve.FirstParameter()), curve.Value(curve.LastParameter())
        pa, pb = (a.X(), a.Y(), a.Z()), (b.X(), b.Y(), b.Z())
        along = fx.unit(fx.sub(pb, pa))
        inward = fx.cross(up, along)
        if fx.dot(fx.sub(mid, pa), inward) < 0:
            inward = fx.neg(inward)
        d = fx.dot(fx.sub(mid, pa), inward)
        radius = (d * d + height * height) / (2 * height)
        length = 4 * (math.dist(pa, pb) + d) + 1.0
        base = fx.add(fx.add(fx.add(pa, inward, d), up, height - radius), along, -length / 2)
        cylinder = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*base), gp_Dir(*along)), radius, length)
        shape = _common(shape, cylinder.Shape())
    return shape


def mirrored(shape: TopoDS_Shape, face: TopoDS_Face) -> TopoDS_Shape:
    """``shape`` mirrored in the plane of ``face`` (a concave dome)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Trsf

    plane = face_plane(face)
    assert plane is not None
    trsf = gp_Trsf()
    trsf.SetMirror(gp_Ax2(gp_Pnt(*plane.origin), gp_Dir(*plane.normal)))
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()


@register
class Dome(FeatureType):
    """Domes on flat faces."""

    type_name = "dome"
    makes_solid = True
    params = (ParamSpec("distance", kind=Kind.LENGTH),)

    def _domes(self, feature: Feature, ctx: BuildContext) -> tuple[list[NamedShape], list[Issue]]:
        picked, issues = resolve_faces(feature, ctx, "faces")
        height = self.number(feature, "distance")
        if height < 0:
            raise FeatureError(f"{feature.name}: the distance cannot be negative. Use Reverse.")
        lean = None
        pick = feature.refs.get("direction")
        if isinstance(pick, list):  # the panel stores a one item list
            pick = pick[0] if pick else None
        if isinstance(pick, dict):  # TR147 (D1805)
            from fdcad.core.features.geometry_refs import resolve_placement

            found = resolve_placement(ctx, pick, feature.name, "direction")
            issues = issues + found.issues
            lean = found.direction
        out = []
        for k, (_name, face) in enumerate(picked, start=1):
            try:
                solid = dome_solid(feature, face, height, ctx)
                if lean is not None:
                    from fdcad.core.features.dome_direction import sheared

                    plane = face_plane(face)
                    assert plane is not None  # dome_solid refuses curved faces
                    solid = sheared(feature.name, solid, plane.origin, plane.normal, lean)
                if feature.params.get("reverse") is True:
                    solid = mirrored(solid, face)
                if abs(volume_of(solid)) < 1e-9:  # edge domes on a face that is not convex
                    raise FeatureError(
                        "the dome cannot rise from every edge of this face. Tick Continuous dome."
                    )
            except FeatureError as exc:
                text = str(exc)
                raise FeatureError(
                    text if text.startswith(feature.name) else f"{feature.name}: {text}"
                ) from exc
            out.append(NamedShape(solid, restrict([], solid, f"{feature.id}/dome/{k}")))
        return out, issues

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Add the domes, or cut them in with Reverse."""
        body = require_body(feature, ctx)
        domes, issues = self._domes(feature, ctx)
        operation = "cut" if feature.params.get("reverse") is True else "boss"
        result = body
        for dome in domes:
            result = combine(feature.id, feature.name, result, dome, operation)
        issues = issues + check_result(feature.id, feature.name, ctx.body, result, None)
        return FeatureResult(body=result, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The domes, for the preview."""
        from fdcad.core.features.solids import compound

        domes, _issues = self._domes(feature, ctx)
        return NamedShape(compound([d.shape for d in domes]), [])
