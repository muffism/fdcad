"""Miter Flange (PHASE5_SPEC P5.6, DECISIONS D531): a sketched profile along a chain of edges.

Type ``miter_flange``. The sketch holds an open chain of lines on a plane square
to an end edge of the chain, starting at that edge's end point. An arc between two
lines, tangent to both, is a bend with the arc's radius on the sketch's side
(TR170, D2306). The lines are
the continuation of the picked face; every edge of the chain gets the same
walls and bends, mitred at the corners of the chain.

Params (all optional): ``gap`` (space at each mitre), ``radius``, ``method``,
``k_factor``, ``allowance`` (own bend values), ``propagate`` (add the edges joined
smoothly to the picked ones, TR30.3). ``offset_start`` and ``offset_end`` (lengths)
stop the flange short of the chain's free start and end, for a partial miter flange
(TR170, D1113); the chain starts at its free end with the smallest X, then Y, in the
wall's frame.

Refs: ``edges`` (straight edges on one face of one wall, end to end), ``sketch``,
``sheet_metal``.

Face roles: ``<fid>/e<i>/wall<k>/<role>``, ``<fid>/e<i>/bend<k>/<role>``,
``<fid>/trim<i>/<role>`` and ``<fid>/e<i>/mitre<k><end>/<role>``.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

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
from fdcad.core.features.extrude import sketch_input_raw
from fdcad.core.features.lookup import resolve_edge
from fdcad.core.features.sheetmetal.base_flange import _chain, _Segment
from fdcad.core.features.sheetmetal.common import require_sheet, value
from fdcad.core.features.sheetmetal.edge_flange import Pick, find_edge
from fdcad.core.features.sheetmetal.model import (
    Bend,
    SheetModel,
    SheetResult,
    Vec2,
    Wall,
    along,
    apply,
    basis,
    box,
    folded_bend,
    oriented_box,
    unit2,
)
from fdcad.core.features.sheetmetal.params import (
    METHODS,
    RELIEF_BY,
    RELIEFS,
    BendRule,
    Relief,
    bend_allowance,
    relief_from,
    rule_from,
    sheet_defaults,
)
from fdcad.core.features.solids import transform
from fdcad.core.naming.names import NamedShape
from fdcad.core.sketch.model import Sketch
from fdcad.core.units import Kind

_TOL = 1e-6
#: Sharpest chain corner allowed: the turn between edges, in radians (170 degrees).
MAX_TURN = math.radians(170)


@dataclass
class Turn:
    """A corner of the profile: signed turn (left positive), setback and bend values."""

    angle: float
    setback: float
    up_left: bool
    #: The bend's inner radius: the rule's, or the sketch arc's (TR170, D2306).
    radius: float = 0.0


@dataclass
class _Edge:
    """A picked edge in travel order: start, end, outward direction and mitred ends."""

    pick: Pick
    a: Vec2
    b: Vec2
    #: Mitre at the start / end: (corner, unit normal pointing to the other flange).
    start: tuple[Vec2, Vec2] | None = None
    end: tuple[Vec2, Vec2] | None = None


def profile_turns(
    points: list[Vec2],
    radius: float,
    thickness: float,
    owner: str,
    arcs: list[float | None] | None = None,
) -> tuple[list[Turn], list[float]]:
    """Turns and straight wall widths of a profile given as (out, up) points from the edge.

    The first turn is from the sheet's own direction (1, 0) to the first line (D531).
    ``arcs[k]`` is the radius of a sketch arc drawn at point ``k`` (TR170, D2306): the
    bend there takes the arc's radius on the sketch's side of the sheet.
    """
    dirs: list[Vec2] = [(1.0, 0.0)]
    sizes: list[float] = []
    for p, q in itertools.pairwise(points):
        size = math.hypot(q[0] - p[0], q[1] - p[1])
        if size < _TOL:
            raise FeatureError(f"{owner}: a profile line has no length. Remove it.")
        dirs.append(((q[0] - p[0]) / size, (q[1] - p[1]) / size))
        sizes.append(size)
    turns: list[Turn] = []
    for u, v in itertools.pairwise(dirs):
        angle = math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1])
        if abs(angle) < 1e-9:
            raise FeatureError(
                f"{owner}: the profile must turn away from the sheet and at every corner. "
                "Join lines that are in line."
            )
        if abs(abs(angle) - math.pi) < 1e-6:
            raise FeatureError(
                f"{owner}: the profile folds back on itself. "
                "Change the profile angles so it does not turn back."
            )
        arc = arcs[len(turns)] if arcs is not None and len(turns) < len(arcs) else None
        inner = radius
        if arc is not None:
            inner = arc if angle > 0 else arc - thickness
            if inner <= _TOL:
                raise FeatureError(
                    f"{owner}: a profile arc is smaller than the sheet thickness on its "
                    "outside. Use an arc radius larger than the thickness."
                )
        layer = inner if angle > 0 else inner + thickness
        turns.append(Turn(angle, layer * math.tan(abs(angle) / 2), angle > 0, inner))
    widths = []
    for k, size in enumerate(sizes):
        width = size - turns[k].setback - (turns[k + 1].setback if k + 1 < len(turns) else 0.0)
        if width <= _TOL:
            raise FeatureError(
                f"{owner}: profile line {k + 1} is too short for its bends. Make it longer "
                "or use a smaller bend radius."
            )
        widths.append(width)
    return turns, widths


@register
class MiterFlange(FeatureType):
    """Adds a profiled flange along a chain of edges, mitred at the corners."""

    type_name = "miter_flange"
    makes_solid = True
    params = (
        ParamSpec("gap", kind=Kind.LENGTH, optional=True),
        ParamSpec("propagate", default=False, optional=True),
        ParamSpec("offset_start", kind=Kind.LENGTH, optional=True),
        ParamSpec("offset_end", kind=Kind.LENGTH, optional=True),
        ParamSpec("radius", kind=Kind.LENGTH, optional=True),
        ParamSpec("method", choices=METHODS, optional=True),
        ParamSpec("k_factor", kind=Kind.NUMBER, optional=True),
        ParamSpec("allowance", kind=Kind.LENGTH, optional=True),
        # Own relief at an offset end (TR170, D2306), as Edge Flange's.
        ParamSpec("relief", choices=RELIEFS, optional=True),
        ParamSpec("relief_by", choices=RELIEF_BY, optional=True),
        ParamSpec("relief_ratio", kind=Kind.NUMBER, optional=True),
        ParamSpec("relief_width", kind=Kind.LENGTH, optional=True),
        ParamSpec("relief_depth", kind=Kind.LENGTH, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Add the flange and rebuild the sheet."""
        model, issues = self.model(feature, ctx)
        return SheetResult(body=model.build(feature.id, feature.name), issues=issues, sheet=model)

    def model(self, feature: Feature, ctx: BuildContext) -> tuple[SheetModel, list[Issue]]:
        """The sheet with this flange added."""
        name = feature.name
        model = require_sheet(feature, ctx)
        t = model.thickness
        rule = rule_from(feature, sheet_defaults(feature, ctx).rule)
        gap = value(feature, "gap", 0.0)
        if gap < 0:
            raise FeatureError(f"{name}: the gap cannot be negative. Enter zero or more.")
        refs = feature.refs.get("edges")
        if not isinstance(refs, list) or not refs:
            raise FeatureError(f"{name}: pick a chain of straight edges of one wall.")
        issues: list[Issue] = []
        picks: list[Pick] = []
        edges = []
        for ref in refs:
            if not isinstance(ref, dict):
                raise FeatureError(f"{name}: an edge pick is damaged. Pick the edges again.")
            edge, found = resolve_edge(ctx.body, ref, name)
            issues.extend(found)
            edges.append(edge)
        if feature.params.get("propagate") is True and ctx.body is not None:
            edges = _propagated(ctx.body.shape, edges)
        for number, edge in enumerate(edges, 1):
            picks.append(find_edge(model, edge, name, str(number)))
        if len({(p.wid, p.top) for p in picks}) != 1:
            raise FeatureError(
                f"{name}: the edges must all lie on one face of one wall. Pick edges of one face."
            )
        chain = _order(picks, name)
        points, arcs = self._profile(feature, ctx, model, chain, name)
        turns, widths = profile_turns(points, rule.radius, t, name, arcs)
        relief = None
        if isinstance(feature.params.get("relief"), str):  # TR170 (D2306)
            relief = relief_from(feature, sheet_defaults(feature, ctx).relief, t)
        self._build(feature, model, rule, chain, turns, widths, gap, relief)
        return model, issues

    def _profile(
        self, feature: Feature, ctx: BuildContext, model: SheetModel, chain: list[_Edge], name: str
    ) -> tuple[list[Vec2], list[float | None]]:
        """The profile as (out, up) points from the chain's start (D531), and the radius
        of the arc drawn at each point (None for a sharp corner, TR170, D2306)."""
        sketch = sketch_input_raw(feature, ctx)
        segments = _chain(sketch.model, name)
        pts, radii = _sharp_points(sketch.model, segments, name)
        place = model.placements(False)[chain[0].pick.wid].Inverted()
        local = []
        for x, y in pts:
            p = sketch.plane.to_3d(x, y)
            local.append(apply(place, (p.X(), p.Y(), p.Z())))
        level = model.thickness if chain[0].pick.top else 0.0
        first, last = chain[0], chain[-1]

        def near(q: tuple[float, float, float], c: Vec2) -> bool:
            return math.hypot(q[0] - c[0], q[1] - c[1]) < 1e-5 and abs(q[2] - level) < 1e-5

        if near(local[-1], first.a) or near(local[-1], last.b):
            local.reverse()
            radii.reverse()
        if near(local[0], last.b) and not near(local[0], first.a):
            chain.reverse()
            for item in chain:
                item.a, item.b = item.b, item.a
                item.start, item.end = item.end, item.start
        start = chain[0]
        if not near(local[0], start.a):
            raise FeatureError(
                f"{name}: the profile must start at an end of the edge chain. "
                "Sketch it on a plane square to an end edge, from its end point."
            )
        d = unit2((start.b[0] - start.a[0], start.b[1] - start.a[1]))
        n = sketch.plane.normal
        o = apply(place, (0.0, 0.0, 0.0))
        nl = apply(place, n)
        if abs((nl[0] - o[0]) * d[0] + (nl[1] - o[1]) * d[1]) < 1 - 1e-6:
            raise FeatureError(
                f"{name}: the profile sketch must be square to the end edge. "
                "Sketch it on a plane square to that edge."
            )
        w = start.pick.w
        sign = 1.0 if start.pick.top else -1.0
        out = []
        for q in local:
            rel = (q[0] - start.a[0], q[1] - start.a[1])
            out.append((rel[0] * w[0] + rel[1] * w[1], (q[2] - level) * sign))
        return out, radii

    def _build(
        self,
        feature: Feature,
        model: SheetModel,
        rule: BendRule,
        chain: list[_Edge],
        turns: list[Turn],
        widths: list[float],
        gap: float,
        relief: Relief | None = None,
    ) -> None:
        name, fid, t = feature.name, feature.id, model.thickness
        from dataclasses import replace

        allowances = [
            bend_allowance(replace(rule, radius=turn.radius or rule.radius), t,
                           abs(turn.angle), name)
            for turn in turns
        ]  # fmt: skip
        biggest = max([rule.radius, *[tn.radius for tn in turns]])
        reach = sum(widths) + sum(tn.setback for tn in turns) + biggest + 2 * t + 1.0
        ext = reach * (1 + math.tan(MAX_TURN / 2)) + 1.0
        level_sign = 1 if chain[0].pick.top else -1
        made: list[tuple[int, _Edge, list[str], float, float]] = []
        for i, item in enumerate(chain, start=1):
            w = item.pick.w
            e = along(w)
            # Edge coordinates: x along e from the low end.
            lo = item.a if _dot(item.a, e) <= _dot(item.b, e) else item.b
            length = math.hypot(item.b[0] - item.a[0], item.b[1] - item.a[1])
            low_mitre, high_mitre = self._ends(item, lo, e)
            off_lo, off_hi = _offsets(feature, chain, i, item, e, low_mitre, high_mitre)
            if off_lo + off_hi >= length - _TOL:
                raise FeatureError(
                    f"{name}: the start and end offsets leave nothing of edge {i}. "
                    "Enter smaller offsets."
                )
            x0 = -ext if low_mitre else off_lo
            x1 = length + ext if high_mitre else length - off_hi
            spans = self._spans(model, item, lo, turns, widths, allowances, rule, x0, x1)
            limits = []
            for s0, s1 in spans:
                lo_x = off_lo if low_mitre is None else _limit(low_mitre, lo, w, e, s0, s1, gap)
                hi_x = (
                    length - off_hi
                    if high_mitre is None
                    else _limit(high_mitre, lo, w, e, s0, s1, gap)
                )
                if hi_x - lo_x <= _TOL:
                    raise FeatureError(
                        f"{name}: edge {i} is too short for the mitred bends. "
                        "Pick a longer edge or use a smaller profile."
                    )
                limits.append((lo_x, hi_x))
            ids = self._add_stack(model, fid, i, item, lo, turns, widths, allowances, rule,
                                  limits, x0, x1, level_sign)  # fmt: skip
            back = turns[0].setback
            t_lo = x0
            t_hi = x1
            if back > _TOL or low_mitre or high_mitre:
                origin = (lo[0] + e[0] * t_lo - w[0] * back, lo[1] + e[1] * t_lo - w[1] * back)
                model.walls[item.pick.wid].cuts.append(
                    oriented_box(
                        f"{fid}/trim{i}", origin, w, (0.0, 0.0, -1.0),
                        (t_hi - t_lo, back + t + 1.0, t + 1.0),
                    )
                )  # fmt: skip
            if relief is not None:
                for side, end in (("a", off_lo if low_mitre is None else 0.0),
                                  ("b", off_hi if high_mitre is None else 0.0)):  # fmt: skip
                    if end > _TOL:
                        x = off_lo if side == "a" else length - off_hi
                        model.walls[item.pick.wid].cuts.append(
                            _relief_cut(f"{fid}/relief{i}{side}", lo, w, e, x, side, back,
                                        relief, t)
                        )  # fmt: skip
            made.append((i, item, ids, x0, x1))
        places = model.placements(False)
        for i, item, ids, _x0, _x1 in made:
            parent = places[item.pick.wid]
            for tag, mitre in (("a", item.start), ("b", item.end)):
                if mitre is None:
                    continue
                corner, normal = mitre
                origin = (corner[0] - normal[0] * gap / 2, corner[1] - normal[1] * gap / 2)
                big = 4 * ext + 100.0
                half = oriented_box(
                    f"{fid}/e{i}/mitre", origin, normal, (-big, 0.0, -big), (big, big, big)
                )
                for k, wid in enumerate(ids, start=1):
                    local = places[wid].Inverted().Multiplied(parent)
                    cut = transform(half, local)
                    named = NamedShape(
                        cut.shape, [(f"{fid}/e{i}/mitre{k}{tag}/{n.rsplit('/', 1)[1]}", f)
                                    for n, f in cut.faces]
                    )  # fmt: skip
                    model.walls[wid].cuts.append(named)

    @staticmethod
    def _ends(
        item: _Edge, lo: Vec2, e: Vec2
    ) -> tuple[tuple[Vec2, Vec2] | None, tuple[Vec2, Vec2] | None]:
        """The mitres at the low and high ends in edge coordinates."""
        low = high = None
        for mitre in (item.start, item.end):
            if mitre is None:
                continue
            corner = mitre[0]
            at = _dot((corner[0] - lo[0], corner[1] - lo[1]), e)
            if at < _TOL:
                low = mitre
            else:
                high = mitre
        return low, high

    @staticmethod
    def _spans(
        model: SheetModel,
        item: _Edge,
        lo: Vec2,
        turns: list[Turn],
        widths: list[float],
        allowances: list[float],
        rule: BendRule,
        x0: float,
        x1: float,
    ) -> list[tuple[float, float]]:
        """How far out from the edge each bend reaches (smallest and largest)."""
        trial = SheetModel(model.thickness, "root", basis((0.0, 0.0), (0.0, 1.0)).Inverted())
        trial.walls["root"] = Wall("root", "x", box("root", (-1, -1, 0), (1, 1, model.thickness)))
        w = item.pick.w
        sign = 1 if item.pick.top else -1
        stack = _stack_bends("t", "root", lo, w, turns, widths, allowances, rule, sign,
                             [(x0, x1)] * len(turns))  # fmt: skip
        for bend in stack:
            trial.bends[bend.bid] = bend
        places = trial.placements(False)
        to_edge = basis(lo, w).Inverted()
        out = []
        for bend in stack:
            solid = transform(folded_bend(bend, model.thickness), places[bend.parent])
            flat = transform(solid, to_edge)
            bb = Bnd_Box()
            BRepBndLib.AddOptimal_s(flat.shape, bb, False, False)
            out.append((bb.CornerMin().Y(), bb.CornerMax().Y()))
        return out

    @staticmethod
    def _add_stack(
        model: SheetModel,
        fid: str,
        i: int,
        item: _Edge,
        lo: Vec2,
        turns: list[Turn],
        widths: list[float],
        allowances: list[float],
        rule: BendRule,
        limits: list[tuple[float, float]],
        x0: float,
        x1: float,
        sign: int,
    ) -> list[str]:
        stack = _stack_bends(
            f"{fid}/e{i}", item.pick.wid, lo, item.pick.w, turns, widths, allowances, rule,
            sign, limits, fid,
        )  # fmt: skip
        ids = []
        for k, bend in enumerate(stack):
            origin = limits[k][0]
            plate = box(
                bend.child, (x0 - origin, 0.0, 0.0), (x1 - origin, widths[k], model.thickness)
            )
            model.walls[bend.child] = Wall(bend.child, fid, plate)
            model.bends[bend.bid] = bend
            ids.append(bend.child)
        return ids


