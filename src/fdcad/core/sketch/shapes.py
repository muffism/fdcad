"""Preset sketch shapes (TUTORIAL_REVIEW_SPEC_2 TR228, DECISIONS D927).

Triangles by three sides (SSS), two sides and the angle between them (SAS) or one
side and the two angles on it (ASA); an isosceles trapezoid by its two widths and
height; a keyhole; a Reuleaux triangle (constant width); an egg; and a superellipse.
Each is a closed outline of joined pieces (``gear.Piece``) centred on the origin,
counter clockwise. Sizes are in millimetres and angles in radians. No Qt.
"""

from __future__ import annotations

import math

from fdcad.core.sketch.gear import Piece

Vec = tuple[float, float]
SHAPES = (
    "triangle_sss",
    "triangle_sas",
    "triangle_asa",
    "trapezoid",
    "keyhole",
    "reuleaux",
    "egg",
    "superellipse",
)
#: Points per quarter of a spline shape.
QUARTER_POINTS = 7


class ShapeError(ValueError):
    """The sizes make no shape; the message says what to change."""


def _centred(points: list[Vec]) -> list[Vec]:
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    return [(x - cx, y - cy) for x, y in points]


def _polygon(points: list[Vec]) -> list[Piece]:
    n = len(points)
    return [Piece("line", [points[i], points[(i + 1) % n]]) for i in range(n)]


def triangle(a: float, b: float, c: float) -> list[Piece]:
    """A triangle with sides ``a`` (the base), ``b`` and ``c``, base level."""
    if min(a, b, c) <= 0:
        raise ShapeError("Every side must be longer than zero. Type larger sides.")
    if a >= b + c or b >= a + c or c >= a + b:
        raise ShapeError(
            "Those sides cannot close: each side must be shorter than the other two "
            "together. Type other sides."
        )
    # Base from (0, 0) to (a, 0); the apex is b from the base's end and c from its start.
    x = (a * a + c * c - b * b) / (2 * a)
    y = math.sqrt(max(c * c - x * x, 0.0))
    return _polygon(_centred([(0.0, 0.0), (a, 0.0), (x, y)]))


def triangle_sas(a: float, b: float, angle: float) -> list[Piece]:
    """Sides ``a`` and ``b`` with ``angle`` between them."""
    if not 0 < angle < math.pi:
        raise ShapeError("The angle must be between 0 and 180 degrees. Type another angle.")
    if min(a, b) <= 0:
        raise ShapeError("Every side must be longer than zero. Type larger sides.")
    c = math.sqrt(a * a + b * b - 2 * a * b * math.cos(angle))
    return triangle(a, c, b)


def triangle_asa(side: float, angle_a: float, angle_b: float) -> list[Piece]:
    """Side ``side`` with angles ``angle_a`` and ``angle_b`` at its two ends."""
    if side <= 0:
        raise ShapeError("The side must be longer than zero. Type a larger side.")
    if min(angle_a, angle_b) <= 0 or angle_a + angle_b >= math.pi:
        raise ShapeError(
            "The two angles must each be above zero and add up to less than 180 degrees. "
            "Type other angles."
        )
    apex = math.pi - angle_a - angle_b
    c = side * math.sin(angle_b) / math.sin(apex)  # from the first end
    b = side * math.sin(angle_a) / math.sin(apex)  # from the second end
    return triangle(side, b, c)


def trapezoid(bottom: float, top: float, height: float) -> list[Piece]:
    """An isosceles trapezoid: ``bottom`` and ``top`` widths, ``height`` apart."""
    if min(bottom, height) <= 0 or top < 0:
        raise ShapeError("The widths and height must be above zero. Type larger sizes.")
    if top == 0:
        return triangle(bottom, math.hypot(bottom / 2, height), math.hypot(bottom / 2, height))
    b, t, h = bottom / 2, top / 2, height / 2
    return _polygon([(-b, -h), (b, -h), (t, h), (-t, h)])


def keyhole(diameter: float, slot_width: float, length: float) -> list[Piece]:
    """A round hole ``diameter`` across with a slot ``slot_width`` wide running down to
    ``length`` below its centre."""
    r, h = diameter / 2, slot_width / 2
    if min(r, h) <= 0:
        raise ShapeError("The sizes must be above zero. Type larger sizes.")
    if h >= r:
        raise ShapeError("The slot must be narrower than the hole. Type a smaller slot width.")
    s = math.sqrt(r * r - h * h)
    if length <= s:
        raise ShapeError(
            f"The slot must reach past the hole ({s:.3g} mm below the centre). Type a longer slot."
        )
    return [
        Piece("arc", [(h, -s), (-h, -s)], (0.0, 0.0), r),
        Piece("line", [(-h, -s), (-h, -length)]),
        Piece("line", [(-h, -length), (h, -length)]),
        Piece("line", [(h, -length), (h, -s)]),
    ]


def reuleaux(width: float) -> list[Piece]:
    """A Reuleaux triangle: the same ``width`` in every direction."""
    if width <= 0:
        raise ShapeError("The width must be above zero. Type a larger width.")
    r = width / math.sqrt(3)  # from the centre to a corner
    corners = [
        (
            r * math.cos(math.pi / 2 + k * 2 * math.pi / 3),
            r * math.sin(math.pi / 2 + k * 2 * math.pi / 3),
        )
        for k in range(3)
    ]
    return [
        Piece("arc", [corners[(k + 1) % 3], corners[(k + 2) % 3]], corners[k], width)
        for k in range(3)
    ]


def _trig(t: float) -> tuple[float, float]:
    """cos and sin with round off near zero removed, so quarter ends meet exactly."""
    c, s = math.cos(t), math.sin(t)
    return (0.0 if abs(c) < 1e-12 else c), (0.0 if abs(s) < 1e-12 else s)


def _quarters(point: object, n: int = QUARTER_POINTS) -> list[Piece]:
    """Four spline pieces through ``point(t)`` for t over each quarter turn."""
    pieces = []
    for q in range(4):
        pts = [point(q * math.pi / 2 + i * (math.pi / 2) / (n - 1)) for i in range(n)]  # type: ignore[operator]
        pieces.append(Piece("spline", pts))
    for q in range(4):  # each quarter ends where the next starts
        pieces[q].points[-1] = pieces[(q + 1) % 4].points[0]
    return pieces


def egg(width: float, height: float) -> list[Piece]:
    """An egg ``width`` across and ``height`` tall, blunter at the bottom."""
    if min(width, height) <= 0:
        raise ShapeError("The width and height must be above zero. Type larger sizes.")
    a = width / 2
    top, bottom = 0.58 * height, 0.42 * height
    shift = (top - bottom) / 2  # so the egg's height is centred on the origin

    def point(t: float) -> Vec:
        x, y = _trig(t)
        return (a * x, (top if y >= 0 else bottom) * y - shift)

    return _quarters(point)


def superellipse(width: float, height: float, exponent: float) -> list[Piece]:
    """|x/a|^n + |y/b|^n = 1: ``exponent`` 2 is an ellipse, larger is squarer."""
    if min(width, height) <= 0:
        raise ShapeError("The width and height must be above zero. Type larger sizes.")
    if not 0.5 <= exponent <= 20:
        raise ShapeError("Type an exponent between 0.5 and 20 (2 is an ellipse).")
    a, b, e = width / 2, height / 2, 2 / exponent

    def point(t: float) -> Vec:
        c, s = _trig(t)
        return (
            a * math.copysign(abs(c) ** e, c),
            b * math.copysign(abs(s) ** e, s),
        )

    return _quarters(point, 9)
