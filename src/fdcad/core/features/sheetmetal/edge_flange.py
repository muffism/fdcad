"""Edge Flange (PHASE5_SPEC P5.3): a wall bent from each picked straight edge of the sheet.

Type ``edge_flange``. Params (all optional except ``length``):
- ``angle``: bend angle (default 90 degrees). ``angle_mode``: "angle" (default),
  "perpendicular" or "parallel" to the face in ``refs.angle_face``.
- ``end_condition``: "blind" (default) or "up_to_vertex" (``refs.end``).
  ``vertex_end``: "normal" (end face through the vertex, default) or "parallel"
  (a plane parallel to the base through the vertex).
- ``length``: length of every flange. ``length2`` to ``length8``: own lengths of
  the 2nd to 8th picked edges (multi length, D337).
- ``length_from``: "outer_sharp" (default), "inner_sharp" or "tangent" (D335).
- ``reverse``: bend to the other side.
- ``position``: "material_inside" (default), "material_outside", "bend_outside",
  "virtual_sharp" (D335) or "offset" (TR30.2: ``offset_distance`` in from the edge,
  with ``offset_rule`` applied there). ``trim_side_bends`` (false when missing; new
  flanges get it on). ``gap``: length.
- ``radius``, ``method``, ``k_factor``, ``allowance``: own bend values.
- ``relief``, ``relief_by``, ``relief_ratio``, ``relief_width``, ``relief_depth``,
  ``corner_relief``, ``corner_relief_size``: own relief, as the Sheet Metal folder.

Refs: ``edges`` (edge references, pick order), ``sheet_metal``, ``end``, ``angle_face``,
``profile_sketch`` (a closed sketch that shapes the flange wall, TR166, D1101; see
``flange_profile``).

Face roles: walls ``<fid>/flange<k>/<role>``, bends ``<fid>/bend<k>/<role>``
(see ``model``), trimmed parent faces ``<fid>/trim<k>/<role>`` and reliefs
``<fid>/relief<k>a/<role>``, ``<fid>/relief<k>b/<role>``; circular corner reliefs
``<fid>/corner<i>_<j>/round``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureState,
    FeatureType,
    Issue,
    ParamSpec,
    PreviewHandle,
    Vec3,
    register,
    ruler_step,
)
from fdcad.core.features.lookup import resolve_edge, resolve_face, resolve_vertex
from fdcad.core.features.sheetmetal.common import require_sheet
from fdcad.core.features.sheetmetal.flange_profile import has_profile, profile_plan
from fdcad.core.features.sheetmetal.model import (
    Bend,
    SheetModel,
    SheetResult,
    Vec2,
    Wall,
    along,
    apply,
    box,
    folded_child,
    fuse_all,
    inside,
    oriented_box,
    rounded_slot,
    unit2,
)
from fdcad.core.features.sheetmetal.params import (
    CORNER_RELIEFS,
    METHODS,
    RELIEF_BY,
    RELIEFS,
    Relief,
    bend_allowance,
    relief_from,
    rule_from,
    sheet_defaults,
)
from fdcad.core.features.solids import line_ends
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind, UnitSystem

POSITIONS = ("material_inside", "material_outside", "bend_outside", "virtual_sharp", "offset")
#: Rules an Offset position applies at its new place (TR30.2, D696).
OFFSET_RULES = ("material_inside", "material_outside", "bend_outside")
LENGTH_FROM = ("outer_sharp", "inner_sharp", "tangent")
#: Edges that may have their own length (``length2`` to ``length8``).
MAX_LENGTHS = 8
_TOL = 1e-6


@dataclass
class _Pick:
    """A picked edge, found on a wall: ends ``a``, ``b`` and outward ``w`` in its frame."""

    wid: str
    a: Vec2
    b: Vec2
    w: Vec2
    top: bool


@dataclass
class _Plan:
    """One flange to add."""

    pick: _Pick
    bend: Bend
    wall_len: float
    offset: float  # length minus wall length
    length_param: str
    cuts: list[NamedShape]
    #: Ends trimmed short of the edge: "a" (start) or "b" (end), and by how much.
    relief_ends: list[tuple[str, float]]
    #: The wall cut to a profile sketch, in the child's frame (TR166, D1101).
    plate: NamedShape | None = None


def length_name(k: int) -> str:
    """The parameter that holds the length of the ``k``-th picked edge (from 1)."""
    return "length" if k == 1 else f"length{k}"


def setback(position: str, radius: float, thickness: float, angle: float) -> float:
    """How far the bend's tangent line sits inside the picked edge (D335)."""
    if position == "material_inside":
        return radius + thickness
    if position == "material_outside":
        return radius
    if position == "virtual_sharp":
        return (radius + thickness) * math.tan(angle / 2)
    return 0.0


