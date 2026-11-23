"""Selected Regions picks: references to sketch regions, and how they resolve (D190).

``fdcad.core.features.sketch.sketch_for`` uses this to give a feature the profile of
its picked regions.

A pick is stored in the feature's ``refs.regions`` list as
``{"kind": "region", "name": "region(e3+|e9-)", "snapshot": {"point": [u, v], "area": a}}``
(FDEF_SPEC 5.3.3). The name is the sketch curves that bound the region and the side
of each (``fdcad.core.sketch.regions``), so it survives dimension changes and moves.

Resolution, in line with PLAN section 6 item 6:

1. The region with the same name.
2. Else the one region whose curves include every curve and side of the name (a new
   curve cut into the region). The feature gets a warning that names the pick.
3. Else the pick is lost: an error names the pick and asks the user to pick again.
   The region is never swapped silently (CLAUDE.md rule 12).
"""

from __future__ import annotations

from typing import Any

from fdcad.core.document.model import Feature
from fdcad.core.features.base import FeatureError, FeatureState, Issue
from fdcad.core.sketch.regions import Region, Regions, parse_sides

KIND = "region"
LOST_CODE = "region_lost"


def region_reference(region: Region) -> dict[str, Any]:
    """The stored form of a pick (FDEF_SPEC 5.3.3)."""
    return {
        "kind": KIND,
        "name": region.name,
        "snapshot": {
            "point": [round(region.centre[0], 9), round(region.centre[1], 9)],
            "area": round(region.area, 9),
        },
    }


def picks_of(feature: Feature) -> list[dict[str, Any]]:
    """The region picks stored on a feature (empty when it uses the whole sketch)."""
    picks = feature.refs.get("regions")
    if not isinstance(picks, list):
        return []
    return [p for p in picks if isinstance(p, dict)]


def pick_label(index: int) -> str:
    """How the Selected Regions box and messages call pick ``index`` (0 based)."""
    return f"Region {index + 1}"


def resolve_regions(
    found: Regions, picks: list[dict[str, Any]], owner: str, sketch_name: str
) -> tuple[list[Region], list[Issue]]:
    """The regions the picks name, and warnings. Raises FeatureError for a lost pick."""
    chosen: list[Region] = []
    issues: list[Issue] = []
    for index, pick in enumerate(picks):
        name = str(pick.get("name", ""))
        label = pick_label(index)
        region = found.find(name)
        if region is None:
            sides = parse_sides(name)
            wider = [r for r in found.regions if sides is not None and sides <= r.sides]
            if len(wider) != 1:
                raise FeatureError(
                    f"{owner} failed: {label} of Selected Regions is lost because "
                    f"{sketch_name} changed. Pick the region again in Selected Regions.",
                    highlight=[name],
                )
            region = wider[0]
            issues.append(
                Issue(
                    FeatureState.WARNING,
                    f"{owner}: {label} of Selected Regions now has more curves around it, "
                    f"because {sketch_name} changed. Check the result, or pick the region "
                    "again to clear this warning.",
                    highlight=[region.name],
                    code="region_changed",
                )
            )
        if all(region is not r for r in chosen):
            chosen.append(region)
    return chosen, issues
