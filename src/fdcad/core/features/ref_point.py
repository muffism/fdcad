"""Reference point (PHASE2_SPEC P2.10 item 3, FDEF_SPEC 5.3.20, D251).

Params: ``method`` (``arc_centre``, ``face_centre``, ``intersection``,
``projection``, ``along_curve``, ``sketch_point``, ``values``); ``distance`` and
``percent`` (along_curve: a length from the start, or with ``by_percent`` a
percent of the length; ``reverse`` measures from the end); ``x``, ``y``, ``z``
(values). Refs: ``first`` and ``second`` as the method needs. ``centre_of_mass``
(TR80, D1021) needs no picks: the centre of the solids built so far, or the part's
typed centre of mass when Mass Properties has one.
"""

from __future__ import annotations

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.GCPnts import GCPnts_AbscissaPoint
from OCP.gp import gp_Pnt

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
    closest_between_lines,
    dot,
    length_param,
    line_plane_hit,
    picks,
    scale,
    sub,
)
from fdcad.core.units import Kind

METHODS = (
    "arc_centre",
    "face_centre",
    "intersection",
    "projection",
    "along_curve",
    "sketch_point",
    "values",
    "centre_of_mass",  # TR80 (D1021)
)
PICK_COUNT = {
    "arc_centre": 1,
    "face_centre": 1,
    "intersection": 2,
    "projection": 2,
    "along_curve": 1,
    "sketch_point": 1,
    "values": 0,
    "centre_of_mass": 0,
}
#: Lines closer than this cross (mm).
_CROSS_TOL = 1e-6


def guess_method(kinds: list[str]) -> str | None:
    """The method the picks suggest (P2.10 item 3)."""
    k = tuple(kinds)
    if k == ("circle",):
        return "arc_centre"
    if k in (("plane",), ("face",), ("cylinder",)):
        return "face_centre"
    if k in (("line",), ("curve",)):
        return "along_curve"
    if k == ("point",):
        return "sketch_point"
    if len(k) == 2 and "point" in k:
        return "projection"
    if len(k) == 2:
        return "intersection"
    return None


def _along(geo: Geo, feature: Feature, owner: str) -> Vec3:
    if geo.edge is None:
        raise FeatureError(f"{owner}: pick an edge to place the point along.")
    curve = BRepAdaptor_Curve(geo.edge)
    t0, t1 = curve.FirstParameter(), curve.LastParameter()
    total = GCPnts_AbscissaPoint.Length_s(curve)
    if bool(feature.params.get("by_percent", False)):
        dist = total * length_param(feature, "percent", 50.0) / 100.0
    else:
        dist = length_param(feature, "distance")
    if dist < -1e-9:
        # Not "longer than the edge", which it said before (D2644).
        what = "percentage" if bool(feature.params.get("by_percent", False)) else "distance"
        raise FeatureError(
            f"{owner}: the {what} is less than 0. Enter 0 or more, or turn on Reverse direction "
            "to measure from the other end."
        )
    if dist > total + 1e-9:
        raise FeatureError(
            f"{owner}: the distance is longer than the edge ({total:.3f} mm). "
            "Enter a smaller value."
        )
    reverse = bool(feature.params.get("reverse", False))
    start = t1 if reverse else t0
    step = -dist if reverse else dist
    finder = GCPnts_AbscissaPoint(curve, step, start)
    if not finder.IsDone():
        raise FeatureError(
            f"{owner}: the point could not be placed along the edge. "
            "Change the distance or pick another edge."
        )
    p = curve.Value(finder.Parameter())
    return p.X(), p.Y(), p.Z()


#: How far an endless line (an axis) is followed to find where it meets a face, mm.
_LINE_REACH = 1.0e5