def length_offset(length_from: str, radius: float, thickness: float, angle: float) -> float:
    """Typed length minus the flat wall length (D335)."""
    if length_from == "outer_sharp":
        return (radius + thickness) * math.tan(angle / 2)
    if length_from == "inner_sharp":
        return radius * math.tan(angle / 2)
    return 0.0


@register
class EdgeFlange(FeatureType):
    """Adds a bent wall along each picked edge."""

    type_name = "edge_flange"
    makes_solid = True
    params = (
        ParamSpec("angle", kind=Kind.ANGLE, optional=True),
        ParamSpec("angle_mode", choices=("angle", "perpendicular", "parallel"), optional=True),
        ParamSpec("end_condition", choices=("blind", "up_to_vertex"), optional=True),
        ParamSpec("vertex_end", choices=("normal", "parallel"), optional=True),
        ParamSpec("length", kind=Kind.LENGTH, optional=True),
        ParamSpec("length_from", choices=LENGTH_FROM, optional=True),
        ParamSpec("reverse", default=False, optional=True),
        ParamSpec("position", choices=POSITIONS, optional=True),
        ParamSpec("offset_distance", kind=Kind.LENGTH, optional=True),
        ParamSpec("offset_rule", choices=OFFSET_RULES, optional=True),
        ParamSpec("trim_side_bends", default=False, optional=True),
        ParamSpec("gap", kind=Kind.LENGTH, optional=True),
        ParamSpec("radius", kind=Kind.LENGTH, optional=True),
        ParamSpec("method", choices=METHODS, optional=True),
        ParamSpec("k_factor", kind=Kind.NUMBER, optional=True),
        ParamSpec("allowance", kind=Kind.LENGTH, optional=True),
        ParamSpec("relief", choices=RELIEFS, optional=True),
        ParamSpec("relief_by", choices=RELIEF_BY, optional=True),
        ParamSpec("relief_ratio", kind=Kind.NUMBER, optional=True),
        ParamSpec("relief_width", kind=Kind.LENGTH, optional=True),
        ParamSpec("relief_depth", kind=Kind.LENGTH, optional=True),
        ParamSpec("corner_relief", choices=CORNER_RELIEFS, optional=True),
        ParamSpec("corner_relief_size", kind=Kind.LENGTH, optional=True),
    )

    def kind_of(self, name: str) -> Kind | None:
        """``length2`` to ``length8`` are lengths too."""
        if name.startswith("length") and name[6:].isdigit():
            return Kind.LENGTH
        return super().kind_of(name)

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Add the flanges and rebuild the sheet."""
        model, _plans, issues = self.model(feature, ctx)
        body = model.build(feature.id, feature.name)
        return SheetResult(body=body, issues=issues, sheet=model)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The whole sheet with the new flanges, for the live preview."""
        model, _plans, _issues = self.model(feature, ctx)
        return model.build(feature.id, feature.name)

    def preview_handles(self, feature: Feature, ctx: BuildContext) -> list[PreviewHandle]:
        """A length arrow on every Blind flange: the multi length labels in the view."""
        if feature.params.get("end_condition", "blind") != "blind" or has_profile(feature):
            return []
        model, plans, _issues = self.model(feature, ctx)
        places = model.placements(False)
        inch = ctx.document.units is UnitSystem.IN
        out = []
        for plan in plans:
            parent = places[plan.bend.parent].Multiplied(folded_child(plan.bend, model.thickness))
            mid = plan.bend.length / 2
            base = apply(parent, (mid, -plan.offset, 0.0))
            tip = apply(parent, (mid, 1.0 - plan.offset, 0.0))
            direction = (tip[0] - base[0], tip[1] - base[1], tip[2] - base[2])
            value = plan.wall_len + plan.offset
            step = ruler_step(max(value, plan.bend.length), inch)
            out.append(PreviewHandle(plan.length_param, base, direction, value, step=step))
        return out

    # Building ------------------------------------------------------------------

    def model(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[SheetModel, list[_Plan], list[Issue]]:
        """The sheet with this feature's flanges added."""
        name = feature.name
        model = require_sheet(feature, ctx)
        defaults = sheet_defaults(feature, ctx)
        thickness = model.thickness
        rule = rule_from(feature, defaults.rule)
        relief = relief_from(feature, defaults.relief, thickness)
        refs = feature.refs.get("edges")
        if not isinstance(refs, list) or not refs:
            raise FeatureError(f"{name}: pick one or more straight edges of the sheet.")
        issues: list[Issue] = []
        picks: list[_Pick] = []
        for number, ref in enumerate(refs, 1):
            if not isinstance(ref, dict):
                raise FeatureError(f"{name}: an edge pick is damaged. Pick the edges again.")
            edge, found = resolve_edge(ctx.body, ref, name)
            issues.extend(found)
            picks.append(find_edge(model, edge, name, str(number)))
        own = any(isinstance(feature.params.get(length_name(k)), Param) for k in range(2, 9))
        if own and len(picks) > MAX_LENGTHS:
            # Edges past the eighth have no length of their own (audit A item 23, D739).
            issues.append(
                Issue(
                    FeatureState.WARNING,
                    f"{name}: only the first {MAX_LENGTHS} edges can have their own length, so "
                    f"edges {MAX_LENGTHS + 1} and on use Length 1. Split the flange into two "
                    "features to give them their own lengths.",
                    code="shared_length",
                )
            )
        angle = self._angle(feature, ctx, model, picks, issues)
        position = str(feature.params.get("position", "material_inside"))
        gap = _value(feature, "gap", 0.0)
        if gap < 0:
            raise FeatureError(f"{name}: the gap cannot be negative. Enter zero or more.")
        allowance = bend_allowance(rule, thickness, angle, name)
        back = setback(position, rule.radius, thickness, angle)
        if position == "offset":
            # The flange moves in from the edge; the chosen rule applies there (TR30.2).
            distance = _value(feature, "offset_distance", 0.0)
            if distance < 0:
                raise FeatureError(
                    f"{name}: the offset distance cannot be negative. Enter zero or more."
                )
            inner = str(feature.params.get("offset_rule", "material_inside"))
            back = setback(inner, rule.radius, thickness, angle) + distance
        plans: list[_Plan] = []
        for k, pick in enumerate(picks, start=1):
            plan = self._plan(feature, ctx, model, k, pick, picks, angle, back, gap)
            plan = replace(plan, bend=replace(plan.bend, allowance=allowance))
            plans.append(plan)
        if has_profile(feature):
            if len(plans) != 1 or feature.params.get("end_condition", "blind") != "blind":
                raise FeatureError(
                    f"{name}: a flange profile works on one edge with a Blind end. "
                    "Pick one edge, or remove the profile sketch."
                )
            plans = [profile_plan(feature, ctx, plans[0], relief, thickness)]
        if relief.corner == "circular":
            plans = _corner_holes(feature, model, plans, relief)
        for k, plan in enumerate(plans, start=1):
            self._add(feature, model, k, plan, relief)
        return model, plans, issues

    def _angle(
        self,
        feature: Feature,
        ctx: BuildContext,
        model: SheetModel,
        picks: list[_Pick],
        issues: list[Issue],
    ) -> float:
        name = feature.name
        mode = str(feature.params.get("angle_mode", "angle"))
        if mode == "angle":
            angle = _value(feature, "angle", math.pi / 2)
        else:
            ref = feature.refs.get("angle_face")
            if not isinstance(ref, dict):
                raise FeatureError(
                    f"{name}: pick a face for the flange to follow, or enter an angle."
                )
            face, found = resolve_face(ctx.body, ref, name)
            issues.extend(found)
            from fdcad.core.features.sketch import face_plane

            plane = face_plane(face)
            if plane is None:
                raise FeatureError(f"{name}: the angle face must be flat. Pick a flat face.")
            pick = picks[0]
            place = model.placements(False)[pick.wid].Inverted()
            o = apply(place, (0.0, 0.0, 0.0))
            m = apply(place, plane.normal)
            m = (m[0] - o[0], m[1] - o[1], m[2] - o[2])
            up = _up(feature, pick)
            mw = m[0] * pick.w[0] + m[1] * pick.w[1]
            mn = m[2] * up
            angle = math.atan2(-mw, mn) if mode == "parallel" else math.atan2(mn, mw)
            angle = angle % math.pi
        if not 1e-6 < angle < math.pi - 1e-6:
            raise FeatureError(
                f"{name}: the flange angle must be between 0 and 180 degrees. Enter another angle."
            )
        return angle

    def _plan(
        self,
        feature: Feature,
        ctx: BuildContext,
        model: SheetModel,
        k: int,
        pick: _Pick,
        picks: list[_Pick],
        angle: float,
        back: float,
        gap: float,
    ) -> _Plan:
        name, fid, thickness = feature.name, feature.id, model.thickness
        rule_radius = rule_from(feature, sheet_defaults(feature, ctx).rule).radius
        w = pick.w
        e = along(w)
        a, b = pick.a, pick.b
        if a[0] * e[0] + a[1] * e[1] > b[0] * e[0] + b[1] * e[1]:
            a, b = b, a
        span = math.hypot(b[0] - a[0], b[1] - a[1])
        trim = feature.params.get("trim_side_bends") is True
        cut_start = cut_end = 0.0
        for other in picks:
            if other is pick or other.wid != pick.wid:
                continue
            for point in (other.a, other.b):
                shared = gap + (back if trim else 0.0) if trim else gap / 2
                if _near(point, a):
                    cut_start = max(cut_start, shared)
                if _near(point, b):
                    cut_end = max(cut_end, shared)
        length = span - cut_start - cut_end
        if length <= _TOL:
            raise FeatureError(
                f"{name}: edge {k} is too short for the gap and the neighbouring bends. "
                "Reduce the gap or pick a longer edge."
            )
        start = (a[0] + e[0] * cut_start - w[0] * back, a[1] + e[1] * cut_start - w[1] * back)
        up = _up(feature, pick)
        bend = Bend(
            f"{fid}/bend{k}", fid, pick.wid, f"{fid}/flange{k}", start, w, length, up,
            rule_radius, angle, 0.0,
        )  # fmt: skip
        cuts: list[NamedShape] = []
        if back > _TOL:
            margin = back + thickness + 1.0
            cuts.append(
                oriented_box(
                    f"{fid}/trim{k}", start, w, (0.0, 0.0, -1.0), (length, margin, thickness + 1.0)
                )
            )
        length_param = (
            length_name(k) if isinstance(feature.params.get(length_name(k)), Param) else "length"
        )
        length_from = str(feature.params.get("length_from", "outer_sharp"))
        offset = length_offset(length_from, rule_radius, thickness, angle)
        if feature.params.get("end_condition", "blind") == "up_to_vertex":
            wall_len = self._to_vertex(feature, ctx, model, bend)
            offset = 0.0
        else:
            typed = _value(feature, length_param, 0.0)
            if has_profile(feature):
                typed = max(typed, offset + 1.0)  # the profile sets the wall (D1101)
            if typed <= 0:
                raise FeatureError(
                    f"{name}: the flange length must be greater than zero. Enter a longer flange."
                )
            wall_len = typed - offset
        if wall_len <= _TOL:
            raise FeatureError(
                f"{name}: flange {k} is shorter than its bend. Enter a longer length."
            )
        ends = [(side, cut) for side, cut in (("a", cut_start), ("b", cut_end)) if cut > _TOL]
        return _Plan(pick, bend, wall_len, offset, length_param, cuts, ends)

    def _to_vertex(
        self, feature: Feature, ctx: BuildContext, model: SheetModel, bend: Bend
    ) -> float:
        name = feature.name
        ref = feature.refs.get("end")
        if not isinstance(ref, dict):
            raise FeatureError(f"{name}: Up to Vertex needs a vertex. Pick one, or choose Blind.")
        point, _found = resolve_vertex(ctx.body, ref, name)
        parent = model.placements(False)[bend.parent]
        local = apply(parent.Inverted(), point)
        child = folded_child(bend, model.thickness)
        if feature.params.get("vertex_end", "normal") == "parallel":
            o = apply(child, (0.0, 0.0, 0.0))
            y = apply(child, (0.0, 1.0, 0.0))
            dz = y[2] - o[2]
            if abs(dz) < 1e-9:
                raise FeatureError(
                    f"{name}: a flange parallel to the base never reaches the vertex. "
                    "Choose the end face through the vertex."
                )
            return (local[2] - o[2]) / dz
        return apply(child.Inverted(), local)[1]

    def _add(
        self, feature: Feature, model: SheetModel, k: int, plan: _Plan, relief: Relief
    ) -> None:
        fid, thickness = feature.id, model.thickness
        bend = plan.bend
        cuts = list(plan.cuts)
        depth = _depth(plan)
        if depth > _TOL:
            for side, trimmed in plan.relief_ends:
                cuts.append(_relief(fid, k, side, trimmed, bend, relief, depth, thickness))
        model.walls[bend.parent].cuts.extend(cuts)
        child = bend.child
        plate = plan.plate or box(child, (0.0, 0.0, 0.0), (bend.length, plan.wall_len, thickness))
        model.walls[child] = Wall(child, fid, plate)
        model.bends[bend.bid] = bend


def _depth(plan: _Plan) -> float:
    """How far the bend's tangent line sits inside the edge."""
    p, a, w = plan.bend.p0, plan.pick.a, plan.bend.w
    return (a[0] - p[0]) * w[0] + (a[1] - p[1]) * w[1]


def _relief(
    fid: str,
    k: int,
    side: str,
    trimmed: float,
    bend: Bend,
    relief: Relief,
    depth: float,
    thickness: float,
) -> NamedShape:
    """The relief at one end of a bend that stops short of its edge (D336).

    The relief itself sits against the bend end and reaches ``relief.depth``
    past the tangent line. The rest of the trimmed length, out to the corner,
    is cleared down to the tangent line so no loose corner tab is left.
    """
    prefix = f"{fid}/relief{k}{side}"
    length, width = bend.length, relief.width
    clear = trimmed + thickness + 1.0
    y1, z = depth + thickness + 1.0, thickness + 1.0
    if side == "a":
        notch, rest = (-width, 0.0), (-clear, 0.0)
    else:
        notch, rest = (length, length + width), (length, length + clear)
    y0 = -relief.depth
    if relief.kind == "obround" and width / 2 < y1 - y0:
        cut = rounded_slot(prefix, bend.p0, bend.w, notch[0], notch[1], y0, y1, z)
    else:
        cut = oriented_box(prefix, bend.p0, bend.w, (notch[0], y0, -1.0), (notch[1], y1, z))
    corner = oriented_box(
        f"{prefix}/corner", bend.p0, bend.w, (rest[0], 0.0, -1.0), (rest[1], y1, z)
    )
    pieces = [cut, corner]
    # The neighbouring bend's tangent line sits ``trimmed - depth`` past this bend's
    # end. When that is wider than the relief, the strip between the two reliefs,
    # inside both tangent lines, is closed in by the neighbour's relief whenever that
    # relief reaches across under it: it would be a loose piece, so clear it too.
    gap = trimmed - depth
    under = gap - relief.depth
    if gap - width > _TOL and _TOL < under <= width + _TOL:
        loose = (-gap, -width) if side == "a" else (length + width, length + gap)
        pieces.append(
            oriented_box(
                f"{prefix}/loose", bend.p0, bend.w, (loose[0], y0, -1.0), (loose[1], 0.0, z)
            )
        )
    return fuse_all(prefix, prefix, pieces)


def _corner_holes(
    feature: Feature, model: SheetModel, plans: list[_Plan], relief: Relief
) -> list[_Plan]:
    """A round hole where the tangent lines of two bends that share a corner meet; bends
    that would reach it stop at the circle (D540)."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    from fdcad.core.naming.names import faces_of

    t = model.thickness
    radius = (relief.corner_size if relief.corner_size > 0 else 2 * t) / 2
    plans = list(plans)
    for i in range(len(plans)):
        for j in range(i + 1, len(plans)):
            first, second = plans[i], plans[j]
            if first.pick.wid != second.pick.wid:
                continue
            ends = (first.pick.a, first.pick.b)
            if not any(_near(p, q) for p in ends for q in (second.pick.a, second.pick.b)):
                continue
            b1, b2 = first.bend, second.bend
            e1, e2 = along(b1.w), along(b2.w)
            det = e1[0] * (-e2[1]) - e1[1] * (-e2[0])
            if abs(det) < 1e-9:
                continue
            rx, ry = b2.p0[0] - b1.p0[0], b2.p0[1] - b1.p0[1]
            u = (rx * (-e2[1]) - ry * (-e2[0])) / det
            centre = (b1.p0[0] + e1[0] * u, b1.p0[1] + e1[1] * u)
            for k in (i, j):
                plans[k] = _stop_at(feature, plans[k], centre, radius)
            axis = gp_Ax2(gp_Pnt(centre[0], centre[1], -1.0), gp_Dir(0, 0, 1))
            shape = BRepPrimAPI_MakeCylinder(axis, radius, t + 2.0).Shape()
            prefix = f"{feature.id}/corner{i + 1}_{j + 1}"
            model.walls[first.pick.wid].cuts.append(
                NamedShape(shape, [(f"{prefix}/round", f) for f in faces_of(shape)])
            )
    return plans


def _stop_at(feature: Feature, plan: _Plan, centre: Vec2, radius: float) -> _Plan:
    """``plan`` with its bend shortened so it ends at the circle."""
    bend = plan.bend
    e = along(bend.w)
    x = (centre[0] - bend.p0[0]) * e[0] + (centre[1] - bend.p0[1]) * e[1]
    room = _outside(centre, bend)
    short = radius - room
    if short <= 0:
        return plan
    if bend.length - short <= _TOL:
        raise FeatureError(
            f"{feature.name}: the corner relief is longer than a bend. Enter a smaller size."
        )
    ends = dict(plan.relief_ends)
    if x < 0:
        p0 = (bend.p0[0] + e[0] * short, bend.p0[1] + e[1] * short)
        bend = replace(bend, p0=p0, length=bend.length - short)
        ends["a"] = ends.get("a", 0.0) + short
    else:
        bend = replace(bend, length=bend.length - short)
        ends["b"] = ends.get("b", 0.0) + short
    return replace(plan, bend=bend, relief_ends=list(ends.items()))


def _outside(p: Vec2, bend: Bend) -> float:
    """How far ``p`` lies beyond either end of ``bend``, along it."""
    e = along(bend.w)
    x = (p[0] - bend.p0[0]) * e[0] + (p[1] - bend.p0[1]) * e[1]
    return -x if x < 0 else x - bend.length if x > bend.length else 0.0


def _near(p: Vec2, q: Vec2) -> bool:
    return math.hypot(p[0] - q[0], p[1] - q[1]) < 1e-6


def _value(feature: Feature, name: str, default: float) -> float:
    value = feature.params.get(name)
    return value.value if isinstance(value, Param) else default


def _up(feature: Feature, pick: _Pick) -> int:
    up = 1 if pick.top else -1
    return -up if feature.params.get("reverse") else up


def find_edge(model: SheetModel, edge: Any, owner: str, label: str) -> _Pick:
    """The wall that ``edge`` bounds, with the edge in that wall's frame.

    ``label`` is the edge's number in the pick list, or empty for a single edge;
    messages use it instead of the internal edge name.
    """
    ends = line_ends(edge)
    if ends is None:
        raise FeatureError(f"{owner}: {_edge_words(label)} is not straight. Pick a straight edge.")
    t = model.thickness
    places = model.placements(False)
    for wid in model.walls:
        if wid not in places:
            continue
        inv = places[wid].Inverted()
        a3, b3 = apply(inv, ends[0]), apply(inv, ends[1])
        for level in (0.0, t):
            if abs(a3[2] - level) > 1e-6 or abs(b3[2] - level) > 1e-6:
                continue
            d = unit2((b3[0] - a3[0], b3[1] - a3[1]))
            piece = model.piece(wid).shape
            mid = ((a3[0] + b3[0]) / 2, (a3[1] + b3[1]) / 2)
            delta = min(t, 1.0) * 0.25
            for w in ((d[1], -d[0]), (-d[1], d[0])):
                out: Vec3 = (mid[0] + w[0] * delta, mid[1] + w[1] * delta, t / 2)
                inn: Vec3 = (mid[0] - w[0] * delta, mid[1] - w[1] * delta, t / 2)
                if inside(piece, inn) and not inside(piece, out):
                    return _Pick(wid, (a3[0], a3[1]), (b3[0], b3[1]), w, level > 0)
    raise FeatureError(
        f"{owner}: {_edge_words(label)} is not a straight outside edge of a flat wall. "
        "Pick an edge of a flat face of the sheet."
    )


def _edge_words(label: str) -> str:
    """ "edge 2" for the second picked edge, or "the picked edge"."""
    return f"edge {label}" if label else "the picked edge"


#: Public names for the other sheet metal features.
Pick = _Pick
relief_cut = _relief
