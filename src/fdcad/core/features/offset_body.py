"""Offset Body: grow or shrink every face of a body (TUTORIAL_REVIEW_SPEC_2 TR129, D825).

Type ``offset_body``. Params:

- ``distance``: length, how far every face moves along its normal.
- ``inward``: optional boolean, shrink instead of grow.
- ``corners``: optional "sharp" (default: faces meet where they cross) or
  "rounded" (outside corners and edges become rounds of radius ``distance``).

Refs: ``bodies`` (any face of the body; the first is used), needed when the part has
several bodies.

Each face of the body keeps its name on its moved face, so later features stay
attached; the rounds made at corners are named ``<fid>/round``.
"""

from __future__ import annotations

from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepOffset import BRepOffset_MakeOffset, BRepOffset_Skin
from OCP.GeomAbs import GeomAbs_Arc, GeomAbs_Intersection
from OCP.Message import Message_ProgressRange
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS, TopoDS_Shape

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
from fdcad.core.features.modify import changed_faces, length, require_body, resolve_faces
from fdcad.core.features.solids import check_result, compound, solids
from fdcad.core.naming.names import NamedFace, NamedShape, restrict
from fdcad.core.occ import ShapeMap, shape_list
from fdcad.core.units import Kind

CORNERS = ("sharp", "rounded")
_TOL = 1e-4


@register
class OffsetBody(FeatureType):
    """Moves every face of a body out or in by one distance."""

    type_name = "offset_body"
    makes_solid = True
    params = (
        ParamSpec("distance", kind=Kind.LENGTH),
        ParamSpec("inward", default=False, optional=True),
        ParamSpec("corners", choices=CORNERS, optional=True),
    )

    def _target(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[TopoDS_Shape, list[TopoDS_Shape], list[Issue]]:
        body = require_body(feature, ctx)
        found = solids(body.shape)
        if len(found) == 1:
            return found[0], [], []
        picked, issues = resolve_faces(feature, ctx, "bodies", required=False)
        if not picked:
            raise FeatureError(
                f"{feature.name}: the part has {len(found)} bodies. Pick a face of the body "
                "to offset."
            )
        key = picked[0][1]
        for solid in found:
            fmap = ShapeMap()
            TopExp.MapShapes_s(solid, TopAbs_FACE, fmap)
            if fmap.Contains(key):
                return solid, [s for s in found if not s.IsSame(solid)], issues
        raise FeatureError(f"{feature.name}: the picked face is not on a body. Pick it again.")

    def _offset(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        body = require_body(feature, ctx)
        owner, fid = feature.name, feature.id
        d = length(feature, "distance", "distance")
        sign = -1.0 if feature.params.get("inward") is True else 1.0
        rounded = feature.params.get("corners") == "rounded"
        solid, others, issues = self._target(feature, ctx)
        maker = BRepOffset_MakeOffset()
        maker.Initialize(
            solid,
            sign * d,
            _TOL,
            BRepOffset_Skin,
            False,
            False,
            GeomAbs_Arc if rounded else GeomAbs_Intersection,
            False,
        )
        try:
            maker.MakeOffsetShape(Message_ProgressRange())
            done = maker.IsDone() and not maker.Shape().IsNull()
        except Exception:  # kernel failure becomes a feature error
            done = False
        made = maker.Shape() if done else None
        if made is None or not solids(made) or not BRepCheck_Analyzer(made).IsValid():
            hint = (
                "Use a smaller distance, or Rounded corners."
                if not rounded
                else "Use a smaller distance."
            )
            if sign < 0:
                hint = "Use a distance smaller than the thinnest part of the body."
            from fdcad.core.features.shell import diagnose

            tight = diagnose(body, solid, d, outward=sign > 0)  # TR346 (D1405): name a face
            if tight:
                name, radius = tight[0]
                more = f" and {len(tight) - 1} more" if len(tight) > 1 else ""
                raise FeatureError(
                    f"{owner}: the body could not be offset: face {name}{more} bends with a "
                    f"radius of {radius:.3g} mm, smaller than the {d:.3g} mm distance. "
                    "Use a smaller distance, or round that face first.",
                    highlight=[n for n, _r in tight],
                )
            cause = "the wall may be too thin" if sign < 0 else "sharp corners may not meet"
            raise FeatureError(f"{owner}: the body could not be offset ({cause}). {hint}")
        made = solids(made)[0]
        names: list[NamedFace] = []
        for name, face in body.faces:
            for new in shape_list(maker.Generated(face)):
                if new.ShapeType() == TopAbs_FACE:
                    names.append((name, TopoDS.Face(new)))
        shape = compound([made, *others]) if others else made
        if others:
            names += list(body.faces)
        return NamedShape(shape, restrict(names, shape, f"{fid}/round")), issues

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Offset the body."""
        result, issues = self._offset(feature, ctx)
        issues = issues + check_result(feature.id, feature.name, ctx.body, result, None)
        return FeatureResult(body=result, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The moved faces, for the preview."""
        body = require_body(feature, ctx)
        result, _issues = self._offset(feature, ctx)
        return changed_faces(body.shape, result, feature.id)
