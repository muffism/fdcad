"""Split bodies with planes, faces or sketches (PHASE3_SPEC P3.4 item 3, DECISIONS D233).

Refs:
- ``tools``: planes (``{"feature": "f2"}``) and flat faces (treated as endless),
  curved faces (used as they are, so they must cut right through), and sketches
  (``{"feature": "f9"}`` of a sketch: its curves cut through all, both ways,
  along the sketch normal).
- ``bodies``: optional, the bodies to split; without any, every body is split.
- ``tolerance``: optional length: faces closer than this count as touching (TR261).

Key ``keep``: piece numbers to keep (from 1, ordered by centre X, then Y, then
Z, over all pieces); without it every piece is kept.

Face roles: faces of the split bodies keep their names (split faces get
``#1``, ``#2``); new cut faces are ``cut/face#k``.
"""

from __future__ import annotations

from typing import Any

from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.gp import gp_Trsf, gp_Vec
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureState,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.bodies import body_indices, join, names_on, rest_of
from fdcad.core.features.booleans import result_shape
from fdcad.core.features.geometry_refs import resolve_placement
from fdcad.core.features.intersect import endless_plane
from fdcad.core.features.lookup import resolve_face
from fdcad.core.features.solids import FUZZY_TOLERANCE, bounding_size, compound, solids
from fdcad.core.naming.names import NamedShape, carry, centroid, restrict
from fdcad.core.occ import BRepAlgoAPI_Splitter, ShapeList
from fdcad.core.units import Kind