def _stack_bends(
    prefix: str,
    parent: str,
    lo: Vec2,
    w: Vec2,
    turns: list[Turn],
    widths: list[float],
    allowances: list[float],
    rule: BendRule,
    sign: int,
    limits: list[tuple[float, float]],
    owner: str = "x",
) -> list[Bend]:
    """The bends of one edge's flange, each starting at its own limit along the edge."""
    e = along(w)
    out = []
    previous = parent
    prev_origin = 0.0
    for k, turn in enumerate(turns):
        xs, xe = limits[k]
        up = sign if turn.up_left else -sign
        child = f"{prefix}/wall{k + 1}"
        if k == 0:
            back = turn.setback
            p0: Vec2 = (lo[0] + e[0] * xs - w[0] * back, lo[1] + e[1] * xs - w[1] * back)
            bw: Vec2 = w
        else:
            p0 = (xs - prev_origin, widths[k - 1])
            bw = (0.0, 1.0)
        out.append(
            Bend(
                f"{prefix}/bend{k + 1}", owner, previous, child, p0, bw, xe - xs, up,
                turn.radius or rule.radius, abs(turn.angle), allowances[k],
            )
        )  # fmt: skip
        previous, prev_origin = child, xs
    return out


def _limit(
    mitre: tuple[Vec2, Vec2], lo: Vec2, w: Vec2, e: Vec2, s0: float, s1: float, gap: float
) -> float:
    """The furthest a bend reaching from s0 to s1 out may run toward a mitre (D531)."""
    corner, n = mitre
    wn = _dot(w, n)
    s = s1 if wn > 0 else s0
    k = _dot((lo[0] - corner[0], lo[1] - corner[1]), n) + s * wn + gap / 2
    return -k / _dot(e, n)


