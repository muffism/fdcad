"""Repair Sketch: find and fix small faults (TUTORIAL_REVIEW_SPEC_2 TR37, D1300).

``find_faults`` lists gaps between end points smaller than a tolerance,
overlapping lines and duplicate curves, tiny segments, duplicate points, zero
length lines, zero radius arcs and circles, and relations or dimensions that
name a missing entity or the wrong kind of entity. ``fix`` repairs one fault
and returns how far it moved points; nothing is fixed unless asked (CLAUDE.md
section 5 item 12). Pure Python, no Qt.
"""

from __future__ import annotations

import contextlib
import math
from collections import defaultdict
from dataclasses import dataclass, field

from fdcad.core.sketch.model import (
    Arc,
    Circle,
    Curve,
    Line,
    Point,
    Sketch,
    curve_ends,
    entity_points,
)

#: Default tolerance of the Repair Sketch panel, in mm (the near miss of D763).
DEFAULT_TOLERANCE = 0.05
#: Two points closer than this are at the same place; a length below it is zero.
ZERO = 1e-6

Vec = tuple[float, float]

#: Fault kinds in the order the list shows them (removals and merges that other
#: fixes depend on come first).
KINDS = (
    "bad_relation",
    "bad_dimension",
    "zero_line",
    "zero_radius",
    "tiny",
    "duplicate_curve",
    "overlap",
    "duplicate_point",
    "gap",
)


@dataclass
class Fault:
    """One fault. ``key`` names the item a fix works on: a relation (``r<index>``),
    a dimension id or a curve id; ``entities`` are what the list selects."""

    kind: str
    key: str
    entities: list[str]
    message: str
    at: Vec | None = None
    #: How far the fix moves points, in mm (0 when it only removes items).
    move: float = 0.0
    #: The second point or curve of a pair fault.
    other: str = ""
    extra: dict[str, float] = field(default_factory=dict)


def _is_origin(sketch: Sketch, pid: str) -> bool:
    p = sketch.entities.get(pid)
    return (
        isinstance(p, Point)
        and p.construction
        and abs(p.x) < 1e-12
        and abs(p.y) < 1e-12
        and any(r.type == "fixed" and r.entities == [pid] for r in sketch.relations)
    )


def _mm(value: float) -> str:
    return f"{value:.4g} mm"


def _users(sketch: Sketch) -> dict[str, list[str]]:
    """Curve ids by the point ids they use."""
    out: dict[str, list[str]] = defaultdict(list)
    for c in sketch.curves(True):
        for pid in entity_points(c):
            out[pid].append(c.id)
    return out


def _joined(sketch: Sketch, a: str, b: str) -> bool:
    """True when a coincident relation already ties points ``a`` and ``b``."""
    return any(
        r.type == "coincident" and set(r.entities) == {a, b} and not r.off for r in sketch.relations
    )


def _length(sketch: Sketch, c: Curve) -> float | None:
    """Length of a line or arc; None for other curves."""
    if isinstance(c, Line):
        return math.dist(sketch.xy(c.p1), sketch.xy(c.p2))
    if isinstance(c, Arc):
        cx, cy = sketch.xy(c.center)
        (sx, sy), (ex, ey) = sketch.xy(c.start), sketch.xy(c.end)
        r = math.hypot(sx - cx, sy - cy)
        a0, a1 = math.atan2(sy - cy, sx - cx), math.atan2(ey - cy, ex - cx)
        sweep = (a1 - a0) % (2 * math.pi) if c.ccw else (a0 - a1) % (2 * math.pi)
        return r * sweep
    return None


# Finding ---------------------------------------------------------------------------


