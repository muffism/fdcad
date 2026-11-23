"""Shared helpers for reference geometry features (PHASE2_SPEC P2.10, D251).

A reference feature reads up to three picks from ``refs`` (``first``, ``second``,
``third``). A pick is a face, edge or vertex reference (FDEF_SPEC 7), a feature
(``{"feature": "f2"}``: a plane, axis, point, coordinate system or the origin) or a
sketch point or line (``{"feature": "f5", "sketch_entity": "e3"}``). Each pick
resolves to a :class:`Geo`, plain geometry the methods combine.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepGProp import BRepGProp
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Line, GeomAbs_Plane
from OCP.GProp import GProp_GProps
from OCP.TopoDS import TopoDS_Edge, TopoDS_Face

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import BuildContext, Datum, FeatureError, Issue
from fdcad.core.plane_normal import plane_normal
from fdcad.core.sketch.model import Arc, Circle, Line, Point
from fdcad.core.sketch.profiles import SketchPlane

Vec3 = tuple[float, float, float]
#: Feature types that make a plane a sketch can sit on.
PLANE_TYPES = frozenset({"plane", "ref_plane"})
#: Every reference geometry feature type, built in planes included.
REFERENCE_TYPES = frozenset({"plane", "ref_plane", "ref_axis", "ref_point", "coord_system"})
PICKS = ("first", "second", "third")
_TOL = 1e-9


# Vector maths ---------------------------------------------------------------------------


def add(a: Vec3, b: Vec3) -> Vec3:
    """a + b."""
    return a[0] + b[0], a[1] + b[1], a[2] + b[2]


def sub(a: Vec3, b: Vec3) -> Vec3:
    """a - b."""
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def scale(a: Vec3, k: float) -> Vec3:
    """a times k."""
    return a[0] * k, a[1] * k, a[2] * k


def dot(a: Vec3, b: Vec3) -> float:
    """Dot product."""
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vec3, b: Vec3) -> Vec3:
    """Cross product."""
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def norm(a: Vec3) -> float:
    """Length."""
    return math.sqrt(dot(a, a))


def unit(a: Vec3) -> Vec3 | None:
    """``a`` scaled to length 1, or None when it has no length."""
    n = norm(a)
    return None if n < _TOL else scale(a, 1.0 / n)


def rotate(v: Vec3, axis: Vec3, angle: float) -> Vec3:
    """``v`` turned by ``angle`` radians about the unit vector ``axis`` (Rodrigues)."""
    c, s = math.cos(angle), math.sin(angle)
    return add(add(scale(v, c), scale(cross(axis, v), s)), scale(axis, dot(axis, v) * (1 - c)))


def x_hint(normal: Vec3) -> Vec3:
    """A sketch X axis for a plane: model X projected onto it, or -Z when square to X (D74)."""
    axis = (1.0, 0.0, 0.0) if abs(normal[0]) < 0.999 else (0.0, 0.0, -1.0)
    x = unit(sub(axis, scale(normal, dot(axis, normal))))
    assert x is not None
    return x


def plane_at(origin: Vec3, normal: Vec3, x_dir: Vec3 | None = None) -> SketchPlane:
    """A sketch plane; ``x_dir`` is made square to the normal, or chosen as D74 does."""
    n = unit(normal)
    if n is None:
        raise FeatureError("The plane has no direction. Pick other references.")
    x = None
    if x_dir is not None:
        x = unit(sub(x_dir, scale(n, dot(x_dir, n))))
    return SketchPlane(origin, n, x if x is not None else x_hint(n))


# Picks ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Geo:
    """A resolved pick.

    ``kind``: ``point``, ``line`` (an axis or straight edge: ``point`` and unit
    ``direction``), ``plane`` (``point``, unit ``direction`` as normal, ``x_dir``),
    ``circle`` (a round edge: centre ``point``, axis ``direction``, ``radius``),
    ``cylinder`` (a cylinder or cone face: axis ``point`` and ``direction``),
    ``curve`` (any other edge) or ``face`` (any other face, ``point`` its centre).
    """

    kind: str
    point: Vec3
    direction: Vec3 | None = None
    x_dir: Vec3 | None = None
    radius: float = 0.0
    edge: TopoDS_Edge | None = None
    face: TopoDS_Face | None = None
    length: float = 0.0
    #: The sketch normal of a sketch point (plane Project along the normal, D526).
    normal: Vec3 | None = None


def _pnt(p: Any) -> Vec3:
    return p.X(), p.Y(), p.Z()


def edge_geo(edge: TopoDS_Edge) -> Geo:
    """A straight edge as a line, a round edge as a circle, else a curve."""
    curve = BRepAdaptor_Curve(edge)
    props = GProp_GProps()
    BRepGProp.LinearProperties_s(edge, props)
    length = props.Mass()
    kind = curve.GetType()
    if kind == GeomAbs_Line:
        a, b = _pnt(curve.Value(curve.FirstParameter())), _pnt(curve.Value(curve.LastParameter()))
        d = unit(sub(b, a))
        if d is not None:
            return Geo("line", a, d, edge=edge, length=length)
    if kind == GeomAbs_Circle:
        circ = curve.Circle()
        return Geo(
            "circle",
            _pnt(circ.Location()),
            _pnt(circ.Axis().Direction()),
            radius=circ.Radius(),
            edge=edge,
            length=length,
        )
    return Geo("curve", _pnt(curve.Value(curve.FirstParameter())), edge=edge, length=length)


def face_geo(face: TopoDS_Face) -> Geo:
    """A flat face as a plane (normal pointing out of the part), a round face as a cylinder."""
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    centre = _pnt(props.CentreOfMass())
    surface = BRepAdaptor_Surface(face)
    kind = surface.GetType()
    normal = plane_normal(face) if kind == GeomAbs_Plane else None
    if normal is not None:
        return Geo("plane", centre, normal, x_hint(normal), face=face)
    if kind in (GeomAbs_Cylinder, GeomAbs_Cone):
        axis = (surface.Cylinder() if kind == GeomAbs_Cylinder else surface.Cone()).Axis()
        return Geo("cylinder", _pnt(axis.Location()), _pnt(axis.Direction()), face=face)
    return Geo("face", centre, face=face)


def datum_geo(datum: Datum) -> Geo:
    """Reference geometry of an earlier feature as a pick."""
    if datum.kind == "plane" and datum.direction is not None:
        return Geo("plane", datum.origin, datum.direction, datum.x_dir)
    if datum.kind == "axis" and datum.direction is not None:
        return Geo("line", datum.origin, datum.direction, length=datum.size)
    return Geo("point", datum.origin)


def resolve_pick(ref: Any, ctx: BuildContext, owner: str) -> tuple[Geo, list[Issue]]:
    """Resolve one pick of ``refs`` (see the module docstring)."""
    from fdcad.core.naming.resolve import resolve_edge, resolve_face, resolve_vertex

    if not isinstance(ref, dict):
        raise FeatureError(f"{owner}: a reference is missing. Pick it again.")
    if "feature" in ref:
        fid = str(ref["feature"])
        if "sketch_entity" in ref:
            return _sketch_geo(fid, str(ref["sketch_entity"]), ctx, owner), []
        try:
            ftype = ctx.document.feature(fid).type
        except KeyError as exc:
            raise FeatureError(f"{owner}: the referenced feature is gone. Pick it again.") from exc
        if ftype == "origin":
            moved = ctx.results.get(fid)
            if moved is not None and moved.datum is not None:  # a moved origin (D2419)
                return Geo("point", moved.datum.origin), []
            return Geo("point", (0.0, 0.0, 0.0)), []
        result = ctx.result(fid)
        if result.datum is not None:
            return datum_geo(result.datum), []
        if result.plane is not None:
            p = result.plane
            return Geo("plane", p.origin, p.normal, p.x_dir), []
        raise FeatureError(
            f"{owner}: the referenced feature is not reference geometry. "
            "Pick a plane, axis or point."
        )
    kind = ref.get("kind")
    if kind == "face":
        face, issues = resolve_face(ctx.body, ref, owner)
        return face_geo(face), issues
    if kind == "edge":
        edge, issues = resolve_edge(ctx.body, ref, owner)
        return edge_geo(edge), issues
    if kind == "vertex":
        point, issues = resolve_vertex(ctx.body, ref, owner)
        return Geo("point", point), issues
    raise FeatureError(f"{owner}: a reference is damaged. Pick it again.")


def _sketch_geo(fid: str, eid: str, ctx: BuildContext, owner: str) -> Geo:
    out = ctx.result(fid).sketch
    if out is None:
        raise FeatureError(f"{owner}: the referenced feature is not a sketch. Pick it again.")
    ent = out.model.entities.get(eid)
    plane = out.plane
    if isinstance(ent, Point):
        return Geo("point", _pnt(plane.to_3d(ent.x, ent.y)), normal=plane.normal)
    if isinstance(ent, Line):
        a = _pnt(plane.to_3d(*out.model.xy(ent.p1)))
        b = _pnt(plane.to_3d(*out.model.xy(ent.p2)))
        d = unit(sub(b, a))
        if d is not None:
            return Geo("line", a, d, length=norm(sub(b, a)))
    if isinstance(ent, Arc | Circle):
        # A round sketch curve gives its axis: through the centre, square to the sketch
        # (audit B item 3, D718).
        centre = _pnt(plane.to_3d(*out.model.xy(ent.center)))
        return Geo("line", centre, plane.normal, length=2 * out.model.radius(ent.id))
    raise FeatureError(
        f"{owner}: the sketch item {eid} is gone or is not a point, line, arc or circle. "
        "Pick it again."
    )


def picks(feature: Feature, ctx: BuildContext, count: int) -> tuple[list[Geo], list[Issue]]:
    """The first ``count`` picks; a missing one is an error naming which (P2.10)."""
    geos: list[Geo] = []
    issues: list[Issue] = []
    for i, key in enumerate(PICKS[:count]):
        ref = feature.refs.get(key)
        if ref is None:
            raise FeatureError(
                f"{feature.name}: reference {i + 1} is missing. Pick it to finish the feature."
            )
        geo, more = resolve_pick(ref, ctx, feature.name)
        geos.append(geo)
        issues += more
    return geos, issues


def length_param(feature: Feature, name: str, default: float = 0.0) -> float:
    """A length or angle value, or ``default`` when the parameter is absent."""
    value = feature.params.get(name)
    return value.value if isinstance(value, Param) else default


def need(geo: Geo, kinds: tuple[str, ...], owner: str, index: int, what: str) -> Geo:
    """Check that pick ``index`` (from 1) is one of ``kinds``, else say what to pick."""
    if geo.kind not in kinds:
        raise FeatureError(f"{owner}: reference {index} must be {what}. Pick it again.")
    return geo


def point_of(geo: Geo) -> Vec3:
    """A pick used as a point: a vertex or point, a circle's centre, a face centre."""
    return geo.point


