"""Reference plane (PHASE2_SPEC P2.10 item 1, PLAN Phase 2, FDEF_SPEC 5.3.20, D251).

Params: ``method`` (``offset``, ``angle``, ``three_points``, ``normal_to_curve``,
``mid_plane``, ``parallel_point``), ``distance`` (offset), ``angle`` (angle),
``flip`` (offset to the other side, the angle the other way, the other halving
plane of a mid plane between faces that are not parallel, TR360, or the other side
of the cylinder for a tangent plane, D2629),
``flip_normal``, ``origin_on_curve`` (normal_to_curve), ``along_normal``
(project: along the sketch point's normal, D526), ``normal_x``, ``normal_y``,
``normal_z`` (screen: the view direction captured when it was made, D526).
Refs: ``first``, ``second``, ``third`` as each method needs.
"""

from __future__ import annotations

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.Extrema import Extrema_ExtPC
from OCP.gp import gp_Pnt, gp_Vec
from OCP.TopoDS import TopoDS_Face

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    Datum,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    register,
)
from fdcad.core.features.datum import (
    Geo,
    Vec3,
    add,
    cross,
    dot,
    length_param,
    need,
    norm,
    picks,
    plane_at,
    rotate,
    scale,
    sub,
    unit,
)
from fdcad.core.sketch.profiles import SketchPlane
from fdcad.core.units import Kind

METHODS = (
    "offset",
    "angle",
    "three_points",
    "normal_to_curve",
    "mid_plane",
    "parallel_point",
    "project",
    "screen",
    "tangent",  # TR74 (D903)
    "line_point",
)
#: How many picks each method needs; normal_to_curve takes an optional second.
PICK_COUNT = {
    "offset": 1,
    "angle": 2,
    "three_points": 3,
    "normal_to_curve": 1,
    "mid_plane": 2,
    "parallel_point": 2,
    "project": 2,
    "screen": 1,
    "tangent": 2,
    "line_point": 2,
}
#: Keys of the stored view direction of a Parallel to screen plane (D526).
SCREEN_KEYS = ("normal_x", "normal_y", "normal_z")
_PLANE = ("plane",)
_PLANE_WHAT = "a plane or a flat face"


def guess_method(kinds: list[str]) -> str | None:
    """The method the picks suggest, from their kinds in order (P2.10: guessed, then changeable)."""
    k = tuple(kinds)
    table = {
        ("plane",): "offset",
        ("line",): "normal_to_curve",
        ("circle",): "normal_to_curve",
        ("curve",): "normal_to_curve",
        ("plane", "line"): "angle",
        ("line", "plane"): "angle",
        ("plane", "plane"): "mid_plane",
        ("plane", "point"): "parallel_point",
        ("point", "plane"): "parallel_point",
        ("line", "point"): "normal_to_curve",
        ("circle", "point"): "normal_to_curve",
        ("curve", "point"): "normal_to_curve",
        ("point", "point", "point"): "three_points",
        ("point", "face"): "project",
        ("face", "point"): "project",
        ("point", "cylinder"): "project",
        ("cylinder", "point"): "project",
        ("cylinder", "plane"): "tangent",
        ("plane", "cylinder"): "tangent",
    }
    return table.get(k)


def _tangent_at(geo: Geo, near: Vec3 | None) -> tuple[Vec3, Vec3]:
    """Point and unit tangent of an edge at the spot nearest ``near`` (or its start)."""
    if geo.edge is None:
        if geo.kind == "line" and geo.direction is not None:
            p = geo.point
            if near is not None:
                p = add(geo.point, scale(geo.direction, dot(sub(near, geo.point), geo.direction)))
            return p, geo.direction
        raise FeatureError("Reference 1 must be an edge, a curve or an axis. Pick it again.")
    curve = BRepAdaptor_Curve(geo.edge)
    t = curve.FirstParameter()
    if near is not None:
        ext = Extrema_ExtPC(gp_Pnt(*near), curve)
        if ext.IsDone() and ext.NbExt() > 0:
            best = min(range(1, ext.NbExt() + 1), key=ext.SquareDistance)
            t = ext.Point(best).Parameter()
    p, v = gp_Pnt(), gp_Vec()
    curve.D1(t, p, v)
    d = unit((v.X(), v.Y(), v.Z()))
    if d is None:
        raise FeatureError("The curve has no direction at that point. Pick another point.")
    return (p.X(), p.Y(), p.Z()), d


