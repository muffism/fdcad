"""Pattern at model points (TUTORIAL_REVIEW_SPEC_2 TR365, DECISIONS D887).

Type ``point_pattern``. Copies the seed (``features``, ``faces`` or ``bodies``, as
the other patterns) to points picked on the part, with no sketch:

- ``refs.targets``: vertices, round edges (their centre) and round faces such as
  hole walls (their axis).
- ``refs.hole_faces``: flat faces; every round hole through them is a target.

Each copy moves the seed's reference point (``refs.point``, else the seed's centre)
onto its target. For a round edge, a hole axis or a hole of a face the copy keeps
the seed's height along that axis, so a copied counterbore or boss sits on the
face like the seed does. Key ``skip``: ``[k, 1]`` pairs, ``k`` counting targets
from 1 in pick order.
"""

from __future__ import annotations

import math
from typing import Any

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    register,
)
from fdcad.core.features.direct import translation
from fdcad.core.features.linear_pattern import COMMON_PARAMS, MAX_INSTANCES
from fdcad.core.features.patterns import Placement, apply_pattern
from fdcad.core.features.solids import check_result
from fdcad.core.naming.names import NamedShape

Vec3 = tuple[float, float, float]
#: A target: the point, and the axis along which the copy keeps the seed's height.
Target = tuple[Vec3, Vec3 | None]


def _circle(edge: Any) -> Target | None:
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAbs import GeomAbs_Circle

    curve = BRepAdaptor_Curve(edge)
    if curve.GetType() != GeomAbs_Circle:
        return None
    ax = curve.Circle().Axis()
    p, d = ax.Location(), ax.Direction()
    return (p.X(), p.Y(), p.Z()), (d.X(), d.Y(), d.Z())


def _round_face(face: Any) -> Target | None:
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder

    surface = BRepAdaptor_Surface(face)
    if surface.GetType() != GeomAbs_Cylinder:
        return None
    ax = surface.Cylinder().Axis()
    p, d = ax.Location(), ax.Direction()
    return (p.X(), p.Y(), p.Z()), (d.X(), d.Y(), d.Z())


def _holes_of(face: Any) -> list[Target]:
    """The centres of the round holes through a flat face: its inner circle loops."""
    from OCP.BRepTools import BRepTools
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_WIRE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    outer = BRepTools.OuterWire_s(TopoDS.Face(face))
    out: list[Target] = []
    wires = TopExp_Explorer(face, TopAbs_WIRE)
    while wires.More():
        wire = wires.Current()
        if not wire.IsSame(outer):
            edges = TopExp_Explorer(wire, TopAbs_EDGE)
            found = _circle(TopoDS.Edge(edges.Current())) if edges.More() else None
            if found is not None:
                out.append(found)
        wires.Next()
    return out


def targets(feature: Feature, ctx: BuildContext) -> tuple[list[Target], list[Issue]]:
    """Every target point, in pick order."""
    from fdcad.core.naming.resolve import resolve_edge, resolve_face, resolve_vertex

    name = feature.name
    out: list[Target] = []
    issues: list[Issue] = []
    for ref in feature.refs.get("targets") or []:
        kind = ref.get("kind") if isinstance(ref, dict) else None
        if kind == "vertex":
            point, found = resolve_vertex(ctx.body, ref, name)
            out.append((point, None))
        elif kind == "edge":
            edge, found = resolve_edge(ctx.body, ref, name)
            target = _circle(edge)
            if target is None:
                raise FeatureError(f"{name}: a picked edge is not round. Pick a round edge.")
            out.append(target)
        elif kind == "face":
            face, found = resolve_face(ctx.body, ref, name)
            target = _round_face(face)
            if target is None:
                raise FeatureError(f"{name}: a picked face is not round. Pick a hole wall.")
            out.append(target)
        else:
            raise FeatureError(f"{name}: pick vertices, round edges or hole walls.")
        issues += found
    for ref in feature.refs.get("hole_faces") or []:
        face, found = resolve_face(ctx.body, ref, name)
        issues += found
        holes = _holes_of(face)
        if not holes:
            raise FeatureError(f"{name}: a picked face has no round holes. Pick another face.")
        out += holes
    return out, issues


def _tools_centre(feature: Feature, ctx: BuildContext) -> Vec3:
    """The centre of the seed features' own solids (what they add or cut). The faces
    they leave on the part can include a whole face they touched, which would pull the
    centre away from the seed."""
    from fdcad.core.features.patterns import _seed_tools
    from fdcad.core.features.solids import compound
    from fdcad.core.naming.names import centroid

    tools = [tool.shape for _seed, tool, _op in _seed_tools(feature, ctx)]
    if not tools:
        raise FeatureError(f"{feature.name}: pick features, faces or bodies to copy.")
    return centroid(compound(tools))


@register
class PointPattern(FeatureType):
    """Copies features, faces or bodies to points on the part."""

    type_name = "point_pattern"
    makes_solid = True
    params = COMMON_PARAMS

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Copy the seed and check the result."""
        body, issues = self._build(feature, ctx, partial=False)
        issues += check_result(feature.id, feature.name, ctx.body, body, None)
        if feature.refs.get("bodies"):
            issues = [i for i in issues if i.code != "separate_body"]
        return FeatureResult(body=body, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The patterned part, for the live preview."""
        return self._build(feature, ctx, feature.params.get("preview") == "partial")[0]

    def _build(
        self, feature: Feature, ctx: BuildContext, partial: bool
    ) -> tuple[NamedShape, list[Issue]]:
        placements, issues = self.placements(feature, ctx)
        if partial:
            placements = placements[:1]
        outcome = apply_pattern(feature, ctx, placements)
        return outcome.body, issues + outcome.issues

    def placements(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[list[Placement], list[Issue]]:
        """One copy per target, the seed's own spot left out."""
        from fdcad.core.features.geometry_refs import resolve_placement
        from fdcad.core.features.seeds import seed_centre

        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part is empty. Add a body first.")
        found, issues = targets(feature, ctx)
        if not found:
            raise FeatureError(
                f"{name}: pick vertices, round edges, hole walls or faces with holes."
            )
        if len(found) > MAX_INSTANCES:
            raise FeatureError(f"{name}: at most {MAX_INSTANCES} instances. Pick fewer points.")
        if feature.refs.get("point") is not None:
            place = resolve_placement(ctx, feature.refs["point"], name, "point")
            start = place.point
            issues += place.issues
        elif feature.refs.get("features") and not feature.refs.get("geometry"):
            start = _tools_centre(feature, ctx)
        else:
            start = seed_centre(feature, ctx)
        out: list[Placement] = []
        for k, (point, axis) in enumerate(found, start=1):
            delta = (point[0] - start[0], point[1] - start[1], point[2] - start[2])
            if axis is not None:  # keep the seed's height along the axis
                along = sum(delta[i] * axis[i] for i in range(3))
                delta = (
                    delta[0] - along * axis[0],
                    delta[1] - along * axis[1],
                    delta[2] - along * axis[2],
                )
            if math.sqrt(sum(c * c for c in delta)) < 1e-6:
                continue  # the seed's own spot
            out.append(Placement((k, 1), translation(delta)))
        return out, issues