def direction_of(geo: Geo, owner: str, index: int) -> Vec3:
    """A pick used as a direction: along a line, normal of a plane, axis of a circle."""
    if geo.kind in ("line", "plane", "circle", "cylinder") and geo.direction is not None:
        return geo.direction
    raise FeatureError(
        f"{owner}: reference {index} gives no direction. Pick a straight edge, an axis, "
        "a plane or a flat face."
    )


def line_plane_hit(p: Vec3, d: Vec3, origin: Vec3, normal: Vec3) -> Vec3 | None:
    """Where the line through ``p`` along ``d`` meets the plane, or None when parallel."""
    den = dot(d, normal)
    if abs(den) < 1e-12:
        return None
    t = dot(sub(origin, p), normal) / den
    return add(p, scale(d, t))


def closest_between_lines(p1: Vec3, d1: Vec3, p2: Vec3, d2: Vec3) -> tuple[Vec3, float] | None:
    """The middle of the shortest link between two lines and its length, None when parallel."""
    w = sub(p1, p2)
    b = dot(d1, d2)
    den = 1 - b * b
    if den < 1e-12:
        return None
    d, e = dot(d1, w), dot(d2, w)
    s = (b * e - d) / den
    t = (e - b * d) / den
    a = add(p1, scale(d1, s))
    c = add(p2, scale(d2, t))
    return scale(add(a, c), 0.5), norm(sub(a, c))