def _normal_at(face: TopoDS_Face, u: float, v: float) -> Vec3 | None:
    """Unit normal of ``face`` at (u, v), pointing out of the part."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.TopAbs import TopAbs_REVERSED

    props = BRepLProp_SLProps(BRepAdaptor_Surface(face), u, v, 1, 1e-9)
    if not props.IsNormalDefined():
        return None
    d = props.Normal()
    n = (d.X(), d.Y(), d.Z())
    return scale(n, -1.0) if face.Orientation() == TopAbs_REVERSED else n


def _nearest_on_face(face: TopoDS_Face, point: Vec3, owner: str) -> tuple[Vec3, float, float]:
    """The point of ``face`` nearest ``point`` and its surface parameters."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf

    vertex = BRepBuilderAPI_MakeVertex(gp_Pnt(*point)).Vertex()
    dist = BRepExtrema_DistShapeShape(vertex, face)
    if not dist.IsDone() or dist.NbSolution() == 0:
        raise FeatureError(f"{owner}: the point could not be projected. Pick another face.")
    p = dist.PointOnShape2(1)
    proj = GeomAPI_ProjectPointOnSurf(p, BRep_Tool.Surface_s(face))
    if proj.NbPoints() == 0:
        raise FeatureError(f"{owner}: the point could not be projected. Pick another face.")
    u, v = proj.LowerDistanceParameters()
    return (p.X(), p.Y(), p.Z()), u, v


def _along_to_face(
    face: TopoDS_Face, point: Vec3, direction: Vec3, owner: str
) -> tuple[Vec3, float, float]:
    """Where the line through ``point`` along ``direction`` first meets ``face`` (either way)."""
    from OCP.gp import gp_Dir, gp_Lin
    from OCP.IntCurvesFace import IntCurvesFace_Intersector

    hits = IntCurvesFace_Intersector(face, 1e-7)
    hits.Perform(gp_Lin(gp_Pnt(*point), gp_Dir(*direction)), -1e9, 1e9)
    if not hits.IsDone() or hits.NbPnt() == 0:
        raise FeatureError(
            f"{owner}: the point does not reach the face along the sketch normal. "
            "Turn off Along Sketch Normal or pick another face."
        )
    best = min(range(1, hits.NbPnt() + 1), key=lambda i: abs(hits.WParameter(i)))
    p = hits.Pnt(best)
    return (p.X(), p.Y(), p.Z()), hits.UParameter(best), hits.VParameter(best)


def _project_plane(feature: Feature, geos: list[Geo], owner: str) -> SketchPlane:
    """Through a point projected onto a face, normal to the face there (D526)."""
    points = [g for g in geos if g.kind == "point"]
    faces = [g for g in geos if g.face is not None]
    if not points or not faces:
        raise FeatureError(f"{owner}: pick a point and a face to project it onto.")
    point, face = points[0], faces[0].face
    assert face is not None
    if bool(feature.params.get("along_normal", False)):
        if point.normal is None:
            raise FeatureError(
                f"{owner}: only a sketch point can be projected along the sketch normal. "
                "Pick a sketch point or turn off Along Sketch Normal."
            )
        at, u, v = _along_to_face(face, point.point, point.normal, owner)
    else:
        at, u, v = _nearest_on_face(face, point.point, owner)
    n = _normal_at(face, u, v)
    if n is None:
        raise FeatureError(f"{owner}: the face has no normal at that point. Pick another point.")
    return plane_at(at, n)


def _bisector(one: Geo, two: Geo, flip: bool, owner: str) -> SketchPlane:
    """The plane through the line where two non-parallel planes meet, halving the angle
    between them (TR360, D910). Of the two halving planes, the one that has the picked
    faces on opposite sides is used; ``flip`` takes the other one."""
    assert one.direction is not None and two.direction is not None
    n1, n2 = one.direction, two.direction
    d = cross(n1, n2)
    dd = dot(d, d)
    h1, h2 = dot(n1, one.point), dot(n2, two.point)
    on = scale(add(scale(cross(n2, d), h1), scale(cross(d, n1), h2)), 1.0 / dd)
    sum_n, diff_n = unit(add(n1, n2)), unit(sub(n1, n2))
    if sum_n is None or diff_n is None:
        raise FeatureError(f"{owner}: the two planes cannot be halved. Pick other faces.")

    def splits(m: Vec3) -> bool:
        return dot(sub(one.point, on), m) * dot(sub(two.point, on), m) < 0

    normal = diff_n if splits(diff_n) and not splits(sum_n) else sum_n
    if flip:
        normal = sum_n if normal is diff_n else diff_n
    return plane_at(on, normal, d)


