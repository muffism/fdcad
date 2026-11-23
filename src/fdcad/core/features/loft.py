"""Loft, boss or cut: join profiles with a solid (PHASE2_SPEC P2.3, DECISIONS D220).

Params:

- ``operation``: "boss" or "cut". ``merge``: optional boolean (bosses).
- ``start_constraint`` and ``end_constraint``: "default" (smooth through the
  profiles), "none" (straight between profiles when both ends are none),
  "normal" (leaves square to the profile) or "direction" (along
  ``refs.start_direction`` or ``refs.end_direction``). ``start_length`` and
  ``end_length``: how far the start or end direction reaches.
- ``connect_<k>``: optional whole number, the vertex where profile ``k`` (1 based)
  starts, so the profiles join point to point.
- ``close_loft``: optional boolean, joins the last profile back to the first.
- Thin Feature (bosses): the ``thin_*`` keys of the extrude.

Refs: ``profiles``, a list of sketches (``{"feature": "f5"}``) or flat faces, in
order, or loops of model edges (TR138, D1908: ``{"kind": "loop", "edges": [...]}``,
closed and flat). The first or the last can be a point (a vertex, sketch point or reference
point) for a pointed end (TR135, D826). Face roles: ``cap/start``, ``cap/end`` and
``side/<entity>`` from the first profile's curves.
"""

from __future__ import annotations

from typing import Any

from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid, BRepBuilderAPI_MakeWire
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
from OCP.BRepTools import BRepTools, BRepTools_WireExplorer
from OCP.gp import gp_Trsf, gp_Vec
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SHELL, TopAbs_WIRE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face, TopoDS_Shape, TopoDS_Wire

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    Vec3,
    register,
)
from fdcad.core.features.extrude_thin import THIN_TYPES, thin_on, thin_sketch
from fdcad.core.features.solids import (
    FUZZY_TOLERANCE,
    check_result,
    combine_or_keep,
    expected_issues,
    is_valid,
    profile_centre,
    volume_of,
)
from fdcad.core.naming.names import NamedFace, NamedShape, carry, restrict
from fdcad.core.occ import shape_list
from fdcad.core.sketch.profiles import Profile
from fdcad.core.units import Kind

#: "tangent" and "curvature" (TR136 item 2, D1924): along the faces next to a face
#: profile, with one or two guiding copies.
CONSTRAINTS = ("default", "none", "normal", "direction", "tangent", "curvature")


class Section:
    """One profile: its outer wire, inner wires (thin walls), its plane normal and names."""

    def __init__(
        self,
        outer: TopoDS_Wire | None,
        inner: list[TopoDS_Wire],
        normal: Vec3,
        profile: Profile | None,
        point: Vec3 | None = None,
    ) -> None:
        self.outer, self.inner, self.normal, self.profile = outer, inner, normal, profile
        #: A pointed end (TR135): the point, with no wire.
        self.point = point
        #: Extra connector points (TR136 item 1, D2403), matched in order between profiles.
        self.marks: list[Vec3] = []

    def centre(self) -> Vec3:
        """The middle of the profile, or the point."""
        if self.point is not None:
            return self.point
        assert self.outer is not None
        return _centre(self.outer)


def _wires_of(face: TopoDS_Face) -> tuple[TopoDS_Wire, list[TopoDS_Wire]]:
    outer = BRepTools.OuterWire_s(face)
    inner = []
    explorer = TopExp_Explorer(face, TopAbs_WIRE)
    while explorer.More():
        w = TopoDS.Wire(explorer.Current())
        if not w.IsSame(outer):
            inner.append(w)
        explorer.Next()
    return outer, inner


def _rotated(wire: TopoDS_Wire, start: int) -> TopoDS_Wire:
    """``wire`` with its edges reordered so it starts at edge ``start``."""
    edges: list[TopoDS_Edge] = []
    explorer = BRepTools_WireExplorer(wire)
    while explorer.More():
        edges.append(explorer.Current())
        explorer.Next()
    if not edges or start % len(edges) == 0:
        return wire
    k = start % len(edges)
    maker = BRepBuilderAPI_MakeWire()
    for edge in edges[k:] + edges[:k]:
        maker.Add(edge)
    return maker.Wire() if maker.IsDone() else wire


