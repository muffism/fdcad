"""Linear pattern in one or two directions (PHASE3_SPEC P3.2 item 1, DECISIONS D234).

Params:
- ``spacing1``: length between copies. ``count1``: number of instances, the seed included.
- ``reverse1``: boolean. ``fill1``: optional, "spacing" (default) or "up_to": fill
  up to ``refs.up_to1`` (a vertex, edge, face or plane) less ``offset1`` (length), or
  "total" (TR142, D962): ``count1`` instances spread evenly over ``total1`` (length,
  from the seed to the last copy), or "fit" (TR398, D1502): as many copies
  ``spacing1`` apart as fit in the overall size ``total1``, the seed included.
- ``law1``, ``law2``: optional spacing law (TR366, D981): "even" (default), "growing"
  (each gap ``ratio1`` times the one before; the first gap is the spacing) or
  "random" (each copy moved by up to ``jitter1`` percent of the spacing either way,
  the same every rebuild for one ``seed1``), or "fractions" (TR366, D1018: copy
  ``k + 1`` sits at the ``k``-th number of ``fractions1``, a text list such as
  "0.1, 0.3, 1", times the run from the seed to the last copy, ``spacing1`` times
  the copies; one number per copy), or "increment" (TR59, D1513: each gap is the one
  before plus ``increment1``, a length; the first gap is the spacing).
- ``vary`` (TR59, D1513, every pattern of features): text such as "depth 2": values of
  the seed features that grow by the step at each copy (see ``patterns.parse_vary``).
- ``instance_values`` (TR59 item 3, D1900): text such as "3: depth 8": the values
  one copy uses in place of the seed's (see ``patterns.parse_instance_values``).
- ``second_direction``: optional boolean, turns on direction 2 with ``spacing2``,
  ``count2``, ``reverse2``, ``fill2``, ``offset2`` and ``refs.up_to2``.
- ``seed_only2``: optional boolean: direction 2 repeats only the seed.
- ``symmetric1``, ``symmetric2``: optional booleans (TR140, D811): the same number of
  copies at the same spacing on the other side of the seed too. Copies on the far
  side are numbered after the near side's (count + 1, count + 2...) for Skip.
- ``seed_cell1``, ``seed_cell2``: optional numbers (TR270, D1501): the cell of the
  grid that holds the seed, 1 (default) to the count; earlier cells are copies the
  other way. Not with Symmetric.
- ``rotate``: optional angle (TR270, D1501): with direction 2, both directions turn
  by it about their common normal, so the whole grid turns in its plane.
- ``geometry``, ``merge``, ``propagate_colours``: optional booleans (see ``patterns``).
- ``preview``: optional, "full" (default) or "partial" (the preview shows only
  the first copy in each direction).

Refs: ``direction1`` and ``direction2`` (a straight edge, flat face, plane,
axis or sketch line), and the seed: ``features``, ``faces`` or ``bodies``.
Key ``skip``: instances to skip, as ``[i, j]`` pairs.
"""

from __future__ import annotations

import math

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    register,
    value_label,
)
from fdcad.core.features.direct import translation
from fdcad.core.features.geometry_refs import dot, minus, resolve_placement, scaled
from fdcad.core.features.patterns import CHECKS, REGION_MODES, Placement, apply_pattern
from fdcad.core.features.seeds import seed_centre
from fdcad.core.features.solids import check_result
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind

MAX_INSTANCES = 1000
#: How copies are spaced along a direction (TR142 adds "total", TR398 "fit").
FILLS = ("spacing", "up_to", "total", "fit")
#: How the gaps between copies change along a direction (TR366).
LAWS = ("even", "growing", "random", "fractions", "increment")


def parse_fractions(text: str) -> list[float] | None:
    """Numbers split by commas, semicolons or spaces, or None when one is not a number."""
    import math
    import re

    out = []
    for part in re.split(r"[,; ]+", text.strip()):
        if not part:
            continue
        try:
            value = float(part)
        except ValueError:
            return None
        if not math.isfinite(value):
            return None
        out.append(value)
    return out


