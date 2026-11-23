"""Base Flange (PHASE5_SPEC P5.2): the first wall of a sheet metal part.

Type ``base_flange``. A closed profile becomes a flat plate of the sheet
thickness. An open profile of lines and arcs is thickened into a bent wall:
every sharp corner becomes a bend of the default radius and every arc a bend
of the arc's radius (D334).

Params (all optional):
- ``flip_side``: thicken to the other side of the sketch. ``symmetric``: half each side.
- ``start_condition``, ``start_offset``, ``start_reverse``: the From list, as Extrude.
  The start must be parallel to the sketch plane.
- Open profiles: ``end_condition`` ("blind" default, "mid_plane", "two_directions",
  "up_to_vertex", "up_to_face", "offset_from_face"), ``depth``, ``reverse``,
  ``end_condition2``, ``depth2``, ``end_offset``, ``end_offset2`` and the other
  end keys of Extrude. Faces must be parallel to the sketch plane.
- ``radius``, ``method``, ``k_factor``, ``allowance``: this feature's own bend values.

Refs: ``sketch``, ``sheet_metal`` (the Sheet Metal folder), ``start``, ``end``, ``end2``.

Face roles: closed profiles ``<fid>/bottom``, ``<fid>/top``, ``<fid>/side/<entity>``.
Open profiles: walls ``<fid>/wall/<line>/<role>`` and bends ``<fid>/bend/<entity>/<role>``
(see ``model``), where a sharp corner's entity is ``<line>_<line>``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from OCP.gp import gp_Vec

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    SketchOutput,
    Vec3,
    register,
)
from fdcad.core.features.extrude import direction1, direction2, sketch_input_raw
from fdcad.core.features.extrude_end import END_CONDITIONS, resolve_end
from fdcad.core.features.extrude_start import START_CONDITIONS, Start, resolve_start
from fdcad.core.features.sheetmetal.model import (
    Bend,
    SheetModel,
    SheetResult,
    Wall,
    box,
    frame,
    translate,
)
from fdcad.core.features.sheetmetal.params import (
    METHODS,
    BendRule,
    bend_allowance,
    rule_from,
    sheet_defaults,
)
from fdcad.core.features.solids import prism, transform
from fdcad.core.naming.names import NamedShape
from fdcad.core.sketch.model import Arc, Line, Sketch
from fdcad.core.units import Kind

_JOIN = 1e-6


@dataclass
class _Segment:
    """One piece of an open profile, in sketch coordinates, in travel order."""

    eid: str
    start: tuple[float, float]
    end: tuple[float, float]
    arc: Arc | None = None


@register
class BaseFlange(FeatureType):
    """Thickens a sketch into the first sheet metal wall."""

    type_name = "base_flange"
    makes_solid = True
    params = (
        ParamSpec("flip_side", default=False, optional=True),
        ParamSpec("symmetric", default=False, optional=True),
        ParamSpec("start_condition", choices=START_CONDITIONS, optional=True),
        ParamSpec("start_offset", kind=Kind.LENGTH, optional=True),
        ParamSpec("start_reverse", default=False, optional=True),
        ParamSpec(
            "end_condition",
            choices=("blind", "mid_plane", "two_directions", *END_CONDITIONS),
            default="blind",
            optional=True,
        ),
        ParamSpec("depth", kind=Kind.LENGTH, optional=True),
        ParamSpec("depth2", kind=Kind.LENGTH, optional=True),
        ParamSpec("reverse", default=False, optional=True),
        ParamSpec("end_condition2", choices=("blind", *END_CONDITIONS), optional=True),
        ParamSpec("end_offset", kind=Kind.LENGTH, optional=True),
        ParamSpec("end_offset2", kind=Kind.LENGTH, optional=True),
        ParamSpec("end_offset_reverse", default=False, optional=True),
        ParamSpec("end_offset_reverse2", default=False, optional=True),
        ParamSpec("radius", kind=Kind.LENGTH, optional=True),
        ParamSpec("method", choices=METHODS, optional=True),
        ParamSpec("k_factor", kind=Kind.NUMBER, optional=True),
        ParamSpec("allowance", kind=Kind.LENGTH, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Build the first wall (or bent walls) of the sheet."""
        model = self.model(feature, ctx)
        body = model.build(feature.id, feature.name)
        return SheetResult(body=body, sheet=model)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The flange itself, for the live preview."""
        return self.model(feature, ctx).build(feature.id, feature.name)

    def model(self, feature: Feature, ctx: BuildContext) -> SheetModel:
        """The sheet model this feature starts."""
        name = feature.name
        if ctx.body is not None:  # TR281 (D2312): one Base Flange per sheet
            from fdcad.core.features.sheetmetal.common import latest_sheet

            if latest_sheet(feature, ctx)[0] is not None:
                raise FeatureError(
                    f"{name}: this sheet already has its first wall. Use Edge Flange to add "
                    "walls, or add a Sheet Metal folder to start another sheet body."
                )
        defaults = sheet_defaults(feature, ctx)
        rule = rule_from(feature, defaults.rule)
        sketch = sketch_input_raw(feature, ctx)
        start = resolve_start(feature, ctx, sketch)
        if start.surface is not None:
            raise FeatureError(
                f"{name}: the From face or plane must be parallel to the sketch. "
                "Pick a parallel face or choose Sketch Plane."
            )
        side = 0.5 if feature.params.get("symmetric") else 0.0
        if not side and feature.params.get("flip_side"):
            side = 1.0
        if sketch.profile is not None:
            return _closed(feature, sketch, start, defaults.thickness, side)
        return _open(feature, ctx, sketch, start, defaults.thickness, side, rule)


def _closed(
    feature: Feature, sketch: SketchOutput, start: Start, thickness: float, side: float
) -> SheetModel:
    assert sketch.profile is not None
    plane, fid = sketch.plane, feature.id
    n = plane.normal
    level = start.shift - side * thickness
    plate = prism(fid, sketch.profile, gp_Vec(n[0] * thickness, n[1] * thickness, n[2] * thickness))
    plate = translate(plate, (n[0] * level, n[1] * level, n[2] * level))
    origin = tuple(plane.origin[i] + n[i] * level for i in range(3))
    place = frame((origin[0], origin[1], origin[2]), plane.x_dir, n)
    local = transform(plate, place.Inverted())
    rename = {f"{fid}/cap/start": f"{fid}/bottom", f"{fid}/cap/end": f"{fid}/top"}
    local = NamedShape(local.shape, [(rename.get(nm, nm), f) for nm, f in local.faces])
    wid = f"{fid}/wall"
    model = SheetModel(thickness, wid, place)
    model.walls[wid] = Wall(wid, fid, local)
    return model


def _chain(sketch: Sketch, owner: str) -> list[_Segment]:
    """The open profile's lines and arcs in order from one free end to the other."""
    pieces: list[_Segment] = []
    for curve in sketch.curves():
        if isinstance(curve, Line):
            pieces.append(_Segment(curve.id, sketch.xy(curve.p1), sketch.xy(curve.p2)))
        elif isinstance(curve, Arc):
            pieces.append(_Segment(curve.id, sketch.xy(curve.start), sketch.xy(curve.end), curve))
        else:
            raise FeatureError(
                f"{owner}: an open profile can use only lines and arcs. Remove the circle."
            )
    if not pieces:
        raise FeatureError(f"{owner}: the sketch has no lines. Draw a profile.")

    def key(p: tuple[float, float]) -> tuple[int, int]:
        return (round(p[0] / _JOIN), round(p[1] / _JOIN))

    count: dict[tuple[int, int], int] = {}
    for s in pieces:
        for p in (s.start, s.end):
            count[key(p)] = count.get(key(p), 0) + 1
    if any(c > 2 for c in count.values()):
        raise FeatureError(f"{owner}: the profile branches. Draw one chain of lines and arcs.")
    ends = [p for p, c in count.items() if c == 1]
    if not ends:
        raise FeatureError(
            f"{owner}: the profile is neither closed nor a single open chain. "
            "Close the contour, or draw one open chain of lines and arcs."
        )
    at = min(ends)
    left = list(pieces)
    out: list[_Segment] = []
    while left:
        found = next((s for s in left if key(s.start) == at or key(s.end) == at), None)
        if found is None:
            raise FeatureError(f"{owner}: the profile has gaps. Join the lines end to end.")
        left.remove(found)
        if key(found.start) != at:
            found = _Segment(found.eid, found.end, found.start, found.arc)
        out.append(found)
        at = key(found.end)
    if out[0].arc is not None or out[-1].arc is not None:
        raise FeatureError(
            f"{owner}: an open profile must start and end with a line. "
            "Add a line at each end of the chain."
        )
    return out


