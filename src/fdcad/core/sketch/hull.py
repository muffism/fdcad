"""Convex Hull of sketch curves (TUTORIAL_REVIEW_SPEC_2 TR229, DECISIONS D912).

The convex outline around the picked curves becomes new, joined sketch geometry.
Circles and arcs keep their exact shape: the outline is arcs on them joined by the
lines that touch two of them (tangent relations added). Lines and points give
corners; ellipses and splines are followed by short lines through points along
them. No Qt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from fdcad.core.sketch.model import (
    Arc,
    Circle,
    Ellipse,
    EllipseArc,
    Line,
    Point,
    Sketch,
    Spline,
)

Vec = tuple[float, float]

#: Points along each circle when finding which parts of it lie on the outline.
CIRCLE_STEPS = 720
#: Points along an ellipse or spline (these give short lines).
CURVE_STEPS = 48


class HullError(ValueError):
    """No outline can be made; the message says what to change."""


@dataclass(frozen=True)
class _Item:
    """A circle (``radius`` > 0) or a corner point (``radius`` 0) on the outline."""

    centre: Vec
    radius: float
    #: The arc span the item may use (start angle, sweep), or None for a whole circle.
    span: tuple[float, float] | None = None


def _sources(sketch: Sketch, ids: list[str], arcs_exact: bool) -> list[tuple[Vec, _Item]]:
    """Sample points of the picked curves, each tagged with the item it belongs to."""
    from fdcad.core.sketch.freeform import sample

    out: list[tuple[Vec, _Item]] = []

    def corner(p: Vec) -> None:
        out.append((p, _Item(p, 0.0)))

    for eid in ids:
        e = sketch.entities.get(eid)
        if isinstance(e, Point):
            corner((e.x, e.y))
        elif isinstance(e, Line):
            corner(sketch.xy(e.p1))
            corner(sketch.xy(e.p2))
        elif isinstance(e, Circle):
            c, r = sketch.xy(e.center), e.radius
            item = _Item(c, r)
            for i in range(CIRCLE_STEPS):
                t = math.tau * i / CIRCLE_STEPS
                out.append(((c[0] + r * math.cos(t), c[1] + r * math.sin(t)), item))
        elif isinstance(e, Arc):
            c = sketch.xy(e.center)
            s, f = sketch.xy(e.start), sketch.xy(e.end)
            if not e.ccw:
                s, f = f, s
            r = math.dist(c, s)
            t0 = math.atan2(s[1] - c[1], s[0] - c[0])
            sweep = (math.atan2(f[1] - c[1], f[0] - c[0]) - t0) % math.tau or math.tau
            exact: _Item | None = _Item(c, r, (t0, sweep)) if arcs_exact else None
            steps = max(int(CIRCLE_STEPS * sweep / math.tau), 8)
            for i in range(steps + 1):
                t = t0 + sweep * i / steps
                p = (c[0] + r * math.cos(t), c[1] + r * math.sin(t))
                out.append((p, exact if exact is not None else _Item(p, 0.0)))
        elif isinstance(e, (Ellipse, EllipseArc, Spline)):
            for p in sample(sketch, e, CURVE_STEPS):
                corner(p)
    return out


def _hull(points: list[tuple[Vec, _Item]]) -> list[tuple[Vec, _Item]]:
    """Counter clockwise convex hull (monotone chain) of tagged points."""
    pts = sorted(set(points), key=lambda q: (q[0][0], q[0][1], q[1].radius))
    if len(pts) < 3:
        return pts

    def turn(o: Vec, a: Vec, b: Vec) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[Vec, _Item]] = []
    for p in pts:
        while len(lower) >= 2 and turn(lower[-2][0], lower[-1][0], p[0]) <= 1e-12:
            lower.pop()
        lower.append(p)
    upper: list[tuple[Vec, _Item]] = []
    for p in reversed(pts):
        while len(upper) >= 2 and turn(upper[-2][0], upper[-1][0], p[0]) <= 1e-12:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _tangent(a: _Item, b: _Item) -> tuple[Vec, Vec]:
    """Where the outline leaves ``a`` and reaches ``b`` (both lie to its left)."""
    dx, dy = b.centre[0] - a.centre[0], b.centre[1] - a.centre[1]
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    vx, vy = uy, -ux  # to the right of the direction of travel: outward
    k = max(-1.0, min(1.0, (a.radius - b.radius) / length))
    s = math.sqrt(1.0 - k * k)
    nx, ny = k * ux + s * vx, k * uy + s * vy
    return (
        (a.centre[0] + a.radius * nx, a.centre[1] + a.radius * ny),
        (b.centre[0] + b.radius * nx, b.centre[1] + b.radius * ny),
    )


def _in_span(item: _Item, p: Vec) -> bool:
    if item.span is None:
        return True
    t0, sweep = item.span
    t = math.atan2(p[1] - item.centre[1], p[0] - item.centre[0])
    return (t - t0) % math.tau <= sweep + 1e-6


def _items(hull: list[tuple[Vec, _Item]]) -> list[_Item]:
    """The hull's items in order, with runs on one circle joined."""
    items: list[_Item] = []
    for _p, item in hull:
        if not items or items[-1] != item:
            items.append(item)
    if len(items) > 1 and items[0] == items[-1]:
        items.pop()
    return items


