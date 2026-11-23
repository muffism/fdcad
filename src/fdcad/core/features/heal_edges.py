"""Heal Edges: close small gaps and loose edges of a body (TR262, D1807).

The Geometry Check fix for edges with gaps (D356) and inexact edges (D1416). The
kernel's shape fixer runs on every solid of the part: edge curves and their face
curves are made to agree again (same parameter), vertex and edge tolerances are
cut back to what the geometry needs, and small gaps between the edges of a face
outline are closed. Only the tolerances and curve fits change: no face moves, so
every face keeps its name.

Params: ``tolerance`` (length, default 0.01 mm): the largest gap closed. A gap
larger than that stays and is named in a warning, with the next step.
"""

from __future__ import annotations

from typing import Any

from OCP.BRep import BRep_Tool
from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepLib import BRepLib
from OCP.ShapeBuild import ShapeBuild_ReShape
from OCP.ShapeFix import ShapeFix_Shape
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Shape

from fdcad.core.document.model import Feature, Param
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
from fdcad.core.features.modify import require_body
from fdcad.core.features.solids import check_result, compound, solids
from fdcad.core.naming.names import NamedShape, carry, restrict
from fdcad.core.occ import ShapeList, ShapeMap
from fdcad.core.units import Kind

DEFAULT_TOLERANCE = 0.01


class Healed:
    """One healed body: where each face of the body handed in went."""

    def __init__(
        self, solid: TopoDS_Shape, copier: BRepBuilderAPI_Copy, context: ShapeBuild_ReShape
    ) -> None:
        self.faces = ShapeMap()
        TopExp.MapShapes_s(solid, TopAbs_FACE, self.faces)
        self.copier = copier
        self.context = context

    def value(self, shape: TopoDS_Shape) -> TopoDS_Shape | None:
        """The healed face for a face of the body, or None for a face of another body."""
        if not self.faces.Contains(shape):
            return None
        return self.context.Value(self.copier.ModifiedShape(shape))


class _ReShapeHistory:
    """The copies and the fixer's replacements as the history ``carry`` reads."""

    def __init__(self, steps: list[Healed]) -> None:
        self.steps = steps

    def _value(self, shape: TopoDS_Shape) -> TopoDS_Shape:
        for step in self.steps:
            new = step.value(shape)
            if new is not None:
                return new
        return shape  # a face of a body that was left as it was

    def IsRemoved(self, shape: TopoDS_Shape) -> bool:  # noqa: N802 (kernel history name)
        return bool(self._value(shape).IsNull())

    def Modified(self, shape: TopoDS_Shape) -> ShapeList:  # noqa: N802
        out = ShapeList()
        new = self._value(shape)
        if not new.IsNull() and not new.IsSame(shape):
            explorer = TopExp_Explorer(new, TopAbs_FACE)
            while explorer.More():
                out.Append(explorer.Current())
                explorer.Next()
        return out


def _valid(shape: TopoDS_Shape) -> bool:
    return bool(BRepCheck_Analyzer(shape).IsValid())


def largest_gap(shape: TopoDS_Shape) -> float:
    """The largest edge tolerance of ``shape`` (the widest gap an edge closes)."""
    worst = 0.0
    explorer = TopExp_Explorer(shape, TopAbs_EDGE)
    while explorer.More():
        worst = max(worst, BRep_Tool.Tolerance_s(TopoDS.Edge(explorer.Current())))
        explorer.Next()
    return worst


def heal(shape: TopoDS_Shape, tolerance: float) -> tuple[TopoDS_Shape, Healed]:
    """A healed copy of ``shape``, and where its faces went.

    The work is done on a copy (D1066). The fixer and the tolerance updates below
    change edges and vertices where they are, and a body shares most of them with the
    results of the features before it: healing in place changed those results too,
    and left some of them not valid.
    """
    copier = BRepBuilderAPI_Copy(shape, True, False)
    original, shape = shape, copier.Shape()
    fixer = ShapeFix_Shape(shape)
    fixer.SetPrecision(1e-7)
    fixer.SetMinTolerance(1e-7)
    fixer.SetMaxTolerance(tolerance)
    fixer.Perform()
    shape = fixer.Shape()
    # Edge tolerances are measured again from the curves (forced), and vertex
    # tolerances follow, so a loose tolerance that no real gap needs is cut back.
    BRepLib.SameParameter_s(shape, 1e-7, True)
    BRepLib.UpdateTolerances_s(shape, False)
    return shape, Healed(original, copier, fixer.Context())


@register
class HealEdges(FeatureType):
    """Closes small gaps and refits loose edges, without moving any face."""

    type_name = "heal_edges"
    makes_solid = True
    params = (ParamSpec("tolerance", kind=Kind.LENGTH, optional=True),)

    def _healed(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        body = require_body(feature, ctx)
        value = feature.params.get("tolerance")
        tolerance = value.value if isinstance(value, Param) else DEFAULT_TOLERANCE
        if tolerance <= 0:
            raise FeatureError(
                f"{feature.name}: the tolerance must be greater than zero. Enter a larger value."
            )
        pieces: list[Any] = []
        contexts = []
        kept = 0
        for solid in solids(body.shape) or [body.shape]:
            try:
                fixed, context = heal(solid, tolerance)
            except Exception as exc:  # kernel failure: a feature error (CLAUDE.md 5.7)
                raise FeatureError(
                    f"{feature.name} failed: the kernel could not heal the body. "
                    "Heal the imported file in the program that made it."
                ) from exc
            if fixed.IsNull():
                raise FeatureError(
                    f"{feature.name} failed: healing left nothing. "
                    "Heal the imported file in the program that made it."
                )
            # Healing must not make a body worse (D1066): a body that was valid and
            # would not be after it (its faces were fitted loosely, by a deform say,
            # and only its loose edges hold it together) stays as it was. So does a
            # body whose loosest edge would come out looser than it went in.
            looser = largest_gap(fixed) > max(largest_gap(solid), tolerance) * 1.001
            if looser or (not _valid(fixed) and _valid(solid)):
                pieces.append(solid)
                kept += 1
                continue
            pieces.append(fixed)
            contexts.append(context)
        shape = pieces[0] if len(pieces) == 1 else compound(pieces)
        names = carry(body.faces, _ReShapeHistory(contexts))
        result = NamedShape(shape, restrict(names, shape, f"{feature.id}/face"))
        issues: list[Issue] = []
        if kept:
            which = "1 body" if kept == 1 else f"{kept} bodies"
            issues.append(
                Issue(
                    FeatureState.WARNING,
                    f"{feature.name}: {which} would be worse after healing and "
                    f"{'stays as it was' if kept == 1 else 'stay as they were'}. Rebuild the "
                    "loose faces, or make the feature that fitted them more exact.",
                    code="heal_kept",
                )
            )
        left = largest_gap(shape)
        if left > tolerance:
            issues.append(
                Issue(
                    FeatureState.WARNING,
                    f"{feature.name}: a gap of {left:.3g} mm is still there, wider than the "
                    f"{tolerance:g} mm tolerance. Enter a larger tolerance, or rebuild the "
                    "faces next to it.",
                    code="gap_left",
                )
            )
        return result, issues

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Heal every body of the part."""
        result, issues = self._healed(feature, ctx)
        issues = issues + check_result(feature.id, feature.name, ctx.body, result, None)
        return FeatureResult(body=result, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The healed part, for the preview."""
        return self._healed(feature, ctx)[0]