def _crossings(a: Geo, b: Geo) -> list[Vec3]:
    """Every point where the two items meet, ordered along the first line or edge
    (TR353, D984). An axis or other endless line is followed both ways."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.gp import gp_Dir, gp_Lin

    def shape_of(g: Geo) -> object:
        if g.edge is not None or g.face is not None:
            return g.edge or g.face
        if g.kind == "line" and g.direction is not None:
            line = gp_Lin(gp_Pnt(*g.point), gp_Dir(*g.direction))
            return BRepBuilderAPI_MakeEdge(line, -_LINE_REACH, _LINE_REACH).Edge()
        return None

    shapes = [shape_of(g) for g in (a, b)]
    if any(s is None for s in shapes):
        return []
    dist = BRepExtrema_DistShapeShape(shapes[0], shapes[1])
    if not dist.IsDone() or dist.NbSolution() == 0 or dist.Value() > _CROSS_TOL:
        return []
    found: list[Vec3] = []
    for k in range(1, dist.NbSolution() + 1):
        p = dist.PointOnShape1(k)
        point = (p.X(), p.Y(), p.Z())
        if all(sum((point[i] - q[i]) ** 2 for i in range(3)) > 1e-12 for q in found):
            found.append(point)
    line = a if a.kind == "line" else b
    if line.direction is not None:
        d, o = line.direction, line.point
        found.sort(key=lambda q: sum((q[i] - o[i]) * d[i] for i in range(3)))
    return found


def _intersection(a: Geo, b: Geo, owner: str, crossing: int = 1) -> Vec3:
    lines = [g for g in (a, b) if g.kind == "line"]
    planes = [g for g in (a, b) if g.kind == "plane"]
    if len(lines) == 2:
        assert lines[0].direction is not None and lines[1].direction is not None
        found = closest_between_lines(
            lines[0].point, lines[0].direction, lines[1].point, lines[1].direction
        )
        if found is None or found[1] > _CROSS_TOL:
            raise FeatureError(f"{owner}: the two lines do not cross. Pick lines that meet.")
        return found[0]
    if lines and planes:
        line, plane = lines[0], planes[0]
        assert line.direction is not None and plane.direction is not None
        hit = line_plane_hit(line.point, line.direction, plane.point, plane.direction)
        if hit is None:
            raise FeatureError(f"{owner}: the line is parallel to the plane. Pick another pair.")
        return hit
    crossings = _crossings(a, b)
    if crossings:
        if crossing > len(crossings):
            raise FeatureError(
                f"{owner}: the references cross {len(crossings)} times, so there is no crossing "
                f"{crossing}. Enter a crossing number from 1 to {len(crossings)}."
            )
        return crossings[crossing - 1]
    raise FeatureError(f"{owner}: the two references do not meet. Pick items that cross.")


def _projection(a: Geo, b: Geo, owner: str) -> Vec3:
    point = a if a.kind == "point" else b
    target = b if point is a else a
    if point.kind != "point":
        raise FeatureError(f"{owner}: pick a point and a plane or face to project it onto.")
    if target.kind == "plane" and target.direction is not None:
        n = target.direction
        return sub(point.point, scale(n, dot(sub(point.point, target.point), n)))
    shape = target.face or target.edge
    if shape is None:
        raise FeatureError(f"{owner}: pick a plane, a face or an edge to project onto.")
    vertex = BRepBuilderAPI_MakeVertex(gp_Pnt(*point.point)).Vertex()
    dist = BRepExtrema_DistShapeShape(vertex, shape)
    if not dist.IsDone() or dist.NbSolution() == 0:
        raise FeatureError(f"{owner}: the point could not be projected. Pick another face.")
    p = dist.PointOnShape2(1)
    return p.X(), p.Y(), p.Z()


def make_point(feature: Feature, geos: list[Geo], owner: str) -> Vec3:
    """The point for ``feature``'s method from resolved picks."""
    method = str(feature.params.get("method", "values"))
    if method == "values":
        return (
            length_param(feature, "x"),
            length_param(feature, "y"),
            length_param(feature, "z"),
        )
    if method == "arc_centre":
        if geos[0].kind != "circle":
            raise FeatureError(f"{owner}: pick a round edge, arc or circle.")
        return geos[0].point
    if method == "face_centre":
        if geos[0].face is None:
            raise FeatureError(f"{owner}: pick a face.")
        return geos[0].point if geos[0].kind != "cylinder" else _face_centre(geos[0])
    if method == "sketch_point":
        if geos[0].kind != "point":
            raise FeatureError(f"{owner}: pick a vertex or sketch point.")
        return geos[0].point
    if method == "intersection":
        crossing = feature.params.get("crossing")  # TR353: which crossing, from 1
        index = round(crossing.value) if isinstance(crossing, Param) else 1
        return _intersection(geos[0], geos[1], owner, max(index, 1))
    if method == "projection":
        return _projection(geos[0], geos[1], owner)
    if method == "along_curve":
        return _along(geos[0], feature, owner)
    raise FeatureError(
        f"{owner}: unknown point method '{method}'. Choose another method in the property panel."
    )


def centre_of_mass(ctx: BuildContext, owner: str) -> Vec3:
    """The centre of mass of the solids built so far (uniform density), or the part's
    typed centre (TR80, D1021). It moves with the model on every rebuild."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    from fdcad.core.features.solids import solids
    from fdcad.core.mass import part_override

    override = part_override(ctx.document)
    if override is not None and override.centre is not None:
        return override.centre
    bodies = solids(ctx.body.shape) if ctx.body is not None else []
    if not bodies:
        raise FeatureError(
            f"{owner}: there is no solid above this point to find the centre of. "
            "Move the point below a feature that makes a body."
        )
    total = GProp_GProps()
    for body in bodies:
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(body, props)
        total.Add(props)
    c = total.CentreOfMass()
    return c.X(), c.Y(), c.Z()


def _face_centre(geo: Geo) -> Vec3:
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    props = GProp_GProps()
    assert geo.face is not None
    BRepGProp.SurfaceProperties_s(geo.face, props)
    c = props.CentreOfMass()
    return c.X(), c.Y(), c.Z()


@register
class RefPoint(FeatureType):
    """A reference point. Passes the part through unchanged."""

    type_name = "ref_point"
    params = (
        ParamSpec("method", choices=METHODS, default="values"),
        # Kinds let formulas and variables drive the values (D608).
        *(ParamSpec(n, kind=Kind.LENGTH, optional=True) for n in ("x", "y", "z", "distance")),
        ParamSpec("percent", kind=Kind.NUMBER, optional=True),
        ParamSpec("crossing", kind=Kind.NUMBER, optional=True),  # TR353 (D984)
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Resolve the picks and place the point."""
        method = str(feature.params.get("method", "values"))
        geos, issues = picks(feature, ctx, PICK_COUNT.get(method, 0))
        if method == "centre_of_mass":
            point = centre_of_mass(ctx, feature.name)
        else:
            point = make_point(feature, geos, feature.name)
        return FeatureResult(body=ctx.body, issues=issues, datum=Datum("point", point))
