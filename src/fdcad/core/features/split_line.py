"""Split Line: divide faces into regions without changing the volume (TR60, D1414).

Params: ``method`` "projection" (default) or "intersection"; for projection,
``reverse`` and ``both`` as Projected Curve (D291).

Refs: ``faces`` (the faces to split), ``sketch`` (projection: its curves are
projected onto the faces along ``direction`` or the sketch normal) and ``plane``
(intersection: a reference plane or flat face; the faces are split where it
crosses them).

The new edges can be picked for a fillet, and the regions for Draft, Move Face or
a colour. A split face's pieces are named ``<face name>#k`` by position, as for
any split (PLAN section 6). Deleting the feature joins the faces again.

Silhouette (TR60, D1810): ``refs.direction`` (a plane, flat face or straight
edge) is the pull; each picked cylinder, cone or sphere is split along its outline
(see ``silhouette``). Intersection with a body (D1810): ``refs.tool_body`` (a face of
another body of the part) splits the faces where that body's faces cross them.
"""

from __future__ import annotations

from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepFeat import BRepFeat_SplitShape
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt
from OCP.TopoDS import TopoDS_Edge, TopoDS_Face

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.curves import edges_in
from fdcad.core.features.modify import MakerHistory, require_body, resolve_faces
from fdcad.core.features.solids import check_result
from fdcad.core.naming.names import NamedShape, carry, restrict
from fdcad.core.occ import BRepAlgoAPI_Section

METHODS = ("projection", "intersection", "silhouette")  # silhouette: TR60 (D1810)


def _on(edge: TopoDS_Edge, face: TopoDS_Face) -> bool:
    dist = BRepExtrema_DistShapeShape(edge, face)
    return bool(dist.IsDone() and dist.Value() < 1e-5)


def _projected(feature: Feature, ctx: BuildContext) -> tuple[list[TopoDS_Edge], list[Issue]]:
    from fdcad.core.features.projected_curve import _onto_faces, _sketch

    out = _sketch(feature, ctx, "sketch", "sketch")
    shape, issues = _onto_faces(feature, ctx, out)
    return edges_in(shape), issues


def _one(ref: object) -> object:
    if isinstance(ref, list):  # the panel stores one pick as a list
        return ref[0] if ref else None
    return ref


def _outlines(
    feature: Feature, ctx: BuildContext, found: list[tuple[str, TopoDS_Face]]
) -> tuple[list[TopoDS_Edge], list[Issue]]:
    """Silhouette edges of the picked faces along the pull (TR60, D1810)."""
    from fdcad.core.features.geometry_refs import resolve_placement
    from fdcad.core.features.silhouette import silhouette_plane

    pick = _one(feature.refs.get("direction"))
    if not isinstance(pick, dict):
        raise FeatureError(
            f"{feature.name}: no direction of pull is picked. Pick a plane, flat face or edge."
        )
    placed = resolve_placement(ctx, pick, feature.name, "direction")
    edges: list[TopoDS_Edge] = []
    for name, face in found:
        try:
            plane = silhouette_plane(face, placed.direction)
        except ValueError as exc:
            raise FeatureError(
                f"{feature.name}: face {name} has no outline to split along: {exc}. "
                "Remove it from the list, or use Projection.",
                highlight=[name],
            ) from exc
        if plane is None:
            continue
        section = BRepAlgoAPI_Section(face, plane)
        section.Build()
        if section.IsDone():
            edges += edges_in(section.Shape())
    return edges, placed.issues


def _body_crossed(
    feature: Feature, ctx: BuildContext, faces: list[TopoDS_Face], ref: dict[str, object]
) -> tuple[list[TopoDS_Edge], list[Issue]]:
    """Where another body of the part crosses the faces (TR60, D1810)."""
    from fdcad.core.features.solids import solids
    from fdcad.core.naming.resolve import resolve_face

    body = require_body(feature, ctx)
    face, issues = resolve_face(body, ref, feature.name)
    tool = next((s for s in solids(body.shape) if _owns(s, face)), None)
    if tool is None:
        raise FeatureError(f"{feature.name}: the splitting body was not found. Pick it again.")
    if any(_owns(tool, f) for f in faces):
        raise FeatureError(
            f"{feature.name}: the splitting body is the body of the faces. "
            "Pick a face of another body."
        )
    edges: list[TopoDS_Edge] = []
    for target in faces:
        section = BRepAlgoAPI_Section(target, tool)
        section.Build()
        if section.IsDone():
            edges += edges_in(section.Shape())
    return edges, issues


