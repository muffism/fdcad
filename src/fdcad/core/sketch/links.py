"""Part geometry seen from a sketch, and the fixed copies made from it (WP14, D250).

Part edges, vertices, round edge centres and the part origin, projected onto the
sketch plane, are snap targets. Snapping ties sketch geometry to a fixed
construction copy that remembers its source (``source`` on the entity, FDEF_SPEC 6
item 8). When the part changes, :func:`check_links` finds copies that no longer
match their source; :func:`apply_links` moves them, only when the user confirms
(CLAUDE.md rule 12). Pure Python: the kernel work is in ``projection``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from fdcad.core.sketch.model import Circle, Entity, Line, Point, Sketch

Vec = tuple[float, float]
#: ``(kind, name)``: ``("vertex", "vertex(...)")``, ``("edge", "edge(...)")`` or
#: ``("origin", "")``.
SourceKey = tuple[str, str]
#: Copies further than this from their source are out of date, in millimetres.
LINK_TOL = 1e-6


@dataclass(frozen=True)
class ModelPoint:
    """A projected part vertex, round edge centre or the part origin."""

    xy: Vec
    source: SourceKey | None
    #: Height of the 3D point above the sketch plane, to prefer the nearest of overlaps.
    depth: float = 0.0


@dataclass(frozen=True)
class ModelLine:
    """A straight part edge, projected."""

    a: Vec
    b: Vec
    source: SourceKey | None
    depth: float = 0.0


@dataclass(frozen=True)
class ModelCircle:
    """A round part edge whose axis is along the sketch normal, projected.

    ``arc`` is the counter clockwise start and end angle for a partial edge,
    None for a full circle.
    """

    centre: Vec
    radius: float
    source: SourceKey | None
    depth: float = 0.0
    arc: tuple[float, float] | None = None


ModelTarget = ModelPoint | ModelLine | ModelCircle


@dataclass
class ModelGeometry:
    """Everything of the part a sketch can snap to, in sketch millimetres."""

    points: list[ModelPoint] = field(default_factory=list)
    lines: list[ModelLine] = field(default_factory=list)
    circles: list[ModelCircle] = field(default_factory=list)
    #: Every projected edge as a polyline, for drawing.
    polylines: list[list[Vec]] = field(default_factory=list)
    #: The part origin, projected.
    origin: Vec = (0.0, 0.0)

    @property
    def empty(self) -> bool:
        """True when there is nothing to snap to but the origin."""
        return not (self.lines or self.circles or len(self.points) > 1)


def source_data(key: SourceKey | None) -> dict[str, Any] | None:
    """The ``source`` stored on a copy (FDEF_SPEC 6 item 9)."""
    if key is None:
        return None
    kind, name = key
    return {"kind": kind} if kind == "origin" else {"kind": kind, "name": name}


def source_key(entity: Entity) -> SourceKey | None:
    """The source of a copy, or None for ordinary sketch geometry."""
    raw = getattr(entity, "source", None)
    if not isinstance(raw, dict):
        return None
    return str(raw.get("kind", "")), str(raw.get("name", ""))


def link_keys(sketch: Sketch) -> set[SourceKey]:
    """Every source the sketch's copies were made from."""
    keys = set()
    for e in sketch.entities.values():
        key = source_key(e)
        if key is not None:
            keys.add(key)
    return keys


@dataclass(frozen=True)
class LinkUpdate:
    """A copy that no longer matches its source.

    ``geometry`` is where the copy should go: ``(x, y)`` for a point, ``(x1, y1,
    x2, y2)`` for a line, ``(cx, cy, r)`` for a circle. None when the source is
    gone (``lost``).
    """

    entity: str
    geometry: tuple[float, ...] | None

    @property
    def lost(self) -> bool:
        """True when the source no longer exists."""
        return self.geometry is None


def _wanted(entity: Entity, target: ModelTarget | None) -> tuple[float, ...] | None:
    """Where ``entity`` should be for ``target``, or None when it does not fit."""
    if isinstance(entity, Point):
        if isinstance(target, ModelPoint):
            return target.xy
        if isinstance(target, ModelCircle):
            return target.centre
        return None
    if isinstance(entity, Line) and isinstance(target, ModelLine):
        return (*target.a, *target.b)
    if isinstance(entity, Circle) and isinstance(target, ModelCircle):
        return (*target.centre, target.radius)
    return None


def _current(sketch: Sketch, entity: Entity) -> tuple[float, ...]:
    if isinstance(entity, Point):
        return entity.x, entity.y
    if isinstance(entity, Line):
        return (*sketch.xy(entity.p1), *sketch.xy(entity.p2))
    assert isinstance(entity, Circle)
    return (*sketch.xy(entity.center), entity.radius)


def _line_matches(have: tuple[float, ...], want: tuple[float, ...]) -> bool:
    straight = math.dist(have, want)
    swapped = math.dist(have, (*want[2:], *want[:2]))
    return min(straight, swapped) <= LINK_TOL