def law_positions(
    feature: Feature, k: int | str, spacing: float, steps: list[int]
) -> dict[int, float]:
    """Distance along direction ``k`` of each step number (TR366): ``step x spacing``
    for even spacing, a growing series, or seeded random moves. Negative steps (the
    symmetric side) mirror the positive ones. ``k`` is the param suffix; Array Along
    Curve passes "" for its unnumbered ``law``, ``ratio`` and so on (D1500)."""
    law = feature.params.get(f"law{k}", "even")
    biggest = max((abs(s) for s in steps), default=0)
    if law == "growing":
        ratio = _value(feature, f"ratio{k}") or 1.0
        if ratio <= 0:
            raise FeatureError(
                f"{feature.name}: the growth ratio must be greater than zero. Enter a ratio "
                "such as 1.2."
            )
        along = [0.0]
        gap = spacing
        for _ in range(biggest):
            along.append(along[-1] + gap)
            gap *= ratio
    elif law == "increment":  # TR59 (D1513): each gap grows by the increment
        step = _value(feature, f"increment{k}")
        along = [0.0]
        for i in range(biggest):
            along.append(along[-1] + spacing + i * step)
    elif law == "fractions":  # TR366 (D1018)
        found = parse_fractions(str(feature.params.get(f"fractions{k}", "")))
        if found is None:
            raise FeatureError(
                f"{feature.name}: the fractions must be numbers such as 0.1, 0.3, 1. Fix the list."
            )
        if len(found) != biggest:
            raise FeatureError(
                f"{feature.name}: {biggest} copies need {biggest} fractions, but the list "
                f"has {len(found)}. Enter one fraction for each copy, or change the count."
            )
        run = spacing * biggest
        along = [0.0] + [f * run for f in found]
    elif law == "random":
        import random

        share = max(0.0, min(_value(feature, f"jitter{k}"), 49.0)) / 100.0
        rng = random.Random(int(_value(feature, f"seed{k}")))
        along = [0.0] + [
            i * spacing + rng.uniform(-share, share) * spacing for i in range(1, biggest + 1)
        ]
    else:
        along = [i * spacing for i in range(biggest + 1)]
    return {s: (along[s] if s >= 0 else -along[-s]) for s in steps}


COMMON_PARAMS = (
    ParamSpec("geometry", default=False, optional=True),
    ParamSpec("merge", default=False, optional=True),
    ParamSpec("propagate_colours", default=False, optional=True),
    ParamSpec("preview", choices=("full", "partial"), optional=True),
    ParamSpec("region_mode", choices=REGION_MODES, optional=True),  # TR398 (D1503)
    ParamSpec("vary", optional=True),  # TR59 (D1513): seed values that grow per copy
    ParamSpec("instance_values", optional=True),  # TR59 item 3 (D1900): one copy's values
    ParamSpec("check", choices=CHECKS, optional=True),  # TR399 (D1519)
)


def count_of(feature: Feature, name: str) -> int:
    """A whole instance count of 0 or more (0 makes no copies, TR345). Raises FeatureError."""
    value = feature.params.get(name)
    if not isinstance(value, Param):
        raise FeatureError(
            f"{feature.name}: the {value_label(name)} value is missing. Enter a number."
        )
    count = round(value.value)
    # A formula can land a hair off a whole number (4.9999999); that still counts
    # (audit B item 29, D738).
    if abs(count - value.value) > 1e-6 or count < 0:
        raise FeatureError(
            f"{feature.name}: the number of instances must be a whole number of 0 or more. "
            "Enter 0 or more."
        )
    if count > MAX_INSTANCES:
        raise FeatureError(
            f"{feature.name}: at most {MAX_INSTANCES} instances. Enter a smaller number."
        )
    return int(count)


