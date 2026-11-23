"""Standard section profiles as sketch outlines (TR367, D991).

Angle, channel, I beam, rectangular and round tube by their sizes, and the top hat
DIN rail (EN 60715, 35 mm wide and 7.5 mm high), centred on the sketch origin.
Each is a list of closed loops (a tube has two); every loop is joined pieces
(``gear.Piece``), counter clockwise. The sizes are the user's, so any catalogue
size can be typed. Sizes in millimetres. No Qt.
"""

from __future__ import annotations

from fdcad.core.sketch.gear import Piece
from fdcad.core.sketch.shapes import ShapeError

Vec = tuple[float, float]
PROFILES = ("angle", "channel", "i_beam", "rect_tube", "round_tube", "din_rail")


def _loop(points: list[Vec]) -> list[Piece]:
    n = len(points)
    return [Piece("line", [points[i], points[(i + 1) % n]]) for i in range(n)]


def _centre(points: list[Vec]) -> list[Vec]:
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    return [(x - cx, y - cy) for x, y in points]


def _positive(*values: float) -> None:
    if min(values) <= 0:
        raise ShapeError("Every size must be above zero. Type larger sizes.")


def angle(leg_a: float, leg_b: float, thickness: float) -> list[list[Piece]]:
    """An L section: legs ``leg_a`` along X and ``leg_b`` along Y."""
    _positive(leg_a, leg_b, thickness)
    if thickness >= min(leg_a, leg_b):
        raise ShapeError("The thickness must be less than both legs. Type a thinner wall.")
    t = thickness
    pts = [(0, 0), (leg_a, 0), (leg_a, t), (t, t), (t, leg_b), (0, leg_b)]
    return [_loop(_centre([(float(x), float(y)) for x, y in pts]))]


def channel(height: float, width: float, thickness: float) -> list[list[Piece]]:
    """A C (U) section: back ``height`` tall, flanges ``width`` deep."""
    _positive(height, width, thickness)
    if 2 * thickness >= height or thickness >= width:
        raise ShapeError("The wall is too thick for the height and width. Type a thinner wall.")
    h, b, t = height, width, thickness
    pts = [(0.0, 0.0), (b, 0.0), (b, t), (t, t), (t, h - t), (b, h - t), (b, h), (0.0, h)]
    return [_loop(_centre(pts))]


def i_beam(height: float, width: float, web: float, flange: float) -> list[list[Piece]]:
    """An I (H) section: ``height`` tall, flanges ``width`` wide and ``flange`` thick,
    with a web ``web`` thick."""
    _positive(height, width, web, flange)
    if 2 * flange >= height or web >= width:
        raise ShapeError("The flanges or web are too thick for the size. Type thinner ones.")
    h, b, w, f = height, width, web, flange
    x0, x1 = (b - w) / 2, (b + w) / 2
    pts = [
        (0.0, 0.0), (b, 0.0), (b, f), (x1, f), (x1, h - f), (b, h - f),
        (b, h), (0.0, h), (0.0, h - f), (x0, h - f), (x0, f), (0.0, f),
    ]  # fmt: skip
    return [_loop(_centre(pts))]


def rect_tube(width: float, height: float, wall: float) -> list[list[Piece]]:
    """A rectangular tube: the outside and the inside outlines."""
    _positive(width, height, wall)
    if 2 * wall >= min(width, height):
        raise ShapeError("The wall is too thick for the tube. Type a thinner wall.")
    w, h, t = width / 2, height / 2, wall
    outer = [(-w, -h), (w, -h), (w, h), (-w, h)]
    inner = [(-w + t, -h + t), (w - t, -h + t), (w - t, h - t), (-w + t, h - t)]
    return [_loop(outer), _loop(inner)]


def round_tube(diameter: float, wall: float) -> list[list[Piece]]:
    """A round tube: the outside and the inside circles, each as two half arcs."""
    _positive(diameter, wall)
    r = diameter / 2
    if wall >= r:
        raise ShapeError("The wall is too thick for the tube. Type a thinner wall.")

    def circle(radius: float) -> list[Piece]:
        return [
            Piece("arc", [(radius, 0.0), (-radius, 0.0)], (0.0, 0.0), radius),
            Piece("arc", [(-radius, 0.0), (radius, 0.0)], (0.0, 0.0), radius),
        ]

    return [circle(r), circle(r - wall)]


def din_rail(thickness: float = 1.0) -> list[list[Piece]]:
    """A top hat DIN rail (EN 60715 TS 35 x 7.5): 35 mm over the flanges, a 27 mm
    wide hat 7.5 mm high, in sheet ``thickness`` thick (1 mm is the usual)."""
    _positive(thickness)
    if thickness >= 3.0:
        raise ShapeError("A DIN rail sheet is thinner than 3 mm. Type a thinner sheet.")
    t, half, hat, high = thickness, 17.5, 13.5, 7.5
    pts = [
        (-half, high - t), (-hat - t, high - t), (-hat - t, 0.0), (hat + t, 0.0),
        (hat + t, high - t), (half, high - t), (half, high), (hat, high), (hat, t),
        (-hat, t), (-hat, high), (-half, high),
    ]  # fmt: skip
    return [_loop(_centre(pts))]