def datum_shape(datum: Datum, half: float) -> Any:
    """Edges that draw reference geometry: an axis line, a point cross, frame axes.

    ``half`` is half the part size (as plane faces use, D75). Planes are drawn as
    plane faces elsewhere, so they give an empty compound here.
    """
    from OCP.BRep import BRep_Builder
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.gp import gp_Pnt
    from OCP.TopoDS import TopoDS_Compound

    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)

    def segment(a: Vec3, b: Vec3) -> None:
        if norm(sub(b, a)) > 1e-9:
            builder.Add(compound, BRepBuilderAPI_MakeEdge(gp_Pnt(*a), gp_Pnt(*b)).Edge())

    o = datum.origin
    if datum.kind == "axis" and datum.direction is not None:
        reach = datum.size / 2 if datum.size > 0 else half
        start = o if datum.size > 0 else sub(o, scale(datum.direction, reach))
        length = datum.size if datum.size > 0 else 2 * half
        segment(start, add(start, scale(datum.direction, length)))
    elif datum.kind == "point":
        r = max(half * 0.03, 0.5)
        for axis in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)):
            segment(sub(o, scale(axis, r)), add(o, scale(axis, r)))
    elif datum.kind == "frame" and datum.direction is not None and datum.x_dir is not None:
        r = max(half * 0.3, 5.0)
        y = cross(datum.direction, datum.x_dir)
        for axis in (datum.x_dir, y, datum.direction):
            segment(o, add(o, scale(axis, r)))
    return compound


def pick_kind(ref: dict[str, Any], types: dict[str, str]) -> str:
    """The kind a stored pick resolves to, without the kernel (to guess the method).

    ``types`` maps feature ids to their types.
    """
    if "feature" in ref:
        if "sketch_entity" in ref:
            return "point"
        ftype = types.get(str(ref["feature"]), "")
        if ftype in PLANE_TYPES:
            return "plane"
        return "line" if ftype == "ref_axis" else "point"
    snapshot = ref.get("snapshot") if isinstance(ref.get("snapshot"), dict) else {}
    assert isinstance(snapshot, dict)
    if ref.get("kind") == "face":
        surface = snapshot.get("surface")
        return {"plane": "plane", "cylinder": "cylinder", "cone": "cylinder"}.get(
            str(surface), "face"
        )
    if ref.get("kind") == "edge":
        return {"line": "line", "circle": "circle"}.get(str(snapshot.get("curve")), "curve")
    return "point"
