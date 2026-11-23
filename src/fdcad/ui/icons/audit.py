"""Icon audit (UI_POLISH_SPEC U5, D670).

Checks every SVG in the icon folder against FDCAD's icon rules, without Qt:

1. A 24 by 24 frame, with one root group that sets no fill, a ``currentColor``
   stroke, 1.5 wide, with round caps and joins.
2. Every stroke is 1.5 wide (no hairlines, no heavy strokes) and keeps round caps.
3. Shapes stay inside 2 to 22.
4. Only the theme colours (``currentColor``, ``#ACCENT``, ``#DANGER``,
   ``#WARNING``). Solid
   fills are only for small dots; larger areas are a light tint.
5. The accent marks the active part only: it is never the whole icon.
6. Straight lines land on the pixel grid: a horizontal or vertical line sits on
   ``0.75 + 1.5 k``, which is a pixel centre at 16 px and an exact pixel edge at
   16, 32 and 48 px (D670). Lines on the centre line 12 are allowed, so symmetric
   icons stay symmetric.
7. Dashes use the house patterns, and secondary lines are at least half opacity.

``audit()`` returns the problems of one icon; ``audit_all()`` of every icon.
"""

from __future__ import annotations

import itertools
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

ICON_DIR = Path(__file__).parent

STROKE = 1.5
LOW, HIGH = 2.0, 22.0
CENTRE = 12.0
COLOURS = frozenset({"none", "currentColor", "#ACCENT", "#CUT", "#DANGER", "#WARNING"})
#: Solid fills larger than this (width or height) must be a tint.
DOT = 5.0
TINT_MAX = 0.35
SECONDARY_MIN = 0.5
DASHES = frozenset({"1.5 3", "4 3 0.5 3"})
GROUP = {
    "fill": "none",
    "stroke": "currentColor",
    "stroke-width": "1.5",
    "stroke-linecap": "round",
    "stroke-linejoin": "round",
}
NS = "{http://www.w3.org/2000/svg}"
_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_TOKEN = re.compile(r"[MLHVACQZmlhvacqz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_ARGS = {"M": 2, "L": 2, "H": 1, "V": 1, "A": 7, "C": 6, "Q": 4, "Z": 0}

Point = tuple[float, float]


def on_grid(value: float) -> bool:
    """True when a line at ``value`` lands on the pixel grid (or on the centre line)."""
    if abs(value - CENTRE) < 1e-6:
        return True
    steps = (value - 0.75) / 1.5
    return abs(steps - round(steps)) < 1e-6


@dataclass
class Shape:
    """One drawn element: its sampled outline and the lines that should be on the grid."""

    tag: str
    points: list[Point] = field(default_factory=list)
    #: ("x", value) for vertical lines, ("y", value) for horizontal ones.
    lines: list[tuple[str, float]] = field(default_factory=list)
    attrs: dict[str, str] = field(default_factory=dict)
    transformed: bool = False

    def box(self) -> tuple[float, float, float, float]:
        """(left, top, right, bottom) of the outline."""
        xs = [p[0] for p in self.points] or [0.0]
        ys = [p[1] for p in self.points] or [0.0]
        return min(xs), min(ys), max(xs), max(ys)


def _arc_points(start: Point, args: list[float]) -> list[Point]:
    """Points along an SVG arc, from the endpoint form (SVG 1.1 appendix F.6)."""
    rx, ry, rot, large, sweep, x2, y2 = args
    x1, y1 = start
    if rx == 0 or ry == 0 or (x1, y1) == (x2, y2):
        return [(x2, y2)]
    rx, ry = abs(rx), abs(ry)
    phi = math.radians(rot)
    cos, sin = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    xp, yp = cos * dx + sin * dy, -sin * dx + cos * dy
    scale = (xp * xp) / (rx * rx) + (yp * yp) / (ry * ry)
    if scale > 1:
        rx, ry = rx * math.sqrt(scale), ry * math.sqrt(scale)
    num = rx * rx * ry * ry - rx * rx * yp * yp - ry * ry * xp * xp
    den = rx * rx * yp * yp + ry * ry * xp * xp
    coef = math.sqrt(max(num / den, 0.0)) if den else 0.0
    if bool(large) == bool(sweep):
        coef = -coef
    cxp, cyp = coef * rx * yp / ry, -coef * ry * xp / rx
    cx = cos * cxp - sin * cyp + (x1 + x2) / 2
    cy = sin * cxp + cos * cyp + (y1 + y2) / 2

    def angle(ux: float, uy: float, vx: float, vy: float) -> float:
        return math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)

    t1 = angle(1, 0, (xp - cxp) / rx, (yp - cyp) / ry)
    dt = angle((xp - cxp) / rx, (yp - cyp) / ry, (-xp - cxp) / rx, (-yp - cyp) / ry)
    if not sweep and dt > 0:
        dt -= 2 * math.pi
    elif sweep and dt < 0:
        dt += 2 * math.pi
    out = []
    for i in range(1, 33):
        t = t1 + dt * i / 32
        ex, ey = rx * math.cos(t), ry * math.sin(t)
        out.append((cos * ex - sin * ey + cx, sin * ex + cos * ey + cy))
    return out


