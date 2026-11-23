"""Helpers shared by features that change the part's faces: fillet, chamfer, shell,
draft and the drafted extrude.

Names are carried through the kernel operation's history (PLAN section 6 item 3).
New faces are named by the feature from the edge or face that made them.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import BuildContext, FeatureError, Fix, Issue
from fdcad.core.naming.names import NamedFace, NamedShape, carry, restrict
from fdcad.core.occ import ShapeList, ShapeListMap, ShapeMap, shape_list


class PartialResultError(FeatureError):
    """Some picked items fail. ``partial`` is the result without them, if one builds.

    The feature stops with an error; the user decides with a fix button whether
    to leave the failing items out (PLAN 5A item 5, CLAUDE.md rule 12).
    """

    def __init__(
        self,
        message: str,
        partial: NamedShape | None,
        failed: list[str],
        fixes: list[Fix] | None = None,
    ) -> None:
        super().__init__(message, fixes, failed)
        self.partial = partial
        self.failed = failed


class _Maker(Protocol):
    def Modified(self, shape: TopoDS_Shape, /) -> ShapeList: ...  # noqa: N802

    def IsDeleted(self, shape: TopoDS_Shape, /) -> bool: ...  # noqa: N802


class MakerHistory:
    """A kernel maker's Modified and IsDeleted, in the form ``carry`` expects."""

    def __init__(self, maker: _Maker) -> None:
        self.maker = maker

    def Modified(self, shape: TopoDS_Shape, /) -> ShapeList:  # noqa: N802
        """Shapes made from ``shape``."""
        return self.maker.Modified(shape)

    def IsRemoved(self, shape: TopoDS_Shape, /) -> bool:  # noqa: N802
        """True when ``shape`` is gone."""
        return bool(self.maker.IsDeleted(shape))


def edges_of(shape: TopoDS_Shape) -> list[TopoDS_Edge]:
    """Distinct edges of ``shape`` in a stable order."""
    emap = ShapeMap()
    TopExp.MapShapes_s(shape, TopAbs_EDGE, emap)
    return [TopoDS.Edge(emap.FindKey(i)) for i in range(1, emap.Extent() + 1)]


def face_edges(face: TopoDS_Face) -> list[TopoDS_Edge]:
    """Distinct edges of one face."""
    return edges_of(face)


def edge_faces(body: TopoDS_Shape, edge: TopoDS_Edge) -> list[TopoDS_Face]:
    """The distinct faces that meet at ``edge``."""
    amap = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(body, TopAbs_EDGE, TopAbs_FACE, amap)
    index = amap.FindIndex(edge)
    out: list[TopoDS_Face] = []
    if index:
        for f in shape_list(amap.FindFromIndex(index)):
            if not any(f.IsSame(g) for g in out):
                out.append(TopoDS.Face(f))
    return out


def unique(edges: Sequence[TopoDS_Edge]) -> list[TopoDS_Edge]:
    """``edges`` without repeats, first one kept."""
    out: list[TopoDS_Edge] = []
    for e in edges:
        if not any(e.IsSame(x) for x in out):
            out.append(e)
    return out


def new_faces(before: TopoDS_Shape, after: NamedShape) -> list[TopoDS_Face]:
    """Faces of ``after`` that are not faces of ``before`` (new or changed)."""
    old = ShapeMap()
    TopExp.MapShapes_s(before, TopAbs_FACE, old)
    out: list[TopoDS_Face] = []
    explorer = TopExp_Explorer(after.shape, TopAbs_FACE)
    while explorer.More():
        face = explorer.Current()
        if not old.Contains(face) and not any(face.IsSame(f) for f in out):
            out.append(TopoDS.Face(face))
        explorer.Next()
    return out


@dataclass
class ResultPreview(NamedShape):
    """A modify feature's preview (D583).

    ``shape`` holds the new and changed faces, as before. ``full`` is the whole
    result, which the view shows in place of the part, and ``accent`` the faces
    the feature made (for example the round faces of a fillet), which it tints.
    Showing the result instead of laying faces over the part avoids the stripes
    two different meshes of one surface make.
    """

    full: TopoDS_Shape | None = None
    accent: list[TopoDS_Face] = field(default_factory=list)
    #: Move Face (TR263 item 2, D798): faces next to the moved ones that stay still, and
    #: faces that stretch to follow. ``accent`` holds the moved faces.
    held: list[TopoDS_Face] = field(default_factory=list)
    stretched: list[TopoDS_Face] = field(default_factory=list)


def changed_faces(before: TopoDS_Shape, after: NamedShape, fid: str = "") -> NamedShape:
    """The new and changed faces, plus the whole result, for the live preview (D109, D583).

    ``fid`` is the feature's id: faces named after it are the ones it made.
    When none are named so, every new or changed face is tinted.
    """
    from fdcad.core.features.solids import compound

    faces = new_faces(before, after)
    accent: list[TopoDS_Face] = []
    for name, face in after.faces:
        if fid and name.split("/", 1)[0] == fid and not any(face.IsSame(f) for f in accent):
            accent.append(face)
    return ResultPreview(compound(faces), [], full=after.shape, accent=accent or faces)