def _item_faults(sketch: Sketch) -> list[Fault]:
    """Relations and dimensions that name a missing entity or the wrong kind."""
    from fdcad.core.sketch.solver import SketchSolveError, _Builder

    out: list[Fault] = []
    builder = _Builder(sketch)
    try:
        builder.add_geometry()
    except (KeyError, TypeError, ValueError):
        return out  # the curves themselves are broken: the other checks say so
    for index, rel in enumerate(sketch.relations):
        missing = [e for e in rel.entities if e not in sketch.entities]
        reason = f"names {', '.join(missing)}, which no longer exists" if missing else ""
        if not reason:
            try:
                builder.add_relation(index, rel)
            except (SketchSolveError, KeyError, TypeError, IndexError) as exc:
                reason = f"does not fit its entities ({exc})"
        if reason:
            out.append(
                Fault(
                    "bad_relation",
                    f"r{index}",
                    [e for e in rel.entities if e in sketch.entities],
                    f"{rel.type.replace('_', ' ').capitalize()} relation {reason}. Fix deletes it.",
                )
            )
    for dim in sketch.dimensions:
        missing = [e for e in dim.entities if e not in sketch.entities]
        reason = f"names {', '.join(missing)}, which no longer exists" if missing else ""
        if not reason:
            trial = (dim.driving, dim.off)
            try:
                dim.driving, dim.off = True, False
                builder.add_dimension(dim)
            except (SketchSolveError, KeyError, TypeError, IndexError) as exc:
                reason = f"does not fit its entities ({exc})"
            finally:
                dim.driving, dim.off = trial
        if reason:
            out.append(
                Fault(
                    "bad_dimension",
                    dim.id,
                    [e for e in dim.entities if e in sketch.entities],
                    f"Dimension {dim.name or dim.id} {reason}. Fix deletes it.",
                )
            )
    return out


def _curve_faults(sketch: Sketch, tolerance: float) -> list[Fault]:
    out: list[Fault] = []
    for c in sketch.curves(True):
        if isinstance(c, Circle | Arc):
            r = sketch.radius(c.id)
            if r <= ZERO:
                out.append(
                    Fault(
                        "zero_radius",
                        c.id,
                        [c.id],
                        f"{type(c).__name__} {c.id} has zero radius. Fix removes it.",
                        sketch.xy(c.center),
                    )
                )
                continue
        length = _length(sketch, c)
        if length is None:
            continue
        ends = curve_ends(c)
        assert ends is not None
        mid = _middle(sketch.xy(ends[0]), sketch.xy(ends[1]))
        if isinstance(c, Line) and length <= ZERO:
            out.append(
                Fault(
                    "zero_line",
                    c.id,
                    [c.id],
                    f"Line {c.id} has zero length. Fix removes it and joins its ends.",
                    mid,
                )
            )
        elif length < tolerance:
            move = math.dist(sketch.xy(ends[0]), sketch.xy(ends[1])) / 2
            out.append(
                Fault(
                    "tiny",
                    c.id,
                    [c.id],
                    f"{type(c).__name__} {c.id} is only {_mm(length)} long. Fix removes it "
                    f"and joins its ends, moving them by {_mm(move)}.",
                    mid,
                    move,
                )
            )
    return out


def _middle(a: Vec, b: Vec) -> Vec:
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def _pair_faults(sketch: Sketch) -> list[Fault]:
    """Duplicate curves and overlapping lines."""
    from fdcad.core.sketch.topology import _bbox, _overlap, _same_curve

    out: list[Fault] = []
    curves = [c for c in sketch.curves(True)]
    boxes = {c.id: _bbox(sketch, c) for c in curves}
    seen: set[str] = set()
    for i, a in enumerate(curves):
        if a.id in seen:
            continue
        ax0, ay0, ax1, ay1 = boxes[a.id]
        for b in curves[i + 1 :]:
            if b.id in seen or a.construction != b.construction:
                continue
            bx0, by0, bx1, by1 = boxes[b.id]
            if bx0 > ax1 + ZERO or ax0 > bx1 + ZERO or by0 > ay1 + ZERO or ay0 > by1 + ZERO:
                continue
            if _same_curve(sketch, a, b):
                seen.add(b.id)
                out.append(
                    Fault(
                        "duplicate_curve",
                        b.id,
                        [a.id, b.id],
                        f"{b.id} lies on top of {a.id}. Fix removes {b.id}.",
                        other=a.id,
                    )
                )
            elif isinstance(a, Line) and isinstance(b, Line) and _overlap(sketch, a, b):
                seen.add(b.id)
                out.append(
                    Fault(
                        "overlap",
                        a.id,
                        [a.id, b.id],
                        f"Lines {a.id} and {b.id} overlap. Fix merges them into one line.",
                        other=b.id,
                    )
                )
    return out


