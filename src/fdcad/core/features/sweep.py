"""Sweep, boss or cut: move a profile along a path (PHASE2_SPEC P2.2, DECISIONS D219).

Params:

- ``operation``: "boss" or "cut". ``merge``: optional boolean (bosses).
- ``profile_type``: "sketch" (default), "circular" with ``diameter`` (a round rod)
  or "face" (TR138, D1516: a flat model face, ``refs.profile_face``, holes included)
  or "body" (TR138 item 3, D2405: cuts only, ``refs.tool_body`` moved along the path).
- ``orientation``: "follow_path" (default), "keep_normal" (the section stays
  parallel to the start section) or "curvature" (TR56, D1504: the section turns with
  the path's curvature, its Frenet frame, as for a helix; no twist), "face" (TR396,
  D1514: the section's up direction keeps to the normal of ``refs.orient_face``, the
  face under the path) or "second_path" (TR396, D1514: the section's X axis points at
  ``refs.x_path``, a sketch or curve beside the path). Neither twists.
- ``twist``: "none" (default), "minimum", "angle" (``twist_angle``) or
  "direction" (the section's up direction follows ``refs.twist_direction``) or
  "turns" (TR56, D1504: ``twist_turns`` whole or part turns, the angle times 360
  degrees). On a closed path an angle or turns twist must be whole turns.
- ``corners`` (TR137, D1515): optional, how the section passes a sharp corner of
  the path: "smooth" (default, the kernel turns the section), "mitre" (the two
  sweeps meet in a sharp edge on the corner's bisector) or "round" (a rounded
  corner about the path's corner point).
- ``start_tangency`` (TR56, D1905): optional, "none" (default: the section is the
  profile as drawn, even where the path leaves its plane at a slant) or
  "path_tangent" (the section is turned square to the path's start).
- ``sweep_direction`` (TR137, D1906): optional, for a profile part way along the
  path (the path crosses its plane): "forward" (default, along the path), "backward"
  or "both"; ``twist_angle2`` or ``twist_turns2`` twist the backward side on its own.
- ``merge_faces`` (TR56, D1905): optional boolean: a smooth path of several pieces is
  swept as one spline, so each profile edge makes one side face.
- Thin Feature (bosses): the ``thin_*`` keys of the extrude (``extrude_thin``).

Refs: ``profile`` (a sketch, ``{"feature": "f5"}``) unless circular; ``path``: a
sketch whose curves form one chain, or ``path_edges``: a chain of edge
references; ``twist_direction``: a plane feature, a flat face or a straight edge;
``guides`` (TR55, D804): one or two sketches, curves or edges the section follows
(``sweep_guides``); orientation and twist then come from the guides.

The path must start (or end) on the profile's plane, or cross it (TR137, D1906).
Face roles: ``cap/start``, ``cap/end`` and ``side/<entity>`` (``#k`` per path
segment after the first).
"""

from __future__ import annotations

import itertools
import math

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_CompCurve
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakeWire,
)
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepFill import BRepFill_NoContact
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt, gp_Vec
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_WIRE
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face, TopoDS_Shape, TopoDS_Vertex, TopoDS_Wire

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureState,
    FeatureType,
    Issue,
    ParamSpec,
    SketchOutput,
    Vec3,
    register,
)
from fdcad.core.features.extrude_thin import THIN_TYPES, join_edges, thin_on, thin_sketch
from fdcad.core.features.solids import (
    FUZZY_TOLERANCE,
    check_result,
    combine_or_keep,
    compound,
    expected_issues,
    is_valid,
)
from fdcad.core.naming.names import NamedFace, NamedShape, restrict
from fdcad.core.occ import shape_list
from fdcad.core.sketch.profiles import Profile
from fdcad.core.units import Kind

TWISTS = ("none", "minimum", "angle", "direction", "turns")
#: How the section turns along the path (TR56 adds "curvature", D1504).
ORIENTATIONS = ("follow_path", "keep_normal", "curvature", "face", "second_path")
#: How the section passes a sharp corner of the path (TR137, D1515).
CORNERS = ("smooth", "mitre", "round")
#: How the section meets the path at its start (TR56 item 1, D1905).
TANGENCIES = ("none", "path_tangent")
_ON_PLANE_TOL = 1e-4  # mm
_TWIST_SAMPLES = 49


def _sketch_output(feature: Feature, ctx: BuildContext, key: str, label: str) -> SketchOutput:
    ref = feature.refs.get(key)
    if not isinstance(ref, dict) or "feature" not in ref:
        raise FeatureError(f"{feature.name} has no {label}. Choose a sketch for the {label}.")
    out = ctx.result(str(ref["feature"])).sketch
    if out is None:
        raise FeatureError(f"{feature.name}: the {label} is not a sketch. Choose a sketch.")
    return out


def path_wire(feature: Feature, ctx: BuildContext) -> tuple[TopoDS_Wire, list[Issue]]:
    """The path as one wire: a sketch chain or a chain of model edges."""
    from fdcad.core.features.modify import resolve_edges
    from fdcad.core.features.sketch_paths import sketch_chain

    if feature.refs.get("path_edges"):
        found, issues = resolve_edges(feature, ctx, "path_edges")
        wire = join_edges([e for _n, e in found])
        if wire is None:
            raise FeatureError(
                f"{feature.name}: the path edges do not join end to end. Pick edges that touch."
            )
        return wire, issues
    from fdcad.core.features.curves import curve_of

    curve = curve_of(ctx, feature.refs.get("path"), feature.name)
    if curve is not None:  # a helix, projected, composite or contour curve (P3.6, P3.7)
        return curve, []
    ref = feature.refs.get("path")
    if (
        isinstance(ref, dict)
        and "feature" in ref
        and ctx.result(str(ref["feature"])).sketch is None
    ):
        raise FeatureError(
            f"{feature.name}: the path is not a sketch or a curve. "
            "Choose a sketch or a curve for the path."
        )
    out = _sketch_output(feature, ctx, "path", "path")
    return sketch_chain(out.model, out.plane, feature.name).wire, []