def path_shape(d: str) -> Shape:
    """Sample a path's outline and find its horizontal and vertical straight lines."""
    shape = Shape("path")
    tokens = _TOKEN.findall(d)
    i, cmd = 0, ""
    pos: Point = (0.0, 0.0)
    start: Point = (0.0, 0.0)
    while i < len(tokens):
        if tokens[i].isalpha():
            cmd = tokens[i].upper()
            i += 1
            if cmd == "Z":
                if pos[0] == start[0] and pos[1] != start[1]:
                    shape.lines.append(("x", pos[0]))
                elif pos[1] == start[1] and pos[0] != start[0]:
                    shape.lines.append(("y", pos[1]))
                pos = start
                continue
        count = _ARGS[cmd]
        args = [float(t) for t in tokens[i : i + count]]
        i += count
        if cmd == "M":
            pos = start = (args[0], args[1])
            shape.points.append(pos)
            cmd = "L"  # further pairs are lines
            continue
        if cmd in ("L", "H", "V"):
            new = (
                (args[0], args[1])
                if cmd == "L"
                else ((args[0], pos[1]) if cmd == "H" else (pos[0], args[0]))
            )
            if new[0] == pos[0] and new[1] != pos[1]:
                shape.lines.append(("x", new[0]))
            elif new[1] == pos[1] and new[0] != pos[0]:
                shape.lines.append(("y", new[1]))
            pos = new
            shape.points.append(pos)
        elif cmd == "A":
            shape.points.extend(_arc_points(pos, args))
            pos = (args[5], args[6])
        elif cmd in ("C", "Q"):
            ctrl = [(args[k], args[k + 1]) for k in range(0, count, 2)]
            curve = [pos, *ctrl]
            for step in range(1, 17):
                shape.points.append(_bezier(curve, step / 16))
            pos = ctrl[-1]
    return shape


