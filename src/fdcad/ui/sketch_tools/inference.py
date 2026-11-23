"""Sketch inference: snaps, inference lines and the relations they add (PLAN Phase 1).

Given the cursor position in sketch millimetres and a pick tolerance, ``find_snap``
returns where the cursor should go and which relations to add for a point
placed there. Snap priority: points (endpoints, the origin), centres,
midpoints, quadrants, intersections, then a position on a curve. When nothing
is close, the cursor lines up horizontally or vertically with existing points
(inference lines, no relation). Pure Python, no Qt.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from fdcad.core.sketch.links import ModelCircle, ModelLine, SourceKey
from fdcad.core.sketch.model import Arc, Circle, Line, Point, Sketch
from fdcad.ui.sketch_tools.geometry import (
    Vec,
    arc_angles,
    dist,
    intersections,
    nearest_on_curve,
    on_arc_range,
)

if TYPE_CHECKING:
    from fdcad.ui.sketch_tools.model_snap import ModelSnapIndex

#: A line within this angle of horizontal or vertical snaps to it and gets the relation.
AXIS_SNAP = math.radians(3.0)


@dataclass
class Snap:
    """Where the cursor snaps and why.

    ``kind`` is ``point``, ``center``, ``midpoint``, ``quadrant``,
    ``intersection``, ``on_curve``, ``aligned``, ``parallel``, ``perpendicular``
    or ``free``. ``relations`` are (relation type, other entity ids) pairs for a
    new point placed here; the new point's id goes first when the relation is
    added. ``model`` is set on a snap to a part point (a vertex, the part origin or
    a round edge centre): the point gets a coincident relation to a fixed
    construction copy of it (D116 item 3). ``model_source`` names that part point
    for the copy (D250). ``model_curve`` is set on a snap to a part edge: the
    point gets ``model_relation`` (coincident or midpoint) to a fixed copy of it.
    """

    kind: str
    x: float
    y: float
    relations: list[tuple[str, list[str]]] = field(default_factory=list)
    guides: list[tuple[Vec, Vec]] = field(default_factory=list)
    target: str | None = None
    model: Vec | None = None
    model_source: SourceKey | None = None
    model_curve: ModelLine | ModelCircle | None = None
    model_relation: str = "coincident"

    @property
    def xy(self) -> Vec:
        """The snapped position."""
        return self.x, self.y


def _points(sketch: Sketch, exclude: set[str]) -> Iterable[Point]:
    for e in sketch.entities.values():
        if isinstance(e, Point) and e.id not in exclude:
            yield e


def _centers(sketch: Sketch) -> set[str]:
    return {e.center for e in sketch.entities.values() if isinstance(e, Circle | Arc)}


def find_snap(
    sketch: Sketch,
    cursor: Vec,
    tol: float,
    exclude: Iterable[str] = (),
    extra: Iterable[Vec] = (),
    model: ModelSnapIndex | None = None,
) -> Snap:
    """Snap ``cursor`` to the sketch. ``exclude`` lists entities being drawn or dragged.

    ``extra`` are more points to line up with (T1.2.5), such as revealed centres
    of the part's round edges. ``model`` adds the projected part geometry (T1.2.2):
    vertices and the origin rank with end points, edge midpoints with midpoints
    and edges with on curve, so the T1.2.3 order holds across sketch and part.
    Sketch items win a tie.
    """
    skip = set(exclude)
    # Ellipses and splines snap by their points only (D278).
    curves = [
        e
        for e in sketch.entities.values()
        if isinstance(e, Line | Circle | Arc) and e.id not in skip
    ]
    # Points that belong to excluded curves are excluded too.
    for e in sketch.entities.values():
        if e.id in skip and isinstance(e, Line):
            skip |= {e.p1, e.p2}
        elif e.id in skip and isinstance(e, Arc):
            skip |= {e.center, e.start, e.end}
        elif e.id in skip and isinstance(e, Circle):
            skip.add(e.center)
    centers = _centers(sketch)

    best: tuple[float, Snap] | None = None

    def offer(d: float, snap: Snap, rank: int) -> None:
        nonlocal best
        score = d + rank * tol * 0.25  # within the tolerance, earlier kinds win
        if d <= tol and (best is None or score < best[0]):
            best = (score, snap)

    for p in _points(sketch, skip):
        kind = "center" if p.id in centers else "point"
        offer(
            dist((p.x, p.y), cursor),
            Snap(kind, p.x, p.y, [("coincident", [p.id])], target=p.id),
            0 if kind == "point" else 1,
        )
    for c in curves:
        if isinstance(c, Line):
            (x1, y1), (x2, y2) = sketch.xy(c.p1), sketch.xy(c.p2)
            mid = ((x1 + x2) / 2, (y1 + y2) / 2)
            offer(dist(mid, cursor), Snap("midpoint", *mid, [("midpoint", [c.id])], target=c.id), 2)
        else:
            if isinstance(c, Arc):
                a0, a1 = arc_angles(sketch, c)
                cx, cy = sketch.xy(c.center)
                r = sketch.radius(c.id)
                half = (a0 + a1) / 2
                mid = (cx + r * math.cos(half), cy + r * math.sin(half))
                snap = Snap("midpoint", *mid, [("midpoint", [c.id])], target=c.id)
                offer(dist(mid, cursor), snap, 2)
            cx, cy = sketch.xy(c.center)
            r = sketch.radius(c.id)
            for k in range(4):
                angle = k * math.pi / 2
                if isinstance(c, Arc) and not on_arc_range(sketch, c, angle):
                    continue
                q = (cx + r * math.cos(angle), cy + r * math.sin(angle))
                offer(
                    dist(q, cursor), Snap("quadrant", *q, [("coincident", [c.id])], target=c.id), 3
                )
    if best is None:
        near = [c for c in curves if dist(nearest_on_curve(sketch, c, cursor), cursor) <= tol * 2]
        for i, a in enumerate(near):
            for b in near[i + 1 :]:
                for ip in intersections(sketch, a, b):
                    rels: list[tuple[str, list[str]]] = [
                        ("coincident", [a.id]),
                        ("coincident", [b.id]),
                    ]
                    offer(dist(ip, cursor), Snap("intersection", *ip, rels), 4)
    hits = model.query(cursor, tol) if model is not None else []
    # Sketch items win a tie: distances worked out in two ways can differ in the last
    # digits, so part items carry a tiny extra distance.
    tie = tol * 1e-6
    for hit in hits:
        if hit.kind == "point" and hit.point is not None:
            snap = Snap("point", *hit.xy, model=hit.xy, model_source=hit.point.source)
            offer(hit.distance + tie, snap, 0)
        elif hit.kind == "midpoint":
            snap = Snap("midpoint", *hit.xy, model_curve=hit.curve, model_relation="midpoint")
            offer(hit.distance + tie, snap, 2)
    if best is None:
        for c in curves:
            q = nearest_on_curve(sketch, c, cursor)
            offer(dist(q, cursor), Snap("on_curve", *q, [("coincident", [c.id])], target=c.id), 5)
        for hit in hits:
            if hit.kind == "on_curve":
                offer(hit.distance + tie, Snap("on_curve", *hit.xy, model_curve=hit.curve), 5)
    if best is not None:
        return best[1]
    return _aligned(sketch, cursor, tol, skip, list(extra))


def _aligned(
    sketch: Sketch, cursor: Vec, tol: float, skip: set[str], extra: list[Vec] | None = None
) -> Snap:
    x, y = cursor
    guides: list[tuple[Vec, Vec]] = []
    best_x: tuple[float, Vec] | None = None
    best_y: tuple[float, Vec] | None = None
    known = [(p.x, p.y) for p in _points(sketch, skip)] + list(extra or [])
    for p in known:
        dx, dy = abs(p[0] - x), abs(p[1] - y)
        if dx <= tol and (best_x is None or dx < best_x[0]):
            best_x = (dx, p)
        if dy <= tol and (best_y is None or dy < best_y[0]):
            best_y = (dy, p)
    if best_x is not None:
        x = best_x[1][0]
    if best_y is not None:
        y = best_y[1][1]
    if best_x is not None:
        guides.append((best_x[1], (x, y)))
    if best_y is not None:
        guides.append((best_y[1], (x, y)))
    return Snap("aligned" if guides else "free", x, y, guides=guides)


def line_direction(start: Vec, end: Snap) -> tuple[Snap, str | None]:
    """Snap a line's end to horizontal or vertical when it is close.

    Returns the end snap (moved onto the axis when it was free) and
    ``"horizontal"``, ``"vertical"`` or None for the relation to add.
    """
    dx, dy = end.x - start[0], end.y - start[1]
    if math.hypot(dx, dy) < 1e-9:
        return end, None
    angle = abs(math.atan2(dy, dx))
    horizontal = min(angle, math.pi - angle) <= AXIS_SNAP
    vertical = abs(angle - math.pi / 2) <= AXIS_SNAP
    if not (horizontal or vertical):
        return end, None
    if end.kind in ("free", "aligned"):
        x, y = (end.x, start[1]) if horizontal else (start[0], end.y)
        end = Snap(end.kind, x, y, end.relations, end.guides, end.target)
        return end, "horizontal" if horizontal else "vertical"  # free: no model link
    # A snapped end keeps its position; add the relation only if it already fits.
    if horizontal and abs(dy) < 1e-6:
        return end, "horizontal"
    if vertical and abs(dx) < 1e-6:
        return end, "vertical"
    return end, None


def _direction(sketch: Sketch, line: Line) -> float | None:
    (x1, y1), (x2, y2) = sketch.xy(line.p1), sketch.xy(line.p2)
    if math.hypot(x2 - x1, y2 - y1) < 1e-9:
        return None
    return math.atan2(y2 - y1, x2 - x1)


def line_relation(
    sketch: Sketch, start: Vec, end: Snap, exclude: Iterable[str] = ()
) -> tuple[Snap, tuple[str, list[str]] | None]:
    """Direction snaps for a new line from ``start`` (T1.2.6, T1.3.1).

    Horizontal and vertical come first (``line_direction``). Otherwise, a line
    within ``AXIS_SNAP`` of parallel or perpendicular to an existing line snaps
    to it. A free end turns onto the direction; a snapped end keeps its place
    and gets the relation only when it already fits. Returns the end snap and
    the relation to add to the new line: (type, other line ids) or None.
    """
    snapped, axis = line_direction(start, end)
    if axis is not None:
        return snapped, (axis, [])
    dx, dy = end.x - start[0], end.y - start[1]
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return end, None
    angle = math.atan2(dy, dx)
    skip = set(exclude)
    best: tuple[float, str, Line, float] | None = None
    for e in sketch.entities.values():
        if not isinstance(e, Line) or e.id in skip:
            continue
        ref = _direction(sketch, e)
        if ref is None:
            continue
        for rtype, offset in (("parallel", 0.0), ("perpendicular", math.pi / 2)):
            target = ref + offset
            off = abs(math.remainder(angle - target, math.pi))
            if off <= AXIS_SNAP and (best is None or off < best[0]):
                best = (off, rtype, e, target)
    if best is None:
        return end, None
    off, rtype, line, target = best
    if end.kind not in ("free", "aligned"):
        return end, ((rtype, [line.id]) if off < 1e-6 else None)
    # Turn the end onto the direction (either way along it), keeping its projection.
    ux, uy = math.cos(target), math.sin(target)
    t = dx * ux + dy * uy
    x, y = start[0] + t * ux, start[1] + t * uy
    guides = [(start, (x, y))]
    return Snap(rtype, x, y, list(end.relations), guides, end.target), (rtype, [line.id])
