"""Jog (PHASE5_SPEC P5.6, DECISIONS D532): two opposite bends along a sketched line.

Type ``jog``. The sketch holds one line on a flat face of the sheet, as for
Sketched Bend (D338). The moved side ends parallel to the fixed side, offset
along the face normal.

Params (all optional except ``offset``):
- ``offset``: length. ``offset_from``: "same_face" (default), "inner_faces" or "outer_faces".
- ``angle``: angle of both bends (default 90 degrees). ``reverse``: jog the other way.
- ``position``: where the first bend sits on the line, as Sketched Bend.
- ``flip_fixed``: keep the other side fixed (first wall only).
- ``radius``, ``method``, ``k_factor``, ``allowance``: own bend values.

Refs: ``sketch``, ``sheet_metal``.

Face roles: ``<fid>/bend1/<role>``, ``<fid>/bend2/<role>``, ``<fid>/split/<role>``,
``<fid>/middle/<old name>`` and ``<fid>/moved/<old name>``.
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
    register,
)
from fdcad.core.features.extrude import sketch_input_raw
from fdcad.core.features.sheetmetal.common import require_sheet, value
from fdcad.core.features.sheetmetal.model import (
    Bend,
    SheetModel,
    SheetResult,
    Vec2,
    Wall,
    along,
    basis,
    common_with,
    oriented_box,
    unit2,
    volume,
)
from fdcad.core.features.sheetmetal.params import (
    METHODS,
    bend_allowance,
    rule_from,
    sheet_defaults,
)
from fdcad.core.features.sheetmetal.sketched_bend import (
    POSITIONS,
    SketchedBend,
    size_of,
    sketch_line,
    span_of,
    tangent_lines,
    wall_of,
)
from fdcad.core.features.solids import transform
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind

OFFSET_FROM = ("same_face", "inner_faces", "outer_faces")
_TOL = 1e-6


def middle_length(shift: float, radius: float, thickness: float, angle: float) -> float:
    """Length of the straight wall between the two bends of a jog (D532)."""
    return (shift - (2 * radius + thickness) * (1 - math.cos(angle))) / math.sin(angle)


@register
class Jog(FeatureType):
    """Offsets part of a wall with two opposite bends."""

    type_name = "jog"
    makes_solid = True
    params = (
        ParamSpec("offset", kind=Kind.LENGTH, optional=True),
        ParamSpec("offset_from", choices=OFFSET_FROM, optional=True),
        ParamSpec("angle", kind=Kind.ANGLE, optional=True),
        ParamSpec("reverse", default=False, optional=True),
        ParamSpec("position", choices=POSITIONS, optional=True),
        ParamSpec("flip_fixed", default=False, optional=True),
        ParamSpec("radius", kind=Kind.LENGTH, optional=True),
        ParamSpec("method", choices=METHODS, optional=True),
        ParamSpec("k_factor", kind=Kind.NUMBER, optional=True),
        ParamSpec("allowance", kind=Kind.LENGTH, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Split the wall and offset the moved side."""
        model = self.model(feature, ctx)
        return SheetResult(body=model.build(feature.id, feature.name), sheet=model)

    def model(self, feature: Feature, ctx: BuildContext) -> SheetModel:
        """The sheet with this jog added."""
        name, fid = feature.name, feature.id
        model = require_sheet(feature, ctx)
        t = model.thickness
        rule = rule_from(feature, sheet_defaults(feature, ctx).rule)
        angle = value(feature, "angle", math.pi / 2)
        if not _TOL < angle < math.pi - _TOL:
            raise FeatureError(
                f"{name}: the jog angle must be between 0 and 180 degrees. "
                "Enter an angle in that range."
            )
        offset = value(feature, "offset", 0.0)
        mode = str(feature.params.get("offset_from", "same_face"))
        shift = (
            offset + t if mode == "inner_faces" else offset - t if mode == "outer_faces" else offset
        )
        if shift <= _TOL:
            raise FeatureError(f"{name}: the jog offset is too small. Enter a larger offset.")
        middle = middle_length(shift, rule.radius, t, angle)
        if middle < -_TOL:
            raise FeatureError(
                f"{name}: the offset is too small for the bend radius and angle. Enter a "
                "larger offset, a smaller radius or a smaller angle."
            )
        middle = max(middle, 0.0)
        allowance = bend_allowance(rule, t, angle, name)
        sketch = sketch_input_raw(feature, ctx)
        ends = sketch_line(sketch, name)
        wid, a, b, top = wall_of(model, ends[0], ends[1], name)
        d = unit2((b[0] - a[0], b[1] - a[1]))
        w: Vec2 = (d[1], -d[0])
        piece = model.piece(wid)
        w = SketchedBend()._moving_side(feature, model, wid, piece, a, w)
        e = along(w)
        level = a[0] * w[0] + a[1] * w[1]
        t1, t2 = tangent_lines(str(feature.params.get("position", "centreline")), level, allowance)
        t3 = t2 + middle + allowance
        big = 1000.0 + 10 * size_of(piece)

        def region(tag: str, lo: float, hi: float) -> NamedShape:
            far = oriented_box(f"{fid}/{tag}", (0.0, 0.0), w, (-big, lo, -1.0), (big, hi, t + 1))
            return common_with(fid, piece, far)

        beyond = region("beyond", t1, big)
        if volume(beyond.shape) <= _TOL:
            raise FeatureError(f"{name}: the line does not cross the wall. Move the line.")
        x0, x1 = span_of(beyond, w)
        moved = region("moving", t3, big)
        if volume(moved.shape) <= _TOL:
            raise FeatureError(
                f"{name}: the jog runs off the wall. Move the line or reduce the offset."
            )
        up = 1 if top else -1
        if feature.params.get("reverse"):
            up = -up
        mid_id, moved_id = f"{fid}/middle", f"{fid}/moved"
        o2: Vec2 = (e[0] * x0 + w[0] * t2, e[1] * x0 + w[1] * t2)
        o3: Vec2 = (e[0] * x0 + w[0] * t3, e[1] * x0 + w[1] * t3)
        to_moved = basis(o3, w).Inverted()
        self_bends = SketchedBend._carry_children
        self_bends(model, wid, moved_id, w, t1, t3, to_moved, name)
        length = x1 - x0
        p1: Vec2 = (e[0] * x0 + w[0] * t1, e[1] * x0 + w[1] * t1)
        b1 = Bend(
            f"{fid}/bend1", fid, wid, mid_id, p1, w, length, up, rule.radius, angle, allowance
        )
        b2 = Bend(
            f"{fid}/bend2", fid, mid_id, moved_id, (0.0, middle), (0.0, 1.0), length, -up,
            rule.radius, angle, allowance,
        )  # fmt: skip
        if middle > _TOL:
            mid = transform(region("middle_cut", t2, t2 + middle), basis(o2, w).Inverted())
            model.walls[mid_id] = Wall(mid_id, fid, _renamed(mid, f"{fid}/middle"))
        moved_local = transform(moved, to_moved)
        model.walls[moved_id] = Wall(moved_id, fid, _renamed(moved_local, f"{fid}/moved"))
        cut = oriented_box(f"{fid}/split", (0.0, 0.0), w, (-big, t1, -1.0), (big, big, t + 1.0))
        model.walls[wid].cuts.append(cut)
        model.bends[b1.bid] = b1
        model.bends[b2.bid] = b2
        return model


def _renamed(named: NamedShape, prefix: str) -> NamedShape:
    return NamedShape(named.shape, [(f"{prefix}/{n}", f) for n, f in named.faces])