def _bezier(points: list[Point], t: float) -> Point:
    while len(points) > 1:
        points = [
            (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            for a, b in itertools.pairwise(points)
        ]
    return points[0]


def element_shape(el: ET.Element) -> Shape | None:
    """The shape of one drawing element, or None for groups and the frame."""
    tag = el.tag.removeprefix(NS)
    attrs = dict(el.attrib)

    def num(key: str) -> float:
        return float(attrs.get(key, "0"))

    if tag == "path":
        shape = path_shape(attrs.get("d", ""))
    elif tag == "circle":
        cx, cy, r = num("cx"), num("cy"), num("r")
        shape = Shape(tag, [(cx - r, cy - r), (cx + r, cy + r)])
    elif tag == "ellipse":
        cx, cy, rx, ry = num("cx"), num("cy"), num("rx"), num("ry")
        shape = Shape(tag, [(cx - rx, cy - ry), (cx + rx, cy + ry)])
    elif tag == "rect":
        x, y, w, h = num("x"), num("y"), num("width"), num("height")
        shape = Shape(tag, [(x, y), (x + w, y + h)])
        if num("rx") < min(w, h) / 2:
            shape.lines = [("x", x), ("x", x + w), ("y", y), ("y", y + h)]
    elif tag == "line":
        x1, y1, x2, y2 = num("x1"), num("y1"), num("x2"), num("y2")
        shape = Shape(tag, [(x1, y1), (x2, y2)])
    else:
        return None
    shape.tag = tag
    shape.attrs = attrs
    shape.transformed = "transform" in attrs
    return shape


def _stroked(shape: Shape, group: dict[str, str]) -> bool:
    return shape.attrs.get("stroke", group.get("stroke", "none")) != "none"


def _colour(shape: Shape, group: dict[str, str]) -> str:
    """The colour that paints the element (stroke first, then fill)."""
    if _stroked(shape, group):
        return shape.attrs.get("stroke", group.get("stroke", "none"))
    return shape.attrs.get("fill", group.get("fill", "none"))


def audit_text(text: str) -> list[str]:
    """Every rule the SVG ``text`` breaks, as short messages (empty when it passes)."""
    problems: list[str] = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        return [f"not valid SVG: {exc}"]
    if root.get("viewBox") != "0 0 24 24" or root.get("width") != "24":
        problems.append("frame: viewBox must be 0 0 24 24 at 24 px")
    groups = [el for el in root if el.tag.removeprefix(NS) == "g"]
    if len(groups) != 1 or len(root) != 1:
        problems.append("frame: one root group holds every shape")
        return problems
    group = dict(groups[0].attrib)
    for key, value in GROUP.items():
        if group.get(key) != value:
            problems.append(f"group: {key} must be {value}")
    shapes = [s for el in groups[0].iter() if (s := element_shape(el)) is not None]
    if not shapes:
        problems.append("empty: no shapes")
        return problems
    accents = 0
    for n, shape in enumerate(shapes, start=1):
        where = f"{shape.tag} {n}"
        a = shape.attrs
        if a.get("stroke-width", "1.5") != "1.5":
            problems.append(f"stroke: {where} is {a['stroke-width']} wide, use 1.5")
        for key in ("stroke-linecap", "stroke-linejoin"):
            if a.get(key, "round") != "round":
                problems.append(f"stroke: {where} {key} must be round")
        for key in ("stroke", "fill"):
            if key in a and a[key] not in COLOURS:
                problems.append(f"colour: {where} {key} {a[key]} is not a theme colour")
        left, top, right, bottom = shape.box()
        if not shape.transformed and (
            left < LOW - 1e-6 or top < LOW - 1e-6 or right > HIGH + 1e-6 or bottom > HIGH + 1e-6
        ):
            problems.append(
                f"bounds: {where} reaches {left:g},{top:g} to {right:g},{bottom:g}, keep in 2 to 22"
            )
        fill = a.get("fill", group.get("fill", "none"))
        if fill != "none":
            opacity = float(a.get("fill-opacity", "1"))
            big = right - left > DOT or bottom - top > DOT
            if big and opacity > TINT_MAX:
                problems.append(f"fill: {where} is a solid area, use a tint of {TINT_MAX} or less")
        if float(a.get("stroke-opacity", "1")) < SECONDARY_MIN and _stroked(shape, group):
            problems.append(f"hairline: {where} stroke opacity below {SECONDARY_MIN}")
        dash = a.get("stroke-dasharray")
        if dash is not None and dash not in DASHES:
            problems.append(f"dash: {where} uses {dash}, use one of {sorted(DASHES)}")
        if _stroked(shape, group) and not shape.transformed:
            for axis, place in shape.lines:
                if not on_grid(place):
                    problems.append(f"grid: {where} has a line at {axis}={place:g}")
        if _colour(shape, group) == "#ACCENT":
            accents += 1
    if accents == len(shapes) and len(shapes) > 1:
        problems.append("accent: the whole icon is accent, keep it for the active part")
    return problems


def audit(name: str, folder: Path = ICON_DIR) -> list[str]:
    """Problems of the icon called ``name``."""
    return audit_text((folder / f"{name}.svg").read_text(encoding="utf-8"))


def names(folder: Path = ICON_DIR) -> list[str]:
    """Every icon file's name, sorted."""
    return sorted(p.stem for p in folder.glob("*.svg"))


def audit_all(folder: Path = ICON_DIR) -> dict[str, list[str]]:
    """Problems of every icon that has any."""
    found = {name: audit(name, folder) for name in names(folder)}
    return {name: problems for name, problems in found.items() if problems}


def ink_box(text: str) -> tuple[float, float, float, float]:
    """(left, top, right, bottom) of every shape in the SVG ``text``, strokes included."""
    root = ET.fromstring(text)
    boxes = [s.box() for el in root.iter() if (s := element_shape(el)) is not None]
    half = STROKE / 2
    return (
        min(b[0] for b in boxes) - half,
        min(b[1] for b in boxes) - half,
        max(b[2] for b in boxes) + half,
        max(b[3] for b in boxes) + half,
    )


def numbers(text: str) -> list[float]:
    """Every number in ``text`` (used by the fixer)."""
    return [float(n) for n in _NUMBER.findall(text)]