def _tangent_plane(geos: list[Geo], owner: str, flip: bool = False) -> SketchPlane:
    """A plane touching a cylinder or cone face (TR74, D903). A point picks the side the
    plane touches (the side facing the point); a plane picks the tangent plane parallel
    to it (its normal, less any part along the axis). ``flip`` touches the opposite side
    instead (D2629): before, the far side of a plane pick could only be had by picking a
    point there."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder

    rounds = [g for g in geos if g.kind == "cylinder"]
    others = [g for g in geos if g.kind != "cylinder"]
    if not rounds or not others:
        raise FeatureError(f"{owner}: pick a cylinder face and a plane or a point.")
    cyl, other = rounds[0], others[0]
    assert cyl.direction is not None and cyl.face is not None
    surface = BRepAdaptor_Surface(cyl.face)
    if surface.GetType() != GeomAbs_Cylinder:
        raise FeatureError(f"{owner}: a tangent plane needs a cylinder face. Pick a cylinder.")
    r = surface.Cylinder().Radius()
    d = cyl.direction
    if other.kind == "plane":
        assert other.direction is not None
        toward = other.direction
    else:
        toward = sub(other.point, cyl.point)
    w = unit(sub(toward, scale(d, dot(toward, d))))
    if w is None:
        raise FeatureError(
            f"{owner}: that pick runs along the cylinder's axis. Pick a plane or point to one side."
        )
    if flip:
        w = scale(w, -1.0)
    if other.kind != "plane":
        along = dot(sub(other.point, cyl.point), d)
        base = add(cyl.point, scale(d, along))
    else:
        base = cyl.point
    return plane_at(add(base, scale(w, r)), w, d)


def screen_normal(feature: Feature) -> Vec3 | None:
    """The stored view direction of a Parallel to screen plane, or None (D526)."""
    values = []
    for key in SCREEN_KEYS:
        value = feature.params.get(key)
        if isinstance(value, Param):
            value = value.value
        if isinstance(value, bool) or not isinstance(value, int | float):
            return None
        values.append(float(value))
    return unit((values[0], values[1], values[2]))


def make_plane(feature: Feature, geos: list[Geo], owner: str) -> SketchPlane:
    """The plane for ``feature``'s method from resolved picks."""
    method = str(feature.params.get("method", "offset"))
    flip = bool(feature.params.get("flip", False))
    if method == "offset":
        base = need(geos[0], _PLANE, owner, 1, _PLANE_WHAT)
        assert base.direction is not None
        d = length_param(feature, "distance") * (-1.0 if flip else 1.0)
        plane = plane_at(add(base.point, scale(base.direction, d)), base.direction, base.x_dir)
    elif method == "angle":
        planes = [g for g in geos if g.kind == "plane"]
        lines = [g for g in geos if g.kind == "line"]
        if not planes or not lines:
            raise FeatureError(
                f"{owner}: pick a plane or flat face and a straight edge or axis "
                "for an angle plane."
            )
        base, axis = planes[0], lines[0]
        assert base.direction is not None and axis.direction is not None
        if abs(dot(base.direction, axis.direction)) > 1e-6:
            raise FeatureError(
                f"{owner}: the axis must lie in or parallel to the plane. Pick another edge."
            )
        angle = length_param(feature, "angle") * (-1.0 if flip else 1.0)
        normal = rotate(base.direction, axis.direction, angle)
        plane = plane_at(axis.point, normal, axis.direction)
    elif method == "three_points":
        p1, p2, p3 = (g.point for g in geos[:3])
        n = unit(cross(sub(p2, p1), sub(p3, p1)))
        if n is None:
            raise FeatureError(
                f"{owner}: the three points lie on one line. Pick a point off that line."
            )
        plane = plane_at(p1, n, sub(p2, p1))
    elif method == "normal_to_curve":
        near = geos[1].point if len(geos) > 1 else None
        on, tangent = _tangent_at(geos[0], near)
        on_curve = bool(feature.params.get("origin_on_curve", False))
        origin = on if (near is None or on_curve) else near
        plane = plane_at(origin, tangent)
    elif method == "mid_plane":
        one = need(geos[0], _PLANE, owner, 1, _PLANE_WHAT)
        two = need(geos[1], _PLANE, owner, 2, _PLANE_WHAT)
        assert one.direction is not None and two.direction is not None
        if norm(cross(one.direction, two.direction)) > 1e-6:
            plane = _bisector(one, two, flip, owner)  # TR360 (D910)
        else:
            gap = dot(sub(two.point, one.point), one.direction)
            plane = plane_at(
                add(one.point, scale(one.direction, gap / 2)), one.direction, one.x_dir
            )
    elif method == "parallel_point":
        bases = [g for g in geos if g.kind == "plane"]
        points = [g for g in geos if g.kind != "plane"]
        if not bases or not points:
            raise FeatureError(f"{owner}: pick a plane or flat face and a point.")
        assert bases[0].direction is not None
        plane = plane_at(points[0].point, bases[0].direction, bases[0].x_dir)
    elif method == "project":
        plane = _project_plane(feature, geos, owner)
    elif method == "tangent":
        plane = _tangent_plane(geos, owner, flip)
    elif method == "line_point":
        lines = [g for g in geos if g.kind == "line"]
        points = [g for g in geos if g.kind != "line"]
        if not lines or not points:
            raise FeatureError(f"{owner}: pick a straight edge or axis and a point.")
        axis = lines[0]
        assert axis.direction is not None
        n = unit(cross(axis.direction, sub(points[0].point, axis.point)))
        if n is None:
            raise FeatureError(f"{owner}: the point is on the line. Pick a point off the line.")
        plane = plane_at(axis.point, n, axis.direction)
    elif method == "screen":
        view = screen_normal(feature)
        if view is None:
            raise FeatureError(
                f"{owner}: the view direction is missing. Press Use Current View to take it."
            )
        point = need(geos[0], ("point",), owner, 1, "a vertex, sketch point or reference point")
        plane = plane_at(point.point, view)
    else:
        raise FeatureError(
            f"{owner}: unknown plane method '{method}'. "
            "Choose another method in the property panel."
        )
    if bool(feature.params.get("flip_normal", False)):
        n = plane.normal
        plane = SketchPlane(plane.origin, (-n[0], -n[1], -n[2]), plane.x_dir)
    from fdcad.core.features.extra_placement import apply, has_extra

    if has_extra(feature):  # TR149 (D980): an extra offset in the plane's own axes
        origin, normal, x_dir = apply(feature, plane.origin, plane.normal, plane.x_dir)
        plane = SketchPlane(origin, normal, x_dir)
    return plane