def _sketch_tool(ctx: BuildContext, fid: str, size: float, owner: str) -> TopoDS_Shape:
    """The sketch's curves swept both ways through the part as cutting faces."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform

    out = ctx.result(fid).sketch
    if out is None:
        raise FeatureError(
            f"{owner}: {ctx._name(fid)} is not a sketch. Pick a plane, face or sketch."
        )
    from fdcad.core.features.curves import sketch_curve_edges
    from fdcad.core.features.solids import compound

    # Drawn curves only: construction lines and text outlines lay out the sketch and
    # must not cut or imprint the bodies (audit B item 16, D716).
    edges = sketch_curve_edges(out, owner)
    curves = compound(edges) if edges else None
    if curves is None:
        raise FeatureError(
            f"{owner}: {ctx._name(fid)} has no curves to cut with. Draw curves in the sketch."
        )
    n = out.plane.normal
    back = gp_Trsf()
    back.SetTranslation(gp_Vec(-n[0] * size, -n[1] * size, -n[2] * size))
    start = BRepBuilderAPI_Transform(curves, back, True).Shape()
    return BRepPrimAPI_MakePrism(
        start, gp_Vec(n[0] * size * 2, n[1] * size * 2, n[2] * size * 2)
    ).Shape()


def kept_indices(feature: Feature, count: int) -> list[int]:
    """Kept piece indexes from 0, from the ``keep`` key (all pieces without it)."""
    keep_raw = feature.data.get("keep")
    if not isinstance(keep_raw, list):
        return list(range(count))
    keep = [k - 1 for k in keep_raw if isinstance(k, int) and 1 <= k <= count]
    if not keep:
        raise FeatureError(f"{feature.name}: tick at least one body to keep.")
    return keep


def _lost_pieces(feature: Feature, count: int) -> list[Issue]:
    """A warning for kept piece numbers past the piece count, which were dropped without a
    word (audit B item 30, D740)."""
    keep_raw = feature.data.get("keep")
    if not isinstance(keep_raw, list):
        return []
    lost = [k for k in keep_raw if isinstance(k, int) and k > count]
    if not lost:
        return []
    return [
        Issue(
            FeatureState.WARNING,
            f"{feature.name}: the split now makes {count} bodies, so body "
            f"{', '.join(map(str, lost))} to keep is gone. Edit the split and tick the "
            "bodies to keep again.",
            code="pieces_lost",
        )
    ]


@register
class Split(FeatureType):
    """Cuts bodies into pieces with planes, faces or sketches."""

    type_name = "split"
    makes_solid = True
    params = (ParamSpec("tolerance", kind=Kind.LENGTH, optional=True),)  # TR261

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Split the bodies and keep the ticked pieces."""
        body, issues = self._build(feature, ctx)
        return FeatureResult(body=body, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The split part, for the live preview."""
        return self._build(feature, ctx)[0]

    def pieces(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[NamedShape, list[int], list[Any]]:
        """Every piece (one named shape), the split body indices and warnings."""
        name = feature.name
        assert ctx.body is not None
        if feature.refs.get("bodies"):
            indices, issues = body_indices(ctx, feature.refs["bodies"], name)
        else:
            indices, issues = list(range(len(solids(ctx.body.shape)))), []
        targets = [solids(ctx.body.shape)[i] for i in indices]
        size = bounding_size(*targets) * 4 + 10
        tools = ShapeList()
        refs = feature.refs.get("tools")
        if not isinstance(refs, list) or not refs:
            raise FeatureError(f"{name}: pick planes, faces or sketches to split with.")
        for ref in refs:
            if isinstance(ref, dict) and ref.get("kind") == "face":
                face, found = resolve_face(ctx.body, ref, name)
                issues += found
                from fdcad.core.features.direct import outward_normal

                normal = outward_normal(face)
                if normal is not None:
                    tools.Append(endless_plane(centroid(face), normal, size, targets))
                else:
                    tools.Append(face)
                continue
            fid = ref.get("feature") if isinstance(ref, dict) else None
            if isinstance(fid, str) and ctx.result(fid).sketch is not None:
                tools.Append(_sketch_tool(ctx, fid, size, name))
                continue
            place = resolve_placement(ctx, ref, name, "plane")
            issues += place.issues
            tools.Append(endless_plane(place.point, place.direction, size, targets))
        # Each body is split on its own, so overlapping bodies never cut each other.
        shapes: list[TopoDS_Shape] = []
        names: list[Any] = []
        for target in targets:
            args = ShapeList()
            args.Append(target)
            op = BRepAlgoAPI_Splitter()
            op.SetArguments(args)
            op.SetTools(tools)
            from fdcad.core.features.combine import tolerance_of

            typed = tolerance_of(feature)  # TR261: near touching faces count as touching
            op.SetFuzzyValue(max(FUZZY_TOLERANCE, typed) if typed else FUZZY_TOLERANCE)
            op.SetRunParallel(True)
            op.SetToFillHistory(True)
            try:
                op.Build()
                ok = op.IsDone()
            except Exception:
                ok = False
            made = result_shape(op) if ok else None
            if made is None:
                raise FeatureError(
                    f"{name} failed: the kernel could not cut the bodies. Move the tool slightly."
                )
            shapes.extend(solids(made))
            names.extend(carry(names_on(ctx.body, target), op.History()))
        shape = compound(shapes)
        pieces = sorted(solids(shape), key=lambda s: tuple(round(v, 6) for v in centroid(s)))
        if len(pieces) <= len(targets):
            raise FeatureError(
                f"{name}: the tools do not cut through any body. Move or extend them."
            )
        whole = compound(pieces)
        return NamedShape(whole, restrict(names, whole, f"{feature.id}/cut")), indices, issues

    def kept_bodies(self, feature: Feature, ctx: BuildContext) -> list[tuple[int, TopoDS_Shape]]:
        """The kept pieces with their numbers from 1, for saving to files (D528)."""
        if ctx.body is None:
            raise FeatureError(
                f"{feature.name}: the part has no bodies to split. Add a body first."
            )
        named, _indices, _issues = self.pieces(feature, ctx)
        pieces = solids(named.shape)
        return [(k + 1, pieces[k]) for k in kept_indices(feature, len(pieces))]

    def _build(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part has no bodies to split. Add a body first.")
        named, indices, issues = self.pieces(feature, ctx)
        pieces = solids(named.shape)
        keep = kept_indices(feature, len(pieces))
        issues = [*issues, *_lost_pieces(feature, len(pieces))]
        kept = [pieces[k] for k in keep]
        shape = kept[0] if len(kept) == 1 else compound(kept)
        kept_named = NamedShape(shape, restrict(names_on(named, shape), shape, f"{feature.id}/cut"))
        result = join([rest_of(ctx.body, indices, feature.id), kept_named], feature.id)
        assert result is not None
        return result, issues
