"""Sketch fillet and sketch chamfer (PHASE2_SPEC P2.8 items 6 and 7).

Both work on the corner between two lines: the lines are cut back from where
they meet and an arc (fillet) or a line (chamfer) joins them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Arc, Dimension, Line, Point, Relation, Sketch
from fdcad.core.sketch.ops.geom import Vec, basic_curves, crossings, dist, geo
from fdcad.core.sketch.ops.pieces import Report, move_end
from fdcad.core.sketch.solver import measure_angle

CHAMFER_KINDS = ("angle_distance", "distance_distance")


class CornerError(ValueError):
    """The fillet or chamfer cannot be made; the message says why and what to do."""


class NeedsConfirmError(CornerError):
    """Making it would delete dimensions or relations on the corner."""


@dataclass
class CornerResult:
    """What a fillet or chamfer made."""

    curve: str = ""
    corner_point: str | None = None
    dimensions: list[str] = field(default_factory=list)
    report: Report = field(default_factory=Report)


@dataclass(frozen=True)
class _Corner:
    x: Vec
    ends: tuple[str, str]  # the corner end point of each line
    dirs: tuple[Vec, Vec]  # unit directions from the corner along each kept piece
    reach: tuple[float, float]  # length of each kept piece from the corner
    theta: float  # angle between the two kept pieces


def lines_at(sketch: Sketch, pid: str) -> list[str]:
    """Lines with an end at point ``pid`` or at a point on top of it."""
    at = sketch.xy(pid)
    out = []
    for c in basic_curves(sketch):
        if isinstance(c, Line) and any(dist(sketch.xy(p), at) < 1e-6 for p in (c.p1, c.p2)):
            out.append(c.id)
    return out


def _corner(sketch: Sketch, l1: str, pick1: Vec, l2: str, pick2: Vec) -> _Corner:
    e1, e2 = sketch.entities.get(l1), sketch.entities.get(l2)
    if not isinstance(e1, Line) or not isinstance(e2, Line) or l1 == l2:
        raise CornerError("Pick two lines, or the corner point where two lines meet.")
    xs = crossings(geo(sketch, l1), geo(sketch, l2))
    if not xs:
        raise CornerError("The lines are parallel, so they have no corner. Pick two other lines.")
    x = xs[0]
    ends: list[str] = []
    dirs: list[Vec] = []
    reach: list[float] = []
    for line, pick in ((e1, pick1), (e2, pick2)):
        a, b = sketch.xy(line.p1), sketch.xy(line.p2)
        # The corner end is the end nearer the corner; the kept piece runs to the other.
        near, far = (line.p1, b) if dist(a, x) <= dist(b, x) else (line.p2, a)
        g = geo(sketch, line.id)
        if dist(pick, x) > 1e-9:
            tp, tx, tf = g.param(pick), g.param(x), g.param(far)
            if (tp - tx) * (tf - tx) < 0:
                raise CornerError(
                    "Click each line on the side to keep, between the corner and its far end."
                )
        length = dist(far, x)
        if length < 1e-9:
            raise CornerError("A line ends at the corner on both sides. Pick another corner.")
        ends.append(near)
        dirs.append(((far[0] - x[0]) / length, (far[1] - x[1]) / length))
        reach.append(length)
    cos = max(-1.0, min(1.0, dirs[0][0] * dirs[1][0] + dirs[0][1] * dirs[1][1]))
    theta = math.acos(cos)
    if theta < 1e-6 or theta > math.pi - 1e-6:
        raise CornerError(
            "The lines are in line, so there is no corner to round. "
            "Pick two lines that meet at an angle."
        )
    return _Corner(x, (ends[0], ends[1]), (dirs[0], dirs[1]), (reach[0], reach[1]), theta)


def _corner_links(sketch: Sketch, ends: tuple[str, str]) -> list[Relation | Dimension]:
    """Relations and dimensions on the corner end points, other than the joins that
    tie the two corner ends to each other."""
    ids = set(ends)
    out: list[Relation | Dimension] = []
    for r in sketch.relations:
        if not set(r.entities) & ids:
            continue
        if r.type == "coincident" and set(r.entities) <= ids:
            continue
        out.append(r)
    out += [d for d in sketch.dimensions if set(d.entities) & ids]
    return out


def _keep_corner(
    sketch: Sketch, c: _Corner, l1: str, l2: str, keep: bool, force: bool
) -> str | None:
    """Move what holds the corner to a construction point at it (keep), or check
    that deleting it was confirmed. Returns the new point id or None."""
    links = _corner_links(sketch, c.ends)
    if not links:
        return None
    if not keep:
        if not force:
            raise NeedsConfirmError(
                f"The corner has {len(links)} relations or dimensions that would be deleted. "
                "Click again to delete them, or turn on Keep constrained corners."
            )
        return None
    pid = sketch.add_point(c.x[0], c.x[1], construction=True)
    sketch.relate("intersection", pid, l1, l2)
    for item in links:
        item.entities = [pid if e in c.ends else e for e in item.entities]
    # A relation that now names the new point twice says nothing.
    sketch.relations = [
        r for r in sketch.relations if not (r.type == "coincident" and r.entities.count(pid) > 1)
    ]
    return pid


def fillet(
    sketch: Sketch,
    l1: str,
    pick1: Vec,
    l2: str,
    pick2: Vec,
    radius: float,
    keep_corner: bool = True,
    force: bool = False,
    dimension: bool = True,
    equal_to: str | None = None,
) -> CornerResult:
    """Round the corner between lines ``l1`` and ``l2`` with an arc of ``radius``.

    The arc is tangent to both lines and joined to their new ends. It gets a radius
    dimension, or Equal with ``equal_to`` when ``dimension`` is off.
    """
    if radius <= 1e-9:
        raise CornerError("Type a fillet radius larger than zero.")
    c = _corner(sketch, l1, pick1, l2, pick2)
    cut = radius / math.tan(c.theta / 2)
    if cut > min(c.reach) + 1e-9:
        largest = min(c.reach) * math.tan(c.theta / 2)
        # Both units: the sketch does not know the part's units (audit D2 item 11, D743).
        raise CornerError(
            f"The radius is too large for these lines: the largest that fits is "
            f"{largest:.4g} mm ({largest / 25.4:.4g} in). Use a smaller radius."
        )
    result = CornerResult()
    result.corner_point = _keep_corner(sketch, c, l1, l2, keep_corner, force)
    t1 = (c.x[0] + cut * c.dirs[0][0], c.x[1] + cut * c.dirs[0][1])
    t2 = (c.x[0] + cut * c.dirs[1][0], c.x[1] + cut * c.dirs[1][1])
    bis = (c.dirs[0][0] + c.dirs[1][0], c.dirs[0][1] + c.dirs[1][1])
    n = math.hypot(*bis)
    h = radius / math.sin(c.theta / 2)
    centre = (c.x[0] + h * bis[0] / n, c.x[1] + h * bis[1] / n)
    p1 = _move_corner_end(sketch, l1, c.ends[0], t1, result.report)
    p2 = _move_corner_end(sketch, l2, c.ends[1], t2, result.report)
    a1 = math.atan2(t1[1] - centre[1], t1[0] - centre[0])
    a2 = math.atan2(t2[1] - centre[1], t2[0] - centre[0])
    # The short way round from t1 to t2.
    ccw = (a2 - a1) % (2 * math.pi) < math.pi
    start, end = (a1, a2) if ccw else (a2, a1)
    aid = sketch.add_arc(centre[0], centre[1], radius, start, end)
    arc = sketch.entities[aid]
    assert isinstance(arc, Arc)
    # The arc uses the lines' new end points, so Tangent holds at that shared point.
    own = (arc.start, arc.end)
    if ccw:
        arc.start, arc.end = p1, p2
    else:
        arc.start, arc.end = p2, p1
    for pid in own:
        sketch.entities.pop(pid, None)
    sketch.relate("tangent", aid, l1)
    sketch.relate("tangent", aid, l2)
    if equal_to is not None and not dimension and equal_to in sketch.entities:
        sketch.relate("equal", aid, equal_to)
    elif dimension:
        dim = sketch.dimension("radius", [aid], Param(f"{radius:.6g}mm", radius))
        result.dimensions.append(dim.id)
    result.curve = aid
    return result


def _move_corner_end(sketch: Sketch, lid: str, pid: str, to: Vec, report: Report) -> str:
    line = sketch.entities[lid]
    assert isinstance(line, Line)
    return move_end(sketch, lid, line.p2 == pid, to, report)


def chamfer(
    sketch: Sketch,
    l1: str,
    pick1: Vec,
    l2: str,
    pick2: Vec,
    kind: str,
    d1: float,
    d2: float = 0.0,
    angle: float = math.pi / 4,
) -> CornerResult:
    """Cut the corner between lines ``l1`` and ``l2`` with a straight line.

    ``angle_distance``: ``d1`` along the first line and the chamfer at ``angle`` to
    it. ``distance_distance``: ``d1`` along the first line and ``d2`` along the
    second. A construction point keeps the corner, so the chamfer is dimensioned
    from it.
    """
    if kind not in CHAMFER_KINDS:
        raise CornerError(f"Unknown chamfer type '{kind}'. Choose a chamfer type from the list.")
    if d1 <= 1e-9 or (kind == "distance_distance" and d2 <= 1e-9):
        raise CornerError("Type chamfer distances larger than zero.")
    c = _corner(sketch, l1, pick1, l2, pick2)
    if kind == "angle_distance":
        if not 1e-6 < angle < math.pi - c.theta - 1e-6:
            raise CornerError("The chamfer angle does not fit this corner. Use a smaller angle.")
        d2 = d1 * math.sin(angle) / math.sin(c.theta + angle)
    if d1 > c.reach[0] + 1e-9 or d2 > c.reach[1] + 1e-9:
        raise CornerError("The chamfer is longer than the lines allow. Use smaller distances.")
    result = CornerResult()
    pid = _keep_corner(sketch, c, l1, l2, True, True)
    if pid is None:
        pid = sketch.add_point(c.x[0], c.x[1], construction=True)
        sketch.relate("intersection", pid, l1, l2)
    result.corner_point = pid
    q1 = (c.x[0] + d1 * c.dirs[0][0], c.x[1] + d1 * c.dirs[0][1])
    q2 = (c.x[0] + d2 * c.dirs[1][0], c.x[1] + d2 * c.dirs[1][1])
    p1 = _move_corner_end(sketch, l1, c.ends[0], q1, result.report)
    p2 = _move_corner_end(sketch, l2, c.ends[1], q2, result.report)
    lid = sketch.add_line(q1[0], q1[1], q2[0], q2[1])
    line = sketch.entities[lid]
    assert isinstance(line, Line)
    sketch.relate("coincident", line.p1, p1)
    sketch.relate("coincident", line.p2, p2)
    dim = sketch.dimension("distance", [pid, p1], Param(f"{d1:.6g}mm", d1))
    result.dimensions.append(dim.id)
    if kind == "distance_distance":
        dim = sketch.dimension("distance", [pid, p2], Param(f"{d2:.6g}mm", d2))
    else:
        dim = sketch.dimension("angle", [l1, lid], Param(f"{math.degrees(angle):.6g}deg", angle))
        dim.supplement = _supplement(sketch, l1, lid, angle)
    result.dimensions.append(dim.id)
    result.curve = lid
    return result


def _supplement(sketch: Sketch, a: str, b: str, angle: float) -> bool:
    direct = abs(measure_angle(sketch, a, b))
    return abs(direct - angle) > abs(math.pi - direct - angle)


def is_point(sketch: Sketch, eid: str) -> bool:
    """True when ``eid`` is a point."""
    return isinstance(sketch.entities.get(eid), Point)


@dataclass
class RoundAllResult:
    """What Round All Corners made: the arcs, the shared dimension, and the corners that
    could not be rounded with why."""

    arcs: list[str] = field(default_factory=list)
    dimension: str | None = None
    skipped: list[str] = field(default_factory=list)


def corners_of(sketch: Sketch, line_ids: list[str]) -> list[tuple[str, str, Vec]]:
    """Corners between the given lines: (line, line, corner point), in line order. A point
    where more than two of the lines meet is not a corner of a profile and is left out."""
    lines = [i for i in line_ids if isinstance(sketch.entities.get(i), Line)]
    ends: list[tuple[Vec, str]] = []
    for lid in lines:
        line = sketch.entities[lid]
        assert isinstance(line, Line)
        ends += [(sketch.xy(line.p1), lid), (sketch.xy(line.p2), lid)]
    out: list[tuple[str, str, Vec]] = []
    used: set[int] = set()
    for i, (at, _lid) in enumerate(ends):
        if i in used:
            continue
        here = [j for j, (other, _l) in enumerate(ends) if dist(other, at) < 1e-6]
        used.update(here)
        owners = [ends[j][1] for j in here]
        if len(owners) == 2 and owners[0] != owners[1]:
            out.append((owners[0], owners[1], at))
    return out


def round_all(
    sketch: Sketch,
    line_ids: list[str],
    radius: float,
    overrides: dict[int, float] | None = None,
) -> RoundAllResult:
    """Round every corner between ``line_ids`` (TR227, D834): one radius dimension on
    the first arc and Equal on the others, except corners in ``overrides`` (index into
    ``corners_of``), which get their own radius dimension. A corner whose lines are too
    short is skipped and named in ``skipped``."""
    if radius <= 1e-9:
        raise CornerError("Type a radius larger than zero.")
    overrides = overrides or {}
    found = corners_of(sketch, line_ids)
    if not found:
        raise CornerError("The picked lines have no corners. Pick lines that meet end to end.")
    result = RoundAllResult()
    first: str | None = None
    for index, (l1, l2, _at) in enumerate(found):
        own = overrides.get(index)
        r = own if own is not None else radius
        a, b = sketch.entities.get(l1), sketch.entities.get(l2)
        if not isinstance(a, Line) or not isinstance(b, Line):
            result.skipped.append(f"corner {index + 1}: a line was used up by another corner")
            continue
        pick1 = _middle(sketch, a)
        pick2 = _middle(sketch, b)
        try:
            made = fillet(
                sketch,
                l1,
                pick1,
                l2,
                pick2,
                r,
                force=True,
                dimension=own is not None or first is None,
                equal_to=first if own is None else None,
            )
        except CornerError as exc:
            result.skipped.append(f"corner {index + 1}: {exc}")
            continue
        result.arcs.append(made.curve)
        if own is None and first is None:
            first = made.curve
            result.dimension = made.dimensions[0] if made.dimensions else None
    if not result.arcs:
        raise CornerError(
            "No corner could be rounded: " + "; ".join(result.skipped) + ". Use a smaller radius."
        )
    return result


def _middle(sketch: Sketch, line: Line) -> Vec:
    a, b = sketch.xy(line.p1), sketch.xy(line.p2)
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
