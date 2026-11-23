"""Face fillet with a hold line (TR29, DECISIONS D1409).

A face fillet (``fillet_type`` "face") with ``method`` "hold_line" and
``refs.hold_lines`` (edges on one face set): the round meets that face along the
hold line, so its size follows the gap between the hold line and the edge where
the sets meet. The face between them is used up by the round and goes.

The kernel's fillet cannot use up a whole face (the round would end exactly on
the face's far edge), so the round is built here, for straight edges between two
flat faces, like the shaped profiles (``fillet_profile``): a circular cross
section touching both faces at the hold line's distance, at each end of the edge;
a prism when the two distances match, else a ruled solid between the two
sections. It is cut from a convex edge or added to a concave one.
"""

from __future__ import annotations

import math

from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeVertex,
    BRepBuilderAPI_MakeWire,
)
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
from OCP.gp import gp_Pnt
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Shape, TopoDS_Wire

from fdcad.core.document.model import Feature
from fdcad.core.features.base import BuildContext, FeatureError, Issue
from fdcad.core.features.fillet_profile import Corner, corner_of, profile_curve
from fdcad.core.features.solids import compound
from fdcad.core.naming.names import NamedFace, NamedShape

REFS = "hold_lines"


def uses_hold_line(feature: Feature) -> bool:
    """True for a face fillet with the Hold Line method."""
    return (
        feature.params.get("fillet_type") == "face" and feature.params.get("method") == "hold_line"
    )


def hold_shape(feature: Feature, ctx: BuildContext) -> tuple[TopoDS_Shape, list[Issue]]:
    """The hold line edges as one shape."""
    from fdcad.core.features.modify import resolve_edges

    if not feature.refs.get(REFS):
        raise FeatureError(
            f"{feature.name}: the Hold Line method needs hold line edges. "
            "Pick the edges the round should follow."
        )
    found, issues = resolve_edges(feature, ctx, REFS)
    return compound([e for _n, e in found]), issues


def _distance(point: gp_Pnt, shape: TopoDS_Shape) -> float:
    vertex = BRepBuilderAPI_MakeVertex(point).Vertex()
    dist = BRepExtrema_DistShapeShape(vertex, shape)
    return float(dist.Value()) if dist.IsDone() else 0.0


def _section(corner: Corner, at: gp_Pnt, d: float) -> tuple[TopoDS_Wire, TopoDS_Edge]:
    p0 = gp_Pnt(at.XYZ().Added(corner.u_first.Scaled(d).XYZ()))
    p2 = gp_Pnt(at.XYZ().Added(corner.u_second.Scaled(d).XYZ()))
    curve = profile_curve("circular", at, p0, p2, corner.angle, 0.5)
    arc = BRepBuilderAPI_MakeEdge(curve).Edge()
    wire = BRepBuilderAPI_MakeWire()
    wire.Add(BRepBuilderAPI_MakeEdge(at, p0).Edge())
    wire.Add(arc)
    wire.Add(BRepBuilderAPI_MakeEdge(p2, at).Edge())
    return wire.Wire(), arc


def tool_for(
    owner: str, name: str, corner: Corner, hold: TopoDS_Shape, role: str
) -> tuple[TopoDS_Shape, list[NamedFace]]:
    """The solid between the sharp corner and the round along one edge."""
    start = corner.start
    end = gp_Pnt(start.XYZ().Added(corner.along.XYZ()))
    gaps = [_distance(start, hold), _distance(end, hold)]
    if min(gaps) < 1e-6:
        raise FeatureError(
            f"{owner}: the hold line touches edge {name}, so the round has no size there. "
            "Pick a hold line apart from the edge."
        )
    sections = BRepOffsetAPI_ThruSections(True, True)
    for point, gap in zip((start, end), gaps, strict=True):
        wire, _arc = _section(corner, point, gap)
        sections.AddWire(wire)
    sections.Build()
    if not sections.IsDone():
        raise FeatureError(
            f"{owner}: the round along edge {name} could not be made. Pick another hold line."
        )
    shape = sections.Shape()
    named: list[NamedFace] = []
    from fdcad.core.naming.names import faces_of
    from fdcad.core.plane_normal import plane_normal

    for face in faces_of(shape):
        if plane_normal(face) is None:  # the curved face is the round
            named.append((role, TopoDS.Face(face)))
    return shape, named


def hold_round(
    feature: Feature,
    ctx: BuildContext,
    body: NamedShape,
    items: list[tuple[str, TopoDS_Edge]],
) -> tuple[NamedShape, list[Issue]]:
    """Round the edges where the face sets meet so the rounds follow the hold lines."""
    from fdcad.core.features.solids import combine

    hold, issues = hold_shape(feature, ctx)
    cut: list[TopoDS_Shape] = []
    add: list[TopoDS_Shape] = []
    cut_names: list[NamedFace] = []
    add_names: list[NamedFace] = []
    for position, (name, edge) in enumerate(items, start=1):
        corner = corner_of(body, edge)
        if corner is None or not math.isfinite(corner.angle):
            raise FeatureError(
                f"{feature.name}: edge {position} cannot take a hold line round: it is made "
                "only on straight edges between two flat faces. Use the Radius method.",
                highlight=[name],
            )
        shape, named = tool_for(feature.name, name, corner, hold, f"{feature.id}/fillet/{name}")
        (cut if corner.convex else add).append(shape)
        (cut_names if corner.convex else add_names).extend(named)
    current = body
    if cut:
        current = combine(
            feature.id, feature.name, current, NamedShape(compound(cut), cut_names), "cut"
        )
    if add:
        current = combine(
            feature.id, feature.name, current, NamedShape(compound(add), add_names), "boss"
        )
    return current, issues


__all__ = ["REFS", "hold_round", "uses_hold_line"]
