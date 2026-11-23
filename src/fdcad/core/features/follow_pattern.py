"""Follow Pattern: repeat a later feature at every copy of an existing pattern
(TR399 items 1 and 2, D1904).

Refs: ``pattern`` (``{"feature": <pattern id>}``) and the seed: ``features``,
``faces`` or ``bodies``, as the other patterns. Key ``on``: the ``[i, j]`` copy of
the pattern the seed was built on (``[1, 1]``, the original, by default). Each
rebuild reads the followed pattern's copies, so its count and layout changes carry
over. Params: the shared pattern params (``geometry`` and so on).
"""

from __future__ import annotations

import re
from typing import Any

from OCP.gp import gp_Trsf

from fdcad.core.document.model import Document, Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    register,
)
from fdcad.core.features.linear_pattern import COMMON_PARAMS
from fdcad.core.features.patterns import Placement, apply_pattern, region_skips, skipped
from fdcad.core.features.solids import check_result
from fdcad.core.naming.names import NamedShape

#: Patterns a feature can follow: those whose copies are numbered instances.
FOLLOW_TYPES = (
    "linear_pattern",
    "circular_pattern",
    "sketch_pattern",
    "table_pattern",
    "point_pattern",
    "pattern_chain",
)


def _on(feature: Feature) -> tuple[int, int]:
    raw = feature.data.get("on")
    if isinstance(raw, list) and len(raw) == 2 and all(isinstance(v, int) for v in raw):
        return raw[0], raw[1]
    return 1, 1


def followed(feature: Feature, ctx: BuildContext) -> Feature:
    """The pattern ``feature`` follows. Raises FeatureError."""
    ref = feature.refs.get("pattern")
    fid = ref.get("feature") if isinstance(ref, dict) else None
    if not isinstance(fid, str):
        raise FeatureError(f"{feature.name}: pick the pattern to follow.")
    ctx.result(fid)  # raises when it is missing, later or failed
    pattern = ctx.document.feature(fid)
    if pattern.type not in FOLLOW_TYPES:
        raise FeatureError(
            f"{feature.name}: {pattern.name} has no numbered copies to follow. Pick a Linear, "
            "Circular, Sketch, Table or Point Pattern, or a Pattern Chain."
        )
    return pattern


@register
class FollowPattern(FeatureType):
    """Repeats features, faces or bodies at every copy of an earlier pattern."""

    type_name = "follow_pattern"
    makes_solid = True
    params = COMMON_PARAMS

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Copy the seed to the followed pattern's copies and check the result."""
        placements, issues = self.placements(feature, ctx)
        outcome = apply_pattern(feature, ctx, placements)
        issues += outcome.issues
        issues += check_result(feature.id, feature.name, ctx.body, outcome.body, None)
        if feature.refs.get("bodies"):
            issues = [i for i in issues if i.code != "separate_body"]
        return FeatureResult(body=outcome.body, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The part with the copies, for the live preview."""
        placements, _issues = self.placements(feature, ctx)
        return apply_pattern(feature, ctx, placements).body

    def placements(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[list[Placement], list[Issue]]:
        """The followed pattern's copies (and its original), seen from the copy the seed
        was built on, that copy left out."""
        from fdcad.core.features import REGISTRY
        from fdcad.core.features.preview import body_before

        pattern = followed(feature, ctx)
        ftype: Any = REGISTRY[pattern.type]
        pctx = BuildContext(
            ctx.document,
            body_before(ctx.document, pattern, ctx.results),
            ctx.results,
            ctx.variables,
            ctx.cancelled,
        )
        found, issues = ftype.placements(pattern, pctx)
        gone = skipped(pattern) | region_skips(pattern, pctx, found)
        from fdcad.core.features.pattern_explode import only

        kept = only(pattern)
        moves: dict[tuple[int, int], gp_Trsf] = {(1, 1): gp_Trsf()}
        for p in found:
            if p.index not in gone and (kept is None or p.index == kept):
                moves[p.index] = p.trsf
        on = _on(feature)
        if on not in moves:
            raise FeatureError(
                f"{feature.name}: {pattern.name} no longer makes the copy its seed was built "
                "on. Rebuild the seed on another copy, or raise the pattern's count."
            )
        back = moves[on].Inverted()
        out = [
            Placement(index, trsf.Multiplied(back))
            for index, trsf in sorted(moves.items())
            if index != on
        ]
        return out, list(issues)


_COPY = re.compile(r"(f\d+)/instance(\d+)\.(\d+)/")


def _names(value: Any) -> list[str]:
    """Every face, edge or vertex name in a refs value."""
    out: list[str] = []
    if isinstance(value, dict):
        name = value.get("name")
        if isinstance(name, str):
            out.append(name)
        for item in value.values():
            if isinstance(item, (dict, list)):
                out += _names(item)
    elif isinstance(value, list):
        for item in value:
            out += _names(item)
    return out


def _feature_ids(value: Any) -> list[str]:
    """Every ``{"feature": id}`` in a refs value."""
    out: list[str] = []
    if isinstance(value, dict):
        if isinstance(value.get("feature"), str):
            out.append(str(value["feature"]))
        for item in value.values():
            if isinstance(item, (dict, list)):
                out += _feature_ids(item)
    elif isinstance(value, list):
        for item in value:
            out += _feature_ids(item)
    return out


def follow_target(doc: Document, fid: str) -> tuple[str, tuple[int, int]] | None:
    """The pattern a feature was built on and the copy it sits on (TR399, D1904): a
    face, edge or vertex it uses on a pattern copy, or on a seed feature of a pattern
    that comes before it (the original, ``(1, 1)``). None when there is none."""
    ids = [f.id for f in doc.features]
    if fid not in ids:
        return None
    index = ids.index(fid)
    earlier = doc.features[:index]
    patterns = {f.id: f for f in earlier if f.type in FOLLOW_TYPES}
    feature = doc.feature(fid)
    names = _names(feature.refs)
    for ref_id in _feature_ids(feature.refs):  # a sketch's face sits in the sketch's refs
        if ref_id in ids and doc.feature(ref_id).type == "sketch":
            names += _names(doc.feature(ref_id).refs)
    for name in names:
        match = _COPY.search(name)
        if match is not None and match.group(1) in patterns:
            return match.group(1), (int(match.group(2)), int(match.group(3)))
    for pattern in reversed(list(patterns.values())):
        seeds = [
            r["feature"]
            for r in pattern.refs.get("features") or []
            if isinstance(r, dict) and isinstance(r.get("feature"), str)
        ]
        if any(re.search(rf"(?:^|[(|]){s}/", name) for s in seeds for name in names):
            return pattern.id, (1, 1)
    return None


__all__ = ["FOLLOW_TYPES", "FollowPattern", "follow_target", "followed"]
