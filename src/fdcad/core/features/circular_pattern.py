"""Circular pattern about an axis (PHASE3_SPEC P3.2 item 2, DECISIONS D234).

Params:
- ``count1``: number of instances, the seed included.
- ``angle1``: with ``equal_spacing`` on (the default), the total angle the
  instances share (360 degrees: evenly round; less: the last instance lands on
  the end); off: the angle between neighbouring instances.
- ``reverse1``: boolean, turns the other way.
- ``second_direction``: optional boolean: copies also turn the other way, with
  ``count2`` and ``angle2``. ``symmetric2``: optional boolean, direction 2 uses
  direction 1's values.
- ``law1``, ``law2`` (TR366, D1500): optional, "even" (default) or "angles": each
  copy turns by its own number of degrees from the seed, from the text list
  ``angles1`` or ``angles2`` (one per copy, such as "30, 75, 160"), or "increment"
  (TR59, D1513): each step is the one before plus ``increment1`` (an angle).
- ``geometry``, ``merge``, ``propagate_colours``, ``preview``: as linear patterns.

Refs: ``axis`` (an axis, a round or straight edge, or a cylinder or cone face)
and the seed: ``features``, ``faces`` or ``bodies``. Key ``skip``: ``[i, d]``
pairs, ``d`` 1 for direction 1 and 2 for direction 2.
"""

from __future__ import annotations

import math

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
from fdcad.core.features.direct import rotation
from fdcad.core.features.geometry_refs import resolve_placement
from fdcad.core.features.linear_pattern import COMMON_PARAMS, MAX_INSTANCES, count_of
from fdcad.core.features.patterns import Placement, apply_pattern
from fdcad.core.features.solids import check_result
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind


def _steps(feature: Feature, count: int, total: float) -> float:
    """Angle between neighbouring instances."""
    if feature.params.get("equal_spacing", True) is False:
        return total
    if count <= 1:
        return 0.0
    full = abs(abs(total) - 2 * math.pi) < 1e-9
    return total / count if full else total / (count - 1)


#: How the copies are spread round the axis (TR366, D1500).
LAWS = ("even", "angles", "increment")


def copy_angles(feature: Feature, k: int, count: int, step: float, sign: float) -> list[float]:
    """The turn of each instance of direction ``k`` from the seed (index 0, always 0).

    Even: ``i x step``. Law "angles" (TR366, D1500): ``angles<k>`` is a text list of
    degrees, one per copy, each measured from the seed; Reverse turns them the other way.
    """
    law = feature.params.get(f"law{k}", "even")
    if law == "increment":  # TR59 (D1513): each step grows by the increment angle
        grow = feature.params.get(f"increment{k}")
        inc = (grow.value if isinstance(grow, Param) else 0.0) * sign
        turns = [0.0]
        for i in range(count - 1):
            turns.append(turns[-1] + step + i * inc)
        return turns
    if law != "angles":
        return [step * i for i in range(count)]
    from fdcad.core.features.linear_pattern import parse_fractions

    found = parse_fractions(str(feature.params.get(f"angles{k}", "")))
    if found is None:
        raise FeatureError(
            f"{feature.name}: the copy angles must be numbers of degrees such as 30, 75, 160. "
            "Fix the list."
        )
    if len(found) != count - 1:
        raise FeatureError(
            f"{feature.name}: {count - 1} copies need {count - 1} angles, but the list has "
            f"{len(found)}. Enter one angle for each copy, or change the count."
        )
    return [0.0] + [math.radians(a) * sign for a in found]