def _offsets(
    feature: Feature,
    chain: list[_Edge],
    i: int,
    item: _Edge,
    e: Vec2,
    low: object,
    high: object,
) -> tuple[float, float]:
    """How far the flange stops short of edge ``i``'s low and high ends (D1113)."""
    from fdcad.core.features.sheetmetal.common import value

    start = value(feature, "offset_start", 0.0)
    end = value(feature, "offset_end", 0.0)
    if start < 0 or end < 0:
        raise FeatureError(
            f"{feature.name}: the start and end offsets cannot be negative. Enter zero or more."
        )
    a_low = _dot(item.a, e) <= _dot(item.b, e)
    off_lo = off_hi = 0.0
    if i == 1:  # the chain's start is this edge's a end
        if a_low and low is None:
            off_lo = start
        elif not a_low and high is None:
            off_hi = start
    if i == len(chain):  # the chain's end is this edge's b end
        if a_low and high is None:
            off_hi = end
        elif not a_low and low is None:
            off_lo = end
    return off_lo, off_hi


def _relief_cut(
    prefix: str,
    lo: Vec2,
    w: Vec2,
    e: Vec2,
    x: float,
    side: str,
    back: float,
    relief: Relief,
    t: float,
) -> NamedShape:
    """The relief notch at an offset end of a miter flange (TR170, D2306): against the
    bend's end, outside it, reaching ``relief.depth`` past the bend's tangent line."""
    from fdcad.core.features.sheetmetal.model import rounded_slot

    origin = (lo[0] - w[0] * back, lo[1] - w[1] * back)
    n0, n1 = (x - relief.width, x) if side == "a" else (x, x + relief.width)
    y0, y1, z = -relief.depth, back + t + 1.0, t + 1.0
    if relief.kind == "obround" and relief.width / 2 < y1 - y0:
        return rounded_slot(prefix, origin, w, n0, n1, y0, y1, z)
    return oriented_box(prefix, origin, w, (n0, y0, -1.0), (n1, y1, z))


