"""Fully Define Sketch (TR35, DECISIONS D762).

Works out relations and dimensions that make a sketch fully defined at its
current shape, so nothing moves:

1. Relations that already hold: Horizontal and Vertical lines, and two points in
   the same place made Coincident.
2. Sizes: the diameter of each circle and the radius of each arc, then the
   length of each line.
3. Positions, by the chosen scheme: ``baseline`` (every point's horizontal and
   vertical distance from the datum point), ``chain`` (each point's distance from
   the one before it, sorted along each axis, starting at the datum) or ``datum``
   (datum pairs: the horizontal and vertical distance of each point from the
   datum, the same pairs as baseline but listed point by point). A point level
   with the datum gets a Horizontal or Vertical relation to it instead of a zero
   distance when relations are on.

Each candidate is tried on a copy and kept only when it takes away freedom
without a conflict, so no relation or dimension is ever redundant. It stops as
soon as the sketch is fully defined. Entities already fully defined are skipped.
Pure Python: the solver wrapper only (CLAUDE.md 5.6).
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Arc, Circle, Line, Point, Sketch
from fdcad.core.sketch.solver import (
    SketchSolveError,
    SketchStatus,
    _build,
    defined_entities,
    measure,
    solve,
)
from fdcad.core.units import UnitSystem

SCHEMES = ("chain", "baseline", "datum")
#: Two points this close (mm) are the same place; a line this close to level is level.
_SAME = 1e-9
#: Candidates tried at most, so a huge sketch never stalls the panel.
MAX_TRIES = 2000


@dataclass(frozen=True)
class Proposal:
    """One relation or dimension the command would add."""

    kind: str  # "relation" or "dimension"
    type: str
    entities: tuple[str, ...]
    value: float = 0.0  # mm or radians, for dimensions

    def text(self, units: UnitSystem) -> str:
        """A row of the list the panel shows."""
        name = self.type.replace("_", " ").capitalize()
        if self.kind == "relation":
            return f"{name}: {', '.join(self.entities)}"
        return f"{name} {_typed(self.value, self.type, units)}: {', '.join(self.entities)}"


class FullyDefineError(ValueError):
    """The sketch cannot be fully defined as it is. The message says what to do."""


def _typed(value: float, dtype: str, units: UnitSystem) -> str:
    if dtype == "angle":
        return f"{math.degrees(value):.6g}deg"
    if units is UnitSystem.IN:
        return f"{value / 25.4:.6g}in"
    return f"{value:.6g}mm"


def origin_of(sketch: Sketch) -> str | None:
    """The sketch origin: the fixed construction point at (0, 0)."""
    fixed = {r.entities[0] for r in sketch.relations if r.type == "fixed" and r.entities}
    for e in sketch.entities.values():
        if isinstance(e, Point) and e.id in fixed and math.hypot(e.x, e.y) < _SAME:
            return e.id
    return None


def _dof(sketch: Sketch) -> int | None:
    """Freedom left, or None when the sketch has a conflict or a redundant item."""
    try:
        diagnosis = _build(sketch).s.diagnose()
    except SketchSolveError:
        return None
    if list(diagnosis.conflicting) or list(diagnosis.redundant):
        return None
    return int(diagnosis.dof)


def _relation_candidates(sketch: Sketch, free: set[str]) -> list[Proposal]:
    out: list[Proposal] = []
    have = {(r.type, tuple(r.entities)) for r in sketch.relations}
    for e in sketch.entities.values():
        if not isinstance(e, Line) or e.id not in free:
            continue
        (x1, y1), (x2, y2) = sketch.xy(e.p1), sketch.xy(e.p2)
        length = math.hypot(x2 - x1, y2 - y1)
        if length < _SAME:
            continue
        if abs(y2 - y1) <= _SAME * max(length, 1.0) and ("horizontal", (e.id,)) not in have:
            out.append(Proposal("relation", "horizontal", (e.id,)))
        elif abs(x2 - x1) <= _SAME * max(length, 1.0) and ("vertical", (e.id,)) not in have:
            out.append(Proposal("relation", "vertical", (e.id,)))
    points = [e for e in sketch.entities.values() if isinstance(e, Point) and e.id in free]
    for i, a in enumerate(points):
        for b in points[i + 1 :]:
            if math.hypot(a.x - b.x, a.y - b.y) < _SAME:
                out.append(Proposal("relation", "coincident", (a.id, b.id)))
    return out


def _size_candidates(sketch: Sketch, free: set[str]) -> list[Proposal]:
    out: list[Proposal] = []
    for e in sketch.entities.values():
        if e.id not in free:
            continue
        if isinstance(e, Circle):
            out.append(Proposal("dimension", "diameter", (e.id,), 2 * e.radius))
        elif isinstance(e, Arc):
            out.append(Proposal("dimension", "radius", (e.id,), sketch.radius(e.id)))
    for e in sketch.entities.values():
        if isinstance(e, Line) and e.id in free:
            (x1, y1), (x2, y2) = sketch.xy(e.p1), sketch.xy(e.p2)
            out.append(Proposal("dimension", "distance", (e.id,), math.hypot(x2 - x1, y2 - y1)))
    return out


def _axis(datum: str, pid: str, axis: int, value: float, relations: bool) -> Proposal:
    if value < _SAME and relations:
        # Level with the datum: a relation instead of a zero distance.
        return Proposal("relation", "vertical" if axis == 0 else "horizontal", (datum, pid))
    dtype = "horizontal_distance" if axis == 0 else "vertical_distance"
    return Proposal("dimension", dtype, (datum, pid), value)


def _position_candidates(
    sketch: Sketch, free: set[str], scheme: str, datum: str, relations: bool
) -> list[Proposal]:
    points = [
        e
        for e in sketch.entities.values()
        if isinstance(e, Point) and e.id in free and e.id != datum and not e.construction
    ]
    # Construction points (handles, centres made by tools) come last, so curves come first.
    points += [
        e
        for e in sketch.entities.values()
        if isinstance(e, Point) and e.id in free and e.id != datum and e.construction
    ]
    dx, dy = sketch.xy(datum)
    out: list[Proposal] = []
    if scheme == "chain":
        for axis in (0, 1):
            ordered = sorted(points, key=lambda p: (p.x, p.y)[axis])
            before = datum
            for p in ordered:
                b = sketch.xy(before)
                out.append(_axis(before, p.id, axis, abs((p.x, p.y)[axis] - b[axis]), relations))
                before = p.id
        return out
    for p in points:  # baseline and datum pairs
        out.append(_axis(datum, p.id, 0, abs(p.x - dx), relations))
        out.append(_axis(datum, p.id, 1, abs(p.y - dy), relations))
    if scheme == "baseline":  # all horizontal distances first, then all vertical ones
        out.sort(key=lambda c: c.type != "horizontal_distance" and c.type != "vertical")
    return out


def _add(sketch: Sketch, proposal: Proposal, units: UnitSystem) -> None:
    if proposal.kind == "relation":
        sketch.relate(proposal.type, *proposal.entities)
    else:
        text = _typed(proposal.value, proposal.type, units)
        sketch.dimension(proposal.type, list(proposal.entities), Param(text, proposal.value))


def propose(
    sketch: Sketch,
    units: UnitSystem,
    entities: set[str] | None = None,
    relations: bool = True,
    dimensions: bool = True,
    scheme: str = "baseline",
    datum: str | None = None,
) -> list[Proposal]:
    """What would make the sketch (or ``entities`` of it) fully defined, without moving
    anything. Raises FullyDefineError for a sketch with a conflict or no datum."""
    if scheme not in SCHEMES:
        raise FullyDefineError(f"unknown scheme {scheme}. Choose Chain, Baseline or Datum Pairs.")
    work = copy.deepcopy(sketch)
    try:
        status = solve(copy.deepcopy(sketch)).status
    except SketchSolveError as exc:
        raise FullyDefineError(str(exc)) from exc
    if status is SketchStatus.OVER:
        raise FullyDefineError(
            "the sketch has conflicting or extra relations or dimensions. "
            "Fix the highlighted items first, then try again."
        )
    datum = datum or origin_of(sketch)
    if datum is None or datum not in sketch.entities:
        raise FullyDefineError("the sketch has no origin point. Pick a point as the datum.")
    defined = defined_entities(work)
    wanted = set(sketch.entities) if entities is None else set(entities)
    # A curve's points are part of it, so picking a line also frees its end points.
    for eid in list(wanted):
        e = sketch.entities.get(eid)
        if isinstance(e, Line):
            wanted |= {e.p1, e.p2}
        elif isinstance(e, Circle):
            wanted.add(e.center)
        elif isinstance(e, Arc):
            wanted |= {e.center, e.start, e.end}
    free = {eid for eid in wanted if eid not in defined}
    candidates: list[Proposal] = []
    if relations:
        candidates += _relation_candidates(work, free)
    if dimensions:
        candidates += _size_candidates(work, free)
        candidates += _position_candidates(work, free, scheme, datum, relations)
    elif relations:
        candidates += [
            c for c in _position_candidates(work, free, scheme, datum, True) if c.kind == "relation"
        ]
    dof = _dof(work)
    if dof is None:
        raise FullyDefineError(
            "the sketch has conflicting or extra relations or dimensions. "
            "Fix the highlighted items first, then try again."
        )
    kept: list[Proposal] = []
    for tries, candidate in enumerate(candidates):
        if dof == 0 or tries >= MAX_TRIES:
            break
        trial = copy.deepcopy(work)
        try:
            _add(trial, candidate, units)
        except ValueError:
            continue
        after = _dof(trial)
        if after is not None and after < dof:
            work, dof = trial, after
            kept.append(candidate)
    return kept


def apply(sketch: Sketch, proposals: list[Proposal], units: UnitSystem) -> None:
    """Add the proposals to ``sketch`` (the caller makes it one undo step)."""
    for proposal in proposals:
        _add(sketch, proposal, units)


def check_unmoved(before: Sketch, after: Sketch) -> float:
    """The largest distance any point moved, in mm (zero when nothing moved)."""
    worst = 0.0
    for e in before.entities.values():
        if isinstance(e, Point) and e.id in after.entities:
            p = after.entities[e.id]
            assert isinstance(p, Point)
            worst = max(worst, math.hypot(p.x - e.x, p.y - e.y))
    return worst


__all__ = ["SCHEMES", "FullyDefineError", "Proposal", "apply", "measure", "origin_of", "propose"]