def sections(feature: Feature, ctx: BuildContext) -> tuple[list[Section], list[Issue]]:
    """Each picked profile as a section, in order."""
    from fdcad.core.features.sweep import _sketch_output

    owner = feature.name
    refs = feature.refs.get("profiles")
    if not isinstance(refs, list) or len(refs) < 2:
        raise FeatureError(f"{owner}: a loft needs at least two profiles. Add another profile.")
    out: list[Section] = []
    issues: list[Issue] = []
    thin = thin_on(feature)
    for k, ref in enumerate(refs, start=1):
        if not isinstance(ref, dict):
            raise FeatureError(f"{owner}: profile {k} is missing. Pick it again or remove it.")
        if _is_point(ref, ctx):
            if k not in (1, len(refs)):
                raise FeatureError(
                    f"{owner}: profile {k} is a point. Only the first or last profile can be a "
                    "point. Pick a sketch or face, or move the point to an end."
                )
            from fdcad.core.features.geometry_refs import resolve_placement

            place = resolve_placement(ctx, ref, owner, "point")
            issues.extend(place.issues)
            out.append(Section(None, [], (0.0, 0.0, 0.0), None, tuple(place.point)))  # type: ignore[arg-type]
            continue
        if ref.get("kind") == "loop":  # TR138 (D1908): a closed loop of model edges
            outer, normal, found = loop_profile(ctx, ref, owner, k)
            issues.extend(found)
            out.append(Section(outer, [], normal, None))
            continue
        if ref.get("kind") == "face":
            from fdcad.core.features.extrude_start import _flat_normal
            from fdcad.core.naming.resolve import resolve_face

            try:
                face, found = resolve_face(ctx.body, ref, owner)
            except FeatureError as exc:
                name = str(ref.get("name", ""))
                raise FeatureError(
                    f"{owner}: profile {k} ({name}) was lost. Pick it again or remove it.",
                    highlight=[name],
                ) from exc
            issues.extend(found)
            flat = _flat_normal(face)
            if flat is None:
                raise FeatureError(f"{owner}: profile {k} is not a flat face. Pick a flat face.")
            outer, inner = _wires_of(face)
            out.append(Section(outer, inner, flat[0], None))
            continue
        holder = Feature(feature.id, feature.type, owner, params=feature.params, refs={"p": ref})
        sketch = _sketch_output(holder, ctx, "p", f"profile {k}")
        if thin:
            sketch = thin_sketch(feature, ctx, sketch)
        if sketch.profile is None:
            raise FeatureError(f"{owner}: profile {k}: {sketch.profile_error}")
        if len(sketch.profile.faces) != 1:
            raise FeatureError(
                f"{owner}: profile {k} has {len(sketch.profile.faces)} regions. "
                "Each loft profile must be one closed region. Edit the sketch."
            )
        outer, inner = _wires_of(sketch.profile.faces[0])
        if not thin:
            inner = []  # holes in a solid loft are not joined (D220)
        out.append(Section(outer, inner, sketch.plane.normal, sketch.profile))
    if sum(1 for s in out if s.point is None) < 1:
        raise FeatureError(
            f"{owner}: a loft needs at least one profile that is not a point. Add a sketch."
        )
    from fdcad.core.features.loft_connectors import match_numbers, vertex_points

    for k, section in enumerate(out, start=1):
        if section.outer is not None:  # TR136 item 1 (D2403): more connectors
            section.marks = vertex_points(section.outer, match_numbers(feature, k))
        start = feature.params.get(f"connect_{k}")
        if (
            section.outer is not None
            and isinstance(start, int)
            and not isinstance(start, bool)
            and start
        ):
            section.outer = _rotated(section.outer, start)
    return out, issues