def _wire_ends(wire: TopoDS_Wire) -> tuple[gp_Pnt, gp_Pnt]:
    first, last = TopoDS_Vertex(), TopoDS_Vertex()
    TopExp.Vertices_s(wire, first, last)
    return BRep_Tool.Pnt_s(first), BRep_Tool.Pnt_s(last)


def _path_start(wire: TopoDS_Wire) -> tuple[gp_Pnt, gp_Vec]:
    curve = BRepAdaptor_CompCurve(wire)
    point, tangent = gp_Pnt(), gp_Vec()
    curve.D1(curve.FirstParameter(), point, tangent)
    return point, tangent


def _reversed(wire: TopoDS_Wire) -> TopoDS_Wire:
    return TopoDS.Wire(wire.Reversed())


def _self_crossing(wire: TopoDS_Wire) -> bool:
    """True when two edges of the path that do not follow each other touch."""
    edges: list[TopoDS_Edge] = []
    explorer = TopExp_Explorer(wire, TopAbs_EDGE)
    while explorer.More():
        edges.append(TopoDS.Edge(explorer.Current()))
        explorer.Next()
    closed = BRep_Tool.IsClosed_s(wire)
    for i in range(len(edges)):
        for j in range(i + 2, len(edges)):
            if closed and i == 0 and j == len(edges) - 1:
                continue
            dist = BRepExtrema_DistShapeShape(edges[i], edges[j])
            if dist.IsDone() and dist.Value() < 1e-6:
                return True
    return False


def _direction(feature: Feature, ctx: BuildContext) -> Vec3:
    """The twist direction vector from a plane, a flat face or a straight edge."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Plane

    from fdcad.core.features.solids import line_ends

    owner = feature.name
    ref = feature.refs.get("twist_direction")
    if not isinstance(ref, dict):
        raise FeatureError(
            f"{owner}: pick a plane, a flat face or a straight edge for the direction."
        )
    if "feature" in ref and "kind" not in ref:
        res = ctx.results.get(str(ref["feature"]))
        if res is None or res.plane is None:
            raise FeatureError(f"{owner}: the direction pick was lost. Pick it again.")
        return res.plane.normal
    if ref.get("kind") == "edge":
        from fdcad.core.naming.resolve import resolve_edge

        edge, _issues = resolve_edge(ctx.body, ref, owner)
        ends = line_ends(edge)
        if ends is None:
            raise FeatureError(
                f"{owner}: the direction edge is not straight. Pick a straight edge."
            )
        a, b = ends
        d = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        n = math.sqrt(sum(c * c for c in d))
        return (d[0] / n, d[1] / n, d[2] / n)
    from fdcad.core.naming.resolve import resolve_face

    face, _issues = resolve_face(ctx.body, ref, owner)
    surface = BRepAdaptor_Surface(face)
    if surface.GetType() != GeomAbs_Plane:
        raise FeatureError(f"{owner}: the direction face is not flat. Pick a flat face.")
    d = surface.Plane().Axis().Direction()
    return (d.X(), d.Y(), d.Z())


def _twist_spine(wire: TopoDS_Wire, start_normal: gp_Vec, angle: float) -> TopoDS_Wire:
    """An auxiliary spine that turns ``angle`` radians around the path from start to end.

    The section's up direction follows a frame carried along the path with the
    least turning (double reflection), plus a turn growing evenly with length.
    Points are spaced evenly by length. The spine is used in the kernel's plane mode
    (the section lies in the plane square to the path through each point), which is
    exact here; the curvilinear mode distorts long sweeps in this kernel version (D703).
    The spine stays closer to the path than its tightest bend, so each of those
    planes meets the spine once.
    """
    from OCP.collections import Array1_gp_Pnt
    from OCP.GCPnts import GCPnts_AbscissaPoint
    from OCP.GeomAbs import GeomAbs_C2
    from OCP.GeomAPI import GeomAPI_PointsToBSpline

    curve = BRepAdaptor_CompCurve(wire)
    u0 = curve.FirstParameter()
    total = GCPnts_AbscissaPoint.Length_s(curve)
    n = _TWIST_SAMPLES
    points: list[gp_Pnt] = []
    tangents: list[gp_Vec] = []
    for i in range(n):
        if i == 0 or total <= 0:
            u = u0
        elif i == n - 1:
            u = curve.LastParameter()
        else:
            u = GCPnts_AbscissaPoint(curve, total * i / (n - 1), u0).Parameter()
        p, t = gp_Pnt(), gp_Vec()
        curve.D1(u, p, t)
        points.append(p)
        tangents.append(t.Normalized() if t.Magnitude() > 1e-12 else gp_Vec(0, 0, 1))
    step = total / (n - 1) if total > 0 else 1.0
    bend = max((a.Angle(b) / step for a, b in itertools.pairwise(tangents)), default=0.0)
    reach = max(total, 1.0)
    if bend > 1e-9:
        reach = min(reach, 0.5 / bend)  # half the tightest bend radius
    normal = start_normal.Normalized()
    array = Array1_gp_Pnt(1, n)
    for i in range(n):
        if i > 0:
            # Double reflection carries the normal with the least turning.
            v1 = gp_Vec(points[i - 1], points[i])
            c1 = v1.Dot(v1)
            if c1 > 1e-18:
                r = normal.Subtracted(v1.Multiplied(2 * v1.Dot(normal) / c1))
                tl = tangents[i - 1].Subtracted(v1.Multiplied(2 * v1.Dot(tangents[i - 1]) / c1))
                v2 = tangents[i].Subtracted(tl)
                c2 = v2.Dot(v2)
                normal = r.Subtracted(v2.Multiplied(2 * v2.Dot(r) / c2)) if c2 > 1e-18 else r
            # Keep it square to the path, so the point lies in the section's plane.
            normal = normal.Subtracted(tangents[i].Multiplied(normal.Dot(tangents[i])))
            normal = normal.Normalized()
        turn = angle * i / (n - 1)
        side = tangents[i].Crossed(normal)
        up = normal.Multiplied(math.cos(turn)).Added(side.Multiplied(math.sin(turn)))
        array.SetValue(i + 1, points[i].Translated(up.Multiplied(reach)))
    spline = GeomAPI_PointsToBSpline(array, 3, 8, GeomAbs_C2, 1e-7).Curve()
    return BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(spline).Edge()).Wire()


def _flat_path_normal(wire: TopoDS_Wire) -> gp_Dir | None:
    """The normal of the plane a curved path lies in; None for a straight or 3D path."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepLib import BRepLib_FindSurface
    from OCP.GeomAbs import GeomAbs_Line, GeomAbs_Plane

    explorer = TopExp_Explorer(wire, TopAbs_EDGE)
    straight = True
    while explorer.More():
        if BRepAdaptor_Curve(TopoDS.Edge(explorer.Current())).GetType() != GeomAbs_Line:
            straight = False
        explorer.Next()
    if straight:
        return None
    found = BRepLib_FindSurface(wire, 1e-6, True)
    if not found.Found():
        return None
    from OCP.GeomAdaptor import GeomAdaptor_Surface

    surface = GeomAdaptor_Surface(found.Surface())
    if surface.GetType() != GeomAbs_Plane:
        return None
    return surface.Plane().Axis().Direction()


