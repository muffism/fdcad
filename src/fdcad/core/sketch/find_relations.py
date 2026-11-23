"""Find relations missing from existing geometry (TUTORIAL_REVIEW_SPEC_2 TR416, DECISIONS
D896).

Geometry drawn without relations (or imported from DXF and SVG) is often nearly
horizontal, vertical, joined, tangent, parallel, square or equal. :func:`suggest`
lists the relations that fit within an angle and a distance tolerance and are not
there yet, for the user to tick and add in one step. No Qt.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

from fdcad.core.sketch.model import Arc, Circle, Line, Sketch

#: Default tolerances: 1 degree and 0.05 mm.
ANGLE = math.radians(1.0)
DISTANCE = 0.05


@dataclass(frozen=True)
class Suggestion:
    """One relation that fits: its type and the entities, in the order to add them."""

    type: str
    entities: tuple[str, ...]


def _direction(sketch: Sketch, line: Line) -> tuple[float, float, float]:
    (x1, y1), (x2, y2) = sketch.xy(line.p1), sketch.xy(line.p2)
    return math.atan2(y2 - y1, x2 - x1), x2 - x1, y2 - y1


def _off(angle: float, target: float) -> float:
    """How far ``angle`` is from ``target`` as a line direction (either way round)."""
    return abs(math.remainder(angle - target, math.pi))


def _existing(sketch: Sketch) -> set[tuple[str, frozenset[str]]]:
    return {(r.type, frozenset(r.entities)) for r in sketch.relations}


def suggest(sketch: Sketch, angle: float = ANGLE, distance: float = DISTANCE) -> list[Suggestion]:
    """Relations that fit the geometry within the tolerances and are not there yet."""
    have = _existing(sketch)
    out: list[Suggestion] = []

    def add(rtype: str, *ids: str) -> None:
        if (rtype, frozenset(ids)) not in have:
            out.append(Suggestion(rtype, ids))
            have.add((rtype, frozenset(ids)))

    lines = [e for e in sketch.entities.values() if isinstance(e, Line) and not e.construction]
    axis: set[str] = set()
    for line in lines:
        a, _dx, _dy = _direction(sketch, line)
        if _off(a, 0.0) <= angle:
            add("horizontal", line.id)
            axis.add(line.id)
        elif _off(a, math.pi / 2) <= angle:
            add("vertical", line.id)
            axis.add(line.id)
    for p, q in itertools.combinations(lines, 2):
        if p.id in axis and q.id in axis:
            continue  # both already follow an axis: parallel or square comes with it
        ap, aq = _direction(sketch, p)[0], _direction(sketch, q)[0]
        if _off(ap, aq) <= angle:
            add("parallel", p.id, q.id)
        elif _off(ap, aq + math.pi / 2) <= angle:
            add("perpendicular", p.id, q.id)
    # Ends that nearly meet but are separate points.
    ends: list[tuple[str, str]] = []
    for e in sketch.entities.values():
        if isinstance(e, Line):
            ends += [(e.id, e.p1), (e.id, e.p2)]
        elif isinstance(e, Arc):
            ends += [(e.id, e.start), (e.id, e.end)]
    for (ca, pa), (cb, pb) in itertools.combinations(ends, 2):
        if ca != cb and pa != pb and math.dist(sketch.xy(pa), sketch.xy(pb)) <= distance:
            add("coincident", pa, pb)
    # Lines that leave an arc's end along its tangent.
    for line in lines:
        for arc in (e for e in sketch.entities.values() if isinstance(e, Arc)):
            shared = {line.p1, line.p2} & {arc.start, arc.end}
            if not shared:
                continue
            pid = shared.pop()
            c = sketch.xy(arc.center)
            at = sketch.xy(pid)
            radial = math.atan2(at[1] - c[1], at[0] - c[0])
            if _off(_direction(sketch, line)[0], radial + math.pi / 2) <= angle:
                add("tangent", line.id, arc.id)
    rounds = [e for e in sketch.entities.values() if isinstance(e, (Arc, Circle))]
    for r1, r2 in itertools.combinations(rounds, 2):
        if abs(sketch.radius(r1.id) - sketch.radius(r2.id)) <= distance:
            add("equal", r1.id, r2.id)
    return out


def add_suggestions(sketch: Sketch, picked: list[Suggestion]) -> int:
    """Add the picked relations. Returns how many were added."""
    for s in picked:
        sketch.relate(s.type, *s.entities)
    return len(picked)
