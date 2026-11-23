"""Gear and sprocket profiles for sketches (TUTORIAL_REVIEW_SPEC_2 TR161, DECISIONS D866).

Spur gears use the involute tooth form from the published gear geometry: pitch
radius m z / 2, base radius r cos(alpha), addendum m (1 + x) and dedendum
m (1.25 - x) for a profile shift x, and the tooth thickness m (pi / 2 + 2 x tan
alpha) on the pitch circle. Each flank is a spline through points of its
involute (a straight radial piece below the base circle); tips and roots are arcs
about the centre. On an external gear the root meets each flank through a short
rounded spline of about the root fillet radius. An internal gear gives the
outline of the hole (its teeth point inward); draw the ring's outer edge yourself.

Sprockets for roller chain: pitch diameter p / sin(180 / z), a seat arc of radius
0.505 d1 + 0.069 d1^(1/3) for each roller (d1 the roller diameter), and straight
flanks up to the tip circle D + 1.25 p - d1. Chain sizes are the common ANSI and
ISO roller chain pitches and roller diameters.

Timing belt pulleys (TR348, D2007): the outside diameter is the pitch diameter
z p / pi less twice the belt's pitch line offset; between round lands on that
circle each groove is a round bottomed groove for the curved tooth belts (GT2,
GT3, HTD 3M and 5M) or a straight flanked one with a flat floor for the
trapezoid belts (MXL, XL, T2.5, T5). Groove sizes are the belt tooth sizes from
the published belt standards plus a printing clearance, so the profiles are for
printed and cut pulleys, not inspection gauges.

A ``fillet`` radius given to a spur gear makes a true round root: an arc tangent
to the root circle and to the flank's radial foot.

Everything is in mm, centred on the origin, added as ordinary joined sketch
curves. No Qt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from fdcad.core.sketch.model import Arc, Line, Sketch, Spline

Vec = tuple[float, float]

#: Roller chain sizes: name to (pitch, roller diameter) in mm.
CHAINS: dict[str, tuple[float, float]] = {
    "25 (1/4 in)": (6.35, 3.30),
    "35 (3/8 in)": (9.525, 5.08),
    "40 (1/2 in)": (12.7, 7.92),
    "50 (5/8 in)": (15.875, 10.16),
    "60 (3/4 in)": (19.05, 11.91),
    "04B (6 mm)": (6.0, 4.0),
    "05B (8 mm)": (8.0, 5.0),
    "06B (3/8 in)": (9.525, 6.35),
    "08B (1/2 in)": (12.7, 8.51),
    "10B (5/8 in)": (15.875, 10.16),
}
#: Points along each involute flank.
FLANK_POINTS = 6


@dataclass(frozen=True)
class Belt:
    """A timing belt kind: pitch, pitch line offset, groove depth and width at the
    outside diameter, the groove shape, and the flank angle of trapezoid grooves."""

    pitch: float
    offset: float
    depth: float
    width: float
    round: bool
    flank: float = 0.0  # included angle in degrees (trapezoid grooves)


#: Timing belts (TR348, D2007): tooth sizes from the published belt standards with
#: about 0.1 mm of clearance for printing.
BELTS: dict[str, Belt] = {
    "GT2 (2 mm)": Belt(2.0, 0.254, 0.76, 1.38, True),
    "GT3 (3 mm)": Belt(3.0, 0.381, 1.17, 2.0, True),
    "HTD 3M": Belt(3.0, 0.381, 1.22, 2.0, True),
    "HTD 5M": Belt(5.0, 0.5715, 2.11, 3.4, True),
    "MXL (0.08 in)": Belt(2.032, 0.254, 0.56, 1.14, False, 40.0),
    "XL (0.2 in)": Belt(5.08, 0.254, 1.32, 2.7, False, 50.0),
    "T2.5": Belt(2.5, 0.3, 0.75, 1.75, False, 40.0),
    "T5": Belt(5.0, 0.5, 1.25, 2.96, False, 40.0),
}


class GearError(ValueError):
    """The values cannot make a gear; the message says what to change."""


@dataclass
class Piece:
    """One curve of the outline: a spline through ``points``, an arc (``centre``,
    ``radius``, from ``points[0]`` to ``points[-1]`` counter clockwise) or a line."""

    kind: str  # "spline", "arc" or "line"
    points: list[Vec]
    centre: Vec = (0.0, 0.0)
    radius: float = 0.0
    #: Arcs only: run clockwise about ``centre`` from the first point to the last.
    clockwise: bool = False


def _inv(a: float) -> float:
    return math.tan(a) - a


def _polar(r: float, t: float) -> Vec:
    return (r * math.cos(t), r * math.sin(t))


def gear_outline(
    module: float,
    teeth: int,
    pressure: float = math.radians(20.0),
    shift: float = 0.0,
    fillet: float | None = None,
    internal: bool = False,
) -> list[Piece]:
    """The closed outline, counter clockwise round the centre."""
    if module <= 0:
        raise GearError("The module must be greater than zero. Type a module.")
    if not 6 <= teeth <= 400:
        raise GearError("A gear needs 6 to 400 teeth. Type another tooth count.")
    if not math.radians(10) <= pressure <= math.radians(35):
        raise GearError("Use a pressure angle from 10 to 35 degrees, usually 20.")
    r = module * teeth / 2
    rb = r * math.cos(pressure)
    add, ded = module * (1 + shift), module * (1.25 - shift)
    half = (math.pi / 2 + 2 * shift * math.tan(pressure)) / teeth
    if internal:  # the hole: around each tooth angle the outline is out at the root
        inner, outer = r - add, r + ded
        rounding = 0.0
    else:
        inner, outer = r - ded, r + add
        rounding = 0.38 * module if fillet is None else max(fillet, 0.0)
    if inner <= 0.2 * r:
        raise GearError("The teeth are too deep for so few teeth. Use more teeth or less shift.")

    def width(rho: float) -> float:
        """Half the angular width of the tooth (external) or space (internal) at ``rho``."""
        rho = max(rho, rb)
        return half + _inv(pressure) - _inv(math.acos(min(rb / rho, 1.0)))

    lo = inner + rounding
    radii = [lo + (outer - lo) * k / (FLANK_POINTS - 1) for k in range(FLANK_POINTS)]
    pitch = 2 * math.pi / teeth
    if width(outer) <= 0 or width(lo) >= pitch / 2:
        raise GearError(
            "The teeth would cross each other. "
            "Use fewer teeth, more shift or a smaller pressure angle."
        )
    pieces: list[Piece] = []
    for i in range(teeth):
        c = i * pitch
        rising = [_polar(rho, c - width(rho)) for rho in radii]
        falling = [_polar(rho, c + width(rho)) for rho in reversed(radii)]
        pieces.append(Piece("spline", rising))
        pieces.append(Piece("arc", [rising[-1], falling[0]], radius=outer))
        pieces.append(Piece("spline", falling))
        next_start = _polar(radii[0], c + pitch - width(radii[0]))
        a0 = c + width(lo)
        a1 = c + pitch - width(lo)
        if rounding > 0 and fillet is not None and fillet > 0:  # a true round root (D2007)
            ends = (c + width(lo), c + pitch - width(radii[0]))
            pieces.extend(_round_root(falling[-1], next_start, *ends, inner, rounding, a1 - a0))
        elif rounding > 0:
            turn = min(rounding / inner, (a1 - a0) / 3)
            foot0, foot1 = _polar(inner, a0 + turn), _polar(inner, a1 - turn)
            bend0 = _polar(inner + rounding * 0.3, a0 + turn * 0.4)
            bend1 = _polar(inner + rounding * 0.3, a1 - turn * 0.4)
            pieces.append(Piece("spline", [falling[-1], bend0, foot0]))
            pieces.append(Piece("arc", [foot0, foot1], radius=inner))
            pieces.append(Piece("spline", [foot1, bend1, next_start]))
        else:
            pieces.append(Piece("arc", [falling[-1], next_start], radius=inner))
    return pieces


def _round_root(
    start: Vec, end: Vec, a0: float, a1: float, inner: float, rf: float, gap: float
) -> list[Piece]:
    """From the falling flank's foot ``start`` (at angle ``a0``) round the root to the
    next rising flank's foot ``end`` (at angle ``a1``): a radial piece, an arc of radius
    ``rf`` tangent to it and to the root circle, the root arc, and the mirror pair."""
    delta = math.asin(rf / (inner + rf))
    if 2 * delta >= gap:
        raise GearError(
            "The root fillet is too large for the gap between teeth. Type a smaller one."
        )
    reach = (inner + rf) * math.cos(delta)  # where the fillet meets the radial foot
    out: list[Piece] = []
    foot0, foot1 = _polar(reach, a0), _polar(reach, a1)
    c0, c1 = _polar(inner + rf, a0 + delta), _polar(inner + rf, a1 - delta)
    root0, root1 = _polar(inner, a0 + delta), _polar(inner, a1 - delta)
    if math.dist(start, foot0) > 1e-9:
        out.append(Piece("line", [start, foot0]))
    out.append(Piece("arc", [foot0, root0], centre=c0, radius=rf, clockwise=True))
    out.append(Piece("arc", [root0, root1], radius=inner))
    out.append(Piece("arc", [root1, foot1], centre=c1, radius=rf, clockwise=True))
    if math.dist(foot1, end) > 1e-9:
        out.append(Piece("line", [foot1, end]))
    return out


def pulley_outline(belt: str, teeth: int) -> list[Piece]:
    """A timing belt pulley's closed outline (TR348, D2007)."""
    if belt not in BELTS:
        raise GearError(f'"{belt}" is not a belt FDCAD knows. Choose one from the list.')
    if not 8 <= teeth <= 300:
        raise GearError("A pulley needs 8 to 300 teeth. Type another tooth count.")
    b = BELTS[belt]
    outside = teeth * b.pitch / math.pi / 2 - b.offset
    floor = outside - b.depth
    pitch = 2 * math.pi / teeth
    half = math.asin(min(b.width / 2 / outside, 0.99))  # half the groove's angle at the top
    if 2 * half >= pitch * 0.9:
        raise GearError("The grooves would run into each other. Use more teeth.")
    pieces: list[Piece] = []
    for i in range(teeth):
        c = i * pitch
        g0, g1 = _polar(outside, c - half), _polar(outside, c + half)
        if b.round:
            # One arc through both groove edges and the groove bottom.
            chord = math.dist(g0, g1)
            sag = outside * math.cos(half) - floor
            radius = (chord * chord / 4 + sag * sag) / (2 * sag)
            centre = _polar(floor + radius, c)
            pieces.append(Piece("arc", [g0, g1], centre=centre, radius=radius, clockwise=True))
        else:
            spread = math.tan(math.radians(b.flank / 2)) * b.depth
            floor_half = max(b.width / 2 - spread, 0.1 * b.width)
            f0 = (floor * math.cos(c) + floor_half * math.sin(c),
                  floor * math.sin(c) - floor_half * math.cos(c))  # fmt: skip
            f1 = (floor * math.cos(c) - floor_half * math.sin(c),
                  floor * math.sin(c) + floor_half * math.cos(c))  # fmt: skip
            pieces += [Piece("line", [g0, f0]), Piece("line", [f0, f1]), Piece("line", [f1, g1])]
        nxt = _polar(outside, c + pitch - half)
        pieces.append(Piece("arc", [g1, nxt], radius=outside))
    return pieces