def _orient_face(feature: Feature, ctx: BuildContext) -> TopoDS_Shape:
    """The face under the path that keeps the section's up direction (TR396, D1514)."""
    from fdcad.core.features.lookup import resolve_face

    refs = feature.refs.get("orient_face")
    ref = refs[0] if isinstance(refs, list) and refs else refs
    if not isinstance(ref, dict) or ctx.body is None:
        raise FeatureError(
            f"{feature.name}: Normal to Face needs the face under the path. Click it."
        )
    face, _issues = resolve_face(ctx.body, ref, feature.name)
    return face


def _second_path(feature: Feature, ctx: BuildContext) -> TopoDS_Wire:
    """The sketch or curve the section's X axis points at (TR396, D1514)."""
    ref = feature.refs.get("x_path")
    if not isinstance(ref, dict):
        raise FeatureError(
            f"{feature.name}: Follow Second Path needs a second path. Choose a sketch or curve."
        )
    shim = Feature(feature.id, feature.type, feature.name, refs={"path": ref})
    wire, _issues = path_wire(shim, ctx)
    return wire


def _path_from_plane(owner: str, path: TopoDS_Wire, point: Vec3, normal: Vec3) -> TopoDS_Wire:
    """The path running away from the profile's plane: reversed when its end is there."""
    first, last = _wire_ends(path)
    if _off_plane(first, point, normal) > _ON_PLANE_TOL:
        if _off_plane(last, point, normal) <= _ON_PLANE_TOL:
            return _reversed(path)
        raise FeatureError(
            f"{owner}: the path must start on the profile's sketch plane. "
            "Move an end of the path onto that plane."
        )
    return path


#: Which way a sweep runs from a profile part way along the path (TR137, D1906).
DIRECTIONS = ("forward", "backward", "both")