def _sharp_points(
    sketch: Sketch, segments: list[_Segment], owner: str
) -> tuple[list[Vec2], list[float | None]]:
    """The profile's points in sketch coordinates with every arc replaced by the sharp
    corner of the lines on each side, and the arc's radius at that corner (D2306).

    An arc must lie between two lines and meet both tangent."""
    if segments[0].arc is not None or segments[-1].arc is not None:
        raise FeatureError(
            f"{owner}: a miter flange profile must start and end with a line. "
            "Add a line before or after the arc."
        )
    pts: list[Vec2] = [segments[0].start]
    radii: list[float | None] = [None]
    k = 0
    while k < len(segments):
        seg = segments[k]
        arc = segments[k + 1].arc if k + 1 < len(segments) else None
        if arc is None:
            pts.append(seg.end)
            radii.append(None)
            k += 1
            continue
        after = segments[k + 2]
        if after.arc is not None:
            raise FeatureError(f"{owner}: two profile arcs meet. Add a line between the arcs.")
        corner = _crossing(seg.start, seg.end, after.start, after.end)
        centre = sketch.xy(arc.center)
        radius = math.dist(centre, sketch.xy(arc.start))
        if (
            corner is None
            or not _tangent(seg.start, seg.end, centre, radius)
            or not _tangent(after.start, after.end, centre, radius)
        ):
            raise FeatureError(
                f"{owner}: a profile arc must meet the lines on both sides tangent. "
                "Add tangent relations to the arc."
            )
        pts.append(corner)
        radii.append(radius)
        pts.append(after.end)  # the line after the arc runs on from the corner
        radii.append(None)
        k += 3
    return pts, radii