def sprocket_outline(chain: str, teeth: int) -> list[Piece]:
    """A roller chain sprocket's closed outline."""
    if chain not in CHAINS:
        raise GearError(f'"{chain}" is not a chain size FDCAD knows. Choose one from the list.')
    if not 6 <= teeth <= 150:
        raise GearError("A sprocket needs 6 to 150 teeth. Type another tooth count.")
    p, d1 = CHAINS[chain]
    rp = p / (2 * math.sin(math.pi / teeth))
    seat = 0.505 * d1 + 0.069 * d1 ** (1 / 3)
    tip = (2 * rp + 1.25 * p - d1) / 2
    pitch = 2 * math.pi / teeth
    span = math.radians(140 - 90 / teeth) / 2  # half the roller seat angle
    pieces: list[Piece] = []
    for i in range(teeth):
        c = i * pitch
        centre = _polar(rp, c)
        inward = c + math.pi  # from the roller toward the sprocket centre
        a_in = (
            centre[0] + seat * math.cos(inward - span),
            centre[1] + seat * math.sin(inward - span),
        )
        a_out = (
            centre[0] + seat * math.cos(inward + span),
            centre[1] + seat * math.sin(inward + span),
        )
        pieces.append(Piece("arc", [a_in, a_out], centre=centre, radius=seat))
        nxt = _polar(rp, c + pitch)
        back = c + pitch + math.pi - span
        b_in = (nxt[0] + seat * math.cos(back), nxt[1] + seat * math.sin(back))
        tip_pt = _polar(tip, c + pitch / 2)
        pieces.append(Piece("line", [a_out, tip_pt]))
        pieces.append(Piece("line", [tip_pt, b_in]))
    return pieces