def _grid(points: list[Point], size: float) -> dict[tuple[int, int], list[Point]]:
    grid: dict[tuple[int, int], list[Point]] = defaultdict(list)
    for p in points:
        grid[(math.floor(p.x / size), math.floor(p.y / size))].append(p)
    return grid


def _near(grid: dict[tuple[int, int], list[Point]], p: Point, size: float) -> list[Point]:
    gx, gy = math.floor(p.x / size), math.floor(p.y / size)
    return [q for dx in (-1, 0, 1) for dy in (-1, 0, 1) for q in grid.get((gx + dx, gy + dy), [])]


def _point_faults(sketch: Sketch, tolerance: float) -> list[Fault]:
    """Duplicate points (same place, not joined) and gaps between open ends."""
    from fdcad.core.sketch.topology import _Nodes

    out: list[Fault] = []
    users = _users(sketch)
    points = [e for e in sketch.entities.values() if isinstance(e, Point)]
    # Duplicate points: two point ids at one place that no relation or curve ties.
    grid = _grid(points, 1e-3)
    done: set[frozenset[str]] = set()
    for p in points:
        for q in _near(grid, p, 1e-3):
            pair = frozenset((p.id, q.id))
            if q.id == p.id or pair in done:
                continue
            if math.hypot(p.x - q.x, p.y - q.y) > ZERO or _joined(sketch, p.id, q.id):
                continue
            if set(users.get(p.id, [])) & set(users.get(q.id, [])):
                continue  # ends of one curve: a zero length curve, listed on its own
            if _is_origin(sketch, p.id) or _is_origin(sketch, q.id):
                continue  # a point on the sketch origin is not a duplicate of it
            keep, drop = sorted((p.id, q.id), key=lambda s: (len(s), s))
            done.add(pair)
            out.append(
                Fault(
                    "duplicate_point",
                    drop,
                    [keep, drop],
                    f"Points {keep} and {drop} are at the same place. Fix merges them.",
                    (p.x, p.y),
                    other=keep,
                )
            )
    # Gaps: open ends of curves (coincident and overlapping points count as one)
    # closer than the tolerance to another open end.
    nodes = _Nodes(sketch)
    ends_of: dict[str, list[str]] = defaultdict(list)
    for c in sketch.curves(True):
        ends = curve_ends(c)
        if ends is None:
            continue
        for pid in ends:
            ends_of[nodes.find(pid)].append(pid)
    open_ends = [sketch.point(pids[0]) for pids in ends_of.values() if len(pids) == 1]
    if tolerance <= 0:
        return out
    egrid = _grid(open_ends, tolerance)
    paired: set[str] = set()
    for p in open_ends:
        if p.id in paired:
            continue
        best: tuple[float, Point] | None = None
        for q in _near(egrid, p, tolerance):
            if q.id == p.id or q.id in paired or nodes.find(q.id) == nodes.find(p.id):
                continue
            if set(users.get(p.id, [])) & set(users.get(q.id, [])):
                continue  # both ends of one curve: closing it would collapse it
            d = math.hypot(p.x - q.x, p.y - q.y)
            if d <= tolerance and (best is None or d < best[0]):
                best = (d, q)
        if best is None:
            continue
        d, q = best
        paired |= {p.id, q.id}
        out.append(
            Fault(
                "gap",
                p.id,
                [p.id, q.id],
                f"Gap of {_mm(d)} between {p.id} and {q.id}. Fix joins the ends, "
                f"moving each by {_mm(d / 2)}.",
                _middle((p.x, p.y), (q.x, q.y)),
                d / 2,
                other=q.id,
            )
        )
    return out