def split_at_plane(path: TopoDS_Wire, point: Vec3, normal: Vec3) -> tuple[TopoDS_Wire, TopoDS_Wire]:
    """The path cut where it first crosses the profile's plane (TR137 item 1, D1906):
    the part after the crossing, and the part before it reversed, both running away
    from the plane. Raises ValueError when the path does not cross the plane."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepTools import BRepTools_WireExplorer
    from OCP.Geom import Geom_Plane
    from OCP.GeomAPI import GeomAPI_IntCS
    from OCP.TopAbs import TopAbs_REVERSED

    plane = Geom_Plane(gp_Pnt(*point), gp_Dir(*normal))
    before: list[TopoDS_Edge] = []
    after: list[TopoDS_Edge] = []
    cut = False
    explorer = BRepTools_WireExplorer(path)
    while explorer.More():
        edge = explorer.Current()
        explorer.Next()
        if cut:
            after.append(edge)
            continue
        adaptor = BRepAdaptor_Curve(edge)
        u0, u1 = adaptor.FirstParameter(), adaptor.LastParameter()
        curve = BRep_Tool.Curve_s(edge, u0, u1)
        hits = GeomAPI_IntCS(curve, plane)
        reverse = edge.Orientation() == TopAbs_REVERSED
        found = sorted(
            hits.Parameters(k)[2] for k in range(1, hits.NbPoints() + 1) if hits.IsDone()
        )
        found = [u for u in found if u0 + 1e-7 < u < u1 - 1e-7]
        if not found:
            before.append(edge)
            continue
        u = found[-1] if reverse else found[0]
        a = BRepBuilderAPI_MakeEdge(curve, u0, u).Edge()
        b = BRepBuilderAPI_MakeEdge(curve, u, u1).Edge()
        if reverse:
            a, b = TopoDS.Edge(b.Reversed()), TopoDS.Edge(a.Reversed())
        before.append(a)
        after.append(b)
        cut = True
    if not cut:
        raise ValueError("the path does not cross the plane")

    def wire(edges: list[TopoDS_Edge]) -> TopoDS_Wire:
        maker = BRepBuilderAPI_MakeWire()
        for e in edges:
            maker.Add(e)
        return maker.Wire()

    return wire(after), _reversed(wire(before))


def _paths_from_plane(
    feature: Feature, path: TopoDS_Wire, point: Vec3, normal: Vec3
) -> list[TopoDS_Wire]:
    """The path or paths to sweep along (TR137 item 1, D1906): from an end on the
    profile's plane as before, or from where the path crosses the plane part way
    along, ``sweep_direction`` one way, the other way or both."""
    owner = feature.name
    first, last = _wire_ends(path)
    on_end = min(_off_plane(first, point, normal), _off_plane(last, point, normal))
    direction = str(feature.params.get("sweep_direction", "forward"))
    if direction not in DIRECTIONS:
        raise FeatureError(f"{owner}: unknown direction '{direction}'. Choose another.")
    if on_end <= _ON_PLANE_TOL:
        return [_path_from_plane(owner, path, point, normal)]
    try:
        ahead, behind = split_at_plane(path, point, normal)
    except Exception:
        raise FeatureError(
            f"{owner}: the path must start on the profile's sketch plane or cross it. "
            "Move the path so it passes through that plane."
        ) from None
    return {"forward": [ahead], "backward": [behind], "both": [ahead, behind]}[direction]


def _face_profile(feature: Feature, ctx: BuildContext) -> tuple[Profile, Vec3, Vec3, gp_Vec]:
    """A flat model face as the profile (TR138, D1516): its outline and holes, its plane,
    and side faces named ``side/edge<k>`` by the face's edges in order."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Plane

    from fdcad.core.features.lookup import resolve_face

    refs = feature.refs.get("profile_face")
    ref = refs[0] if isinstance(refs, list) and refs else refs
    if not isinstance(ref, dict) or ctx.body is None:
        raise FeatureError(f"{feature.name}: Face profile needs a flat face. Click one.")
    face, _issues = resolve_face(ctx.body, ref, feature.name)
    surface = BRepAdaptor_Surface(face)
    if surface.GetType() != GeomAbs_Plane:
        raise FeatureError(
            f"{feature.name}: the profile face is not flat. Click a flat face, or use a sketch."
        )
    plane = surface.Plane()
    normal = plane.Axis().Direction()
    from OCP.TopAbs import TopAbs_REVERSED

    if face.Orientation() == TopAbs_REVERSED:
        normal = normal.Reversed()
    x = plane.XAxis().Direction()
    loc = plane.Location()
    edges: list[tuple[TopoDS_Edge, str]] = []
    explorer = TopExp_Explorer(face, TopAbs_EDGE)
    while explorer.More():
        edges.append((TopoDS.Edge(explorer.Current()), f"edge{len(edges) + 1}"))
        explorer.Next()
    profile = Profile([face], edges)
    return (
        profile,
        (loc.X(), loc.Y(), loc.Z()),
        (normal.X(), normal.Y(), normal.Z()),
        gp_Vec(x.X(), x.Y(), x.Z()),
    )


class _Settings:
    """How the section moves along the path."""

    def __init__(self, feature: Feature, ctx: BuildContext, start_up: gp_Vec) -> None:
        owner = feature.name
        orientation = feature.params.get("orientation", "follow_path")
        self.keep = orientation == "keep_normal"
        self.curvature = orientation == "curvature"  # TR56 (D1504)
        self.corners = str(feature.params.get("corners", "smooth"))  # TR137 (D1515)
        if self.corners not in CORNERS:
            raise FeatureError(f"{owner}: unknown corner '{self.corners}'. Choose another corner.")
        self.support: TopoDS_Shape | None = None  # TR396 (D1514)
        self.x_path: TopoDS_Wire | None = None
        if orientation in ("face", "second_path"):
            if str(feature.params.get("twist", "none")) != "none":
                raise FeatureError(
                    f"{owner}: the section's turning comes from the face or second path, so "
                    "it cannot twist as well. Set the twist to None."
                )
            if orientation == "face":
                self.support = _orient_face(feature, ctx)
            else:
                self.x_path = _second_path(feature, ctx)
        self.twist = str(feature.params.get("twist", "none"))
        if self.twist not in TWISTS:
            raise FeatureError(
                f"{owner}: unknown twist '{self.twist}'. "
                "Choose another twist in the property panel."
            )
        if self.keep and self.twist in ("angle", "direction", "turns"):
            raise FeatureError(
                f"{owner}: Keep Normal Constant cannot twist. Choose Follow Path or no twist."
            )
        if self.curvature and self.twist != "none":
            raise FeatureError(
                f"{owner}: Follow Curvature sets the section's turning itself, so it cannot "
                "twist. Set the twist to None, or choose Follow Path."
            )
        self.angle = 0.0
        if self.twist == "angle":
            value = feature.params.get("twist_angle")
            if not isinstance(value, Param):
                raise FeatureError(f"{owner}: the twist angle is missing. Enter an angle.")
            self.angle = value.value
        if self.twist == "turns":  # TR56 (D1504)
            value = feature.params.get("twist_turns")
            if not isinstance(value, Param):
                raise FeatureError(f"{owner}: the number of turns is missing. Enter it.")
            self.angle = value.value * 2 * math.pi
        self.direction: Vec3 | None = (
            _direction(feature, ctx) if self.twist == "direction" else None
        )
        self.start_up = start_up
        # TR56 item 1 (D1905): Path Tangent turns the section square to the path's start.
        tangency = str(feature.params.get("start_tangency", "none"))
        if tangency not in TANGENCIES:
            raise FeatureError(
                f"{owner}: unknown start tangency '{tangency}'. Choose None or Path Tangent."
            )
        self.square = tangency == "path_tangent"
        #: Later profiles along the path (TR137 item 2, D1907), set by the sweep.
        self.sections: list[TopoDS_Wire] = []

    def apply(self, maker: BRepOffsetAPI_MakePipeShell, wire: TopoDS_Wire, start: gp_Pnt) -> None:
        """Set the section mode on ``maker``."""
        if self.keep:
            _p, tangent = _path_start(wire)
            maker.SetMode(gp_Ax2(start, gp_Dir(tangent)))
        elif self.curvature:  # TR56 (D1504): the Frenet frame, even on a flat path
            maker.SetMode(True)
        elif self.support is not None:  # TR396 (D1514): up keeps to the face's normal
            maker.SetMode(self.support)
        elif self.x_path is not None:  # TR396 (D1514): X points at the second path
            maker.SetMode(self.x_path, True, BRepFill_NoContact)
        elif self.twist in ("angle", "turns"):
            maker.SetMode(_twist_spine(wire, self.start_up, self.angle), False, BRepFill_NoContact)
        elif self.twist == "direction":
            assert self.direction is not None
            maker.SetMode(gp_Dir(*self.direction))
        elif self.twist == "none" and (normal := _flat_path_normal(wire)) is not None:
            # A flat path: the section's up direction keeps to the path's plane. The
            # kernel's Frenet frame flips where a spline changes the way it bends (D707).
            maker.SetMode(normal)
        else:
            maker.SetMode(self.twist == "none")  # True: Frenet, False: least turning