def outline(sketch: Sketch, ids: list[str]) -> list[tuple[str, Vec, Vec, Vec, float]]:
    """The outline as pieces (kind "line" or "arc", start, end, centre, radius), counter
    clockwise and joined end to start."""
    for arcs_exact in (True, False):
        points = _sources(sketch, ids, arcs_exact)
        if not points:
            raise HullError("Pick the curves to wrap first.")
        items = _items(_hull(points))
        if len(items) < 2 or (all(i.radius == 0 for i in items) and len(items) < 3):
            if len(items) == 1 and items[0].radius > 0 and items[0].span is None:
                raise HullError("A circle on its own is already convex. Pick more curves.")
            raise HullError("The curves have no area to wrap. Pick curves that are not in a line.")
        n = len(items)
        ends = [_tangent(items[i], items[(i + 1) % n]) for i in range(n)]
        if not all(_in_span(items[i], ends[i][0]) for i in range(n)) or not all(
            _in_span(items[(i + 1) % n], ends[i][1]) for i in range(n)
        ):
            continue  # an arc's tangent point is past its end: follow the arc by points
        pieces: list[tuple[str, Vec, Vec, Vec, float]] = []
        for i in range(n):
            item = items[i]
            arrive, leave = ends[i - 1][1], ends[i][0]
            if item.radius > 0 and math.dist(arrive, leave) > 1e-9:
                pieces.append(("arc", arrive, leave, item.centre, item.radius))
            pieces.append(("line", leave, ends[i][1], (0.0, 0.0), 0.0))
        return [p for p in pieces if p[0] == "arc" or math.dist(p[1], p[2]) > 1e-9]
    raise HullError("The outline could not be found. Pick other curves.")


def add_hull(sketch: Sketch, ids: list[str]) -> list[str]:
    """Add the convex outline around the picked curves; returns the new curve ids."""
    from fdcad.core.sketch.gear import Piece, add_to_sketch

    found = outline(sketch, ids)
    pieces = [
        Piece(kind, [a, b], centre, radius) if kind == "arc" else Piece(kind, [a, b])
        for kind, a, b, centre, radius in found
    ]
    made = add_to_sketch(sketch, pieces)
    for i, cid in enumerate(made):
        nxt = made[(i + 1) % len(made)]
        kinds = {type(sketch.entities[cid]), type(sketch.entities[nxt])}
        if kinds == {Line, Arc}:
            sketch.relate("tangent", cid, nxt)
    return made
