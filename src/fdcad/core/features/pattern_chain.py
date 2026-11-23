"""Pattern Chain: several pattern steps applied in order (TR141 item 1, D1901).

Each step's copies feed the next, so "linear, circular" spreads a row of copies and
then turns the whole row round an axis, while "circular, linear" turns the seed and
then moves every turned copy along. Each kind of step is used at most once.

Params:
- ``steps``: text, the step order, such as "mirror, linear, circular, scale".
- Linear step: ``spacing``, ``instances`` (how many along it, the seed included),
  ``reverse``; refs ``direction``.
- Circular step: ``turns`` (instances round the axis), ``angle`` (the total angle the
  instances share; 360 degrees or more spreads them evenly round), ``reverse_turn``;
  refs ``axis``.
- Mirror step: refs ``plane``: the seed and its mirror image.
- Scale step: ``scales`` (instances), ``factor`` (each copy this many times the size
  of the one before), about refs ``centre`` (a point; the origin when empty).
- ``geometry``, ``merge``, ``propagate_colours``, ``preview``, ``check`` and the
  rest of the shared pattern params (see ``linear_pattern.COMMON_PARAMS``).

Refs: the step refs above and the seed: ``features``, ``faces`` or ``bodies``.
Instances are numbered ``(n, 1)``, ``n`` from 1 (the seed) in step order: the first
step counts fastest. Key ``skip``: instances to skip, as ``[n, 1]`` pairs.
"""

from __future__ import annotations

import math
import re

from OCP.gp import gp_Pnt, gp_Trsf

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.direct import rotation, translation
from fdcad.core.features.geometry_refs import resolve_placement, scaled
from fdcad.core.features.linear_pattern import COMMON_PARAMS, MAX_INSTANCES, count_of
from fdcad.core.features.patterns import Placement, apply_pattern
from fdcad.core.features.solids import check_result
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind

#: The kinds of step a chain can hold.
STEP_KINDS = ("mirror", "linear", "circular", "scale")


def parse_steps(feature: Feature) -> list[str]:
    """The step order from ``steps`` ("linear, circular"). Raises FeatureError."""
    text = str(feature.params.get("steps", "") or "")
    out: list[str] = []
    for word in re.split(r"[,; ]+", text.strip().lower()):
        if not word:
            continue
        if word not in STEP_KINDS:
            raise FeatureError(
                f"{feature.name}: '{word}' is not a pattern step. Enter steps from mirror, "
                "linear, circular and scale, such as linear, circular."
            )
        if word in out:
            raise FeatureError(
                f"{feature.name}: the {word} step is listed twice. Enter each step once."
            )
        out.append(word)
    if not out:
        raise FeatureError(
            f"{feature.name}: the chain has no steps. Enter steps such as linear, circular."
        )
    return out


def _value(feature: Feature, name: str, default: float = 0.0) -> float:
    value = feature.params.get(name)
    return value.value if isinstance(value, Param) else default


def _linear(feature: Feature, ctx: BuildContext) -> tuple[list[gp_Trsf], list[Issue]]:
    place = resolve_placement(ctx, feature.refs.get("direction"), feature.name, "direction")
    direction = place.direction
    if feature.params.get("reverse") is True:
        direction = scaled(direction, -1.0)
    spacing = _value(feature, "spacing")
    if spacing <= 0:
        raise FeatureError(
            f"{feature.name}: the spacing must be greater than zero. Enter a larger spacing."
        )
    count = count_of(feature, "instances")
    return [translation(scaled(direction, spacing * k)) for k in range(count)], list(place.issues)


def _circular(feature: Feature, ctx: BuildContext) -> tuple[list[gp_Trsf], list[Issue]]:
    axis = resolve_placement(ctx, feature.refs.get("axis"), feature.name, "axis")
    count = count_of(feature, "turns")
    total = _value(feature, "angle", 2 * math.pi)
    if total <= 0:
        raise FeatureError(f"{feature.name}: the angle must be greater than zero. Enter one.")
    full = total >= 2 * math.pi - 1e-9
    step = (2 * math.pi / count if full else total / max(count - 1, 1)) if count > 1 else 0.0
    if feature.params.get("reverse_turn") is True:
        step = -step
    out = [rotation(axis.point, axis.direction, step * k) for k in range(count)]
    return out, list(axis.issues)


def _mirror(feature: Feature, ctx: BuildContext) -> tuple[list[gp_Trsf], list[Issue]]:
    from fdcad.core.features.mirror import mirror_trsf

    plane = resolve_placement(ctx, feature.refs.get("plane"), feature.name, "plane")
    return [gp_Trsf(), mirror_trsf(plane.point, plane.direction)], list(plane.issues)


def _scale(feature: Feature, ctx: BuildContext) -> tuple[list[gp_Trsf], list[Issue]]:
    issues: list[Issue] = []
    centre = (0.0, 0.0, 0.0)
    if feature.refs.get("centre") is not None:
        found = resolve_placement(ctx, feature.refs["centre"], feature.name, "point")
        centre, issues = found.point, list(found.issues)
    factor = _value(feature, "factor", 1.0)
    if factor <= 0:
        raise FeatureError(
            f"{feature.name}: the scale factor must be greater than zero. Enter a factor "
            "such as 0.8."
        )
    out = []
    for k in range(count_of(feature, "scales")):
        trsf = gp_Trsf()
        if k:
            trsf.SetScale(gp_Pnt(*centre), factor**k)
        out.append(trsf)
    return out, issues


_STEPS = {"linear": _linear, "circular": _circular, "mirror": _mirror, "scale": _scale}


@register
class PatternChain(FeatureType):
    """Copies features, faces or bodies through several pattern steps in order."""

    type_name = "pattern_chain"
    makes_solid = True
    params = (
        ParamSpec("steps"),
        ParamSpec("spacing", kind=Kind.LENGTH, optional=True),
        ParamSpec("instances", kind=Kind.NUMBER, optional=True),
        ParamSpec("reverse", default=False, optional=True),
        ParamSpec("turns", kind=Kind.NUMBER, optional=True),
        ParamSpec("angle", kind=Kind.ANGLE, optional=True),
        ParamSpec("reverse_turn", default=False, optional=True),
        ParamSpec("scales", kind=Kind.NUMBER, optional=True),
        ParamSpec("factor", kind=Kind.NUMBER, optional=True),
        *COMMON_PARAMS,
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Copy the seed through every step and check the result."""
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
            placements = placements[:3]
        outcome = apply_pattern(feature, ctx, placements)
        return outcome.body, issues + outcome.issues

    def placements(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[list[Placement], list[Issue]]:
        """Every copy, the seed left out: each step's moves applied after the ones before."""
        issues: list[Issue] = []
        moves: list[gp_Trsf] = [gp_Trsf()]
        for kind in parse_steps(feature):
            step, found = _STEPS[kind](feature, ctx)
            issues += found
            if len(moves) * len(step) > MAX_INSTANCES:
                raise FeatureError(
                    f"{feature.name}: the steps make more than {MAX_INSTANCES} instances. "
                    "Enter smaller counts."
                )
            # The first step counts fastest: each later move is applied after it.
            moves = [later.Multiplied(earlier) for later in step for earlier in moves]
        out = [Placement((n + 1, 1), trsf) for n, trsf in enumerate(moves) if n]
        return out, issues


__all__ = ["STEP_KINDS", "PatternChain", "parse_steps"]