def _dir(s: _Segment) -> tuple[float, float, float]:
    dx, dy = s.end[0] - s.start[0], s.end[1] - s.start[1]
    size = math.hypot(dx, dy)
    return (dx / size, dy / size, size)


def _extent(
    feature: Feature, ctx: BuildContext, sketch: SketchOutput, start: Start
) -> tuple[float, float]:
    """How far the walls reach forward and back along the sketch normal."""
    name = feature.name
    n = sketch.plane.normal
    sign = -1.0 if feature.params.get("reverse") else 1.0
    unit: Vec3 = (n[0] * sign, n[1] * sign, n[2] * sign)
    first, second = direction1(feature), direction2(feature)
    forward = back = 0.0
    if first in END_CONDITIONS:
        end = resolve_end(feature, ctx, sketch, start, unit, first)
        if end.distance is None:
            raise FeatureError(
                f"{name}: the end face must be parallel to the sketch. Pick a parallel face."
            )
        forward = end.distance
    elif first == "mid_plane":
        forward = back = self_number(feature, "depth") / 2
    else:
        forward = self_number(feature, "depth")
    if second == "blind":
        back = self_number(feature, "depth2")
    elif second in END_CONDITIONS:
        minus: Vec3 = (-unit[0], -unit[1], -unit[2])
        end = resolve_end(feature, ctx, sketch, start, minus, second, "2")
        if end.distance is None:
            raise FeatureError(
                f"{name}: the end face must be parallel to the sketch. Pick a parallel face."
            )
        back = end.distance
    if forward <= 0 or back < 0:
        raise FeatureError(f"{name}: the depth must be greater than zero. Enter a depth.")
    return (forward, back) if sign > 0 else (back, forward)


