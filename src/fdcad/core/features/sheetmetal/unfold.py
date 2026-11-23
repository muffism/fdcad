"""Unfold and Fold (PHASE5_SPEC P5.5 item 6, DECISIONS D541): cuts across bends.

Type ``unfold``: params ``all_bends``; refs ``bends`` (faces of bends), ``sheet_metal``.
The picked bends are shown flat; the wall nearer the first wall stays fixed.

Type ``fold``: refs ``unfold`` (the Unfold it closes; the newest one before it
when missing), ``sheet_metal``. Material removed after the Unfold (by Extruded
Cut and other cutting features) is cut from the walls in their frames and, across
an unfolded bend, stored on the bend and wrapped onto it when folded.

Face roles: as the walls and bends they change; wrapped cuts ``<bend>/cut<n>``.
"""

from __future__ import annotations

from dataclasses import replace

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
from fdcad.core.features.lookup import resolve_face
from fdcad.core.features.sheetmetal.common import require_sheet
from fdcad.core.features.sheetmetal.model import SheetResult, basis, volume
from fdcad.core.features.sheetmetal.wrap import strip_cut, through
from fdcad.core.features.solids import transform
from fdcad.core.naming.names import NamedShape, faces_of
from fdcad.core.occ import BRepAlgoAPI_Common, BRepAlgoAPI_Cut

_TOL = 1e-6


@register
class Unfold(FeatureType):
    """Shows picked bends flat so cuts can be made across them."""

    type_name = "unfold"
    makes_solid = True
    params = (ParamSpec("all_bends", default=False, optional=True),)

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Lay the picked bends flat."""
        name = feature.name
        model = require_sheet(feature, ctx)
        issues: list[Issue] = []
        if feature.params.get("all_bends") is True:
            chosen = set(model.bends)
        else:
            refs = feature.refs.get("bends")
            if not isinstance(refs, list) or not refs:
                raise FeatureError(f"{name}: pick a face of each bend to unfold, or All Bends.")
            chosen = set()
            assert ctx.body is not None
            for ref in refs:
                if not isinstance(ref, dict):
                    raise FeatureError(f"{name}: a face pick is damaged. Pick the faces again.")
                face, found = resolve_face(ctx.body, ref, name)
                issues.extend(found)
                label = next((n for n, f in ctx.body.faces if f.IsSame(face)), "")
                bid = label.rsplit("/", 1)[0]
                if bid not in model.bends:
                    raise FeatureError(f"{name}: a picked face is not on a bend. Pick a bend face.")
                chosen.add(bid)
        if not chosen:
            raise FeatureError(
                f"{name}: the part has no bends to unfold. Add a flange or a bend first."
            )
        model.unfolded |= chosen
        return SheetResult(body=model.build(feature.id, name), issues=issues, sheet=model)


@register
class Fold(FeatureType):
    """Folds unfolded bends back, keeping the cuts made across them."""

    type_name = "fold"
    makes_solid = True
    params = ()

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Take in the cuts made since the Unfold and fold the bends back."""
        name, fid = feature.name, feature.id
        unfold = self._unfold(feature, ctx)
        result = ctx.result(unfold.id)
        if not isinstance(result, SheetResult) or result.sheet is None or result.body is None:
            raise FeatureError(f"{name}: {unfold.name} failed. Fix it first.")
        if ctx.body is None:
            raise FeatureError(f"{name}: the part has no solid. Fix the features above it.")
        before, after = result.body.shape, ctx.body.shape
        added = BRepAlgoAPI_Cut(after, before)
        if added.IsDone() and volume(added.Shape()) > 1e-6:
            raise FeatureError(
                f"{name}: a feature after {unfold.name} adds material. Only cuts can be made "
                "between Unfold and Fold. Move that feature below Fold."
            )
        gone = BRepAlgoAPI_Cut(before, after)
        model = result.sheet.copy()
        if gone.IsDone() and volume(gone.Shape()) > 1e-7:
            removed = NamedShape(gone.Shape(), [(f"{fid}/cut", f) for f in faces_of(gone.Shape())])
            places = model.placements(False)
            for wid, wall in model.walls.items():
                if wid not in places:
                    continue
                local = transform(removed, places[wid].Inverted())
                common = BRepAlgoAPI_Common(model.piece(wid).shape, local.shape)
                if common.IsDone() and volume(common.Shape()) > 1e-7:
                    wall.cuts.append(local)
            for bid, bend in list(model.bends.items()):
                if bid not in model.unfolded or bend.parent not in places:
                    continue
                to_strip = places[bend.parent].Multiplied(basis(bend.p0, bend.w)).Inverted()
                cut = strip_cut(removed, bend, model.thickness, to_strip)
                if cut is None:
                    continue
                if not through(cut, model.thickness):
                    raise FeatureError(
                        f"{name}: a cut across a bend must go through the sheet. "
                        "Make the cut Through All."
                    )
                model.bends[bid] = replace(bend, cuts=(*bend.cuts, cut))
        model.unfolded = set()
        return SheetResult(body=model.build(fid, name), sheet=model)

    @staticmethod
    def _unfold(feature: Feature, ctx: BuildContext) -> Feature:
        ref = feature.refs.get("unfold")
        if isinstance(ref, dict) and isinstance(ref.get("feature"), str):
            return ctx.document.feature(str(ref["feature"]))
        found: Feature | None = None
        for f in ctx.document.features:
            if f.id == feature.id:
                break
            if f.type == "unfold" and not f.suppressed:
                found = f
        if found is None:
            raise FeatureError(f"{feature.name} needs an Unfold before it. Add an Unfold first.")
        return found