def rename(
    body: NamedShape, maker: Any, shape: TopoDS_Shape, fid: str, extra: list[NamedFace]
) -> NamedShape:
    """Carry ``body``'s names through ``maker`` onto ``shape`` and add ``extra`` names."""
    names = carry(body.faces, MakerHistory(maker))
    return NamedShape(shape, restrict(names + extra, shape, fid))


def require_body(feature: Feature, ctx: BuildContext) -> NamedShape:
    """The part before ``feature``. Raises when there is none."""
    if ctx.body is None:
        raise FeatureError(f"{feature.name} needs a body. Add a boss feature first.")
    return ctx.body


def length(feature: Feature, name: str, label: str, positive: bool = True) -> float:
    """A length parameter in mm. Raises when it is missing or not greater than zero."""
    value = feature.params.get(name)
    if not isinstance(value, Param):
        raise FeatureError(f"{feature.name}: the {label} is missing. Enter a value.")
    if positive and value.value <= 0:
        raise FeatureError(
            f"{feature.name}: the {label} must be greater than zero. Enter a larger value."
        )
    return value.value


def piece_base(name: str) -> str:
    """The picked edge name of a piece name ``edge(...)#k`` (D606); other names unchanged."""
    head, sep, tail = name.rpartition(")#")
    return f"{head})" if sep and tail.isdigit() else name


def resolve_edges(
    feature: Feature, ctx: BuildContext, key: str = "edges", pieces: bool = False
) -> tuple[list[tuple[str, TopoDS_Edge]], list[Issue]]:
    """Every edge reference in ``refs[key]``, as (name, edge), plus snapshot warnings.

    A lost edge is an error naming it, so the user can pick it again (CLAUDE.md 5.12).
    With ``pieces``, a picked edge that an earlier edit split gives every piece,
    named ``<name>#1``, ``<name>#2`` and so on (D606).
    """
    from fdcad.core.naming.resolve import resolve_edge, resolve_edge_pieces

    body = require_body(feature, ctx)
    refs = feature.refs.get(key)
    if not isinstance(refs, list) or not refs:
        raise FeatureError(f"{feature.name}: no edges are picked. Pick edges in the view.")
    out: list[tuple[str, TopoDS_Edge]] = []
    issues: list[Issue] = []
    lost: list[str] = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        name = str(ref.get("name", ""))
        try:
            if pieces:
                edges, found = resolve_edge_pieces(body, ref, feature.name)
            else:
                edge, found = resolve_edge(body, ref, feature.name)
                edges = [edge]
        except FeatureError:
            lost.append(name)
            continue
        issues.extend(found)
        if len(edges) == 1:
            out.append((name, edges[0]))
        else:
            out.extend((f"{name}#{k}", e) for k, e in enumerate(edges, start=1))
    if lost:
        raise FeatureError(lost_message(feature, ctx, lost, "item(s)"), highlight=lost)
    return out, issues


def seam_picks(feature: Feature, ctx: BuildContext, what: str) -> list[Issue]:
    """A warning for each picked edge that is the seam of a round face (D1084).

    A seam is where a closed face (a cylinder, a cone) meets itself, not an edge
    between two faces, so there is nothing to round or bevel there and the kernel
    leaves it out with no word. On a gearbox shaft a pick on the end of a step's
    outline found the seam that starts there, and a fillet of three shoulders
    rounded two and said nothing.
    """
    from OCP.BRep import BRep_Tool

    from fdcad.core.features.base import FeatureState

    if ctx.body is None or not feature.refs.get("edges"):
        return []
    try:
        picked, _found = resolve_edges(feature, ctx)
    except FeatureError:
        return []  # the build itself says what is missing
    owners = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(ctx.body.shape, TopAbs_EDGE, TopAbs_FACE, owners)
    seams = []
    for name, edge in picked:
        if not owners.Contains(edge):
            continue
        faces = shape_list(owners.FindFromKey(edge))
        if any(BRep_Tool.IsClosed_s(edge, TopoDS.Face(f)) for f in faces):
            seams.append(name)
    if not seams:
        return []
    which = "edge is the seam" if len(seams) == 1 else f"{len(seams)} edges are seams"
    return [
        Issue(
            FeatureState.WARNING,
            f"{feature.name}: a picked {which} of a round face, where the face meets "
            f"itself, so nothing is {what} there. Pick the edge you meant, or remove it.",
            code="seam_edge",
            highlight=seams,
        )
    ]