def _crossing(a0: Vec2, a1: Vec2, b0: Vec2, b1: Vec2) -> Vec2 | None:
    """Where the line through a0 and a1 crosses the line through b0 and b1."""
    d1 = (a1[0] - a0[0], a1[1] - a0[1])
    d2 = (b1[0] - b0[0], b1[1] - b0[1])
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-12:
        return None
    t = ((b0[0] - a0[0]) * d2[1] - (b0[1] - a0[1]) * d2[0]) / den
    return (a0[0] + d1[0] * t, a0[1] + d1[1] * t)


def _tangent(p: Vec2, q: Vec2, centre: Vec2, radius: float) -> bool:
    """True when the line through p and q touches the circle."""
    d = (q[0] - p[0], q[1] - p[1])
    size = math.hypot(*d)
    if size < 1e-12:
        return False
    away = abs((centre[0] - p[0]) * d[1] - (centre[1] - p[1]) * d[0]) / size
    return abs(away - radius) < 1e-5 * max(1.0, radius)


def _dot(a: Vec2, b: Vec2) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _propagated(body: object, edges: list[object]) -> list[object]:
    """The picked edges and every edge joined to them smoothly (Propagate, TR30.3): the
    chain stops at a corner that is not tangent, at a cut (where the edge ends) and at a
    curved edge, which a miter flange cannot follow."""
    from fdcad.core.features.modify import tangent_chain

    return list(tangent_chain(body, edges, straight_only=True))