def loop_profile(
    ctx: BuildContext, ref: dict[str, Any], owner: str, k: int
) -> tuple[TopoDS_Wire, Vec3, list[Issue]]:
    """A loft profile made of model edges (TR138, D1908): ``{"kind": "loop", "edges":
    [edge references]}``, joined into one closed wire that lies flat."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepLib import BRepLib_FindSurface
    from OCP.GeomAbs import GeomAbs_Plane
    from OCP.GeomAdaptor import GeomAdaptor_Surface

    from fdcad.core.features.extrude_thin import join_edges
    from fdcad.core.features.lookup import resolve_edge

    edges = []
    issues: list[Issue] = []
    for edge_ref in ref.get("edges") or []:
        edge, found = resolve_edge(ctx.body, edge_ref, owner)
        edges.append(edge)
        issues.extend(found)
    wire = join_edges(edges) if edges else None
    if wire is None or not BRep_Tool.IsClosed_s(wire):
        raise FeatureError(
            f"{owner}: the edges of profile {k} do not make one closed loop. Pick edges that "
            "join end to end all the way round."
        )
    surface = BRepLib_FindSurface(wire, 1e-6, True)
    plane = GeomAdaptor_Surface(surface.Surface()) if surface.Found() else None
    if plane is None or plane.GetType() != GeomAbs_Plane:
        raise FeatureError(
            f"{owner}: the edges of profile {k} do not lie flat. Pick a loop that lies in a "
            "plane, or use a sketch."
        )
    d = plane.Plane().Axis().Direction()
    return wire, (d.X(), d.Y(), d.Z()), issues


def _is_point(ref: dict[str, Any], ctx: BuildContext) -> bool:
    """True for a vertex, a sketch point or a reference point feature."""
    if ref.get("kind") == "vertex":
        return True
    fid = ref.get("feature")
    if "sketch_entity" in ref and isinstance(fid, str):
        from fdcad.core.sketch.model import Point

        try:
            sketch = ctx.result(fid).sketch
        except Exception:
            return False
        entity = sketch.model.entities.get(str(ref["sketch_entity"])) if sketch else None
        return isinstance(entity, Point)
    if isinstance(fid, str) and "kind" not in ref:
        try:
            return ctx.document.feature(fid).type == "ref_point"
        except Exception:
            return False
    return False


def _toward(section: Section, other: Section) -> Vec3:
    """The section's normal, turned to point toward ``other``."""
    a = section.centre()
    b = other.centre()
    n = section.normal
    along = (b[0] - a[0]) * n[0] + (b[1] - a[1]) * n[1] + (b[2] - a[2]) * n[2]
    return n if along >= 0 else (-n[0], -n[1], -n[2])