def reach_along(
    ctx: BuildContext,
    ref: object,
    owner: str,
    start: tuple[float, float, float],
    direction: tuple[float, float, float],
) -> tuple[float, list[Issue]]:
    """How far the Up to reference lies from ``start`` along ``direction``
    (audit B item 1, D717): a plane or flat face where the direction line meets it,
    a vertex at its point, an edge or curved face at its centre."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepGProp import BRepGProp
    from OCP.GeomAbs import GeomAbs_Plane
    from OCP.GProp import GProp_GProps

    from fdcad.core.features.lookup import resolve_edge, resolve_face

    if isinstance(ref, dict) and ref.get("kind") in ("face", "edge"):
        props = GProp_GProps()
        if ref["kind"] == "edge":
            edge, issues = resolve_edge(ctx.body, ref, owner)
            BRepGProp.LinearProperties_s(edge, props)
        else:
            face, issues = resolve_face(ctx.body, ref, owner)
            surface = BRepAdaptor_Surface(face)
            if surface.GetType() == GeomAbs_Plane:
                plane = resolve_placement(ctx, ref, owner, "plane")
                return _to_plane(plane.point, plane.direction, start, direction, owner), issues
            BRepGProp.SurfaceProperties_s(face, props)
        c = props.CentreOfMass()
        return dot(minus((c.X(), c.Y(), c.Z()), start), direction), issues
    if isinstance(ref, dict) and isinstance(ref.get("feature"), str) and "axis" not in ref:
        plane = resolve_placement(ctx, ref, owner, "plane")
        return _to_plane(plane.point, plane.direction, start, direction, owner), list(plane.issues)
    target = resolve_placement(ctx, ref, owner, "point")
    return dot(minus(target.point, start), direction), list(target.issues)


def _to_plane(
    origin: tuple[float, float, float],
    normal: tuple[float, float, float],
    start: tuple[float, float, float],
    direction: tuple[float, float, float],
    owner: str,
) -> float:
    across = dot(direction, normal)
    if abs(across) < 1e-9:
        raise FeatureError(
            f"{owner}: the Up to reference is parallel to the direction, so the copies never "
            "reach it. Pick a reference across the direction."
        )
    return dot(minus(origin, start), normal) / across


@register
class LinearPattern(FeatureType):
    """Copies features, faces or bodies along one or two directions."""

    type_name = "linear_pattern"
    makes_solid = True
    params = (
        ParamSpec("spacing1", kind=Kind.LENGTH),
        # Up to reference fills the count itself, so the panel leaves it out.
        ParamSpec("count1", kind=Kind.NUMBER, optional=True),
        ParamSpec("reverse1", default=False, optional=True),
        ParamSpec("fill1", choices=FILLS, optional=True),
        ParamSpec("offset1", kind=Kind.LENGTH, optional=True),
        ParamSpec("total1", kind=Kind.LENGTH, optional=True),  # TR142 (D962)
        ParamSpec("law1", choices=LAWS, optional=True),  # TR366 (D981)
        ParamSpec("ratio1", kind=Kind.NUMBER, optional=True),
        ParamSpec("jitter1", kind=Kind.NUMBER, optional=True),
        ParamSpec("seed1", kind=Kind.NUMBER, optional=True),
        ParamSpec("fractions1", optional=True),  # TR366 (D1018)
        ParamSpec("increment1", kind=Kind.LENGTH, optional=True),  # TR59 (D1513)
        ParamSpec("increment2", kind=Kind.LENGTH, optional=True),
        ParamSpec("second_direction", default=False, optional=True),
        ParamSpec("spacing2", kind=Kind.LENGTH, optional=True),
        ParamSpec("count2", kind=Kind.NUMBER, optional=True),
        ParamSpec("reverse2", default=False, optional=True),
        ParamSpec("fill2", choices=FILLS, optional=True),
        ParamSpec("offset2", kind=Kind.LENGTH, optional=True),
        ParamSpec("total2", kind=Kind.LENGTH, optional=True),
        ParamSpec("law2", choices=LAWS, optional=True),
        ParamSpec("ratio2", kind=Kind.NUMBER, optional=True),
        ParamSpec("jitter2", kind=Kind.NUMBER, optional=True),
        ParamSpec("seed2", kind=Kind.NUMBER, optional=True),
        ParamSpec("fractions2", optional=True),
        ParamSpec("seed_only2", default=False, optional=True),
        ParamSpec("symmetric1", default=False, optional=True),  # TR140
        ParamSpec("symmetric2", default=False, optional=True),
        ParamSpec("seed_cell1", kind=Kind.NUMBER, optional=True),  # TR270 (D1501)
        ParamSpec("seed_cell2", kind=Kind.NUMBER, optional=True),
        ParamSpec("rotate", kind=Kind.ANGLE, optional=True),
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
        partial = feature.params.get("preview") == "partial"
        return self._build(feature, ctx, partial)[0]

    def _build(
        self, feature: Feature, ctx: BuildContext, partial: bool
    ) -> tuple[NamedShape, list[Issue]]:
        placements, issues = self.placements(feature, ctx)
        if partial:
            placements = [p for p in placements if p.index[0] <= 2 and p.index[1] <= 2]
        outcome = apply_pattern(feature, ctx, placements)
        return outcome.body, issues + outcome.issues

    def _direction(
        self, feature: Feature, ctx: BuildContext, k: int
    ) -> tuple[tuple[float, float, float], float, int, list[Issue]]:
        name = feature.name
        place = resolve_placement(ctx, feature.refs.get(f"direction{k}"), name, "direction")
        direction = place.direction
        if feature.params.get(f"reverse{k}") is True:
            direction = scaled(direction, -1.0)
        issues = list(place.issues)
        if feature.params.get(f"fill{k}") == "total":  # TR142: copies over a total length
            count = count_of(feature, f"count{k}")
            total = _value(feature, f"total{k}")
            if total <= 0:
                raise FeatureError(
                    f"{name}: the total length must be greater than zero. Enter a larger "
                    "total length."
                )
            return direction, (total / (count - 1) if count > 1 else total), count, issues
        spacing = self.number(feature, f"spacing{k}")
        if spacing <= 0:
            raise FeatureError(
                f"{name}: the spacing must be greater than zero. Enter a larger spacing."
            )
        if feature.params.get(f"fill{k}") == "fit":  # TR398 (D1502)
            size = _value(feature, f"total{k}")
            if size < 0:
                raise FeatureError(f"{name}: the overall size cannot be negative. Enter 0 or more.")
            count = math.floor(size / spacing + 1e-9) + 1
            if count > MAX_INSTANCES:
                raise FeatureError(
                    f"{name}: {count} copies fit, more than {MAX_INSTANCES}. Enter a larger "
                    "spacing or a smaller overall size."
                )
            return direction, spacing, count, issues
        if feature.params.get(f"fill{k}") == "up_to":
            offset = abs(_value(feature, f"offset{k}"))
            start = seed_centre(feature, ctx)
            along, found = reach_along(ctx, feature.refs.get(f"up_to{k}"), name, start, direction)
            issues += found
            reach = along - offset
            if reach < 0:
                raise FeatureError(
                    f"{name}: the Up to reference lies behind the seed. Reverse the direction."
                )
            count = math.floor(reach / spacing + 1e-9) + 1
        else:
            count = count_of(feature, f"count{k}")
        return direction, spacing, count, issues

    def placements(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[list[Placement], list[Issue]]:
        """Every copy, the seed left out."""
        d1, s1, n1, issues = self._direction(feature, ctx, 1)
        second = feature.params.get("second_direction") is True
        d2, s2, n2 = (0.0, 0.0, 0.0), 0.0, 1
        if second:
            d2, s2, n2, found = self._direction(feature, ctx, 2)
            issues += found
            if abs(abs(dot(d1, d2)) - 1.0) < 1e-9:
                raise FeatureError(
                    f"{feature.name}: direction 2 is parallel to direction 1, so copies "
                    "would land on each other. Pick another direction 2."
                )
        steps1 = _steps(n1, feature.params.get("symmetric1") is True)
        steps2 = _steps(n2, second and feature.params.get("symmetric2") is True)
        steps1 = _seed_cell(feature, 1, n1, steps1)  # TR270 (D1501)
        if second:
            steps2 = _seed_cell(feature, 2, n2, steps2)
            d1, d2 = _rotated(feature, d1, d2)
        at1 = law_positions(feature, 1, s1, [i for i, _a in steps1])  # TR366
        at2 = law_positions(feature, 2, s2, [j for j, _b in steps2])
        if len(steps1) * len(steps2) > MAX_INSTANCES:
            raise FeatureError(f"{feature.name}: at most {MAX_INSTANCES} instances. Use fewer.")
        seed_only = feature.params.get("seed_only2") is True
        out: list[Placement] = []
        for i, a in steps1:
            for j, b in steps2:
                if i == 0 and j == 0:
                    continue
                if seed_only and j != 0 and i != 0:
                    continue
                delta = (
                    d1[0] * at1[i] + d2[0] * at2[j],
                    d1[1] * at1[i] + d2[1] * at2[j],
                    d1[2] * at1[i] + d2[2] * at2[j],
                )
                out.append(Placement((a, b), translation(delta)))
        return out, issues


def _value(feature: Feature, name: str) -> float:
    value = feature.params.get(name)
    return value.value if isinstance(value, Param) else 0.0


def _seed_cell(
    feature: Feature, k: int, count: int, steps: list[tuple[int, int]]
) -> list[tuple[int, int]]:
    """Shift the steps so the seed sits in cell ``seed_cell<k>`` (TR270, D1501).

    Cell ``s`` (1 to the count) holds the seed: cells before it are copies the other
    way. Instance numbers stay the cell numbers, so cell 1 is always the first."""
    value = feature.params.get(f"seed_cell{k}")
    if not isinstance(value, Param):
        return steps
    cell = round(value.value)
    if cell == 1:
        return steps
    if feature.params.get(f"symmetric{k}") is True:
        raise FeatureError(
            f"{feature.name}: a symmetric direction already has the seed in the middle. "
            "Turn off Symmetric, or set the seed cell to 1."
        )
    if abs(cell - value.value) > 1e-9 or not 1 <= cell <= count:
        raise FeatureError(
            f"{feature.name}: the seed cell must be a whole number from 1 to {count}. "
            "Enter a cell number within the count."
        )
    return [(i - (cell - 1), n) for i, n in steps]


def _rotated(
    feature: Feature, d1: tuple[float, float, float], d2: tuple[float, float, float]
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Both directions turned by ``rotate`` about their common normal (TR270, D1501)."""
    angle = _value(feature, "rotate")
    if abs(angle) < 1e-12:
        return d1, d2
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Vec

    normal = gp_Vec(*d1).Crossed(gp_Vec(*d2))
    axis = gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(normal))
    out = []
    for d in (d1, d2):
        v = gp_Vec(*d).Rotated(axis, angle)
        out.append((v.X(), v.Y(), v.Z()))
    return out[0], out[1]


def _steps(count: int, symmetric: bool) -> list[tuple[int, int]]:
    """(step along the direction, instance number): 0 to count - 1, and with
    ``symmetric`` also -1 to -(count - 1), numbered count + 1 onward (TR140)."""
    out = [(i, i + 1) for i in range(count)]
    if symmetric:
        out += [(-i, count + i) for i in range(1, count)]
    return out