def self_number(feature: Feature, name: str) -> float:
    """A typed length of ``feature``, or an error naming the field."""
    return FeatureType.number(feature, name)


def _open(
    feature: Feature,
    ctx: BuildContext,
    sketch: SketchOutput,
    start: Start,
    thickness: float,
    side: float,
    rule: BendRule,
) -> SheetModel:
    name, fid, plane = feature.name, feature.id, sketch.plane
    segments = _chain(sketch.model, name)
    forward, back = _extent(feature, ctx, sketch, start)
    width = forward + back
    lines = [s for s in segments if s.arc is None]
    # Corners: (setback before, setback after, bend) between consecutive lines.
    setbacks = [[0.0, 0.0] for _ in lines]
    bends: list[tuple[str, int, float, float]] = []  # entity, up, radius, angle
    li = 0
    i = 0
    while i < len(segments) - 1:
        here = segments[i]
        nxt = segments[i + 1]
        arc = nxt.arc
        after = segments[i + 2] if arc is not None else nxt
        a, b = _dir(here), _dir(after)
        cross = a[0] * b[1] - a[1] * b[0]
        dot = a[0] * b[0] + a[1] * b[1]
        turn = math.atan2(cross, dot)
        if abs(turn) < 1e-9:
            raise FeatureError(f"{name}: lines {here.eid} and {after.eid} are in line. Join them.")
        if abs(abs(turn) - math.pi) < 1e-6:
            raise FeatureError(
                f"{name}: the profile folds back on itself at {after.eid}. "
                "Change the angle there so the profile does not turn back."
            )
        up = 1 if turn > 0 else -1
        angle = abs(turn)
        if arc is not None:
            layer = sketch.model.radius(arc.id)
            radius = layer - thickness + side * thickness if up > 0 else layer - side * thickness
            if radius < 0:
                raise FeatureError(
                    f"{name}: arc {arc.id} is too tight for the sheet thickness. "
                    "Make the arc larger."
                )
            entity, back_set = arc.id, 0.0
        else:
            radius = rule.radius
            layer = thickness + radius - side * thickness if up > 0 else radius + side * thickness
            entity, back_set = f"{here.eid}_{after.eid}", layer * math.tan(angle / 2)
        setbacks[li][1] = back_set
        setbacks[li + 1][0] = back_set
        bends.append((entity, up, radius, angle))
        li += 1
        i += 2 if arc is not None else 1
    first = lines[0]
    ux, uy, _size = _dir(first)
    travel = plane.to_3d(ux, uy)
    o3 = plane.to_3d(0.0, 0.0)
    t3: Vec3 = (travel.X() - o3.X(), travel.Y() - o3.Y(), travel.Z() - o3.Z())
    n = plane.normal
    left: Vec3 = (
        n[1] * t3[2] - n[2] * t3[1],
        n[2] * t3[0] - n[0] * t3[2],
        n[0] * t3[1] - n[1] * t3[0],
    )
    p = plane.to_3d(*first.start)
    lift = -side * thickness
    origin: Vec3 = (
        p.X() + n[0] * start.shift + left[0] * lift,
        p.Y() + n[1] * start.shift + left[1] * lift,
        p.Z() + n[2] * start.shift + left[2] * lift,
    )
    model = SheetModel(thickness, "", frame(origin, n, left))
    previous = ""
    for k, line in enumerate(lines):
        size = _dir(line)[2] - setbacks[k][0] - setbacks[k][1]
        if size <= 1e-6:
            raise FeatureError(
                f"{name}: line {line.eid} is too short for the bends at its ends. "
                "Make it longer or use a smaller bend radius."
            )
        wid = f"{fid}/wall/{line.eid}"
        # The first wall's frame sits on the sketch; later walls start at their bend's corner.
        low = -back if k == 0 else 0.0
        plate = box(wid, (low, 0.0, 0.0), (low + width, size, thickness))
        model.walls[wid] = Wall(wid, fid, plate)
        if k == 0:
            model.root = wid
        else:
            entity, up, radius, angle = bends[k - 1]
            bid = f"{fid}/bend/{entity}"
            ba = bend_allowance(replace(rule, radius=radius), thickness, angle, name)
            parent_len = _dir(lines[k - 1])[2] - setbacks[k - 1][0] - setbacks[k - 1][1]
            model.bends[bid] = Bend(
                bid, fid, previous, wid, (-back, parent_len), (0.0, 1.0), width, up,
                radius, angle, ba,
            )  # fmt: skip
        previous = wid
    return model
