"""Partial success for tools with many picks (TR400, D2109).

When a Move Face with several faces or a Hole with several positions fails as a
whole, each pick is tried on its own. The error then names the picks that fail and
offers a fix that finishes on the others: "Keep the faces that worked" drops the
failing faces from the pick list (as Delete Face does), and "Cut the holes that
work" adds the failing points of an existing sketch to the hole's skipped points
(TR143, D1520). Nothing changes until the user clicks the fix (CLAUDE.md 5.12).
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

from fdcad.core.document.model import Feature
from fdcad.core.features.base import FeatureError, Fix

#: Most picks tried one by one (each try is a whole build).
MOST_TRIES = 12
#: The fix action that adds sketch points to a hole's skipped points.
SKIP_POINTS = "skip_points"
#: The fix action that removes failed picks from a list reference (as Delete Face).
DROP_REFS = "drop_refs"


def failing_refs(feature: Feature, key: str, build: Callable[[Feature], Any]) -> list[str] | None:
    """The names of the picks in ``refs[key]`` that fail on their own, or None when
    all or none fail, or there are too few or too many picks to try."""
    refs = feature.refs.get(key)
    if not isinstance(refs, list) or not 2 <= len(refs) <= MOST_TRIES:
        return None
    failed = []
    for ref in refs:
        one = copy.deepcopy(feature)
        one.refs[key] = [copy.deepcopy(ref)]
        try:
            build(one)
        except FeatureError:
            failed.append(str(ref.get("name", "")) if isinstance(ref, dict) else "")
    if not failed or len(failed) == len(refs):
        return None
    return failed


def drop_error(feature: Feature, key: str, failed: list[str], exc: FeatureError) -> FeatureError:
    """The error naming the failing faces, with the fix that keeps the others."""
    from fdcad.core.features.direct import short_name

    listed = ", ".join(short_name(n) for n in failed)
    return FeatureError(
        f"{feature.name} failed: {listed} cannot be moved with the others. "
        "Keep the faces that worked, or change the distance.",
        fixes=[
            Fix(
                "Keep the faces that worked",
                DROP_REFS,
                {"feature": feature.id, "ref": key, "names": failed},
            )
        ],
        highlight=failed,
    )


def failing_points(
    feature: Feature, points: list[str], cut_one: Callable[[int], Any]
) -> list[str] | None:
    """The hole points whose hole fails on its own, or None when all or none fail."""
    if "sketch" not in feature.refs or not 2 <= len(points) <= MOST_TRIES:
        return None
    failed = []
    for i, point in enumerate(points):
        try:
            cut_one(i)
        except FeatureError:
            failed.append(point)
    if not failed or len(failed) == len(points):
        return None
    return failed


def skip_error(feature: Feature, failed: list[str], exc: FeatureError) -> FeatureError:
    """The error naming how many holes fail, with the fix that cuts the others."""
    return FeatureError(
        f"{feature.name} failed: {len(failed)} of its holes cannot be cut. "
        "Cut the holes that work, or move those points.",
        fixes=[
            Fix(
                f"Cut the holes that work (skip {len(failed)})",
                SKIP_POINTS,
                {"feature": feature.id, "points": failed},
            )
        ],
    )


def with_skipped(feature: Feature, points: list[str]) -> Feature:
    """A copy of the hole with ``points`` added to its skipped points."""
    out = copy.deepcopy(feature)
    raw = out.data.get("skip_points")
    skip = [str(p) for p in raw] if isinstance(raw, list) else []
    out.data["skip_points"] = skip + [p for p in points if p not in skip]
    return out