@register
class CircularPattern(FeatureType):
    """Copies features, faces or bodies around an axis."""

    type_name = "circular_pattern"
    makes_solid = True
    params = (
        ParamSpec("count1", kind=Kind.NUMBER),
        ParamSpec("angle1", kind=Kind.ANGLE),
        ParamSpec("equal_spacing", default=True, optional=True),
        ParamSpec("reverse1", default=False, optional=True),
        ParamSpec("second_direction", default=False, optional=True),
        ParamSpec("count2", kind=Kind.NUMBER, optional=True),
        ParamSpec("angle2", kind=Kind.ANGLE, optional=True),
        ParamSpec("symmetric2", default=False, optional=True),
        ParamSpec("law1", choices=LAWS, optional=True),  # TR366 (D1500)
        ParamSpec("angles1", optional=True),
        ParamSpec("law2", choices=LAWS, optional=True),
        ParamSpec("angles2", optional=True),
        ParamSpec("increment1", kind=Kind.ANGLE, optional=True),  # TR59 (D1513)
        ParamSpec("increment2", kind=Kind.ANGLE, optional=True),
        *COMMON_PARAMS,
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Copy the seed and check the result."""
        from fdcad.core.features.pattern_datums import datum_result, datum_seed

        seed = datum_seed(feature, ctx)  # a pattern of reference geometry (TR142, D2402)
        if seed is not None:
            return datum_result(feature, ctx, seed, self.placements(feature, ctx)[0])
        body, issues = self._build(feature, ctx, partial=False)
        issues += check_result(feature.id, feature.name, ctx.body, body, None)
        if feature.refs.get("bodies"):
            issues = [i for i in issues if i.code != "separate_body"]
        return FeatureResult(body=body, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The patterned part, for the live preview."""
        from fdcad.core.features.pattern_datums import datum_preview, datum_seed

        seed = datum_seed(feature, ctx)  # copies of reference geometry (TR142, D2402)
        if seed is not None:
            shape = datum_preview(feature, ctx, seed, self.placements(feature, ctx)[0])
            return NamedShape(shape, [])
        return self._build(feature, ctx, feature.params.get("preview") == "partial")[0]

    def _build(
        self, feature: Feature, ctx: BuildContext, partial: bool
    ) -> tuple[NamedShape, list[Issue]]:
        placements, issues = self.placements(feature, ctx)
        if partial:
            placements = [p for p in placements if p.index[0] <= 2]
        outcome = apply_pattern(feature, ctx, placements)
        return outcome.body, issues + outcome.issues

    def placements(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[list[Placement], list[Issue]]:
        """Every copy, the seed left out."""
        name = feature.name
        axis = resolve_placement(ctx, feature.refs.get("axis"), name, "axis")
        n1 = count_of(feature, "count1")
        total1 = self.number(feature, "angle1")
        if total1 <= 0:
            raise FeatureError(
                f"{name}: the angle must be greater than zero. Enter a larger angle."
            )
        sign = -1.0 if feature.params.get("reverse1") is True else 1.0
        step1 = _steps(feature, n1, total1) * sign
        turns1 = copy_angles(feature, 1, n1, step1, sign)
        out = [
            Placement((i + 1, 1), rotation(axis.point, axis.direction, turns1[i]))
            for i in range(1, n1)
        ]
        if feature.params.get("second_direction") is True:
            if feature.params.get("symmetric2") is True:
                n2, turns2 = n1, turns1
            else:
                n2 = count_of(feature, "count2")
                total2 = self.number(feature, "angle2")
                if total2 <= 0:
                    raise FeatureError(
                        f"{name}: the direction 2 angle must be greater than zero. "
                        "Enter a larger angle."
                    )
                step2 = _steps(feature, n2, total2) * sign
                turns2 = copy_angles(feature, 2, n2, step2, sign)
            out += [
                Placement((i + 1, 2), rotation(axis.point, axis.direction, -turns2[i]))
                for i in range(1, n2)
            ]
        if len(out) + 1 > MAX_INSTANCES:
            raise FeatureError(f"{name}: at most {MAX_INSTANCES} instances. Use fewer.")
        issues = list(axis.issues)
        equal = feature.params.get("equal_spacing", True) is not False
        if equal and total1 > 2 * math.pi + 1e-9:
            # Revolve refuses more than a full turn; the pattern built overlapping copies
            # without a word (audit E item 9.3, D746).
            issues.append(
                Issue(
                    FeatureState.WARNING,
                    f"{name}: the instances spread over more than 360 degrees, so some lie "
                    "on top of others. Enter 360 degrees or less.",
                    code="past_full_turn",
                )
            )
        return out, issues
