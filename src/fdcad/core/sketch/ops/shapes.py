"""Slots and polygons (PHASE2_SPEC P2.8 items 11 and 12).

Both are stored as ordinary lines and arcs with the relations that keep their
shape (DECISIONS D277). The builders return the ids of what they made.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Arc, Circle, Line, Sketch
from fdcad.core.sketch.ops.geom import Vec, dist

SLOT_KINDS = ("straight", "centre_straight", "arc3", "centre_arc")
LENGTH_MODES = ("centre", "overall")


class ShapeError(ValueError):
    """The shape cannot be made from these points."""


@dataclass
class ShapeResult:
    """What a slot or polygon builder made."""

    curves: list[str] = field(default_factory=list)
    construction: list[str] = field(default_factory=list)
    centre: str | None = None
    dimensions: list[str] = field(default_factory=list)


def _arc(sketch: Sketch, centre: str, start: str, end: str, construction: bool) -> str:
    """A counter clockwise arc on existing points."""
    aid = sketch.new_id()
    sketch.entities[aid] = Arc(aid, centre, start, end, True, construction)
    return aid


def _line(sketch: Sketch, p1: str, p2: str, construction: bool) -> str:
    lid = sketch.new_id()
    sketch.entities[lid] = Line(lid, p1, p2, construction)
    return lid


def _pt(sketch: Sketch, p: Vec, construction: bool = False) -> str:
    return sketch.add_point(p[0], p[1], construction)


def straight_slot(
    sketch: Sketch,
    c1: Vec,
    c2: Vec,
    width: float,
    construction: bool = False,
    centre: Vec | None = None,
    add_dimensions: bool = False,
    length_mode: str = "centre",
) -> ShapeResult:
    """A straight slot between end centres ``c1`` and ``c2``.

    With ``centre`` (the centre straight slot) a construction point at the middle
    gets a Midpoint relation on the construction centerline.
    """
    length = dist(c1, c2)
    r = width / 2
    if length < 1e-9 or r < 1e-9:
        raise ShapeError(
            "A slot needs two different end centres and a width. "
            "Click two different end centres, then set the width."
        )
    ux, uy = (c2[0] - c1[0]) / length, (c2[1] - c1[1]) / length
    nx, ny = -uy, ux
    out = ShapeResult()
    e1, e2 = _pt(sketch, c1, True), _pt(sketch, c2, True)
    axis = _line(sketch, e1, e2, True)
    out.construction.append(axis)
    a = _pt(sketch, (c1[0] + r * nx, c1[1] + r * ny), construction)
    b = _pt(sketch, (c2[0] + r * nx, c2[1] + r * ny), construction)
    c = _pt(sketch, (c2[0] - r * nx, c2[1] - r * ny), construction)
    d = _pt(sketch, (c1[0] - r * nx, c1[1] - r * ny), construction)
    top = _line(sketch, a, b, construction)
    cap2 = _arc(sketch, e2, c, b, construction)
    bottom = _line(sketch, c, d, construction)
    cap1 = _arc(sketch, e1, a, d, construction)
    out.curves = [top, cap2, bottom, cap1]
    for line in (top, bottom):
        for cap in (cap1, cap2):
            sketch.relate("tangent", line, cap)
    sketch.relate("equal", cap1, cap2)
    if centre is not None:
        mid = _pt(sketch, centre, True)
        sketch.relate("midpoint", mid, axis)
        out.centre = mid
    if add_dimensions:
        dim = sketch.dimension("distance", [top, bottom], Param(f"{width:.6g}mm", width))
        out.dimensions.append(dim.id)
        out.dimensions.append(_length_dim(sketch, axis, cap1, cap2, length, width, length_mode))
    return out


def _length_dim(
    sketch: Sketch, axis: str, cap1: str, cap2: str, length: float, width: float, mode: str
) -> str:
    if mode == "overall":
        total = length + width
        dim = sketch.dimension("distance", [cap1, cap2], Param(f"{total:.6g}mm", total))
        dim.measure_to = {cap1: "farthest", cap2: "farthest"}
        return dim.id
    dim = sketch.dimension("distance", [axis], Param(f"{length:.6g}mm", length))
    return dim.id


def arc_slot(
    sketch: Sketch,
    centre: Vec,
    start: Vec,
    end: Vec,
    ccw: bool,
    width: float,
    construction: bool = False,
    add_dimensions: bool = False,
) -> ShapeResult:
    """An arc slot along the arc around ``centre`` from ``start`` to ``end``."""
    radius = dist(centre, start)
    r = width / 2
    if radius < 1e-9 or r < 1e-9 or dist(start, end) < 1e-9:
        raise ShapeError(
            "An arc slot needs a centre, two different ends and a width. "
            "Click a centre and two different ends, then set the width."
        )
    if r >= radius:
        raise ShapeError("The slot is wider than its arc allows. Use a smaller width.")
    a0 = math.atan2(start[1] - centre[1], start[0] - centre[0])
    a1 = math.atan2(end[1] - centre[1], end[0] - centre[0])
    if not ccw:
        a0, a1 = a1, a0
    out = ShapeResult()

    def on(rad: float, ang: float) -> Vec:
        return centre[0] + rad * math.cos(ang), centre[1] + rad * math.sin(ang)

    pc = _pt(sketch, centre, True)
    s, e = _pt(sketch, on(radius, a0), True), _pt(sketch, on(radius, a1), True)
    axis = _arc(sketch, pc, s, e, True)
    out.construction.append(axis)
    out.centre = pc
    o0, o1 = (
        _pt(sketch, on(radius + r, a0), construction),
        _pt(sketch, on(radius + r, a1), construction),
    )
    i0, i1 = (
        _pt(sketch, on(radius - r, a0), construction),
        _pt(sketch, on(radius - r, a1), construction),
    )
    outer = _arc(sketch, pc, o0, o1, construction)
    inner = _arc(sketch, pc, i0, i1, construction)
    # End caps turn outward from the slot: at the end from the outer to the inner
    # arc, at the start from the inner to the outer one.
    cap_end = _arc(sketch, e, o1, i1, construction)
    cap_start = _arc(sketch, s, i0, o0, construction)
    out.curves = [outer, cap_end, inner, cap_start]
    for cap in (cap_start, cap_end):
        sketch.relate("tangent", cap, outer)
        sketch.relate("tangent", cap, inner)
    sketch.relate("equal", cap_start, cap_end)
    if add_dimensions:
        dim = sketch.dimension("radius", [cap_start], Param(f"{r:.6g}mm", r))
        out.dimensions.append(dim.id)
        dim = sketch.dimension("radius", [axis], Param(f"{radius:.6g}mm", radius))
        out.dimensions.append(dim.id)
    return out


def polygon(
    sketch: Sketch,
    centre: Vec,
    vertex: Vec,
    sides: int,
    inscribed: bool = True,
    construction: bool = False,
) -> ShapeResult:
    """A regular polygon around ``centre``.

    Inscribed: ``vertex`` is a corner and the corners lie on the construction circle.
    Circumscribed: ``vertex`` is the middle of a side and the sides touch the circle.
    The sides get Equal.
    """
    if not 3 <= sides <= 40:
        raise ShapeError("A polygon has 3 to 40 sides. Enter a number of sides in that range.")
    radius = dist(centre, vertex)
    if radius < 1e-9:
        raise ShapeError("Move the second click away from the centre.")
    ang = math.atan2(vertex[1] - centre[1], vertex[0] - centre[0])
    step = 2 * math.pi / sides
    if inscribed:
        corner_r, start = radius, ang
    else:
        corner_r, start = radius / math.cos(step / 2), ang - step / 2
    out = ShapeResult()
    cid = sketch.add_circle(centre[0], centre[1], radius, construction=True)
    circle = sketch.entities[cid]
    assert isinstance(circle, Circle)
    out.construction.append(cid)
    out.centre = circle.center
    pts = [
        _pt(
            sketch,
            (
                centre[0] + corner_r * math.cos(start + k * step),
                centre[1] + corner_r * math.sin(start + k * step),
            ),
            construction,
        )
        for k in range(sides)
    ]
    out.curves = [_line(sketch, pts[k], pts[(k + 1) % sides], construction) for k in range(sides)]
    if inscribed:
        for p in pts:
            sketch.relate("coincident", p, cid)
    else:
        for lid in out.curves:
            sketch.relate("tangent", lid, cid)
    sketch.relate("equal", *out.curves)
    return out