def find_faults(sketch: Sketch, tolerance: float = DEFAULT_TOLERANCE) -> list[Fault]:
    """Every fault of ``sketch`` with gaps and tiny segments below ``tolerance`` mm."""
    found = (
        _item_faults(sketch)
        + _curve_faults(sketch, tolerance)
        + _pair_faults(sketch)
        + _point_faults(sketch, tolerance)
    )
    tiny = {f.key for f in found if f.kind in ("zero_line", "zero_radius", "tiny")}
    gone = tiny | {f.key for f in found if f.kind == "duplicate_curve"}
    gone_points = {
        p for c in gone if c in sketch.entities for p in entity_points(sketch.entities[c])
    }
    # An overlap or a duplicate point on a curve that a fix removes anyway is not
    # listed again; Fix All finds it afterwards if it is still there.
    found = [
        f
        for f in found
        if not (f.kind in ("overlap", "duplicate_curve") and set(f.entities) & tiny)
        and not (f.kind == "duplicate_point" and set(f.entities) & gone_points)
    ]
    return sorted(found, key=lambda f: KINDS.index(f.kind))


# Fixing ----------------------------------------------------------------------------


def _remove(sketch: Sketch, ids: set[str]) -> None:
    """Delete entities and every relation and dimension naming them."""
    for eid in ids:
        sketch.entities.pop(eid, None)
    sketch.relations = [r for r in sketch.relations if not set(r.entities) & ids]
    sketch.dimensions = [d for d in sketch.dimensions if not set(d.entities) & ids]


def _drop_unused(sketch: Sketch, pids: list[str]) -> None:
    """Delete the points of ``pids`` that no curve uses any more (not the origin)."""
    users = _users(sketch)
    _remove(
        sketch,
        {
            p
            for p in pids
            if p in sketch.entities and not users.get(p) and not _is_origin(sketch, p)
        },
    )


def _node_members(sketch: Sketch, pids: list[str]) -> list[str]:
    """Every point joined to one of ``pids`` by a coincident relation or by place."""
    from fdcad.core.sketch.topology import _Nodes

    nodes = _Nodes(sketch)
    roots = {nodes.find(p) for p in pids}
    return [
        eid
        for eid, e in sketch.entities.items()
        if isinstance(e, Point) and nodes.find(eid) in roots
    ]


def _join(sketch: Sketch, members: list[str], at: Vec, tidy: bool = True) -> None:
    """Move ``members`` to ``at`` (the origin's place when it is one of them) and
    merge them into one point (TR40). With ``tidy``, a point no curve, relation or
    dimension uses afterwards is removed."""
    from fdcad.core.sketch.ops.merge import merge_points

    members = [m for m in members if m in sketch.entities]
    if not members:
        return
    origin = next((m for m in members if _is_origin(sketch, m)), None)
    if origin is not None:
        at = sketch.xy(origin)
    for m in members:
        point = sketch.point(m)
        point.x, point.y = at
    users = _users(sketch)
    keep = origin or next((m for m in members if users.get(m)), members[0])
    for m in members:
        if m != keep and m in sketch.entities:
            # Two ends of one curve stay two points at one place.
            with contextlib.suppress(ValueError):
                merge_points(sketch, keep, m)
    named = {e for r in sketch.relations for e in r.entities}
    named |= {e for d in sketch.dimensions for e in d.entities}
    if tidy and not _users(sketch).get(keep) and keep not in named and origin is None:
        _remove(sketch, {keep})


def _collapse(sketch: Sketch, curve: Curve) -> None:
    """Remove an open curve and join its two ends, and everything joined to them,
    at their middle."""
    ends = curve_ends(curve)
    assert ends is not None
    a, b = ends
    members = _node_members(sketch, [a, b])
    others = [p for p in entity_points(curve) if p not in (a, b)]
    mid = _middle(sketch.xy(a), sketch.xy(b))
    _remove(sketch, {curve.id})
    _drop_unused(sketch, others)
    _join(sketch, members, mid)


