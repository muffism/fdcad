"""Fixed Edge draft (TR323, D1804): each face tilts about one of its own edges.

``draft_type`` "fixed_edge". ``refs.faces`` are the faces to draft and
``refs.fixed_edges`` the edges that stay where they are: each face uses the picked
edge that lies on it. ``refs.neutral`` (a plane or flat face) gives only the pull
direction. A fixed edge must be straight and square to the pull, so the face can
turn about it; each face gets its own neutral plane through its fixed edge and the
kernel tilts all the faces in one call. Faces keep their names.
"""

from __future__ import annotations

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepOffsetAPI import BRepOffsetAPI_DraftAngle
from OCP.GeomAbs import GeomAbs_Line
from OCP.gp import gp_Dir, gp_Pln
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face

from fdcad.core.document.model import Feature
from fdcad.core.features.base import BuildContext, FeatureError, Issue, Vec3
from fdcad.core.features.modify import edges_of, require_body, resolve_edges, resolve_faces
from fdcad.core.naming.names import NamedShape, restrict

#: How far from square to the pull a fixed edge may be (as a cosine).
_SQUARE_TOL = 1e-4


def _edge_on(
    face: TopoDS_Face, edges: list[tuple[str, TopoDS_Edge]]
) -> tuple[str, TopoDS_Edge] | None:
    own = edges_of(face)
    for name, edge in edges:
        if any(edge.IsSame(e) for e in own):
            return name, edge
    return None


def fixed_edge_draft(
    feature: Feature, ctx: BuildContext, pull: Vec3, angle: float
) -> tuple[NamedShape, list[Issue]]:
    """Tilt each picked face by ``angle`` about its fixed edge."""
    owner = feature.name
    body = require_body(feature, ctx)
    faces, issues = resolve_faces(feature, ctx, "faces")
    if not feature.refs.get("fixed_edges"):
        raise FeatureError(
            f"{owner}: no fixed edges are picked. Pick one edge on each face to draft."
        )
    edges, more = resolve_edges(feature, ctx, "fixed_edges")
    issues = issues + more
    direction = gp_Dir(*pull)
    maker = BRepOffsetAPI_DraftAngle(body.shape)
    for name, face in faces:
        found = _edge_on(face, edges)
        if found is None:
            raise FeatureError(
                f"{owner}: face {name} has no fixed edge. Pick one of its edges as the fixed edge.",
                highlight=[name],
            )
        edge_name, edge = found
        curve = BRepAdaptor_Curve(edge)
        if curve.GetType() != GeomAbs_Line:
            raise FeatureError(
                f"{owner}: fixed edge {edge_name} is not straight. Pick a straight edge.",
                highlight=[edge_name],
            )
        line = curve.Line()
        if abs(line.Direction().Dot(direction)) > _SQUARE_TOL:
            raise FeatureError(
                f"{owner}: fixed edge {edge_name} is not square to the pull direction, so the "
                "face cannot turn about it. Pick an edge square to the pull, or another plane.",
                highlight=[edge_name],
            )
        neutral = gp_Pln(line.Location(), direction)
        maker.Add(face, direction, angle, neutral, True)
        if not maker.AddDone():
            raise FeatureError(
                f"{owner}: face {name} cannot be drafted about its fixed edge. "
                "Remove it or pick another edge.",
                highlight=[name],
            )
    try:
        maker.Build()
    except Exception as exc:
        raise FeatureError(
            f"{owner} failed: the faces could not be tilted together. "
            "Use a smaller angle or fewer faces."
        ) from exc
    if not maker.IsDone():
        raise FeatureError(
            f"{owner} failed: the faces could not be tilted together. "
            "Use a smaller angle or fewer faces."
        )
    shape = maker.Shape()
    names = [(n, TopoDS.Face(maker.ModifiedShape(f))) for n, f in body.faces]
    return NamedShape(shape, restrict(names, shape, f"{feature.id}/face")), issues