def resolve_faces(
    feature: Feature, ctx: BuildContext, key: str, required: bool = True
) -> tuple[list[tuple[str, TopoDS_Face]], list[Issue]]:
    """Every face reference in ``refs[key]``, as (name, face), plus snapshot warnings."""
    from fdcad.core.naming.resolve import resolve_face

    body = require_body(feature, ctx)
    refs = feature.refs.get(key)
    if not isinstance(refs, list) or not refs:
        if required:
            raise FeatureError(f"{feature.name}: no faces are picked. Pick faces in the view.")
        return [], []
    out: list[tuple[str, TopoDS_Face]] = []
    issues: list[Issue] = []
    lost: list[str] = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        name = str(ref.get("name", ""))
        try:
            face, found = resolve_face(body, ref, feature.name)
        except FeatureError:
            lost.append(name)
            continue
        issues.extend(found)
        out.append((name, face))
    if lost:
        raise FeatureError(lost_message(feature, ctx, lost, "face(s)"), highlight=lost)
    return out, issues


def lost_message(feature: Feature, ctx: BuildContext, lost: list[str], what: str) -> str:
    """The error for picks that were lost, naming an earlier feature that caused it (D600).

    A pick on faces made by a feature that failed or is suppressed is lost
    because that feature made nothing, not because the pick is wrong. The
    message then names that feature, so the user fixes it instead of picking again.
    """
    head = f"{feature.name}: {len(lost)} picked {what} were lost: {', '.join(lost)}."
    cause = lost_cause(ctx, lost)
    return f"{head} {cause or 'Pick them again or remove them from the list.'}"


def lost_cause(ctx: BuildContext, names: Sequence[str]) -> str:
    """Why picks in ``names`` were lost when an earlier feature failed or is suppressed.

    Returns "" when every feature that made them built (D600).
    """
    for name in names:
        for fid in _owners(name):
            cause = _cause(ctx, fid)
            if cause:
                return cause
    return ""


def _owners(name: str) -> list[str]:
    """The ids of the features that made the faces in a face, edge or vertex name."""
    inner = name[name.find("(") + 1 : name.rfind(")")] if "(" in name else name
    out: list[str] = []
    for part in inner.split("|"):
        fid = part.split("/", 1)[0]
        if fid and fid not in out and "/" in part:
            out.append(fid)
    return out


def _cause(ctx: BuildContext, fid: str) -> str:
    """Why the earlier feature ``fid`` made no faces, or "" when it built."""
    from fdcad.core.features.base import FeatureState

    try:
        earlier = ctx.document.feature(fid)
    except KeyError:
        return ""
    name = earlier.name
    if earlier.suppressed:
        return f"{name} is suppressed. Unsuppress {name} or pick again."
    result = ctx.results.get(fid)
    if result is not None and result.state is FeatureState.ERROR:
        return f"{name} has an error. Fix {name} first."
    return ""


def tangent_chain(
    body: TopoDS_Shape, edges: Sequence[TopoDS_Edge], straight_only: bool = False
) -> list[TopoDS_Edge]:
    """``edges`` plus every edge joined to them smoothly (tangent propagation, P2.4 item 2).

    With ``straight_only`` the walk only goes on through straight edges, so it stops at
    a curved one (Miter Flange Propagate, TR30.3)."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.TopAbs import TopAbs_VERTEX

    vmap = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(body, TopAbs_VERTEX, TopAbs_EDGE, vmap)

    def tangent_at(edge: TopoDS_Edge, vertex: TopoDS_Shape) -> Any:
        curve = BRepAdaptor_Curve(edge)
        p = BRep_Tool.Pnt_s(TopoDS.Vertex(vertex))
        first = curve.Value(curve.FirstParameter())
        u = curve.FirstParameter() if first.Distance(p) < 1e-6 else curve.LastParameter()
        from OCP.gp import gp_Pnt, gp_Vec

        point, tangent = gp_Pnt(), gp_Vec()
        curve.D1(u, point, tangent)
        return tangent

    out = unique(edges)
    queue = list(out)
    while queue:
        edge = queue.pop()
        explorer = TopExp_Explorer(edge, TopAbs_VERTEX)
        while explorer.More():
            vertex = explorer.Current()
            explorer.Next()
            index = vmap.FindIndex(vertex)
            if not index:
                continue
            here = tangent_at(edge, vertex)
            for other in shape_list(vmap.FindFromIndex(index)):
                other_edge = TopoDS.Edge(other)
                if any(other_edge.IsSame(e) for e in out) or BRep_Tool.Degenerated_s(other_edge):
                    continue
                if straight_only:
                    from fdcad.core.features.solids import line_ends

                    if line_ends(other_edge) is None:
                        continue
                there = tangent_at(other_edge, vertex)
                if here.Magnitude() < 1e-9 or there.Magnitude() < 1e-9:
                    continue
                if here.IsParallel(there, 1e-3):
                    out.append(other_edge)
                    queue.append(other_edge)
    return out