def _sweep_wire(
    owner: str,
    path: TopoDS_Wire,
    wire: TopoDS_Wire,
    settings: _Settings,
    start: gp_Pnt,
    more: list[TopoDS_Wire] | None = None,
) -> BRepOffsetAPI_MakePipeShell:
    maker = BRepOffsetAPI_MakePipeShell(path)
    settings.apply(maker, path, start)
    if settings.corners != "smooth":  # TR137 (D1515): how sharp corners of the path join
        from OCP.BRepBuilderAPI import BRepBuilderAPI_RightCorner, BRepBuilderAPI_RoundCorner

        maker.SetTransitionMode(
            BRepBuilderAPI_RightCorner
            if settings.corners == "mitre"
            else BRepBuilderAPI_RoundCorner
        )
    maker.Add(wire, False, settings.square)
    for section in more or []:  # TR137 item 2 (D1907): the section blends into each
        maker.Add(section, False, settings.square)
    try:
        maker.Build()
        if maker.IsDone():
            maker.MakeSolid()
    except Exception as exc:
        raise FeatureError(
            f"{owner}: the profile could not be swept along the path. "
            "Use a smaller profile or a gentler path."
        ) from exc
    if not maker.IsDone():
        raise FeatureError(
            f"{owner}: the profile could not be swept along the path. "
            "Use a smaller profile or a gentler path."
        )
    return maker


def smooth_path(wire: TopoDS_Wire, angle: float = 1e-3) -> bool:
    """True when every joint of the path turns by less than ``angle`` radians."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepTools import BRepTools_WireExplorer
    from OCP.TopAbs import TopAbs_REVERSED

    ends: list[tuple[gp_Vec, gp_Vec]] = []
    explorer = BRepTools_WireExplorer(wire)
    while explorer.More():
        edge = explorer.Current()
        curve = BRepAdaptor_Curve(edge)
        p, a, b = gp_Pnt(), gp_Vec(), gp_Vec()
        curve.D1(curve.FirstParameter(), p, a)
        curve.D1(curve.LastParameter(), p, b)
        if edge.Orientation() == TopAbs_REVERSED:
            a, b = b.Reversed(), a.Reversed()
        ends.append((a, b))
        explorer.Next()
    for (_a, out), (into, _b) in itertools.pairwise(ends):
        if out.Magnitude() < 1e-12 or into.Magnitude() < 1e-12 or out.Angle(into) > angle:
            return False
    return True


def merged_path(wire: TopoDS_Wire) -> TopoDS_Wire | None:
    """A smooth path of several edges as one spline edge, so each profile edge sweeps
    one side face (TR56 item 2, D1905). None for one edge or a path with corners."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepTools import BRepTools_WireExplorer
    from OCP.Geom import Geom_TrimmedCurve
    from OCP.GeomConvert import GeomConvert, GeomConvert_CompCurveToBSplineCurve
    from OCP.TopAbs import TopAbs_REVERSED

    if not smooth_path(wire):
        return None
    joined: GeomConvert_CompCurveToBSplineCurve | None = None
    count = 0
    explorer = BRepTools_WireExplorer(wire)
    while explorer.More():
        edge = explorer.Current()
        explorer.Next()
        count += 1
        from OCP.BRepAdaptor import BRepAdaptor_Curve

        adaptor = BRepAdaptor_Curve(edge)
        first, last = adaptor.FirstParameter(), adaptor.LastParameter()
        curve = BRep_Tool.Curve_s(edge, first, last)
        piece = GeomConvert.CurveToBSplineCurve_s(Geom_TrimmedCurve(curve, first, last))
        if edge.Orientation() == TopAbs_REVERSED:
            piece.Reverse()
        if joined is None:
            joined = GeomConvert_CompCurveToBSplineCurve(piece)
        elif not joined.Add(piece, 1e-6):
            return None
    if joined is None or count < 2:
        return None
    edge = BRepBuilderAPI_MakeEdge(joined.BSplineCurve()).Edge()
    return BRepBuilderAPI_MakeWire(edge).Wire()