def _owns(solid: object, face: TopoDS_Face) -> bool:
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer

    explorer = TopExp_Explorer(solid, TopAbs_FACE)
    while explorer.More():
        if explorer.Current().IsSame(face):
            return True
        explorer.Next()
    return False


def _crossed(
    feature: Feature, ctx: BuildContext, faces: list[TopoDS_Face]
) -> tuple[list[TopoDS_Edge], list[Issue]]:
    from fdcad.core.features.datum import resolve_pick

    tool = _one(feature.refs.get("tool_body"))
    if isinstance(tool, dict):  # TR60 (D1810): another body
        return _body_crossed(feature, ctx, faces, tool)
    ref = feature.refs.get("plane")
    if isinstance(ref, list):  # the panel stores one pick as a list
        ref = ref[0] if ref else None
    if not isinstance(ref, dict):
        raise FeatureError(
            f"{feature.name}: no plane or body is picked. Pick a plane, a flat face or a "
            "face of another body."
        )
    geo, issues = resolve_pick(ref, ctx, feature.name)
    if geo.kind != "plane" or geo.direction is None:
        raise FeatureError(
            f"{feature.name}: the splitting item must be a plane or a flat face. Pick one of those."
        )
    plane = gp_Pln(gp_Pnt(*geo.point), gp_Dir(*geo.direction))
    edges: list[TopoDS_Edge] = []
    for face in faces:
        section = BRepAlgoAPI_Section(face, plane)
        section.Build()
        if section.IsDone():
            edges += edges_in(section.Shape())
    return edges, issues


def split_with(
    feature: Feature, body: NamedShape, faces: list[TopoDS_Face], edges: list[TopoDS_Edge]
) -> NamedShape:
    """``body`` with ``faces`` split by the ``edges`` that lie on them; pieces are named
    ``<face name>#k`` by position. Raises FeatureError when nothing splits."""
    maker = BRepFeat_SplitShape(body.shape)
    added = 0
    for edge in edges:
        for face in faces:
            if _on(edge, face):
                maker.Add(edge, face)
                added += 1
                break
    if not added:
        raise FeatureError(
            f"{feature.name}: no split line lies on the picked faces. "
            "Pick the faces the line crosses, or move the sketch or plane."
        )
    try:
        maker.Build()
        done = maker.IsDone()
    except Exception:  # kernel failure becomes a feature error
        done = False
    if not done:
        raise FeatureError(
            f"{feature.name}: the faces could not be split. The line must cross a face from "
            "edge to edge or close on itself. Change the sketch or plane."
        )
    shape = maker.Shape()
    names = carry(body.faces, MakerHistory(maker))
    return NamedShape(shape, restrict(names, shape, f"{feature.id}/split"))


@register
class SplitLine(FeatureType):
    """Divides faces into regions with new edges; the volume stays the same."""

    type_name = "split_line"
    makes_solid = True
    params = (
        ParamSpec("method", choices=METHODS, default="projection", optional=True),
        ParamSpec("reverse", default=False, optional=True),
        ParamSpec("both", default=False, optional=True),
    )

    def _build(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        body = require_body(feature, ctx)
        found, issues = resolve_faces(feature, ctx, "faces")
        faces = [f for _n, f in found]
        method = feature.params.get("method", "projection")
        if method == "intersection":
            edges, more = _crossed(feature, ctx, faces)
        elif method == "silhouette":
            edges, more = _outlines(feature, ctx, found)
        else:
            edges, more = _projected(feature, ctx)
        issues += more
        return split_with(feature, body, faces, edges), issues

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Split the faces."""
        result, issues = self._build(feature, ctx)
        issues = issues + check_result(feature.id, feature.name, ctx.body, result, None)
        return FeatureResult(body=result, issues=issues)