def _order(picks: list[Pick], owner: str) -> list[_Edge]:
    """The picked edges as one chain in travel order, with the mitre at each corner."""

    def key(p: Vec2) -> tuple[int, int]:
        return (round(p[0] * 1e5), round(p[1] * 1e5))

    count: dict[tuple[int, int], int] = {}
    for p in picks:
        for q in (p.a, p.b):
            count[key(q)] = count.get(key(q), 0) + 1
    if any(c > 2 for c in count.values()):
        raise FeatureError(f"{owner}: the edges branch. Pick one chain of edges.")
    ends = [k for k, c in count.items() if c == 1]
    if not ends:
        raise FeatureError(f"{owner}: the edges form a loop. Leave one edge out.")
    at = min(ends)
    left = list(picks)
    chain: list[_Edge] = []
    while left:
        found = next((p for p in left if key(p.a) == at or key(p.b) == at), None)
        if found is None:
            raise FeatureError(f"{owner}: the edges are not joined end to end. Pick a chain.")
        left.remove(found)
        a, b = (found.a, found.b) if key(found.a) == at else (found.b, found.a)
        chain.append(_Edge(found, a, b))
        at = key(b)
    for prev, nxt in itertools.pairwise(chain):
        d1 = unit2((prev.b[0] - prev.a[0], prev.b[1] - prev.a[1]))
        d2 = unit2((nxt.b[0] - nxt.a[0], nxt.b[1] - nxt.a[1]))
        if _dot(d2, prev.pick.w) > -1e-9:
            raise FeatureError(
                f"{owner}: the edge chain turns inward at a corner. A miter flange needs "
                "outside corners. Pick edges that turn outward."
            )
        if math.acos(max(-1.0, min(1.0, _dot(d1, d2)))) > MAX_TURN:
            raise FeatureError(
                f"{owner}: a chain corner is too sharp to mitre. "
                "Pick edges that meet at a wider angle."
            )
        n = unit2((d1[0] + d2[0], d1[1] + d2[1]))
        prev.end = (prev.b, n)
        nxt.start = (nxt.a, (-n[0], -n[1]))
    return chain