def _more_profiles(
    feature: Feature, ctx: BuildContext, path: TopoDS_Wire, faces: int
) -> list[TopoDS_Wire]:
    """The outlines of ``refs.profiles`` (TR137 item 2, D1907), later sketches the
    section passes through, sorted by where they sit along the path. Each must be one
    closed outline that the path passes through."""
    from OCP.BRepTools import BRepTools

    owner = feature.name
    refs = feature.refs.get("profiles") or []
    if not refs:
        return []
    if faces != 1:
        raise FeatureError(
            f"{owner}: a sweep through several profiles takes one closed outline in each "
            "sketch. Use a sketch with one region for the first profile."
        )
    curve = BRepAdaptor_CompCurve(path)
    found: list[tuple[float, TopoDS_Wire]] = []
    for ref in refs:
        fid = ref.get("feature") if isinstance(ref, dict) else None
        out = ctx.result(fid).sketch if isinstance(fid, str) else None
        if out is None or out.profile is None or len(out.profile.faces) != 1:
            raise FeatureError(
                f"{owner}: each extra profile must be a sketch with one closed region. "
                "Close the sketch, or remove it from the list."
            )
        first, last = curve.FirstParameter(), curve.LastParameter()
        hits = []
        for k in range(65):
            u = first + (last - first) * k / 64
            hits.append((_off_plane(curve.Value(u), out.plane.origin, out.plane.normal), u))
        gap, where = min(hits)
        if gap > max((last - first) / 64, 1.0):
            raise FeatureError(
                f"{owner}: the path does not pass through an extra profile's plane. Move the "
                "profile's sketch onto the path."
            )
        found.append((where, BRepTools.OuterWire_s(out.profile.faces[0])))
    return [w for _u, w in sorted(found, key=lambda item: item[0])]


def _wires(face: TopoDS_Face) -> tuple[TopoDS_Wire, list[TopoDS_Wire]]:
    from OCP.BRepTools import BRepTools

    outer = BRepTools.OuterWire_s(face)
    inner = []
    explorer = TopExp_Explorer(face, TopAbs_WIRE)
    while explorer.More():
        w = TopoDS.Wire(explorer.Current())
        if not w.IsSame(outer):
            inner.append(w)
        explorer.Next()
    return outer, inner


def sweep_profile(
    feature: Feature,
    profile: Profile,
    path: TopoDS_Wire,
    settings: _Settings,
    start: gp_Pnt,
) -> NamedShape:
    """Sweep every profile face (holes included) along ``path`` and name the faces."""
    from fdcad.core.occ import BRepAlgoAPI_Cut

    fid, owner = feature.id, feature.name
    solids_: list[TopoDS_Shape] = []
    names: list[NamedFace] = []
    for face in profile.faces:
        outer, holes = _wires(face)
        parts = []
        more = settings.sections if not holes else []
        if settings.sections and holes:
            raise FeatureError(
                f"{owner}: a sweep through several profiles takes profiles without holes. "
                "Remove the holes, or sweep one profile."
            )
        for w in [outer, *holes]:
            maker = _sweep_wire(owner, path, w, settings, start, more if w is outer else None)
            parts.append(maker)
            explorer = TopExp_Explorer(w, TopAbs_EDGE)
            while explorer.More():
                edge = TopoDS.Edge(explorer.Current())
                explorer.Next()
                entity = profile.entity_of(edge)
                if entity is None:
                    continue
                made = [
                    s for s in shape_list(maker.Generated(edge)) if s.ShapeType() == TopAbs_FACE
                ]
                for k, side in enumerate(made, start=1):
                    suffix = "" if k == 1 else f"#{k}"
                    names.append((f"{fid}/side/{entity}{suffix}", TopoDS.Face(side)))
            if w.IsSame(outer):
                first, last = maker.FirstShape(), maker.LastShape()
                for role, shape in (("cap/start", first), ("cap/end", last)):
                    for f in _faces(shape):
                        names.append((f"{fid}/{role}", f))
        solid = parts[0].Shape()
        for hole in parts[1:]:
            cut = BRepAlgoAPI_Cut(solid, hole.Shape())
            cut.SetFuzzyValue(FUZZY_TOLERANCE)
            cut.Build()
            if not cut.IsDone():
                raise FeatureError(
                    f"{owner}: the profile's holes could not be swept. "
                    "Change the path or the holes slightly."
                )
            from fdcad.core.naming.names import carry

            names = carry(names, cut.History())
            solid = cut.Shape()
        solids_.append(solid)
    shape = solids_[0] if len(solids_) == 1 else compound(solids_)
    return NamedShape(shape, restrict(names, shape, fid))


def _faces(shape: TopoDS_Shape) -> list[TopoDS_Face]:
    from fdcad.core.naming.names import faces_of

    if shape.IsNull():
        return []
    if shape.ShapeType() == TopAbs_FACE:
        return [TopoDS.Face(shape)]
    if shape.ShapeType() == TopAbs_WIRE:
        return [BRepBuilderAPI_MakeFace(TopoDS.Wire(shape), True).Face()]
    return faces_of(shape)


