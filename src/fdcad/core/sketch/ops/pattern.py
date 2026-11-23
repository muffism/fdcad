"""Linear and circular sketch patterns (PHASE2_SPEC P2.8 items 8 and 9).

Each instance is a copy of the picked curves. A construction frame ties the
instances together: an anchor point per grid place (skipped places keep their
anchor without geometry), joined by construction lines whose relations keep
the spacing even. Each copied curve gets Equal with its original, so sizes
follow (DECISIONS D276).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import (
    Arc,
    Circle,
    Ellipse,
    EllipseArc,
    Line,
    Point,
    Sketch,
    entity_points,
    remap,
)
from fdcad.core.sketch.ops.geom import Vec

Transform = Callable[[Vec], Vec]


class PatternError(ValueError):
    """The pattern cannot be made; the message says why."""


@dataclass
class PatternResult:
    """What a pattern made."""

    copies: list[str] = field(default_factory=list)
    frame: list[str] = field(default_factory=list)
    dimensions: list[str] = field(default_factory=list)


def _seed(sketch: Sketch, ids: list[str]) -> list[str]:
    seed = [i for i in dict.fromkeys(ids) if i in sketch.entities]
    if not seed:
        raise PatternError("Pick the curves to pattern.")
    return seed


def anchor_of(sketch: Sketch, seed: list[str]) -> str:
    """The seed point the frame ties to: the first point of the first picked item."""
    ent = sketch.entities[seed[0]]
    if isinstance(ent, Point):
        return ent.id
    if isinstance(ent, Circle | Arc | Ellipse | EllipseArc):
        return ent.start if isinstance(ent, Arc) else ent.center
    return entity_points(ent)[0]


def copy_items(
    sketch: Sketch, seed: list[str], move: Transform, ccw_flip: bool = False
) -> tuple[list[str], dict[str, str]]:
    """Copy the seed curves and points through ``move``. Returns the new ids and the
    point map. Coincident joins among the seed's points are copied, and each copied
    curve gets Equal with its original."""
    mapped: dict[str, str] = {}

    def twin(pid: str) -> str:
        if pid not in mapped:
            p = sketch.point(pid)
            x, y = move((p.x, p.y))
            mapped[pid] = sketch.add_point(x, y, p.construction)
        return mapped[pid]

    made: list[str] = []
    for eid in seed:
        ent = sketch.entities[eid]
        if isinstance(ent, Point):
            made.append(twin(eid))
            continue
        nid = sketch.new_id()
        copy = remap(ent, nid, twin)
        if isinstance(copy, Arc) and ccw_flip:
            copy.ccw = not copy.ccw
        sketch.entities[nid] = copy
        made.append(nid)
        if isinstance(ent, Line | Circle | Arc):
            sketch.relate("equal", eid, nid)
    seed_points = set(mapped)
    for rel in list(sketch.relations):
        if rel.type == "coincident" and set(rel.entities) <= seed_points:
            sketch.relate("coincident", *(mapped[e] for e in rel.entities))
    return made, mapped


def linear(
    sketch: Sketch,
    ids: list[str],
    count1: int,
    spacing1: float,
    angle1: float,
    count2: int = 1,
    spacing2: float = 0.0,
    angle2: float = math.pi / 2,
    skip: set[tuple[int, int]] | None = None,
    add_dimensions: bool = False,
    fix_direction: bool = False,
    direction_line: str | None = None,
) -> PatternResult:
    """A grid of ``count1`` by ``count2`` instances; place (0, 0) is the original."""
    seed = _seed(sketch, ids)
    if count1 < 1 or count2 < 1 or count1 * count2 < 2:
        raise PatternError("A pattern needs two or more instances. Enter 2 or more instances.")
    if (count1 > 1 and spacing1 <= 1e-9) or (count2 > 1 and spacing2 <= 1e-9):
        raise PatternError("Type a spacing larger than zero.")
    skip = skip or set()
    d1 = (math.cos(angle1), math.sin(angle1))
    d2 = (math.cos(angle2), math.sin(angle2))
    if count2 > 1 and abs(d1[0] * d2[1] - d1[1] * d2[0]) < 1e-6:
        raise PatternError("The two directions are parallel. Change the angle of Direction 2.")
    anchor = anchor_of(sketch, seed)
    ax, ay = sketch.xy(anchor)
    result = PatternResult()
    nodes: dict[tuple[int, int], str] = {(0, 0): anchor}
    for j in range(count2):
        for i in range(count1):
            if (i, j) == (0, 0):
                continue
            dx = i * spacing1 * d1[0] + j * spacing2 * d2[0]
            dy = i * spacing1 * d1[1] + j * spacing2 * d2[1]
            if (i, j) in skip:
                nodes[(i, j)] = sketch.add_point(ax + dx, ay + dy, construction=True)
                result.frame.append(nodes[(i, j)])
                continue
            made, mapped = copy_items(sketch, seed, _shift(dx, dy))
            result.copies += made
            nodes[(i, j)] = mapped[anchor]
    rows: list[str] = []
    cols: list[str] = []
    for j in range(count2):
        for i in range(1, count1):
            rows.append(_frame_line(sketch, nodes[(i - 1, j)], nodes[(i, j)], result))
    for j in range(1, count2):
        cols.append(_frame_line(sketch, nodes[(0, j - 1)], nodes[(0, j)], result))
    _even(sketch, rows, count1 - 1)
    if len(cols) > 1:
        sketch.relate("parallel", *cols)
        sketch.relate("equal", *cols)
    if add_dimensions:
        if rows:
            dim = sketch.dimension("distance", [rows[0]], Param(f"{spacing1:.6g}mm", spacing1))
            result.dimensions.append(dim.id)
        if cols:
            dim = sketch.dimension("distance", [cols[0]], Param(f"{spacing2:.6g}mm", spacing2))
            result.dimensions.append(dim.id)
    if fix_direction and rows:
        _fix(sketch, rows[0], angle1, direction_line)
    if fix_direction and cols:
        _fix(sketch, cols[0], angle2, None)
    return result


def _shift(dx: float, dy: float) -> Transform:
    def move(p: Vec) -> Vec:
        return p[0] + dx, p[1] + dy

    return move


def _even(sketch: Sketch, rows: list[str], per_row: int) -> None:
    """Frame lines of all rows: equal and parallel. Lines of a row share their end
    points, so parallel already makes them collinear (Collinear would repeat it)."""
    if len(rows) > 1:
        sketch.relate("equal", *rows)
        sketch.relate("parallel", *rows)


def _fix(sketch: Sketch, lid: str, angle: float, direction_line: str | None) -> None:
    if direction_line is not None and direction_line in sketch.entities:
        sketch.relate("parallel", lid, direction_line)
        return
    a = math.remainder(angle, math.pi)
    if abs(a) < 1e-9:
        sketch.relate("horizontal", lid)
    elif abs(abs(a) - math.pi / 2) < 1e-9:
        sketch.relate("vertical", lid)


def _frame_line(sketch: Sketch, a: str, b: str, result: PatternResult) -> str:
    (x1, y1), (x2, y2) = sketch.xy(a), sketch.xy(b)
    lid = sketch.add_line(x1, y1, x2, y2, construction=True)
    line = sketch.entities[lid]
    assert isinstance(line, Line)
    sketch.relate("coincident", line.p1, a)
    sketch.relate("coincident", line.p2, b)
    result.frame.append(lid)
    return lid


def circular(
    sketch: Sketch,
    ids: list[str],
    centre: Vec,
    count: int,
    total: float = 2 * math.pi,
    equal_spacing: bool = True,
    reverse: bool = False,
    skip: set[int] | None = None,
    add_dimensions: bool = False,
    centre_point: str | None = None,
) -> PatternResult:
    """``count`` instances turned about ``centre``; instance 0 is the original.

    With equal spacing the instances share ``total``; a full turn leaves no
    instance on top of the original. Otherwise ``total`` is the step angle.
    ``centre_point`` names an existing point to tie the centre to.
    """
    seed = _seed(sketch, ids)
    if count < 2:
        raise PatternError("A pattern needs two or more instances. Enter 2 or more instances.")
    skip = skip or set()
    full = abs(abs(total) - 2 * math.pi) < 1e-9
    step = total / (count if full else count - 1) if equal_spacing else total
    if reverse:
        step = -step
    if abs(step) < 1e-9:
        raise PatternError("Type an angle larger than zero.")
    anchor = anchor_of(sketch, seed)
    if math.dist(sketch.xy(anchor), centre) < 1e-6:
        raise PatternError("The pattern centre is on the first point of the picks. Move it.")
    result = PatternResult()
    if centre_point is None:
        cid = sketch.add_point(centre[0], centre[1], construction=True)
        result.frame.append(cid)
    else:
        cid = centre_point
    nodes: list[str] = [anchor]
    for k in range(1, count):
        ang = k * step
        c, s = math.cos(ang), math.sin(ang)

        def turn(p: Vec, c: float = c, s: float = s) -> Vec:
            x, y = p[0] - centre[0], p[1] - centre[1]
            return centre[0] + c * x - s * y, centre[1] + s * x + c * y

        if k in skip:
            x, y = turn(sketch.xy(anchor))
            nodes.append(sketch.add_point(x, y, construction=True))
            result.frame.append(nodes[-1])
            continue
        made, mapped = copy_items(sketch, seed, turn)
        result.copies += made
        nodes.append(mapped[anchor])
    radials = [_frame_line(sketch, cid, n, result) for n in nodes]
    sketch.relate("equal", *radials)
    if add_dimensions:
        r = math.dist(sketch.xy(anchor), centre)
        dim = sketch.dimension("distance", [radials[0]], Param(f"{r:.6g}mm", r))
        result.dimensions.append(dim.id)
        a = abs(math.remainder(step, 2 * math.pi))
        if 1e-6 < a < math.pi - 1e-6:  # opposite radials are parallel: no angle
            for k in range(1, len(radials)):
                adim = sketch.dimension(
                    "angle", [radials[k - 1], radials[k]], Param(f"{math.degrees(a):.6g}deg", a)
                )
                adim.supplement = False
                result.dimensions.append(adim.id)
    return result


def instance_places_linear(
    anchor: Vec,
    count1: int,
    spacing1: float,
    angle1: float,
    count2: int,
    spacing2: float,
    angle2: float,
) -> dict[tuple[int, int], Vec]:
    """Where each instance's anchor goes (for the preview and for clicking skips)."""
    d1 = (math.cos(angle1), math.sin(angle1))
    d2 = (math.cos(angle2), math.sin(angle2))
    return {
        (i, j): (
            anchor[0] + i * spacing1 * d1[0] + j * spacing2 * d2[0],
            anchor[1] + i * spacing1 * d1[1] + j * spacing2 * d2[1],
        )
        for j in range(max(count2, 1))
        for i in range(max(count1, 1))
    }
