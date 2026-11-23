"""Perforated Fold Line (TR370 item 2, DECISIONS D1109): a row of short cuts for hand bending.

Type ``perforation``. Each sketched line on a flat face of a wall gets a row of slots
through the sheet along it: ``slot_length`` long, ``slot_width`` wide, with a
``bridge`` of uncut sheet between slots. The row is centred on the line, so the
ends of the line keep equal bridges. The slots are cut from the wall in its own
frame, so they fold with it and show in the flat pattern.

Params: ``slot_length``, ``slot_width``, ``bridge`` (lengths). Refs: ``sketch``,
``sheet_metal``.

Face roles: ``<fid>/slot<i>_<k>/<role>``.
"""

from __future__ import annotations

import math

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    Vec3,
    register,
)
from fdcad.core.features.extrude import sketch_input_raw
from fdcad.core.features.sheetmetal.common import require_sheet, value
from fdcad.core.features.sheetmetal.locate import local_vector
from fdcad.core.features.sheetmetal.model import (
    SheetModel,
    SheetResult,
    apply,
    inside,
    oriented_box,
    volume,
)
from fdcad.core.naming.names import NamedShape
from fdcad.core.occ import BRepAlgoAPI_Common
from fdcad.core.sketch.model import Line
from fdcad.core.sketch.profiles import SketchPlane
from fdcad.core.units import Kind

TYPE = "perforation"
_TOL = 1e-5


def slot_starts(run: float, slot: float, bridge: float) -> list[float]:
    """Where each slot starts along a line ``run`` long, the row centred on it (D1109)."""
    count = int((run + bridge) // (slot + bridge) + 1e-9)
    if count < 1:
        return []
    used = count * slot + (count - 1) * bridge
    first = (run - used) / 2
    return [first + k * (slot + bridge) for k in range(count)]


@register
class Perforation(FeatureType):
    """Cuts rows of short slots along sketched lines."""

    type_name = TYPE
    makes_solid = True
    params = (
        ParamSpec("slot_length", kind=Kind.LENGTH, optional=True),
        ParamSpec("slot_width", kind=Kind.LENGTH, optional=True),
        ParamSpec("bridge", kind=Kind.LENGTH, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Cut the slots and rebuild the sheet."""
        model = self.model(feature, ctx)
        return SheetResult(body=model.build(feature.id, feature.name), sheet=model)

    def model(self, feature: Feature, ctx: BuildContext) -> SheetModel:
        """The sheet with the slot rows cut."""
        name, fid = feature.name, feature.id
        model = require_sheet(feature, ctx)
        t = model.thickness
        slot = value(feature, "slot_length", 5.0)
        width = value(feature, "slot_width", 0.5)
        bridge = value(feature, "bridge", 2.0)
        if slot <= 0 or width <= 0 or bridge <= 0:
            raise FeatureError(
                f"{name}: enter a slot length, slot width and bridge greater than zero."
            )
        sketch = sketch_input_raw(feature, ctx)
        lines = [c for c in sketch.model.curves() if isinstance(c, Line) and not c.construction]
        if not lines:
            raise FeatureError(f"{name}: the sketch has no lines. Draw the fold lines.")
        plane = sketch.plane
        if wall_of(model, plane.origin, plane.normal) is None:
            raise FeatureError(
                f"{name}: the sketch is not on a flat face of a wall. Draw it on a wall face."
            )
        places = model.placements(False)
        cuts: dict[str, list[NamedShape]] = {}
        for i, line in enumerate(lines, start=1):
            start = world_point(plane, sketch.model.xy(line.p1))
            end = world_point(plane, sketch.model.xy(line.p2))
            middle = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2, (start[2] + end[2]) / 2)
            # The wall under this line (D1072); each line may be on a wall of its own.
            wid = wall_of(model, plane.origin, plane.normal, middle)
            assert wid is not None
            inv = places[wid].Inverted()
            piece = model.piece(wid)
            a = apply(inv, start)
            b = apply(inv, end)
            run = math.hypot(b[0] - a[0], b[1] - a[1])
            if run < _TOL:
                continue
            e = ((b[0] - a[0]) / run, (b[1] - a[1]) / run)
            w = (-e[1], e[0])  # along(w) == e
            for k, x in enumerate(slot_starts(run, slot, bridge), start=1):
                box = oriented_box(
                    f"{fid}/slot{i}_{k}", (a[0], a[1]), w,
                    (x, -width / 2, -1.0), (x + slot, width / 2, t + 1.0),
                )  # fmt: skip
                common = BRepAlgoAPI_Common(piece.shape, box.shape)
                if common.IsDone() and volume(common.Shape()) > _TOL:
                    cuts.setdefault(wid, []).append(box)
        if not cuts:
            raise FeatureError(
                f"{name}: no slot falls on the wall. Draw longer lines on the wall, or use "
                "shorter slots."
            )
        for wid, boxes in cuts.items():
            model.walls[wid].cuts.extend(boxes)
        return model


def world_point(plane: SketchPlane, uv: tuple[float, float]) -> Vec3:
    p = plane.to_3d(uv[0], uv[1])
    return (p.X(), p.Y(), p.Z())


def wall_of(model: SheetModel, origin: Vec3, normal: Vec3, near: Vec3 | None = None) -> str | None:
    """A wall whose z = 0 or z = thickness face holds the plane: with ``near``, a point
    of the plane, the one that has sheet there, else the first.

    Two walls can lie in one plane (the two brims of a hat section). Without ``near``
    the first was taken for every line, so a row of slots drawn on the second brim
    found "no slot on the wall", and marks drawn there were stored on the first brim
    (D1072).
    """
    t = model.thickness
    first: str | None = None
    for wid, place in model.placements(False).items():
        if wid not in model.walls:
            continue
        inv = place.Inverted()
        if abs(abs(local_vector(inv, normal)[2]) - 1) > 1e-6:
            continue
        level = apply(inv, origin)[2]
        if abs(level) < _TOL or abs(level - t) < _TOL:
            if near is None:
                return wid
            if first is None:
                first = wid
            local = apply(inv, near)
            if inside(model.piece(wid).shape, (local[0], local[1], t / 2)):
                return wid
    return first
