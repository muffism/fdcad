"""The sketch problem list (TUTORIAL_REVIEW_SPEC_2 TR38, D1301). Pure Python, no Qt.

A sketch is Under, Fully or Over defined (``solver.SketchStatus``). This module
adds three states the sketch editor shows: Dangling (a relation or dimension
names an item that no longer exists), Invalid (a zero length line, a zero
radius circle or arc, or a spline that crosses itself) and No Solution (the
solver found no answer, with nothing conflicting). ``solve_around`` solves the
sketch with dangling items left out, so the rest still solves.

``problems`` lists each problem: dangling items, conflict sets (items that
share entities are one set), redundant items and invalid geometry.
``diagnose`` lists the ways out of a conflict set, a duplicate dimension
first; ``replacement`` finds the one item a dangling one could name instead.
"""

from __future__ import annotations

import copy
import itertools
import math
from dataclasses import dataclass, field

from fdcad.core.sketch.freeform import sample
from fdcad.core.sketch.model import (
    Arc,
    Circle,
    Line,
    Point,
    Sketch,
    Spline,
)
from fdcad.core.sketch.solver import (
    ConstraintRef,
    SketchSolveError,
    SketchStatus,
    SolveResult,
    solve,
)

#: Display states of the sketch editor, worst first (beside under, full and over).
STATES = ("dangling", "invalid", "no_solution")
#: A dangling item tried against more entities than this is not repaired (speed).
MAX_CANDIDATES = 400
_ZERO = 1e-6


@dataclass
class Problem:
    """One row of the problem list. ``keys`` are relation (``r<index>``) and dimension
    ids, ``entities`` the entities to select; ``group`` numbers a conflict set."""

    kind: str  # dangling, conflicting, redundant, invalid, no_solution
    keys: list[str]
    entities: list[str]
    message: str
    group: int = 0
    #: Dangling items: the names that no longer exist.
    missing: list[str] = field(default_factory=list)


@dataclass
class WayOut:
    """One way out of a conflict set: make a dimension reference or delete an item.
    ``moved`` is how far the most moved point goes (mm)."""

    key: str
    action: str  # reference or delete
    moved: float
    label: str


def _key_of(ref: ConstraintRef) -> str:
    return f"r{ref.key}" if ref.kind == "relation" else str(ref.key)


def item_entities(sketch: Sketch, key: str) -> list[str]:
    """The entity names of relation ``r<index>`` or dimension ``key``."""
    if key.startswith("r") and key[1:].isdigit():
        index = int(key[1:])
        return list(sketch.relations[index].entities) if index < len(sketch.relations) else []
    dim = next((d for d in sketch.dimensions if d.id == key), None)
    return list(dim.entities) if dim is not None else []


def item_name(sketch: Sketch, key: str) -> str:
    """A short name for a relation or dimension in messages."""
    if key.startswith("r") and key[1:].isdigit():
        index = int(key[1:])
        if index < len(sketch.relations):
            kind = sketch.relations[index].type.replace("_", " ").capitalize()
            return f"{kind} relation"
        return "Relation"
    dim = next((d for d in sketch.dimensions if d.id == key), None)
    if dim is None:
        return key
    return f"Dimension {dim.name or dim.id}"


def dangling_items(sketch: Sketch) -> list[str]:
    """Relations (``r<index>``) and dimensions that name a missing entity."""
    out = [
        f"r{i}"
        for i, r in enumerate(sketch.relations)
        if any(e not in sketch.entities for e in r.entities)
    ]
    out += [d.id for d in sketch.dimensions if any(e not in sketch.entities for e in d.entities)]
    return out


def solve_around(sketch: Sketch) -> tuple[SolveResult, list[str]]:
    """Solve ``sketch`` in place with its dangling items left out. Returns the result
    and the dangling items. Raises SketchSolveError as ``solve`` does for other
    unsuitable items."""
    dangling = dangling_items(sketch)
    if not dangling:
        return solve(sketch), []
    rel_off = [
        (sketch.relations[int(k[1:])], sketch.relations[int(k[1:])].off)
        for k in dangling
        if k.startswith("r") and k[1:].isdigit()
    ]
    dims = list(sketch.dimensions)
    try:
        for rel, _was in rel_off:
            rel.off = True
        sketch.dimensions = [d for d in dims if d.id not in dangling]
        result = solve(sketch)
    finally:
        for rel, was in rel_off:
            rel.off = was
        kept = {d.id: d for d in sketch.dimensions}
        sketch.dimensions = [kept.get(d.id, d) for d in dims]
    return result, dangling


