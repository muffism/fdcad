"""Sketched Bend (PHASE5_SPEC P5.4): bend a flat wall along a sketched line.

Type ``sketched_bend``. The sketch holds one line on a flat face of the sheet.
The line is extended across the whole wall (D338). One side stays fixed: for
the first wall the larger side, swapped by ``flip_fixed``; for any other wall
the side joined to the rest of the sheet.

Params (all optional):
- ``angle``: bend angle (default 90 degrees). ``reverse``: bend to the other side.
- ``position``: "centreline" (default), "material_inside", "material_outside"
  or "bend_outside" (D338).
- ``flip_fixed``: keep the other side fixed (first wall only).
- ``radius``, ``method``, ``k_factor``, ``allowance``: own bend values.

Refs: ``sketch``, ``sheet_metal``.

Face roles: the fixed side keeps its names; faces on the moved side are renamed
``<fid>/moved/<old name>``; the bend is ``<fid>/bend/<role>`` and the cut on
the fixed side ``<fid>/split/<role>``.
"""

from __future__ import annotations

import math

from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    SketchOutput,
    register,
)
from fdcad.core.features.extrude import sketch_input_raw
from fdcad.core.features.sheetmetal.common import require_sheet
from fdcad.core.features.sheetmetal.model import (
    Bend,
    SheetModel,
    SheetResult,
    Vec2,
    Wall,
    along,
    apply,
    basis,
    common_with,
    inside,
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
from fdcad.core.features.solids import transform
from fdcad.core.naming.names import NamedShape
from fdcad.core.sketch.model import Line
from fdcad.core.units import Kind

POSITIONS = ("centreline", "material_inside", "material_outside", "bend_outside")
_TOL = 1e-6


def tangent_lines(position: str, level: float, allowance: float) -> tuple[float, float]:
    """Where the fixed side ends and the moved side starts, across the line (D338)."""
    if position == "material_inside":
        return level - allowance, level
    if position == "material_outside":
        return level, level + allowance
    if position == "bend_outside":
        return level, level
    return level - allowance / 2, level + allowance / 2


@register
class SketchedBend(FeatureType):
    """Bends a wall along a sketched line."""

    type_name = "sketched_bend"
    makes_solid = True
    params = (
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
        """Split the wall at the line and turn the moved side about the bend."""
        model = self.model(feature, ctx)
        return SheetResult(body=model.build(feature.id, feature.name), sheet=model)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The bent sheet, for the live preview."""
        return self.model(feature, ctx).build(feature.id, feature.name)

    def model(self, feature: Feature, ctx: BuildContext) -> SheetModel:
        """The sheet with this bend added."""
        name, fid = feature.name, feature.id
        model = require_sheet(feature, ctx)
        t = model.thickness
        rule = rule_from(feature, sheet_defaults(feature, ctx).rule)
        angle_param = feature.params.get("angle")
        angle = angle_param.value if isinstance(angle_param, Param) else math.pi / 2
        if not _TOL < angle < math.pi - _TOL:
            raise FeatureError(
                f"{name}: the bend angle must be between 0 and 180 degrees. "
                "Enter an angle in that range."
            )
        allowance = bend_allowance(rule, t, angle, name)
        sketch = sketch_input_raw(feature, ctx)
        ends = sketch_line(sketch, name)
        wid, a, b, top = wall_of(model, ends[0], ends[1], name)
        d = unit2((b[0] - a[0], b[1] - a[1]))
        w: Vec2 = (d[1], -d[0])
        piece = model.piece(wid)
        w = self._moving_side(feature, model, wid, piece, a, w)
        e = along(w)
        level = a[0] * w[0] + a[1] * w[1]
        position = str(feature.params.get("position", "centreline"))
        t1, t2 = tangent_lines(position, level, allowance)
        big = 1000.0 + 10 * size_of(piece)
        far = oriented_box(f"{fid}/moving", (0.0, 0.0), w, (-big, t2, -1.0), (big, big, t + 1.0))
        moving = common_with(fid, piece, far)
        if volume(moving.shape) <= _TOL:
            raise FeatureError(f"{name}: the line does not cross the wall. Move the line.")
        x0, x1 = span_of(moving, w)
        up = 1 if top else -1
        if feature.params.get("reverse"):
            up = -up
        origin: Vec2 = (e[0] * x0 + w[0] * t2, e[1] * x0 + w[1] * t2)
        to_child = basis(origin, w).Inverted()
        child = f"{fid}/wall"
        renamed = transform(moving, to_child)
        renamed = NamedShape(renamed.shape, [(f"{fid}/moved/{n}", f) for n, f in renamed.faces])
        p0: Vec2 = (e[0] * x0 + w[0] * t1, e[1] * x0 + w[1] * t1)
        bend = Bend(
            f"{fid}/bend", fid, wid, child, p0, w, x1 - x0, up, rule.radius, angle, allowance
        )
        self._carry_children(model, wid, child, w, t1, t2, to_child, name)
        cut = oriented_box(f"{fid}/split", (0.0, 0.0), w, (-big, t1, -1.0), (big, big, t + 1.0))
        model.walls[wid].cuts.append(cut)
        model.walls[child] = Wall(child, fid, renamed)
        model.bends[bend.bid] = bend
        return model

    def _moving_side(
        self,
        feature: Feature,
        model: SheetModel,
        wid: str,
        piece: NamedShape,
        a: Vec2,
        w: Vec2,
    ) -> Vec2:
        """``w`` turned so that it points from the fixed side to the moved side."""
        flip = feature.params.get("flip_fixed", False) is True
        parent = model.parent_bend(wid)
        if parent is not None:
            if flip:
                raise FeatureError(
                    f"{feature.name}: only the side joined to the rest of the sheet can stay "
                    "fixed on this wall. Turn off Flip Fixed Side."
                )
            joined = (parent.length / 2, 0.0)
            side = (joined[0] - a[0]) * w[0] + (joined[1] - a[1]) * w[1]
            return (-w[0], -w[1]) if side > 0 else w
        t = model.thickness
        big = 1000.0 + 10 * size_of(piece)
        level = a[0] * w[0] + a[1] * w[1]
        half = oriented_box("half", (0.0, 0.0), w, (-big, level, -1.0), (big, big, t + 1.0))
        ahead = volume(common_with("half", piece, half).shape)
        larger_ahead = ahead > volume(piece.shape) / 2
        if larger_ahead != flip:
            return (-w[0], -w[1])
        return w

    @staticmethod
    def _carry_children(
        model: SheetModel,
        wid: str,
        child: str,
        w: Vec2,
        t1: float,
        t2: float,
        to_child: object,
        owner: str,
    ) -> None:
        """Bends already on the moved side now start from the new wall."""
        from dataclasses import replace

        from OCP.gp import gp_Trsf

        assert isinstance(to_child, gp_Trsf)
        e = along(w)
        for bid, bend in list(model.bends.items()):
            if bend.parent != wid:
                continue
            be = along(bend.w)
            ends = [bend.p0, (bend.p0[0] + be[0] * bend.length, bend.p0[1] + be[1] * bend.length)]
            levels = [p[0] * w[0] + p[1] * w[1] for p in ends]
            if all(v <= t1 + _TOL for v in levels):
                continue
            if not all(v >= t2 - _TOL for v in levels):
                raise FeatureError(
                    f"{owner}: the bend line crosses the bend of another flange. Move the line."
                )
            p = apply(to_child, (bend.p0[0], bend.p0[1], 0.0))
            nw = (bend.w[0] * e[0] + bend.w[1] * e[1], bend.w[0] * w[0] + bend.w[1] * w[1])
            model.bends[bid] = replace(bend, parent=child, p0=(p[0], p[1]), w=nw)


def sketch_line(sketch: SketchOutput, owner: str) -> list[tuple[float, float, float]]:
    """The ends, in world coordinates, of the one line a bend sketch must hold."""
    lines = [c for c in sketch.model.curves() if isinstance(c, Line)]
    if len(lines) != 1 or len(sketch.model.curves()) != 1:
        raise FeatureError(f"{owner}: the sketch must hold exactly one line. Draw one line.")
    ends = []
    for pid in (lines[0].p1, lines[0].p2):
        p = sketch.plane.to_3d(*sketch.model.xy(pid))
        ends.append((p.X(), p.Y(), p.Z()))
    return ends


def wall_of(
    model: SheetModel,
    a3: tuple[float, float, float],
    b3: tuple[float, float, float],
    owner: str,
) -> tuple[str, Vec2, Vec2, bool]:
    """The wall whose flat face holds the line, the line in its frame, and which face."""
    t = model.thickness
    places = model.placements(False)
    for wid in model.walls:
        if wid not in places:
            continue
        inv = places[wid].Inverted()
        a, b = apply(inv, a3), apply(inv, b3)
        for level in (0.0, t):
            if abs(a[2] - level) > 1e-6 or abs(b[2] - level) > 1e-6:
                continue
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, t / 2)
            if inside(model.piece(wid).shape, mid):
                return wid, (a[0], a[1]), (b[0], b[1]), level > 0
    raise FeatureError(
        f"{owner}: the line is not on a flat face of the sheet. Sketch the line on a flat face."
    )


def size_of(named: NamedShape) -> float:
    box = Bnd_Box()
    BRepBndLib.Add_s(named.shape, box)
    return float(box.CornerMin().Distance(box.CornerMax()))


def span_of(named: NamedShape, w: Vec2) -> tuple[float, float]:
    """Smallest and largest coordinate of ``named`` along the bend direction."""
    flat = transform(named, basis((0.0, 0.0), w).Inverted())
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(flat.shape, box, False, False)
    return box.CornerMin().X(), box.CornerMax().X()
