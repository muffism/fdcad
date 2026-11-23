"""Move, copy, rotate, scale and stretch sketch entities (TUTORIAL_REVIEW_SPEC TR1).

A :class:`Step` is one rigid move, turn or scale. ``move`` changes the picked
entities in place, ``copy`` adds copies (copy ``k`` is ``k`` steps away) and
``stretch`` moves only the points inside a box, so curves that cross the box
get longer or shorter.

Relations and dimensions are sorted by the points they use (DECISIONS D684):

- all of their points stay: kept;
- all of their points move: kept, but a turn drops Horizontal and Vertical (a
  quarter turn swaps them) and a scale scales lengths;
- some move and some stay: removed, because they would pull the moved items
  back. Stretch keeps the ones that still hold after the stretch (a line that
  only got longer stays horizontal).

With Keep relations off, every relation and dimension of the moved entities is
removed. The caller takes the undo checkpoint (CLAUDE.md rule 3). No Qt.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import (
    Circle,
    Dimension,
    Entity,
    Point,
    Relation,
    Sketch,
    entity_points,
    remap,
)
from fdcad.core.sketch.ops.geom import Vec
from fdcad.core.sketch.ops.pieces import _origin

#: Dimension types that measure a length (scaled by Scale Entities).
LENGTH_DIMENSIONS = (
    "distance",
    "horizontal_distance",
    "vertical_distance",
    "radius",
    "diameter",
    "doubled_distance",
    "arc_length",
    "path_length",  # TR45 (D1307)
)
#: Relations whose meaning depends on the sketch axes (dropped or swapped by a turn).
_AXIS_RELATIONS = {"horizontal": "vertical", "vertical": "horizontal"}
_AXIS_DIMENSIONS = {
    "horizontal_distance": "vertical_distance",
    "vertical_distance": "horizontal_distance",
}
#: Relations Stretch can check after it moved some of their points.
_CHECKABLE = ("horizontal", "vertical", "parallel", "perpendicular", "collinear", "coincident")
#: Below this a length or a cross product counts as zero.
_TOL = 1e-6


class TransformError(ValueError):
    """The change cannot be made; the message says why."""


@dataclass(frozen=True)
class Step:
    """One move (``dx``, ``dy``), turn (``angle`` about ``centre``) or scale
    (``factor`` about ``centre``)."""

    kind: str = "move"  # "move", "rotate" or "scale"
    dx: float = 0.0
    dy: float = 0.0
    centre: Vec = (0.0, 0.0)
    angle: float = 0.0
    factor: float = 1.0

    def apply(self, p: Vec, times: int = 1) -> Vec:
        """Where ``p`` goes after ``times`` steps."""
        if self.kind == "move":
            return p[0] + times * self.dx, p[1] + times * self.dy
        x, y = p[0] - self.centre[0], p[1] - self.centre[1]
        if self.kind == "rotate":
            a = times * self.angle
            c, s = math.cos(a), math.sin(a)
            return self.centre[0] + c * x - s * y, self.centre[1] + s * x + c * y
        f = self.factor**times
        return self.centre[0] + f * x, self.centre[1] + f * y

    def scale_of(self, times: int = 1) -> float:
        """How much lengths grow after ``times`` steps."""
        return self.factor**times if self.kind == "scale" else 1.0

    def turn_of(self, times: int = 1) -> float:
        """How far the step turns after ``times`` steps, in radians."""
        return times * self.angle if self.kind == "rotate" else 0.0

    def check(self) -> None:
        """Raise TransformError when the step does nothing or cannot be made."""
        if self.kind == "scale" and (self.factor <= _TOL or not math.isfinite(self.factor)):
            raise TransformError("Type a scale factor larger than zero.")


@dataclass
class TransformReport:
    """What a change did: new entities (copies), and what it removed or changed."""

    entities: list[str] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    dimensions: list[Dimension] = field(default_factory=list)
    #: Relations and dimensions a quarter turn swapped or a scale resized.
    changed: int = 0


# Picks --------------------------------------------------------------------------------


def _picked(sketch: Sketch, ids: list[str]) -> list[str]:
    """The picked entities that can move: existing ones, the origin left out."""
    out = [i for i in dict.fromkeys(ids) if i in sketch.entities and not _origin(sketch, i)]
    if not out:
        raise TransformError("Pick the sketch entities first.")
    return out


def _points_of(sketch: Sketch, ids: list[str]) -> set[str]:
    out: set[str] = set()
    for eid in ids:
        out.update(entity_points(sketch.entities[eid]))
    return {p for p in out if not _origin(sketch, p)}


def _uses(sketch: Sketch, eid: str) -> set[str]:
    """Point ids an entity of a relation or dimension uses."""
    ent = sketch.entities.get(eid)
    return set(entity_points(ent)) if ent is not None else set()


def _state(sketch: Sketch, ents: list[str], moving: set[str]) -> str:
    """``still``, ``moving``, ``mixed`` (whole items on both sides) or ``partial``
    (an item with some of its points moving)."""
    kinds = set()
    for eid in ents:
        pts = _uses(sketch, eid)
        inside = pts & moving
        if not inside:
            kinds.add("still")
        elif inside == pts:
            kinds.add("moving")
        else:
            kinds.add("partial")
    if "partial" in kinds:
        return "partial"
    if kinds == {"moving"}:
        return "moving"
    if kinds == {"still"} or not kinds:
        return "still"
    return "mixed"


# Moving coordinates ---------------------------------------------------------------------


def _set_points(sketch: Sketch, pts: set[str], step: Step, times: int = 1) -> None:
    for pid in pts:
        p = sketch.entities[pid]
        assert isinstance(p, Point)
        p.x, p.y = step.apply((p.x, p.y), times)


def _scale_circles(sketch: Sketch, ids: list[str], f: float) -> None:
    for eid in ids:
        e = sketch.entities[eid]
        if isinstance(e, Circle):
            e.radius *= f


# Relations and dimensions -------------------------------------------------------------------


def _turned_type(table: dict[str, str], kind: str, turn: float) -> str | None:
    """The type after a turn: the same, swapped, or None (dropped)."""
    if kind not in table:
        return kind
    q = turn / (math.pi / 2)
    n = round(q)
    if abs(q - n) > 1e-9:
        return None
    return kind if n % 2 == 0 else table[kind]


_PLAIN = re.compile(r"\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*([A-Za-z\"]*)\s*")


def _scaled(param: Param, f: float) -> Param:
    """``param`` times ``f``, keeping how it was typed: a number keeps its unit, and a
    formula stays a formula, times the factor. Both became plain millimetres before
    (audit D2 item 10, D743)."""
    value = param.value * f
    text = param.expr.strip()
    if text.startswith("="):
        return Param(f"=({text[1:].strip()}) * {f:.9g}", value)
    plain = _PLAIN.fullmatch(text)
    if plain is not None:
        return Param(f"{float(plain.group(1)) * f:.6g}{plain.group(2)}", value)
    return Param(f"{value:.6g}mm", value)


def _fit_relation(rel: Relation, step: Step, times: int, report: TransformReport) -> bool:
    """Fit a relation of moved items to the step. False when it must go."""
    turned = _turned_type(_AXIS_RELATIONS, rel.type, step.turn_of(times))
    if turned is None:
        return False
    if turned != rel.type:
        rel.type = turned
        report.changed += 1
    if rel.type == "offset" and rel.value is not None and step.kind == "scale":
        rel.value *= step.scale_of(times)
        report.changed += 1
    return True


def _fit_dimension(dim: Dimension, step: Step, times: int, report: TransformReport) -> bool:
    """Fit a dimension of moved items to the step. False when it must go."""
    turned = _turned_type(_AXIS_DIMENSIONS, dim.type, step.turn_of(times))
    if turned is None:
        return False
    if turned != dim.type:
        dim.type = turned
        report.changed += 1
    f = step.scale_of(times)
    if dim.type in LENGTH_DIMENSIONS and abs(f - 1.0) > 1e-12:
        dim.param = _scaled(dim.param, f)
        report.changed += 1
    if dim.label is not None and f != 1.0:
        dim.label = (dim.label[0] * f, dim.label[1] * f)
    return True


def _sort_links(
    sketch: Sketch,
    moving: set[str],
    step: Step,
    keep: bool,
    report: TransformReport,
    holds: Callable[[object], bool] | None = None,
) -> None:
    """Keep, fit or remove each relation and dimension (see the module notes)."""

    def kept(item: Relation | Dimension) -> bool:
        state = _state(sketch, item.entities, moving)
        if state == "still":
            return True
        if not keep:
            return False
        if state == "moving":
            if isinstance(item, Relation):
                return _fit_relation(item, step, 1, report)
            return _fit_dimension(item, step, 1, report)
        return state == "partial" and holds is not None and holds(item)

    kept_r: list[Relation] = []
    for rel in sketch.relations:
        (kept_r if kept(rel) else report.relations).append(rel)
    sketch.relations = kept_r
    kept_d: list[Dimension] = []
    for dim in sketch.dimensions:
        (kept_d if kept(dim) else report.dimensions).append(dim)
    sketch.dimensions = kept_d


# Commands -------------------------------------------------------------------------------


def move(
    sketch: Sketch, ids: list[str], step: Step, keep_relations: bool = True
) -> TransformReport:
    """Move, turn or scale the picked entities in place."""
    step.check()
    picked = _picked(sketch, ids)
    moving = _points_of(sketch, picked)
    report = TransformReport()
    _sort_links(sketch, moving, step, keep_relations, report)
    _set_points(sketch, moving, step)
    _scale_circles(sketch, picked, step.scale_of())
    return report


def copy(
    sketch: Sketch,
    ids: list[str],
    step: Step,
    count: int = 1,
    keep_relations: bool = True,
    linked: bool = False,
) -> TransformReport:
    """Add ``count`` copies of the picked entities; copy ``k`` is ``k`` steps away.

    The originals and their relations are left alone. With Keep relations on, the
    relations and dimensions among the picked entities are copied with them. With
    ``linked`` each copied dimension shares a value link (TR193) with its original,
    so changing either changes both (TR122 item 2, D1315).
    """
    step.check()
    if count < 1:
        raise TransformError("Type 1 or more copies.")
    picked = _picked(sketch, ids)
    inside = set(picked) | _points_of(sketch, picked)
    rels = [r for r in sketch.relations if set(r.entities) <= inside]
    dims = [d for d in sketch.dimensions if set(d.entities) <= inside]
    report = TransformReport()
    for k in range(1, count + 1):
        mapped = _copy_once(sketch, picked, step, k)
        report.entities += [mapped[i] for i in picked]
        if not keep_relations:
            continue
        for rel in rels:
            new = Relation(rel.type, [mapped[e] for e in rel.entities], rel.value, rel.off)
            if _fit_relation(new, step, k, report):
                sketch.relations.append(new)
        for dim in dims:
            nd = sketch.dimension(
                dim.type, [mapped[e] for e in dim.entities], dim.param, dim.driving
            )
            nd.measure_to = {mapped[e]: v for e, v in dim.measure_to.items() if e in mapped}
            nd.supplement, nd.label = dim.supplement, dim.label
            if not _fit_dimension(nd, step, k, report):
                sketch.dimensions.remove(nd)
            elif linked and nd.driving and not nd.off:
                if dim.link is None:
                    dim.link = _free_link(sketch, dim.id)
                nd.link = dim.link
    return report


def _free_link(sketch: Sketch, did: str) -> str:
    """A value link name no dimension uses yet, from a dimension id (TR122)."""
    used = {d.link for d in sketch.dimensions if d.link}
    base = f"copy_{did}"
    name, n = base, 2
    while name in used:
        name, n = f"{base}_{n}", n + 1
    return name


def _copy_once(sketch: Sketch, picked: list[str], step: Step, times: int) -> dict[str, str]:
    """One copy of the picked entities; returns old id to new id for entities and points."""
    mapped: dict[str, str] = {}

    def twin(pid: str) -> str:
        if pid not in mapped:
            p = sketch.point(pid)
            x, y = step.apply((p.x, p.y), times)
            mapped[pid] = sketch.add_point(x, y, p.construction)
        return mapped[pid]

    f = step.scale_of(times)
    for eid in picked:
        ent: Entity = sketch.entities[eid]
        if isinstance(ent, Point):
            twin(eid)
            continue
        nid = sketch.new_id()
        new = remap(ent, nid, twin)
        if isinstance(new, Circle):
            new.radius *= f
        sketch.entities[nid] = new
        mapped[eid] = nid
    return mapped


def points_in_box(sketch: Sketch, a: Vec, b: Vec) -> set[str]:
    """Point ids inside the box with corners ``a`` and ``b`` (the origin left out)."""
    x0, x1 = sorted((a[0], b[0]))
    y0, y1 = sorted((a[1], b[1]))
    return {
        e.id
        for e in sketch.entities.values()
        if isinstance(e, Point)
        and x0 - _TOL <= e.x <= x1 + _TOL
        and y0 - _TOL <= e.y <= y1 + _TOL
        and not _origin(sketch, e.id)
    }


def stretch(
    sketch: Sketch, a: Vec, b: Vec, dx: float, dy: float, keep_relations: bool = True
) -> TransformReport:
    """Move the points inside the box ``a``, ``b`` by (``dx``, ``dy``).

    Curves with every point inside move whole; curves that cross the box keep
    their outside points, so they get longer or shorter.
    """
    moving = points_in_box(sketch, a, b)
    if not moving:
        raise TransformError(
            "No sketch points are inside the box. Drag a box across the ends to stretch."
        )
    if math.hypot(dx, dy) < _TOL:
        raise TransformError("Type a distance to stretch by.")
    step = Step("move", dx, dy)
    before = {d.id: _measure(sketch, d) for d in sketch.dimensions if d.driving}
    _set_points(sketch, moving, step)

    def holds(item: object) -> bool:
        if isinstance(item, Relation):
            return item.type in _CHECKABLE and _relation_holds(sketch, item)
        if isinstance(item, Dimension):
            was = before.get(item.id)
            now = _measure(sketch, item)
            return (
                was is not None and now is not None and abs(now - was) <= 1e-6 * max(1.0, abs(was))
            )
        return False

    report = TransformReport()
    _sort_links(sketch, moving, step, keep_relations, report, holds)
    return report


def _measure(sketch: Sketch, dim: Dimension) -> float | None:
    from fdcad.core.sketch.solver import measure

    try:
        return measure(sketch, dim)
    except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError):
        return None


def _relation_holds(sketch: Sketch, rel: Relation) -> bool:
    """True when an axis, direction or join relation is still met by the geometry."""
    lines = [sketch.entities[e] for e in rel.entities]
    if rel.type == "coincident":
        pts = [sketch.xy(e) for e in rel.entities if isinstance(sketch.entities[e], Point)]
        return len(pts) == len(rel.entities) and all(math.dist(pts[0], p) <= _TOL for p in pts[1:])
    pts = [sketch.xy(p) for e in lines for p in entity_points(e)]
    if rel.type == "horizontal":
        return all(abs(p[1] - pts[0][1]) <= _TOL for p in pts)
    if rel.type == "vertical":
        return all(abs(p[0] - pts[0][0]) <= _TOL for p in pts)
    dirs = []
    for e in lines:
        ep = entity_points(e)
        if len(ep) != 2 or isinstance(e, Point):
            return False
        (x1, y1), (x2, y2) = sketch.xy(ep[0]), sketch.xy(ep[1])
        n = math.hypot(x2 - x1, y2 - y1)
        if n < _TOL:
            return False
        dirs.append(((x2 - x1) / n, (y2 - y1) / n))
    if rel.type == "perpendicular":
        return len(dirs) == 2 and abs(dirs[0][0] * dirs[1][0] + dirs[0][1] * dirs[1][1]) <= _TOL
    parallel = all(abs(dirs[0][0] * d[1] - dirs[0][1] * d[0]) <= _TOL for d in dirs[1:])
    if rel.type == "parallel":
        return parallel
    # Collinear: parallel, and every end on the first line.
    ox, oy = pts[0]
    ux, uy = dirs[0]
    return parallel and all(abs((p[0] - ox) * uy - (p[1] - oy) * ux) <= _TOL for p in pts)


def describe(report: TransformReport, names: dict[str, str]) -> str:
    """Status bar note naming what the change removed, or ""."""
    parts = []
    if report.relations:
        kinds = sorted({names.get(r.type, r.type) for r in report.relations})
        n = len(report.relations)
        parts.append(f"{n} relation{'s' if n != 1 else ''} ({', '.join(kinds)})")
    if report.dimensions:
        n = len(report.dimensions)
        ids = ", ".join(d.id for d in report.dimensions)
        parts.append(f"{n} dimension{'s' if n != 1 else ''} ({ids})")
    if not parts:
        return ""
    return "Removed " + " and ".join(parts) + " that no longer fit the moved entities."


__all__ = [
    "LENGTH_DIMENSIONS",
    "Step",
    "TransformError",
    "TransformReport",
    "copy",
    "describe",
    "move",
    "points_in_box",
    "stretch",
]