def _crosses_itself(points: list[tuple[float, float]]) -> bool:
    """True when a polyline crosses itself (segments that do not touch end to end)."""
    segs = list(itertools.pairwise(points))
    n = len(segs)

    def cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    closed = n > 2 and math.dist(points[0], points[-1]) <= _ZERO
    for i in range(n):
        p1, p2 = segs[i]
        for j in range(i + 2, n):
            if closed and i == 0 and j == n - 1:
                continue
            q1, q2 = segs[j]
            d1, d2 = cross(q1, q2, p1), cross(q1, q2, p2)
            d3, d4 = cross(p1, p2, q1), cross(p1, p2, q2)
            if d1 * d2 < 0 and d3 * d4 < 0:
                return True
    return False


def invalid_items(sketch: Sketch) -> list[tuple[str, str]]:
    """Curves with invalid geometry, each with the reason."""
    out: list[tuple[str, str]] = []
    for c in sketch.curves(True):
        if isinstance(c, Line):
            if math.dist(sketch.xy(c.p1), sketch.xy(c.p2)) <= _ZERO:
                out.append((c.id, f"Line {c.id} has zero length."))
        elif isinstance(c, Circle | Arc):
            if sketch.radius(c.id) <= _ZERO:
                out.append((c.id, f"{type(c).__name__} {c.id} has zero radius."))
        elif isinstance(c, Spline):
            try:
                pts = sample(sketch, c)
            except (ValueError, ZeroDivisionError, KeyError):
                continue
            if len(pts) <= 400 and _crosses_itself([(float(x), float(y)) for x, y in pts]):
                out.append((c.id, f"Spline {c.id} crosses itself."))
    return out


def state_of(result: SolveResult | None, dangling: list[str], invalid: list[str]) -> str:
    """The display state: dangling, invalid, no_solution, or under, full, over."""
    if dangling:
        return "dangling"
    if invalid:
        return "invalid"
    if result is None:
        return SketchStatus.OVER.value
    if not result.solved and not result.conflicting and not result.redundant:
        return "no_solution"
    return result.status.value


def _groups(sketch: Sketch, keys: list[str]) -> list[list[str]]:
    """Conflicting items that share an entity, as sets."""
    parent = {k: k for k in keys}

    def find(k: str) -> str:
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    owner: dict[str, str] = {}
    for k in keys:
        for e in item_entities(sketch, k):
            if e in owner:
                parent[find(k)] = find(owner[e])
            else:
                owner[e] = k
    out: dict[str, list[str]] = {}
    for k in keys:
        out.setdefault(find(k), []).append(k)
    return list(out.values())


def problems(
    sketch: Sketch, result: SolveResult | None, dangling: list[str] | None = None
) -> list[Problem]:
    """Every problem of a solved sketch, worst first."""
    out: list[Problem] = []
    for key in dangling if dangling is not None else dangling_items(sketch):
        names = item_entities(sketch, key)
        missing = [e for e in names if e not in sketch.entities]
        out.append(
            Problem(
                "dangling",
                [key],
                [e for e in names if e in sketch.entities],
                f"{item_name(sketch, key)} names {', '.join(missing)}, which no longer exists.",
                missing=missing,
            )
        )
    for eid, reason in invalid_items(sketch):
        out.append(Problem("invalid", [], [eid], reason))
    if result is not None:
        conflicting = list(dict.fromkeys(_key_of(r) for r in result.conflicting))
        for n, group in enumerate(_groups(sketch, conflicting), start=1):
            ents = list(dict.fromkeys(e for k in group for e in item_entities(sketch, k)))
            listed = ", ".join(item_name(sketch, k) for k in group)
            out.append(
                Problem(
                    "conflicting",
                    group,
                    ents,
                    f"Conflict set {n}: {listed}. Use Diagnose to find a way out.",
                    group=n,
                )
            )
        for ref in result.redundant:
            key = _key_of(ref)
            if key in conflicting:
                continue
            out.append(
                Problem(
                    "redundant",
                    [key],
                    item_entities(sketch, key),
                    f"{item_name(sketch, key)} is not needed (harmless: the sketch still "
                    "solves). Delete it to tidy the sketch.",
                )
            )
        if not result.solved and not result.conflicting and not result.redundant:
            out.append(
                Problem(
                    "no_solution",
                    [],
                    [],
                    "The sketch has no solution. Undo the last change or adjust the dimensions.",
                )
            )
    return out


# Ways out -----------------------------------------------------------------------------