def check_links(sketch: Sketch, found: dict[SourceKey, ModelTarget | None]) -> list[LinkUpdate]:
    """Copies whose source moved or is gone, in entity order.

    ``found`` maps each source to its current projected geometry, or None when the
    source no longer resolves. Origin copies are checked like vertices.
    """
    out: list[LinkUpdate] = []
    for e in sketch.entities.values():
        key = source_key(e)
        if key is None or not isinstance(e, Point | Line | Circle):
            continue
        want = _wanted(e, found.get(key))
        if want is None:
            out.append(LinkUpdate(e.id, None))
            continue
        have = _current(sketch, e)
        same = (
            _line_matches(have, want) if isinstance(e, Line) else math.dist(have, want) <= LINK_TOL
        )
        if not same:
            out.append(LinkUpdate(e.id, tuple(float(v) for v in want)))
    return out


def apply_links(sketch: Sketch, updates: list[LinkUpdate]) -> int:
    """Move out of date copies onto their sources. Lost ones stay. Returns how many moved.

    A line keeps the end that is nearer each new end, so it never flips.
    """
    moved = 0
    for u in updates:
        e = sketch.entities.get(u.entity)
        if e is None or u.geometry is None:
            continue
        g = u.geometry
        if isinstance(e, Point) and len(g) == 2:
            e.x, e.y = g
        elif isinstance(e, Line) and len(g) == 4:
            p1, p2 = sketch.point(e.p1), sketch.point(e.p2)
            a, b = (g[0], g[1]), (g[2], g[3])
            straight = math.dist((p1.x, p1.y), a) + math.dist((p2.x, p2.y), b)
            crossed = math.dist((p1.x, p1.y), b) + math.dist((p2.x, p2.y), a)
            if crossed < straight:
                a, b = b, a
            (p1.x, p1.y), (p2.x, p2.y) = a, b
        elif isinstance(e, Circle) and len(g) == 3:
            c = sketch.point(e.center)
            c.x, c.y, e.radius = g[0], g[1], g[2]
        else:
            continue
        moved += 1
    return moved


def updates_to_data(updates: list[LinkUpdate]) -> list[dict[str, Any]]:
    """Updates as plain data for a fix button (FeatureResult issues hold no objects)."""
    return [
        {"entity": u.entity, "geometry": None if u.geometry is None else list(u.geometry)}
        for u in updates
    ]


def updates_from_data(raw: Any) -> list[LinkUpdate]:
    """Read :func:`updates_to_data` back. Damaged items are skipped."""
    out: list[LinkUpdate] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("entity"), str):
            continue
        g = item.get("geometry")
        geometry = tuple(float(v) for v in g) if isinstance(g, list) else None
        out.append(LinkUpdate(item["entity"], geometry))
    return out


def link_messages(name: str, updates: list[LinkUpdate]) -> tuple[str | None, str | None]:
    """Warning texts for moved and for lost copies (CLAUDE.md section 8 item 4)."""
    moved = sum(1 for u in updates if not u.lost)
    lost = len(updates) - moved
    moved_text = lost_text = None
    if moved == 1:
        moved_text = (
            f"{name}: 1 copy of part geometry no longer matches the part. Click Update Copies "
            "to move it onto the part, or open the sketch to check it first."
        )
    elif moved:
        moved_text = (
            f"{name}: {moved} copies of part geometry no longer match the part. Click Update "
            "Copies to move them onto the part, or open the sketch to check them first."
        )
    if lost == 1:
        lost_text = (
            f"{name}: 1 copy of part geometry lost the part edge or corner it was made from. "
            "It stays where it is. Open the sketch to delete or keep it."
        )
    elif lost:
        lost_text = (
            f"{name}: {lost} copies of part geometry lost the part edges or corners they were "
            "made from. They stay where they are. Open the sketch to delete or keep them."
        )
    return moved_text, lost_text


def linked_in(sketch: Sketch, ids: list[str]) -> list[str]:
    """The picked entities that follow the model: a copy with a source, or a curve held
    fixed where it was converted or projected (TR340)."""
    from fdcad.core.sketch.model import Point, entity_points

    fixed = {e for r in sketch.relations if r.type == "fixed" for e in r.entities}
    out = []
    for eid in ids:
        e = sketch.entities.get(eid)
        if e is None:
            continue
        points = [p for p in entity_points(e) if p in sketch.entities]
        sourced = source_key(e) is not None or any(
            isinstance(sketch.entities[p], Point) and source_key(sketch.entities[p]) is not None
            for p in points
        )
        if sourced or (eid in fixed and not isinstance(e, Point)):
            out.append(eid)
    return out


def detach(sketch: Sketch, ids: list[str]) -> list[str]:
    """Make the picked model copies free sketch geometry of the same shape (TR340, D885):
    their source is forgotten and their Fixed relations are removed, so the sketch no
    longer depends on the model. Dimensions on them stay. Returns the detached ids."""
    from fdcad.core.sketch.model import entity_points

    found = linked_in(sketch, ids)
    touched: set[str] = set()
    for eid in found:
        e = sketch.entities[eid]
        touched.add(eid)
        touched.update(entity_points(e))
    for pid in touched:
        ent = sketch.entities.get(pid)
        if ent is not None and getattr(ent, "source", None) is not None:
            ent.source = None  # type: ignore[union-attr]
    sketch.relations = [
        r for r in sketch.relations if not (r.type == "fixed" and set(r.entities) & touched)
    ]
    return found
