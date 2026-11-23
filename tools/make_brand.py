"""Draw the FDCAD mark (DECISIONS D1034, D1036, D1037) and write the two app icon SVG files.

    uv run python tools/make_brand.py

The mark is the letters F and D made the way FDCAD makes parts: a flat profile
(the off white front face) pushed back into a solid (the ember faces), on a deep
cobalt tile. The two letters stand on two neighbouring faces of a cube that is
not drawn: the F is seen from the front left and above, the D from the front
right and above. The F is its face and the cube's near corner; the D is the
face beside it and stands against the back of the F. ``app_icon.svg`` is the
full drawing; ``app_icon_small.svg`` is a bolder one for 16 to 32 px. After
running this, run ``tools/make_app_icon.py`` to make the PNG, ICO and ICNS files
from them.
"""

from __future__ import annotations

import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "fdcad" / "ui"

#: Brand colours.
TILE_TOP, TILE_BOTTOM = "#24388F", "#0A1030"
#: The flat front faces: an off white, faintly warm toward the foot (D1039).
FRONT_TOP, FRONT_BOTTOM = "#FFFEFB", "#F3EEE4"
LIT_TOP, LIT_BOTTOM = "#FFC98A", "#FFA94D"
SHADE_TOP, SHADE_BOTTOM = "#F4680E", "#B83E05"
#: The side walls of the D. They face away from the light the F stands in, and the
#: darker ember sets the F, which stands in front of them, apart from the D (D1037).
DEEP_TOP, DEEP_BOTTOM = "#C24A08", "#8A2E04"
#: The end of the F that is the cube's corner. It lies on the D's face, above the
#: D's side wall, and stays bright to its foot so the two do not run together (D1038).
CORNER_TOP, CORNER_BOTTOM = "#FF7A1F", "#EE650D"

COS, SIN = math.cos(math.radians(30)), math.sin(math.radians(30))
Point = tuple[float, float]
Loop = list[Point]

#: Both letters are drawn in a box this wide and this tall.
WIDTH, HEIGHT = 5.0, 7.0
#: Radius of the outside of the D's bowl.
BOWL = 2.9
#: Straight pieces used for a quarter turn of the D.
TURN_STEPS = 48


def letter_f(stem: float, arm: float) -> list[Loop]:
    """The F profile, clockwise from its top left corner."""
    low = 1.8 + (HEIGHT - 1.8 - arm) * 0.21
    return [
        [
            (0, 0),
            (WIDTH, 0),
            (WIDTH, arm),
            (stem, arm),
            (stem, low),
            (4, low),
            (4, low + arm),
            (stem, low + arm),
            (stem, HEIGHT),
            (0, HEIGHT),
        ]
    ]


def _turn(cx: float, cy: float, radius: float, start: float, end: float) -> Loop:
    """Points along a circular arc, angles in degrees with y pointing down."""
    points = []
    for i in range(TURN_STEPS + 1):
        angle = math.radians(start + (end - start) * i / TURN_STEPS)
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def letter_d(stem: float, arm: float) -> list[Loop]:
    """The D profile: its outline clockwise, then its opening the other way round."""
    outer = [
        (0.0, 0.0),
        *_turn(WIDTH - BOWL, BOWL, BOWL, -90, 0),
        *_turn(WIDTH - BOWL, HEIGHT - BOWL, BOWL, 0, 90),
        (0.0, HEIGHT),
    ]
    left, right, top, bottom = stem, WIDTH - stem, arm, HEIGHT - arm
    inner = max(0.2, min(BOWL - (stem + arm) / 2, (right - left) * 0.9))
    opening = [
        (left, top),
        *_turn(right - inner, top + inner, inner, -90, 0),
        *_turn(right - inner, bottom - inner, inner, 0, 90),
        (left, bottom),
    ]
    opening.reverse()
    return [outer, opening]