def _duplicate_of(sketch: Sketch, key: str) -> bool:
    """True when dimension ``key`` measures the same thing as an earlier dimension."""
    dims = sketch.dimensions
    dim = next((d for d in dims if d.id == key), None)
    if dim is None:
        return False
    for other in dims:
        if other.id == key:
            return False
        if other.type == dim.type and sorted(other.entities) == sorted(dim.entities):
            return True
    return False


def apply_way_out(sketch: Sketch, way: WayOut) -> None:
    """Make the dimension reference, or delete the relation or dimension."""
    if way.action == "reference":
        for d in sketch.dimensions:
            if d.id == way.key:
                d.driving = False
        return
    delete_item(sketch, way.key)


def delete_item(sketch: Sketch, key: str) -> None:
    """Delete relation ``r<index>`` or dimension ``key``."""
    if key.startswith("r") and key[1:].isdigit():
        index = int(key[1:])
        if index < len(sketch.relations):
            del sketch.relations[index]
        return
    sketch.dimensions = [d for d in sketch.dimensions if d.id != key]


def _points(sketch: Sketch) -> dict[str, tuple[float, float]]:
    return {e.id: (e.x, e.y) for e in sketch.entities.values() if isinstance(e, Point)}


def _moved(before: dict[str, tuple[float, float]], after: Sketch) -> float:
    now = _points(after)
    return max((math.dist(xy, now[p]) for p, xy in before.items() if p in now), default=0.0)


def diagnose(sketch: Sketch, keys: list[str]) -> list[WayOut]:
    """The ways out of conflict set ``keys``: each item made reference (dimensions) or
    deleted (relations), kept when the sketch then solves with no conflict. A
    duplicate dimension comes first; then the ways that move least."""
    before = _points(sketch)
    out: list[tuple[bool, WayOut]] = []
    for key in keys:
        is_dim = not (key.startswith("r") and key[1:].isdigit())
        action = "reference" if is_dim else "delete"
        way = WayOut(key, action, 0.0, "")
        trial = copy.deepcopy(sketch)
        apply_way_out(trial, way)
        try:
            result, _ = solve_around(trial)
        except SketchSolveError:
            continue
        if not result.solved or result.conflicting:
            continue
        way.moved = _moved(before, trial)
        verb = "Make it a reference dimension" if is_dim else "Delete it"
        way.label = f"{item_name(sketch, key)}: {verb}. Points move up to {way.moved:.4g} mm."
        out.append((is_dim and _duplicate_of(sketch, key), way))
    out.sort(key=lambda t: (not t[0], t[1].moved))
    return [w for _dup, w in out]


# Dangling items ------------------------------------------------------------------------


def _holds(sketch: Sketch, key: str) -> bool:
    """True when the item solves with nothing conflicting and nothing moving."""
    before = _points(sketch)
    trial = copy.deepcopy(sketch)
    try:
        result, dangling = solve_around(trial)
    except (SketchSolveError, KeyError, TypeError, ValueError):
        return False
    if key in dangling or not result.solved or result.conflicting or result.redundant:
        return False
    return _moved(before, trial) <= 1e-6


def replacement(sketch: Sketch, key: str) -> dict[str, str] | None:
    """The single clear replacement for the missing names of a dangling item: the one
    entity that makes the item fit and already hold where the sketch stands (so
    nothing moves). None when there is no such entity or more than one."""
    names = item_entities(sketch, key)
    missing = [e for e in names if e not in sketch.entities]
    if len(missing) != 1:
        return None
    candidates = [
        eid for eid in sketch.entities if eid not in names and not _is_origin(sketch, eid)
    ][:MAX_CANDIDATES]
    found: list[str] = []
    for eid in candidates:
        trial = copy.deepcopy(sketch)
        set_item_entity(trial, key, missing[0], eid)
        if _holds(trial, key):
            found.append(eid)
            if len(found) > 1:
                return None
    return {missing[0]: found[0]} if found else None


def set_item_entity(sketch: Sketch, key: str, old: str, new: str) -> None:
    """Make relation or dimension ``key`` name ``new`` instead of ``old``."""
    if key.startswith("r") and key[1:].isdigit():
        rel = sketch.relations[int(key[1:])]
        rel.entities = [new if e == old else e for e in rel.entities]
        return
    for d in sketch.dimensions:
        if d.id == key:
            d.entities = [new if e == old else e for e in d.entities]
            if old in d.measure_to:
                d.measure_to[new] = d.measure_to.pop(old)


def _is_origin(sketch: Sketch, pid: str) -> bool:
    p = sketch.entities.get(pid)
    return (
        isinstance(p, Point)
        and p.construction
        and abs(p.x) < 1e-12
        and abs(p.y) < 1e-12
        and any(r.type == "fixed" and r.entities == [pid] for r in sketch.relations)
    )