@register
class RefPlane(FeatureType):
    """A reference plane. Passes the part through unchanged."""

    type_name = "ref_plane"
    params = (
        ParamSpec("method", choices=METHODS, default="offset"),
        # Kinds let formulas and variables drive the values (D608).
        ParamSpec("distance", kind=Kind.LENGTH, optional=True),
        ParamSpec("angle", kind=Kind.ANGLE, optional=True),
        # TR149 (D980): the extra offset and turns, as values formulas can drive
        ParamSpec("extra_dx", kind=Kind.LENGTH, optional=True),
        ParamSpec("extra_dy", kind=Kind.LENGTH, optional=True),
        ParamSpec("extra_dz", kind=Kind.LENGTH, optional=True),
        ParamSpec("extra_rx", kind=Kind.ANGLE, optional=True),
        ParamSpec("extra_ry", kind=Kind.ANGLE, optional=True),
        ParamSpec("extra_rz", kind=Kind.ANGLE, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Resolve the picks and place the plane."""
        method = str(feature.params.get("method", "offset"))
        count = PICK_COUNT.get(method, 1)
        if method == "normal_to_curve" and feature.refs.get("second") is not None:
            count = 2
        geos, issues = picks(feature, ctx, count)
        plane = make_plane(feature, geos, feature.name)
        datum = Datum("plane", plane.origin, plane.normal, plane.x_dir)
        return FeatureResult(body=ctx.body, issues=issues, plane=plane, datum=datum)