def _flat_face(wire: TopoDS_Wire) -> TopoDS_Face:
    """A flat face on ``wire`` (for its centre)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace

    return BRepBuilderAPI_MakeFace(wire, True).Face()


def _moved(wire: TopoDS_Wire, vector: Vec3) -> TopoDS_Wire:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform

    trsf = gp_Trsf()
    trsf.SetTranslation(gp_Vec(*vector))
    return TopoDS.Wire(BRepBuilderAPI_Transform(wire, trsf, True).Shape())


def _direction_ref(feature: Feature, ctx: BuildContext, end: str) -> Vec3:
    holder = Feature(
        feature.id,
        feature.type,
        feature.name,
        refs={"twist_direction": feature.refs.get(f"{end}_direction")},
    )
    from fdcad.core.features.sweep import _direction

    return _direction(holder, ctx)


def _extra(
    feature: Feature, ctx: BuildContext, end: str, section: Section, other: Section
) -> Vec3 | None:
    """How far to place a guiding copy of an end profile, or None for no constraint."""
    kind = str(feature.params.get(f"{end}_constraint", "default"))
    if kind not in CONSTRAINTS:
        raise FeatureError(
            f"{feature.name}: unknown {end} constraint '{kind}'. "
            "Choose another constraint in the property panel."
        )
    if kind in ("default", "none"):
        return None
    value = feature.params.get(f"{end}_length")
    if not isinstance(value, Param) or value.value <= 0:
        raise FeatureError(
            f"{feature.name}: the {end} tangent length must be greater than "
            "zero. Enter a larger length."
        )
    if kind in ("tangent", "curvature"):  # TR136 (D1924)
        d = _adjacent_direction(feature, ctx, end)
    else:
        d = _toward(section, other) if kind == "normal" else _direction_ref(feature, ctx, end)
    if kind in ("direction", "tangent", "curvature"):
        # Point the picked direction toward the next profile.
        t = _toward(section, other)
        if d[0] * t[0] + d[1] * t[1] + d[2] * t[2] < 0:
            d = (-d[0], -d[1], -d[2])
    scale = value.value * 0.25  # the copy sits a quarter of the length out (D220)
    return (d[0] * scale, d[1] * scale, d[2] * scale)


def _adjacent_direction(feature: Feature, ctx: BuildContext, end: str) -> Vec3:
    """The way the faces next to an end's face profile run as they reach it (TR136 item
    2, D1924): at each edge of the profile face, the direction in the neighbouring face
    square to the edge, away from that face, averaged. Raises FeatureError when the end
    is not a face of the part."""
    import math

    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_REVERSED
    from OCP.TopExp import TopExp

    from fdcad.core.naming.names import centroid
    from fdcad.core.naming.resolve import resolve_face
    from fdcad.core.occ import ShapeListMap

    owner = feature.name
    refs = feature.refs.get("profiles") or []
    ref = refs[0 if end == "start" else -1] if refs else None
    if not isinstance(ref, dict) or ref.get("kind") != "face" or ctx.body is None:
        raise FeatureError(
            f"{owner}: Tangent and Curvature at the {end} need a face of the part as the {end} "
            "profile. Pick a face, or choose another constraint."
        )
    face, _issues = resolve_face(ctx.body, ref, owner)
    owners = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(ctx.body.shape, TopAbs_EDGE, TopAbs_FACE, owners)
    total = [0.0, 0.0, 0.0]
    explorer = TopExp_Explorer(face, TopAbs_EDGE)
    while explorer.More():
        edge = TopoDS.Edge(explorer.Current())
        explorer.Next()
        if not owners.Contains(edge):
            continue
        for other in owners.FindFromKey(edge):
            if other.IsSame(face):
                continue
            curve = BRepAdaptor_Curve(edge)
            u = (curve.FirstParameter() + curve.LastParameter()) / 2
            t = gp_Vec()
            p = gp_Pnt()
            curve.D1(u, p, t)
            other_face = TopoDS.Face(other)
            project = GeomAPI_ProjectPointOnSurf(p, BRep_Tool.Surface_s(other_face))
            if project.NbPoints() == 0 or t.Magnitude() < 1e-12:
                continue
            su, sv = project.LowerDistanceParameters()
            props = BRepLProp_SLProps(BRepAdaptor_Surface(other_face), su, sv, 1, 1e-6)
            if not props.IsNormalDefined():
                continue
            n = props.Normal()
            if other_face.Orientation() == TopAbs_REVERSED:
                n.Reverse()
            v = gp_Vec(n.X(), n.Y(), n.Z()).Crossed(t)
            if v.Magnitude() < 1e-12:
                continue
            c = centroid(other_face)
            inward = gp_Vec(c[0] - p.X(), c[1] - p.Y(), c[2] - p.Z())
            if v.Dot(inward) > 0:
                v.Reverse()  # away from the neighbouring face, past the edge
            v.Normalize()
            total = [total[0] + v.X(), total[1] + v.Y(), total[2] + v.Z()]
    size = math.sqrt(sum(c * c for c in total))
    if size < 1e-9:
        raise FeatureError(
            f"{owner}: the faces next to the {end} profile do not point one way. Choose Normal "
            "or Direction instead."
        )
    return (total[0] / size, total[1] / size, total[2] / size)


def _centre(wire: TopoDS_Wire) -> Vec3:
    return profile_centre([_flat_face(wire)])


def facing(secs: list[Section], closed: bool) -> list[bool]:
    """For each section, True when its wire must be reversed so all face along the loft."""
    centres = [sec.centre() for sec in secs]
    out = []
    count = len(secs)
    for i, sec in enumerate(secs):
        before = centres[(i - 1) % count] if (closed or i > 0) else centres[i]
        after = centres[(i + 1) % count] if (closed or i < count - 1) else centres[i]
        d = (after[0] - before[0], after[1] - before[1], after[2] - before[2])
        n = sec.normal
        out.append(d[0] * n[0] + d[1] * n[1] + d[2] * n[2] < 0)
    return out


def _loft(
    owner: str,
    wires: list[TopoDS_Wire],
    ruled: bool,
    closed: bool,
    align: bool = True,
    tips: tuple[Vec3 | None, Vec3 | None] = (None, None),
) -> BRepOffsetAPI_ThruSections:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.gp import gp_Pnt

    maker = BRepOffsetAPI_ThruSections(not closed, ruled)
    maker.CheckCompatibility(align)
    if tips[0] is not None:
        maker.AddVertex(BRepBuilderAPI_MakeVertex(gp_Pnt(*tips[0])).Vertex())
    for w in [*wires, wires[0]] if closed else wires:
        maker.AddWire(w)
    if tips[1] is not None:
        maker.AddVertex(BRepBuilderAPI_MakeVertex(gp_Pnt(*tips[1])).Vertex())
    try:
        maker.Build()
    except Exception as exc:
        raise FeatureError(
            f"{owner}: the profiles could not be joined. Check that they do not cross, "
            "or change the connection points."
        ) from exc
    if not maker.IsDone():
        raise FeatureError(
            f"{owner}: the profiles could not be joined. Check that they do not cross, "
            "or change the connection points."
        )
    return maker


def _closed_solid(shape: TopoDS_Shape) -> TopoDS_Shape:
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_IN

    explorer = TopExp_Explorer(shape, TopAbs_SHELL)
    solid = BRepBuilderAPI_MakeSolid(TopoDS.Shell(explorer.Current())).Solid()
    classifier = BRepClass3d_SolidClassifier(solid)
    classifier.PerformInfinitePoint(1e-7)
    if classifier.State() == TopAbs_IN:
        solid.Reverse()
    return solid


def build_loft(feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
    """The lofted solid, named."""
    from fdcad.core.occ import BRepAlgoAPI_Cut

    owner, fid = feature.name, feature.id
    secs, issues = sections(feature, ctx)
    closed = feature.params.get("close_loft") is True
    ends = [str(feature.params.get(f"{e}_constraint", "default")) for e in ("start", "end")]
    ruled = ends == ["none", "none"]
    if closed and any(e not in ("default", "none") for e in ends):
        raise FeatureError(f"{owner}: a closed loft has no start or end. Set both to Default.")
    if closed and len(secs) < 3:
        raise FeatureError(
            f"{owner}: a closed loft needs at least three profiles. "
            "Add a profile or turn off Close Loft."
        )
    tips = (secs[0].point, secs[-1].point if len(secs) > 1 else None)
    if tips != (None, None):
        if (
            closed
            or thin_on(feature)
            or feature.refs.get("guides")
            or feature.refs.get("centerline")
        ):
            raise FeatureError(
                f"{owner}: a loft to a point works with open, solid lofts without guides. "
                "Turn off Close Loft and Thin Feature, or remove the guides."
            )
        for side, tip in (("start", tips[0]), ("end", tips[1])):
            kind = str(feature.params.get(f"{side}_constraint", "default"))
            if tip is not None and kind not in ("default", "none"):
                raise FeatureError(
                    f"{owner}: the {side} is a point, so it has no {side} tangency. "
                    f"Set the {side} constraint to Default."
                )
    all_secs = secs
    secs = [s for s in secs if s.point is None]
    if tips != (None, None) and len(all_secs) < 2:
        raise FeatureError(f"{owner}: a loft needs at least two profiles. Add another profile.")
    flips = facing(all_secs, closed)
    for sec, flip in zip(all_secs, flips, strict=True):
        if sec.outer is None:
            continue
        if flip:
            sec.outer = TopoDS.Wire(sec.outer.Reversed())
            sec.inner = [TopoDS.Wire(w.Reversed()) for w in sec.inner]
    # Connection points chosen by the user, and closed lofts, keep the wires as they are:
    # the kernel's own alignment works only for open lofts (D220).
    align = not closed and not any(
        isinstance(v, int) and not isinstance(v, bool) and v
        for k, v in feature.params.items()
        if k.startswith("connect_")
    )
    outer = [s.outer for s in secs if s.outer is not None]
    plain_first = outer[0] if outer else None
    if any(s.marks for s in secs):  # several connectors per profile (TR136, D2403)
        from fdcad.core.features.loft_connectors import matched_wires

        if closed or feature.refs.get("guides") or feature.refs.get("centerline"):
            raise FeatureError(
                f"{owner}: extra connectors work on open lofts without guides. Turn off "
                "Close Loft, or clear the connectors."
            )
        outer = matched_wires(owner, outer, [s.marks for s in secs if s.outer is not None])
        align = False
    start = end = None
    if not closed and tips[0] is None:
        start = _extra(feature, ctx, "start", all_secs[0], all_secs[1])
    if not closed and tips[1] is None:
        end = _extra(feature, ctx, "end", all_secs[-1], all_secs[-2])

    def twice(at: str) -> bool:  # TR136 (D1924): curvature holds two guiding copies
        return feature.params.get(f"{at}_constraint") == "curvature"

    def with_guides(wires: list[TopoDS_Wire]) -> list[TopoDS_Wire]:
        out = list(wires)
        if start is not None:
            out.insert(1, _moved(wires[0], start))
            if twice("start"):
                out.insert(2, _moved(wires[0], tuple(2 * c for c in start)))  # type: ignore[arg-type]
        if end is not None:
            out.insert(len(out) - 1, _moved(wires[-1], end))
            if twice("end"):
                out.insert(len(out) - 2, _moved(wires[-1], tuple(2 * c for c in end)))  # type: ignore[arg-type]
        return out

    wires = with_guides(outer)
    guides, centerline = loft_guides(feature, ctx)  # TR55 (D804)
    if guides or centerline is not None:
        if closed or thin_on(feature):
            raise FeatureError(
                f"{owner}: guide curves and a centerline work with open, solid lofts. Turn off "
                "Close Loft and Thin Feature, or remove the guides."
            )
        from fdcad.core.features.loft_guides import added_sections, check_count

        count = feature.params.get("sections")
        n = check_count(count.value) if isinstance(count, Param) else 4
        wires = added_sections(owner, outer, guides, centerline, n)
        ruled, align = False, False
    maker = _loft(owner, wires, ruled, closed, align, tips)
    shape = _closed_solid(maker.Shape()) if closed else maker.Shape()
    names: list[NamedFace] = []
    if not closed:
        names += [(f"{fid}/cap/start", TopoDS.Face(f)) for f in _faces(maker.FirstShape())]
        names += [(f"{fid}/cap/end", TopoDS.Face(f)) for f in _faces(maker.LastShape())]
    first = secs[0].profile
    if first is not None:
        explorer = TopExp_Explorer(outer[0], TopAbs_EDGE)
        while explorer.More():
            edge = TopoDS.Edge(explorer.Current())
            explorer.Next()
            entity = first.entity_of(edge)
            if entity is None and plain_first is not None and plain_first is not outer[0]:
                entity = _split_entity(first, plain_first, edge)  # a split piece (D2403)
            if entity is None:
                continue
            for made in shape_list(maker.Generated(edge)):
                if made.ShapeType() == TopAbs_FACE:
                    names.append((f"{fid}/side/{entity}", TopoDS.Face(made)))
    if thin_on(feature):
        if any(len(s.inner) != 1 for s in secs):
            raise FeatureError(f"{owner}: a thin loft needs closed profiles. Close each profile.")
        hollow = _loft(owner, with_guides([s.inner[0] for s in secs]), ruled, closed, align)
        inner = _closed_solid(hollow.Shape()) if closed else hollow.Shape()
        cut = BRepAlgoAPI_Cut(shape, inner)
        cut.SetFuzzyValue(FUZZY_TOLERANCE)
        cut.Build()
        if not cut.IsDone():
            raise FeatureError(f"{owner}: the thin wall could not be made. Change the thickness.")
        names = carry(names, cut.History())
        shape = cut.Shape()
    result = NamedShape(shape, restrict(names, shape, fid))
    if abs(volume_of(shape)) < 1e-9:  # every profile on one plane (D607)
        raise FeatureError(
            f"{owner}: the profiles lie on one plane, so the loft has no volume. "
            "Move a profile to another plane."
        )
    if not is_valid(None, result):
        raise FeatureError(
            f"{owner}: the loft intersects itself. Change the profiles' order or connection points."
        )
    return result, issues


def _split_entity(first: Profile, plain: TopoDS_Wire, piece: TopoDS_Edge) -> str | None:
    """The sketch entity of the unsplit edge ``piece`` was cut from (TR136, D2403)."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape

    from fdcad.core.features.loft_connectors import edges_of

    curve = BRepAdaptor_Curve(piece)
    mid = curve.Value((curve.FirstParameter() + curve.LastParameter()) / 2)
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex

    vertex = BRepBuilderAPI_MakeVertex(mid).Vertex()
    for edge in edges_of(plain):
        dist = BRepExtrema_DistShapeShape(vertex, edge)
        if dist.IsDone() and dist.Value() < 1e-6:
            return first.entity_of(edge)
    return None