def add_to_sketch(sketch: Sketch, pieces: list[Piece]) -> list[str]:
    """Add the closed outline as joined sketch curves. Returns the new curve ids."""
    from fdcad.core.sketch.curve_convert import spline_handles

    made: list[str] = []
    first: str | None = None
    last: str | None = None

    def start_point(at: Vec) -> str:
        nonlocal first
        if last is not None and math.dist(sketch.xy(last), at) < 1e-6:
            return last
        pid = sketch.add_point(*at)
        first = first or pid
        return pid

    def end_point(at: Vec, closing: bool) -> str:
        if closing and first is not None and math.dist(sketch.xy(first), at) < 1e-6:
            return first
        return sketch.add_point(*at)

    for n, piece in enumerate(pieces):
        closing = n == len(pieces) - 1
        a = start_point(piece.points[0])
        b = end_point(piece.points[-1], closing)
        if piece.kind == "spline":
            inner = [sketch.add_point(*p) for p in piece.points[1:-1]]
            ids = [a, *inner, b]
            hids = [sketch.add_point(*h, True) for h in spline_handles(piece.points)]
            cid = sketch.new_id()
            sketch.entities[cid] = Spline(cid, ids, hids)
        elif piece.kind == "arc":
            cx, cy = piece.centre
            t0 = math.atan2(piece.points[0][1] - cy, piece.points[0][0] - cx)
            t1 = math.atan2(piece.points[-1][1] - cy, piece.points[-1][0] - cx)
            if piece.clockwise:  # a sketch arc runs counter clockwise: swap its ends
                t0, t1 = t1, t0
            cid = sketch.add_arc(cx, cy, piece.radius, t0, t1)
            arc = sketch.entities[cid]
            assert isinstance(arc, Arc)
            for old in (arc.start, arc.end):
                sketch.entities.pop(old, None)
            arc.start, arc.end = (b, a) if piece.clockwise else (a, b)
        else:
            cid = sketch.add_line(*piece.points[0], *piece.points[-1])
            line = sketch.entities[cid]
            assert isinstance(line, Line)
            for old in (line.p1, line.p2):
                sketch.entities.pop(old, None)
            line.p1, line.p2 = a, b
        made.append(cid)
        last = b
    return made