@register
class Sweep(FeatureType):
    """Moves a profile along a path and adds or removes the solid it sweeps."""

    type_name = "sweep"
    makes_solid = True
    params = (
        ParamSpec("operation", choices=("boss", "cut"), default="boss"),
        ParamSpec("merge", default=True, optional=True),
        ParamSpec("profile_type", choices=("sketch", "circular", "face", "body"), optional=True),
        ParamSpec("diameter", kind=Kind.LENGTH, optional=True),
        ParamSpec("orientation", choices=ORIENTATIONS, optional=True),
        ParamSpec("twist", choices=TWISTS, optional=True),
        ParamSpec("twist_angle", kind=Kind.ANGLE, optional=True),
        ParamSpec("twist_turns", kind=Kind.NUMBER, optional=True),  # TR56 (D1504)
        ParamSpec("corners", choices=CORNERS, optional=True),  # TR137 (D1515)
        ParamSpec("start_tangency", choices=TANGENCIES, optional=True),  # TR56 (D1905)
        ParamSpec("sweep_direction", choices=DIRECTIONS, optional=True),  # TR137 (D1906)
        ParamSpec("show_section", kind=Kind.NUMBER, optional=True),  # TR139 (D1909)
        ParamSpec("section_values", optional=True),  # TR396 (D1910)
        ParamSpec("twist_angle2", kind=Kind.ANGLE, optional=True),
        ParamSpec("twist_turns2", kind=Kind.NUMBER, optional=True),
        ParamSpec("merge_faces", default=False, optional=True),
        ParamSpec("thin_type", choices=THIN_TYPES, optional=True),
        ParamSpec("thin_thickness", kind=Kind.LENGTH, optional=True),
        ParamSpec("thin_thickness2", kind=Kind.LENGTH, optional=True),
        ParamSpec("thin_reverse", default=False, optional=True),
        ParamSpec("scale_start", kind=Kind.NUMBER, optional=True),  # TR241
        ParamSpec("scale_end", kind=Kind.NUMBER, optional=True),
        ParamSpec("scale_law", choices=("linear", "smooth"), optional=True),
    )

    def _tool(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        owner = feature.name
        operation = str(feature.params.get("operation", "boss"))
        path, issues = path_wire(feature, ctx)
        if _self_crossing(path):
            raise FeatureError(f"{owner}: the path crosses itself. Change the path so it does not.")
        paths = [path]
        if feature.params.get("profile_type") == "body":  # TR138 item 3 (D2405)
            from fdcad.core.features.sweep_body import body_sweep

            return body_sweep(feature, ctx, path), issues
        if feature.params.get("profile_type") == "circular":
            if thin_on(feature):
                # Thin applies to sketch profiles only; it made a solid rod (D713).
                raise FeatureError(
                    f"{owner}: Thin Feature does not work with a circular profile. "
                    "Turn off Thin Feature, or use Pipe for a tube."
                )
            profile, plane_point, plane_normal, up = self._circle(feature, path)
        elif feature.params.get("profile_type") == "face":  # TR138 (D1516)
            if thin_on(feature):
                raise FeatureError(
                    f"{owner}: Thin Feature works with sketch profiles only. Turn off Thin "
                    "Feature, or use a sketch for the profile."
                )
            profile, plane_point, plane_normal, up = _face_profile(feature, ctx)
            paths = _paths_from_plane(feature, path, plane_point, plane_normal)
            path = paths[0]
        else:
            out = _sketch_output(feature, ctx, "profile", "profile")
            if thin_on(feature):
                if operation == "cut":
                    raise FeatureError(
                        f"{owner}: Thin Feature is for swept bosses only. Turn off Thin Feature."
                    )
                out = thin_sketch(feature, ctx, out)
            if out.profile is None:
                raise FeatureError(f"{owner}: {out.profile_error}")
            profile = out.profile
            plane_point, plane_normal = out.plane.origin, out.plane.normal
            up = gp_Vec(*out.plane.x_dir)
            paths = _paths_from_plane(feature, path, plane_point, plane_normal)
            path = paths[0]
        from fdcad.core.features.sweep_pitch import check_turns

        check_turns(feature, ctx, profile)  # turns of a helix must not overlap (D2649)
        start, _tangent = _path_start(path)
        from fdcad.core.features.sweep_guides import guide_wires, guided_sweep

        guides = guide_wires(feature, ctx)  # TR55 (D804)
        if len(paths) > 1 and (guides or feature.params.get("scale_start") is not None):
            raise FeatureError(
                f"{owner}: a sweep both ways from the profile cannot use guides or scales. "
                "Choose one direction, or move the profile to an end of the path."
            )
        if guides:
            tool, more = guided_sweep(feature, profile, path, up, guides)
            if not is_valid(None, tool):
                raise FeatureError(
                    f"{owner}: the guided sweep intersects itself. Use gentler guides or a "
                    "smaller profile."
                )
            return tool, [*issues, *more]
        if feature.params.get("section_values"):  # TR396 item 1 (D1910)
            from fdcad.core.features.sweep_values import valued_sweep

            if (
                feature.params.get("profile_type") in ("circular", "face")
                or len(paths) > 1
                or (thin_on(feature))
            ):
                raise FeatureError(
                    f"{owner}: section values need a sketch profile and a sweep one way. "
                    "Use a sketch profile, or clear the section values."
                )
            tool = valued_sweep(feature, ctx, out, path, up)
            if not is_valid(None, tool):
                raise FeatureError(
                    f"{owner}: the sweep with section values intersects itself. Use gentler "
                    "formulas or a gentler path."
                )
            return tool, issues
        from fdcad.core.features.law_sections import scaled_sweep, sweep_law_on

        if sweep_law_on(feature):  # TR241 (D816)
            tool = scaled_sweep(feature, profile, path, up)
            if not is_valid(None, tool):
                raise FeatureError(
                    f"{owner}: the scaled sweep intersects itself. Use a gentler path or "
                    "smaller scales."
                )
            return tool, issues
        settings = _Settings(feature, ctx, up)
        if feature.params.get("merge_faces") is True:  # TR56 item 2 (D1905)
            joined = merged_path(path)
            if joined is not None:
                path = joined
            else:
                issues = [
                    *issues,
                    Issue(
                        FeatureState.WARNING,
                        f"{owner}: the path has a sharp corner or one piece, so the side faces "
                        "stay separate. Turn off Merge Tangent Faces, or smooth the corner.",
                        code="faces_not_merged",
                    ),
                ]
        if settings.twist in ("angle", "turns") and BRep_Tool.IsClosed_s(path):
            whole = settings.angle / (2 * math.pi)
            if abs(whole - round(whole)) > 1e-6:  # TR56 (D1504)
                raise FeatureError(
                    f"{owner}: on a closed path the twist must be whole turns, or the ends "
                    f"would not meet ({whole:.4g} turns now). Enter a whole number of turns."
                )
        settings.sections = _more_profiles(feature, ctx, path, len(profile.faces))
        if settings.sections and len(paths) > 1:
            raise FeatureError(
                f"{owner}: a sweep both ways cannot pass through more profiles. Choose one "
                "direction, or remove the other profiles."
            )
        tool = sweep_profile(feature, profile, path, settings, start)
        if len(paths) > 1:  # TR137 item 1 (D1906): the other side, with its own twist
            tool = self._other_side(feature, ctx, profile, paths[1], up, tool)
        if not is_valid(None, tool):
            from fdcad.core.features.sweep_errors import crossing_message, reach

            # TR139 (D1509): name the tightest bend and the ways out.
            raise FeatureError(crossing_message(owner, path, reach(list(profile.faces), start)))
        if settings.keep and settings.twist == "minimum":
            # The section never turns, so there is no twist to keep small (audit B item 20).
            issues = [
                *issues,
                Issue(
                    FeatureState.WARNING,
                    f"{owner}: Keep Normal Constant keeps the profile from turning, so Minimum "
                    "Twist has no effect. Choose Follow Path to use it, or set the twist to None.",
                    code="twist_unused",
                ),
            ]
        return tool, issues

    @staticmethod
    def _other_side(
        feature: Feature,
        ctx: BuildContext,
        profile: Profile,
        path: TopoDS_Wire,
        up: gp_Vec,
        tool: NamedShape,
    ) -> NamedShape:
        """The sweep the other way from the profile, its faces named ``back/...``, fused
        with the first side (TR137 item 1, D1906). ``twist_angle2`` or ``twist_turns2``
        twist this side on its own, else it takes the first side's twist."""
        import copy

        from fdcad.core.features.booleans import boolean_named

        other = copy.copy(feature)
        other.params = dict(feature.params)
        for name in ("twist_angle", "twist_turns"):
            if isinstance(feature.params.get(f"{name}2"), Param):
                other.params[name] = feature.params[f"{name}2"]
        settings = _Settings(other, ctx, up)
        start, _tangent = _path_start(path)
        back = sweep_profile(feature, profile, path, settings, start)
        prefix = f"{feature.id}/"
        renamed = [
            (f"{prefix}back/{n[len(prefix) :]}" if n.startswith(prefix) else n, f)
            for n, f in back.faces
        ]
        return boolean_named(
            "fuse", tool, NamedShape(back.shape, renamed), feature.id, feature.name
        )

    @staticmethod
    def _circle(feature: Feature, path: TopoDS_Wire) -> tuple[Profile, Vec3, Vec3, gp_Vec]:
        value = feature.params.get("diameter")
        if not isinstance(value, Param) or value.value <= 0:
            raise FeatureError(f"{feature.name}: enter a diameter greater than zero.")
        start, tangent = _path_start(path)
        axis = gp_Ax2(start, gp_Dir(tangent))
        edge = BRepBuilderAPI_MakeEdge(gp_Circ(axis, value.value / 2)).Edge()
        wire = BRepBuilderAPI_MakeWire(edge).Wire()
        face = BRepBuilderAPI_MakeFace(wire, True).Face()
        x = axis.XDirection()
        n = tangent.Normalized()
        return (
            Profile([face], [(edge, "circle")]),
            (start.X(), start.Y(), start.Z()),
            (n.X(), n.Y(), n.Z()),
            gp_Vec(x.X(), x.Y(), x.Z()),
        )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Sweep and combine with the part."""
        from fdcad.core.features.sweep_sections import section_number, sweep_section

        operation = str(feature.params.get("operation", "boss"))
        k = section_number(feature)  # TR139 item 2 (D1909)
        extras: dict[str, object] = {}
        if k:
            shape, line = sweep_section(feature, ctx, k)
            extras = {"reference": shape, "report": [line]}
        try:
            tool, issues = self._ground(feature, ctx, *self._tool(feature, ctx))
        except FeatureError as exc:
            if not k:
                raise
            # The section still shows, to find where the sweep goes wrong.
            fail = Issue(FeatureState.ERROR, str(exc), fixes=exc.fixes, highlight=exc.highlight)
            return FeatureResult(body=ctx.body, issues=[fail], extras=extras)
        body = combine_or_keep(feature, ctx.body, tool, operation, ctx, issues)
        found = check_result(feature.id, feature.name, ctx.body, body, None)
        return FeatureResult(
            body=body, issues=issues + expected_issues(feature, found), extras=extras
        )

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The swept solid, for the preview."""
        return self._ground(feature, ctx, *self._tool(feature, ctx))[0]

    @staticmethod
    def _ground(
        feature: Feature, ctx: BuildContext, tool: NamedShape, issues: list[Issue]
    ) -> tuple[NamedShape, list[Issue]]:
        """Ground flat ends for a spring (TR162 item 2, D2408)."""
        if feature.params.get("ground_ends") is not True:
            return tool, issues
        from fdcad.core.features.sweep_ground import ground

        path, _found = path_wire(feature, ctx)
        return ground(feature, ctx, tool, path), issues


def _off_plane(p: gp_Pnt, origin: Vec3, normal: Vec3) -> float:
    return float(
        abs(
            (p.X() - origin[0]) * normal[0]
            + (p.Y() - origin[1]) * normal[1]
            + (p.Z() - origin[2]) * normal[2]
        )
    )
