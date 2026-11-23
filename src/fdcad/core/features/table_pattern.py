"""Table driven pattern (TUTORIAL_REVIEW_SPEC_2 TR58, DECISIONS D821).

Type ``table_pattern``. One copy per row of a table of X and Y positions.

- ``data.rows``: a list of ``[x, y]`` in mm, or ``[x, y, false]`` for a row that
  is ticked off (kept in the table, no copy). The copy of row k has instance
  number k, so the usual ``skip`` list and the Skip copies fix still work.
- ``refs.frame``: optional coordinate system, plane or flat face; X and Y are
  measured along its axes from its origin. Without it, the part's XY axes.
- ``refs.point``: optional reference point of the seed, else the seed's centre.
  Each copy puts the reference point at the row's position. A row at the
  reference point itself is the seed and makes no copy.
- The seed: ``features``, ``faces`` or ``bodies``, as in other patterns.
Params as linear patterns.
"""

from __future__ import annotations

import math
import re

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    register,
)
from fdcad.core.features.direct import translation
from fdcad.core.features.geometry_refs import minus, resolve_placement
from fdcad.core.features.linear_pattern import COMMON_PARAMS, MAX_INSTANCES
from fdcad.core.features.patterns import Placement, apply_pattern
from fdcad.core.features.seeds import seed_centre
from fdcad.core.features.solids import check_result
from fdcad.core.naming.names import NamedShape


def read_rows(text: str) -> list[list[float]]:
    """X and Y rows from text: two numbers a line split by spaces, commas, tabs or
    semicolons (a spreadsheet paste or a text file). Other lines are skipped."""
    out: list[list[float]] = []
    for line in text.splitlines():
        parts = [p for p in re.split(r"[\s,;]+", line.strip()) if p]
        if len(parts) != 2:
            continue
        try:
            row = [float(p) for p in parts]
        except ValueError:
            continue
        if all(math.isfinite(v) for v in row):
            out.append(row)
    return out


def write_rows(rows: list[list[float]]) -> str:
    """The rows as text, one ``x<TAB>y`` a line, for saving the table to a file."""
    return "".join(f"{r[0]:g}\t{r[1]:g}\n" for r in rows)


def table_rows(feature: Feature) -> list[tuple[float, float, bool]]:
    """The stored rows as (x, y, used); malformed rows are left out."""
    raw = feature.data.get("rows")
    out: list[tuple[float, float, bool]] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, list | tuple) or len(item) not in (2, 3):
            continue
        x, y = item[0], item[1]
        if not all(isinstance(v, int | float) and not isinstance(v, bool) for v in (x, y)):
            continue
        used = item[2] if len(item) == 3 else True
        out.append((float(x), float(y), used is not False))
    return out


@register
class TablePattern(FeatureType):
    """Copies features, faces or bodies to the X and Y positions of a table."""

    type_name = "table_pattern"
    makes_solid = True
    params = COMMON_PARAMS

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Copy the seed and check the result."""
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
            placements = placements[:1]
        outcome = apply_pattern(feature, ctx, placements)
        return outcome.body, issues + outcome.issues

    def placements(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[list[Placement], list[Issue]]:
        """One copy per ticked row, the seed's own position left out."""
        name = feature.name
        rows = table_rows(feature)
        if not any(used for _x, _y, used in rows):
            raise FeatureError(f"{name}: the table has no rows. Type or load X and Y positions.")
        if len(rows) > MAX_INSTANCES:
            raise FeatureError(f"{name}: at most {MAX_INSTANCES} rows. Use fewer rows.")
        issues: list[Issue] = []
        if feature.refs.get("point") is not None:
            place = resolve_placement(ctx, feature.refs["point"], name, "point")
            start = place.point
            issues += place.issues
        else:
            start = seed_centre(feature, ctx)
        origin, xdir, ydir = (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)
        if feature.refs.get("frame"):
            from fdcad.core.features.bounding_box import frame_from_ref

            ax = frame_from_ref(ctx, feature.refs["frame"], name)
            loc, xd, yd = ax.Location(), ax.XDirection(), ax.YDirection()
            origin = (loc.X(), loc.Y(), loc.Z())
            xdir, ydir = (xd.X(), xd.Y(), xd.Z()), (yd.X(), yd.Y(), yd.Z())
        # Copies keep the seed's height above the frame's plane.
        normal = (
            xdir[1] * ydir[2] - xdir[2] * ydir[1],
            xdir[2] * ydir[0] - xdir[0] * ydir[2],
            xdir[0] * ydir[1] - xdir[1] * ydir[0],
        )
        height = sum((start[i] - origin[i]) * normal[i] for i in range(3))
        out: list[Placement] = []
        for k, (x, y, used) in enumerate(rows, start=1):
            if not used:
                continue
            target = tuple(
                origin[i] + x * xdir[i] + y * ydir[i] + height * normal[i] for i in range(3)
            )
            delta = minus(target, start)  # type: ignore[arg-type]
            if math.hypot(*delta) < 1e-6:
                continue  # the seed itself
            out.append(Placement((k, 1), translation(delta)))
        return out, issues