def _merge_lines(sketch: Sketch, a: Line, b: Line) -> None:
    """Make line ``a`` cover both lines, then remove ``b``. Nothing moves."""
    x0, y0 = sketch.xy(a.p1)
    x1, y1 = sketch.xy(a.p2)
    length = math.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / length, (y1 - y0) / length

    def t(pid: str) -> float:
        x, y = sketch.xy(pid)
        return (x - x0) * ux + (y - y0) * uy

    ends = [a.p1, a.p2, b.p1, b.p2]
    low = min(ends, key=lambda p: (t(p), p not in (a.p1, a.p2)))
    high = max(ends, key=lambda p: (t(p), p in (a.p1, a.p2)))
    old = [a.p1, a.p2, b.p1, b.p2]
    sketch.entities[a.id] = Line(a.id, low, high, a.construction, a.source)
    _remove(sketch, {b.id})
    _drop_unused(sketch, [p for p in old if p not in (low, high)])


def fix(sketch: Sketch, fault: Fault) -> float:
    """Repair ``fault`` in place. Returns how far points moved (mm). Raises
    ValueError when the fault no longer applies."""
    kind = fault.kind
    if kind == "bad_relation":
        index = int(fault.key[1:])
        if index >= len(sketch.relations):
            raise ValueError("The relation is already gone. Find the faults again.")
        del sketch.relations[index]
        return 0.0
    if kind == "bad_dimension":
        before = len(sketch.dimensions)
        sketch.dimensions = [d for d in sketch.dimensions if d.id != fault.key]
        if len(sketch.dimensions) == before:
            raise ValueError("The dimension is already gone. Find the faults again.")
        return 0.0
    if kind == "duplicate_point" or kind == "gap":
        keep, drop = fault.other, fault.key
        if keep not in sketch.entities or drop not in sketch.entities:
            raise ValueError("The points are already joined. Find the faults again.")
        if kind == "duplicate_point":
            at = sketch.xy(keep)
            members = [keep, drop]
        else:
            at = _middle(sketch.xy(keep), sketch.xy(drop))
            members = _node_members(sketch, [keep, drop])
        moved = max(math.dist(sketch.xy(m), at) for m in members)
        _join(sketch, [keep, *[m for m in members if m != keep]], at, kind == "gap")
        return moved
    curve = sketch.entities.get(fault.key)
    if curve is None or isinstance(curve, Point):
        raise ValueError("The curve is already gone. Find the faults again.")
    if kind == "duplicate_curve":
        _remove(sketch, {curve.id})
        _drop_unused(sketch, entity_points(curve))
        return 0.0
    if kind == "overlap":
        other = sketch.entities.get(fault.other)
        if not isinstance(curve, Line) or not isinstance(other, Line):
            raise ValueError("The lines are already merged. Find the faults again.")
        _merge_lines(sketch, curve, other)
        return 0.0
    if kind == "zero_radius":
        if isinstance(curve, Arc):
            _collapse(sketch, curve)
        else:
            _remove(sketch, {curve.id})
            _drop_unused(sketch, entity_points(curve))
        return 0.0
    if kind in ("zero_line", "tiny"):
        ends = curve_ends(curve)
        if ends is None:
            raise ValueError("Only open curves can be removed this way.")
        moved = math.dist(sketch.xy(ends[0]), sketch.xy(ends[1])) / 2
        _collapse(sketch, curve)
        return moved
    raise ValueError(f"Unknown fault kind '{kind}'.")


def fix_all(sketch: Sketch, tolerance: float = DEFAULT_TOLERANCE) -> tuple[int, float]:
    """Fix every fault, finding them again after each fix since one fix can change
    another. Returns the number fixed and the largest move (mm)."""
    count, largest = 0, 0.0
    skipped: set[tuple[str, str, str]] = set()
    for _ in range(10000):
        faults = [
            f for f in find_faults(sketch, tolerance) if (f.kind, f.key, f.other) not in skipped
        ]
        if not faults:
            break
        fault = faults[0]
        try:
            largest = max(largest, fix(sketch, fault))
            count += 1
        except ValueError:
            skipped.add((fault.kind, fault.key, fault.other))
    return count, largest
