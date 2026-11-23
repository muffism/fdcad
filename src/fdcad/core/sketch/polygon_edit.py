"""Edit a regular polygon after it is drawn (TUTORIAL_REVIEW_SPEC_2 TR114 item 2, D1709).

A polygon is found again from what the Polygon tool made (``ops.shapes.polygon``):
three or more lines that one Equal relation joins into a closed loop, and a
construction circle that every corner lies on (corners on the circle) or every
side touches (sides touch the circle). Editing rebuilds it about the same centre
point, keeping the circle's id, so dimensions and relations on the centre and the
circle stay; those on the old sides and corners go. No Qt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Circle, Line, Point, Sketch, entity_points
from fdcad.core.sketch.ops.shapes import ShapeError, polygon


@dataclass(frozen=True)
class PolygonInfo:
    """A polygon found in a sketch."""

    lines: tuple[str, ...]
    circle: str
    inscribed: bool
    sides: int
    radius: float
    #: Direction from the centre to the first corner (corners on the circle) or to
    #: the middle of the first side (sides touch), in radians.
    angle: float


def _loop(sketch: Sketch, lines: list[str]) -> list[str] | None:
    """The lines in loop order from the first, or None when they do not close."""
    ends = {}
    for lid in lines:
        ln = sketch.entities[lid]
        assert isinstance(ln, Line)
        ends[lid] = (sketch.xy(ln.p1), sketch.xy(ln.p2))
    order = [lines[0]]
    at = ends[lines[0]][1]
    left = set(lines[1:])
    while left:
        nxt = next(
            (k for k in left if any(math.dist(at, p) < 1e-6 for p in ends[k])),
            None,
        )
        if nxt is None:
            return None
        a, b = ends[nxt]
        at = b if math.dist(a, at) < 1e-6 else a
        order.append(nxt)
        left.discard(nxt)
    return order if math.dist(at, ends[lines[0]][0]) < 1e-6 else None


def find_polygon(sketch: Sketch, line_id: str) -> PolygonInfo | None:
    """The polygon line ``line_id`` is a side of, or None."""
    for rel in sketch.relations:
        if rel.type != "equal" or line_id not in rel.entities or len(rel.entities) < 3:
            continue
        lines = list(rel.entities)
        if not all(isinstance(sketch.entities.get(i), Line) for i in lines):
            continue
        order = _loop(sketch, lines)
        if order is None:
            continue
        corners = set()
        for lid in order:
            ln = sketch.entities[lid]
            assert isinstance(ln, Line)
            corners |= {ln.p1, ln.p2}
        for c in sketch.entities.values():
            if not isinstance(c, Circle) or not c.construction:
                continue
            on = {
                p
                for r in sketch.relations
                if r.type == "coincident" and c.id in r.entities
                for p in r.entities
                if p != c.id
            }
            touch = {
                e
                for r in sketch.relations
                if r.type == "tangent" and c.id in r.entities
                for e in r.entities
                if e != c.id
            }
            inscribed = corners <= on
            if not inscribed and not set(order) <= touch:
                continue
            centre = sketch.xy(c.center)
            first = sketch.entities[order[0]]
            assert isinstance(first, Line)
            p1, p2 = sketch.xy(first.p1), sketch.xy(first.p2)
            ref = p1 if inscribed else ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
            angle = math.atan2(ref[1] - centre[1], ref[0] - centre[0])
            return PolygonInfo(tuple(order), c.id, inscribed, len(order), c.radius, angle)
    return None


def edit_polygon(
    sketch: Sketch,
    info: PolygonInfo,
    sides: int,
    inscribed: bool,
    radius: float,
    angle: float,
) -> list[str]:
    """Rebuild the polygon ``info`` with new values. Returns the new side ids."""
    if radius <= 1e-9:
        raise ShapeError("Type a size larger than zero.")
    old_circle = sketch.entities[info.circle]
    assert isinstance(old_circle, Circle)
    centre_id = old_circle.center
    centre = sketch.xy(centre_id)
    construction = all(sketch.entities[lid].construction for lid in info.lines)
    vertex = (centre[0] + radius * math.cos(angle), centre[1] + radius * math.sin(angle))
    scratch = Sketch()
    polygon(scratch, centre, vertex, sides, inscribed)  # checks the values first
    # Drop the old sides, their corners and what names them.
    corners = {p for lid in info.lines for p in entity_points(sketch.entities[lid])}
    gone = set(info.lines)
    for lid in info.lines:
        sketch.entities.pop(lid, None)
    users = {
        p for e in sketch.entities.values() if not isinstance(e, Point) for p in entity_points(e)
    }
    gone |= corners - users
    for pid in corners - users:
        sketch.entities.pop(pid, None)
    sketch.relations = [r for r in sketch.relations if not set(r.entities) & gone]
    sketch.dimensions = [d for d in sketch.dimensions if not set(d.entities) & gone]
    made = polygon(sketch, centre, vertex, sides, inscribed, construction)
    # The new circle takes the old one's place: its id and centre point.
    new_circle = sketch.entities.pop(made.construction[0])
    assert isinstance(new_circle, Circle)
    sketch.entities.pop(new_circle.center, None)
    old_circle.radius = radius
    for r in sketch.relations:
        r.entities = [info.circle if e == new_circle.id else e for e in r.entities]
    for d in sketch.dimensions:
        if d.entities == [info.circle] and d.type in ("diameter", "radius"):
            value = 2 * radius if d.type == "diameter" else radius
            d.param = Param(f"{value:.6g}mm", value)
    return made.curves