def _faces(shape: TopoDS_Shape) -> list[Any]:
    from fdcad.core.naming.names import faces_of

    if shape.IsNull():
        return []
    if shape.ShapeType() == TopAbs_FACE:
        return [shape]
    return list(faces_of(shape))


@register
class Loft(FeatureType):
    """Joins profiles with a smooth solid and adds or removes it."""

    type_name = "loft"
    makes_solid = True
    params = (
        ParamSpec("operation", choices=("boss", "cut"), default="boss"),
        ParamSpec("merge", default=True, optional=True),
        ParamSpec("start_constraint", choices=CONSTRAINTS, optional=True),
        ParamSpec("end_constraint", choices=CONSTRAINTS, optional=True),
        ParamSpec("start_length", kind=Kind.LENGTH, optional=True),
        ParamSpec("end_length", kind=Kind.LENGTH, optional=True),
        ParamSpec("close_loft", default=False, optional=True),
        ParamSpec("show_section", kind=Kind.NUMBER, optional=True),  # TR139 (D1909)
        ParamSpec("thin_type", choices=THIN_TYPES, optional=True),
        ParamSpec("thin_thickness", kind=Kind.LENGTH, optional=True),
        ParamSpec("thin_thickness2", kind=Kind.LENGTH, optional=True),
        ParamSpec("thin_reverse", default=False, optional=True),
        ParamSpec("sections", kind=Kind.NUMBER, optional=True),  # TR55 (D804)
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Loft and combine with the part."""
        operation = str(feature.params.get("operation", "boss"))
        if operation == "cut" and thin_on(feature):
            raise FeatureError(
                f"{feature.name}: Thin Feature is for lofted bosses only. Turn off Thin Feature."
            )
        tool, issues = build_loft(feature, ctx)
        body = combine_or_keep(feature, ctx.body, tool, operation, ctx, issues)
        found = check_result(feature.id, feature.name, ctx.body, body, None)
        extras: dict[str, Any] = {}
        from fdcad.core.features.sweep_sections import loft_section, section_number

        k = section_number(feature)  # TR139 item 2 (D1909)
        if k:
            shape, line = loft_section(feature, tool.shape, ctx, k)
            extras = {"reference": shape, "report": [line]}
        return FeatureResult(
            body=body, issues=issues + expected_issues(feature, found), extras=extras
        )

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The lofted solid, for the preview."""
        return build_loft(feature, ctx)[0]


def loft_guides(feature: Feature, ctx: BuildContext) -> tuple[list[Any], TopoDS_Wire | None]:
    """``refs.guides`` as guides and ``refs.centerline`` as a wire (TR55, D804)."""
    from fdcad.core.features.sweep_guides import Guide, guide_wires

    guides = guide_wires(feature, ctx)
    ref = feature.refs.get("centerline")
    if not isinstance(ref, dict):
        return guides, None
    holder = Feature(feature.id, feature.type, feature.name, refs={"guides": [ref]})
    found = guide_wires(holder, ctx)
    line: Guide | None = found[0] if found else None
    return guides, line.wire if line is not None else None