def _mix(first: str, second: str, share: float) -> str:
    """A colour between two ``#RRGGBB`` colours; share 0 gives the first."""
    share = max(0.0, min(1.0, share))
    a = [int(first[i : i + 2], 16) for i in (1, 3, 5)]
    b = [int(second[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(a[i] + (b[i] - a[i]) * share):02X}" for i in range(3))


#: The lit colour for the pieces of a curved wall, which cannot use a gradient.
LIT_FLAT = _mix(LIT_TOP, LIT_BOTTOM, 0.5)


def _text(points: Loop) -> str:
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in points) + " Z"


def solid(
    loops: list[Loop], right: bool, gap: float, depth: float, unit: float
) -> tuple[list[str], list[Point]]:
    """SVG paths of one solid letter and the points that bound it.

    The cube's near corner is the line x = 0. A letter on the left face ends
    ``gap`` before the corner and is pushed back to the right; a letter on the
    right face (``right``) starts ``gap`` after it and is pushed back to the left.
    """

    def at(point: Point, back: float = 0.0) -> Point:
        x, y = point
        if right:
            along = x + gap
            return ((along - back) * COS * unit, (y - (along + back) * SIN) * unit)
        along = x - WIDTH - gap
        return ((along + back) * COS * unit, (y + (along - back) * SIN) * unit)

    def walls(loop: Loop) -> list[tuple[float, str]]:
        found: list[tuple[float, str]] = []
        count = len(loop)
        for i in range(count):
            a, b = loop[i], loop[(i + 1) % count]
            dx, dy = b[0] - a[0], b[1] - a[1]
            length = math.hypot(dx, dy)
            if length < 1e-9:
                continue
            # The wall's normal, pointing out of the letter (y points down).
            nx, ny = dy / length, -dx / length
            up = -ny
            toward = -nx if right else nx  # toward the side this letter shows
            if up + toward <= 1e-6:
                continue  # the wall faces away from the eye
            if abs(nx) < 1e-6:
                fill = "url(#lit)"
            elif abs(ny) < 1e-6:
                if right:
                    fill = "url(#deep)"
                elif gap == 0 and min(a[0], b[0]) >= WIDTH - 1e-9:
                    fill = "url(#corner)"  # the end that reaches the corner line
                else:
                    fill = "url(#shade)"
            else:
                share = max(0.0, up) / (max(0.0, up) + abs(nx))
                # A straight shaded wall runs from light at its top to dark at its
                # foot, so a curve takes the shade of the end it joins.
                top, foot = (DEEP_TOP, DEEP_BOTTOM) if right else (SHADE_TOP, SHADE_BOTTOM)
                shade = top if (a[1] + b[1]) / 2 < HEIGHT / 2 else foot
                fill = _mix(shade, LIT_FLAT, share)
            mid_x, mid_y = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            # Walls nearer the eye are drawn later.
            order = (-mid_x if right else mid_x) - mid_y
            quad = [at(a), at(b), at(b, depth), at(a, depth)]
            path = f'<path d="{_text(quad)}" fill="{fill}"'
            if not fill.startswith("url"):
                # A hairline in the same colour closes the seams of a curved wall.
                path += f' stroke="{fill}" stroke-width="0.5" stroke-linejoin="round"'
            found.append((order, path + "/>"))
        return found

    paths: list[str] = []
    # The walls of an opening are only seen through it: the outside walls and the
    # front face, drawn after them, cover the rest.
    for loop in loops[1:]:
        paths += [path for _order, path in sorted(walls(loop))]
    paths += [path for _order, path in sorted(walls(loops[0]))]
    front = " ".join(_text([at(p) for p in loop]) for loop in loops)
    rule = ' fill-rule="evenodd"' if len(loops) > 1 else ""
    paths.append(f'<path d="{front}" fill="url(#front)"{rule}/>')
    bounds = [at(p, back) for p in loops[0] for back in (0.0, depth)]
    return paths, bounds


def gradient(name: str, top: str, bottom: str) -> str:
    """A top to bottom gradient."""
    return (
        f'<linearGradient id="{name}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/>'
        "</linearGradient>"
    )


def icon(
    unit: float, depth: float, stem: float, arm: float, radius: float, d_stem: float = 0.0
) -> str:
    """The whole app icon as SVG text, 256 by 256.

    The F is its face and the corner: it runs to the corner line, so the end of its
    top arm, one depth wide, lies on the D's face. The D starts where that end
    stops, against the back of the F. The two solids touch and never overlap.
    ``d_stem`` is the D's stroke where it differs from the F's.
    """
    f_paths, f_points = solid(letter_f(stem, arm), False, 0.0, depth, unit)
    d_paths, d_points = solid(letter_d(d_stem or stem, arm), True, depth, depth, unit)
    xs = [p[0] for p in f_points + d_points]
    ys = [p[1] for p in f_points + d_points]
    dx = 128 - (min(xs) + max(xs)) / 2
    dy = 128 - (min(ys) + max(ys)) / 2
    defs = (
        '<linearGradient id="tile" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{TILE_TOP}"/>'
        f'<stop offset="1" stop-color="{TILE_BOTTOM}"/></linearGradient>'
        + gradient("front", FRONT_TOP, FRONT_BOTTOM)
        + gradient("lit", LIT_TOP, LIT_BOTTOM)
        + gradient("shade", SHADE_TOP, SHADE_BOTTOM)
        + gradient("deep", DEEP_TOP, DEEP_BOTTOM)
        + gradient("corner", CORNER_TOP, CORNER_BOTTOM)
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">'
        f"<defs>{defs}</defs>"
        f'<rect x="8" y="8" width="240" height="240" rx="{radius}" fill="url(#tile)"/>'
        f'<rect x="9.5" y="9.5" width="237" height="237" rx="{radius - 1.5}" fill="none" '
        'stroke="#FFFFFF" stroke-opacity="0.14" stroke-width="3"/>'
        f'<g transform="translate({dx:.1f} {dy:.1f})">'
        # The D first: the F stands in front of the D's left wall (D1037).
        + "".join(d_paths + f_paths)
        + "</g></svg>\n"
    )


def full_icon() -> str:
    """The full drawing. The F is the drawing, and the size, it had when it stood alone."""
    return icon(17.5, 3.0, 1.9, 1.7, 56)


def small_icon() -> str:
    """The bolder drawing for 16 to 32 px."""
    return icon(18.0, 2.6, 2.3, 2.0, 56, d_stem=1.95)


def main() -> int:
    """Write both drawings."""
    (OUT / "app_icon.svg").write_text(full_icon(), encoding="utf-8", newline="\n")
    (OUT / "app_icon_small.svg").write_text(small_icon(), encoding="utf-8", newline="\n")
    print("app_icon.svg and app_icon_small.svg written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
