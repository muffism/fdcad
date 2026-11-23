"""Tab and Slot (PHASE5_SPEC P5.6, DECISIONS D536): tabs on one wall through slots in another.

Type ``tab_slot``. Params (all optional): ``tab_count`` (default 2), ``tab_length``,
``depth`` (default the thickness), ``spacing`` (0: spread over the edge),
``clearance``. ``edge_offset`` (length): the tabs spread between two equal offsets in
from the ends of the edge; with a spacing they stay centred on the edge. ``skip_tabs`` (text
such as "2, 4"): tab numbers left out, with their slots (TR174 item 6, D1107). The Sheet
Metal feature's ``kerf`` makes each slot that much narrower on
each side in the sheet's plane (D802).

Refs: ``edge`` (a straight outside edge of the tab wall), ``face`` (a flat face
of the slot wall), ``sheet_metal``.

Face roles: ``<fid>/tab<k>/<role>``, ``<fid>/slot<k>/<role>``.
"""

from __future__ import annotations

import math

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
from fdcad.core.features.lookup import resolve_edge, resolve_face
from fdcad.core.features.sheetmetal.common import require_sheet, sheet_kerf, value
from fdcad.core.features.sheetmetal.edge_flange import find_edge
from fdcad.core.features.sheetmetal.locate import wall_face
from fdcad.core.features.sheetmetal.model import (
    SheetModel,
    SheetResult,
    along,
    oriented_box,
    volume,
)
from fdcad.core.features.solids import transform
from fdcad.core.occ import BRepAlgoAPI_Common
from fdcad.core.units import Kind

_TOL = 1e-6


def tab_centres(
    span: float, count: int, length: float, spacing: float, offset: float = 0.0
) -> list[float]:
    """Centres of the tabs along an edge of length ``span`` (D536), spread between equal
    ``offset`` margins at both ends when there is no spacing (D1107)."""
    if spacing <= 0:
        pitch = (span - 2 * offset) / count
        return [offset + (i + 0.5) * pitch for i in range(count)]
    return [span / 2 + (i - (count - 1) / 2) * spacing for i in range(count)]


def skipped(feature: Feature, count: int) -> set[int]:
    """Tab numbers (from 1) listed in ``skip_tabs``. Raises FeatureError on a bad entry."""
    raw = feature.params.get("skip_tabs")
    if not isinstance(raw, str) or not raw.strip():
        return set()
    out: set[int] = set()
    for word in raw.split(","):
        word = word.strip()
        if not word:
            continue
        if not word.isdigit() or not 1 <= int(word) <= count:
            raise FeatureError(
                f"{feature.name}: the tabs to skip must be numbers from 1 to {count}. Fix the list."
            )
        out.add(int(word))
    if len(out) >= count:
        raise FeatureError(f"{feature.name}: every tab is skipped. Leave at least one tab.")
    return out


@register
class TabSlot(FeatureType):
    """Adds tabs to an edge and matching slots to the wall they pass through."""

    type_name = "tab_slot"
    makes_solid = True
    params = (
        ParamSpec("tab_count", kind=Kind.NUMBER, optional=True),
        ParamSpec("tab_length", kind=Kind.LENGTH, optional=True),
        ParamSpec("depth", kind=Kind.LENGTH, optional=True),
        ParamSpec("spacing", kind=Kind.LENGTH, optional=True),
        ParamSpec("clearance", kind=Kind.LENGTH, optional=True),
        ParamSpec("edge_offset", kind=Kind.LENGTH, optional=True),
        ParamSpec("skip_tabs", optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Add the tabs and slots and rebuild the sheet."""
        model, issues = self.model(feature, ctx)
        return SheetResult(body=model.build(feature.id, feature.name), issues=issues, sheet=model)

    def model(self, feature: Feature, ctx: BuildContext) -> tuple[SheetModel, list[Issue]]:
        """The sheet with the tabs and slots."""
        name, fid = feature.name, feature.id
        model = require_sheet(feature, ctx)
        t = model.thickness
        edge_ref, face_ref = feature.refs.get("edge"), feature.refs.get("face")
        if not isinstance(edge_ref, dict) or not isinstance(face_ref, dict):
            raise FeatureError(f"{name}: pick the tab edge and a face of the slot wall.")
        edge, issues = resolve_edge(ctx.body, edge_ref, name)
        face, found = resolve_face(ctx.body, face_ref, name)
        issues = [*issues, *found]
        pick = find_edge(model, edge, name, "")
        slot_wall = wall_face(model, face, name).wid
        if slot_wall == pick.wid:
            raise FeatureError(
                f"{name}: the slot face must be on another wall than the tab edge. "
                "Pick a face on the facing wall."
            )
        count = round(value(feature, "tab_count", 2.0))
        length = value(feature, "tab_length", 0.0)
        depth = value(feature, "depth", t)
        spacing = value(feature, "spacing", 0.0)
        clearance = value(feature, "clearance", 0.0)
        # The cut widens a slot and thins a tab by the kerf, so the slot is drawn narrower
        # in the sheet's plane by the kerf on each side (D802); never below the tab.
        kerf = sheet_kerf(feature, ctx)
        across = max(clearance - kerf, -min(length, t) / 4)
        if count < 1 or length <= 0 or depth <= 0 or clearance < 0:
            raise FeatureError(
                f"{name}: enter at least one tab, a tab length and depth greater than zero "
                "and a clearance of zero or more."
            )
        w = pick.w
        e = along(w)
        a, b = pick.a, pick.b
        if a[0] * e[0] + a[1] * e[1] > b[0] * e[0] + b[1] * e[1]:
            a, b = b, a
        span = math.hypot(b[0] - a[0], b[1] - a[1])
        offset = value(feature, "edge_offset", 0.0)
        if offset < 0 or 2 * offset >= span:
            raise FeatureError(
                f"{name}: the edge offset must be zero or more and leave room on the edge. "
                "Enter a smaller offset."
            )
        centres = tab_centres(span, count, length, spacing, offset)
        if min(centres) - length / 2 < -_TOL or max(centres) + length / 2 > span + _TOL:
            raise FeatureError(
                f"{name}: the tabs do not fit on the edge. Use fewer, shorter or closer tabs."
            )
        places = model.placements(False)
        to_slot = places[slot_wall].Inverted().Multiplied(places[pick.wid])
        tabs = []
        slot_piece = model.piece(slot_wall)
        gone = skipped(feature, count)
        for k, c in enumerate(centres, start=1):
            if k in gone:
                continue
            x0, x1 = c - length / 2, c + length / 2
            tabs.append(oriented_box(f"{fid}/tab{k}", a, w, (x0, 0.0, 0.0), (x1, depth, t)))
            slot = oriented_box(
                f"{fid}/slot{k}", a, w,
                (x0 - across, -clearance, -across), (x1 + across, depth + clearance,
                                                     t + across),
            )  # fmt: skip
            local = transform(slot, to_slot)
            common = BRepAlgoAPI_Common(slot_piece.shape, local.shape)
            if not common.IsDone() or volume(common.Shape()) <= _TOL:
                raise FeatureError(
                    f"{name}: tab {k} misses the slot wall. Pick an edge that meets the slot "
                    "wall, or a longer depth."
                )
            model.walls[slot_wall].cuts.append(local)
        model.add_material(pick.wid, tabs)
        return model, issues
