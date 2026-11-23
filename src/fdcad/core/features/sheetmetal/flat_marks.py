"""Flat Marks (TR283 item 2, DECISIONS D1112): sketch lines mapped onto the flat pattern.

Type ``flat_marks``. Every line of a sketch drawn on a flat face of a wall becomes a
cosmetic mark on that wall, like Cross Break's lines (D539): it shows folded and
flat, and the flat pattern DXF and SVG write it with the other marks, so layout
lines, hole centres or part numbers drawn as lines reach the flat blank. Arcs and
circles are written as short lines through points 1 mm apart or less. The part's
shape does not change.

Params: ``title`` (optional text, "Mark" by default). Refs: ``sketch``, ``sheet_metal``.
"""

from __future__ import annotations

import itertools
import math

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    register,
)
from fdcad.core.features.extrude import sketch_input_raw
from fdcad.core.features.sheetmetal.common import own_body, require_sheet
from fdcad.core.features.sheetmetal.model import SheetResult, apply
from fdcad.core.features.sheetmetal.perforation import wall_of, world_point
from fdcad.core.sketch.model import Arc, Circle, Line, Sketch

Vec2 = tuple[float, float]

TYPE = "flat_marks"


@register
class FlatMarks(FeatureType):
    """Copies sketch lines onto a wall as marks that reach the flat pattern."""

    type_name = TYPE
    makes_solid = True
    params = (ParamSpec("title", optional=True),)

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Add the marks to the sheet model; the part is unchanged."""
        name = feature.name
        model = require_sheet(feature, ctx)
        sketch = sketch_input_raw(feature, ctx)
        plane = sketch.plane
        if wall_of(model, plane.origin, plane.normal) is None:
            raise FeatureError(
                f"{name}: the sketch is not on a flat face of a wall. Draw it on a wall face."
            )
        places = model.placements(False)
        raw = feature.params.get("title")
        title = raw.strip() if isinstance(raw, str) and raw.strip() else "Mark"
        sk = sketch.model
        count = 0
        for curve in sk.curves():
            if getattr(curve, "construction", False):
                continue
            for a, b in _pieces(sk, curve):
                start, end = world_point(plane, a), world_point(plane, b)
                middle = (
                    (start[0] + end[0]) / 2,
                    (start[1] + end[1]) / 2,
                    (start[2] + end[2]) / 2,
                )
                # The wall under this piece of the mark (D1072), not the first wall
                # in the sketch's plane.
                wid = wall_of(model, plane.origin, plane.normal, middle)
                assert wid is not None
                inv = places[wid].Inverted()
                p = apply(inv, start)
                q = apply(inv, end)
                model.marks.append((wid, (p[0], p[1]), (q[0], q[1]), title))
                count += 1
        if count == 0:
            raise FeatureError(f"{name}: the sketch has no lines or arcs. Draw the marks.")
        return SheetResult(body=own_body(feature, ctx), sheet=model)


def _pieces(sk: Sketch, curve: object) -> list[tuple[Vec2, Vec2]]:
    """A sketch curve as straight pieces (arcs and circles split into short chords)."""
    if isinstance(curve, Line):
        return [(sk.xy(curve.p1), sk.xy(curve.p2))]
    if isinstance(curve, Circle):
        c, r = sk.xy(curve.center), curve.radius
        start, sweep = 0.0, 2 * math.pi
    elif isinstance(curve, Arc):
        c = sk.xy(curve.center)
        s, e = sk.xy(curve.start), sk.xy(curve.end)
        if not curve.ccw:
            s, e = e, s
        r = math.hypot(s[0] - c[0], s[1] - c[1])
        start = math.atan2(s[1] - c[1], s[0] - c[0])
        end = math.atan2(e[1] - c[1], e[0] - c[0])
        sweep = (end - start) % (2 * math.pi) or 2 * math.pi
    else:
        return []
    steps = max(8, math.ceil(r * sweep))
    pts = [
        (
            c[0] + r * math.cos(start + sweep * k / steps),
            c[1] + r * math.sin(start + sweep * k / steps),
        )
        for k in range(steps + 1)
    ]
    return list(itertools.pairwise(pts))
