"""Sheet metal and laser checks for the Manufacturing Check (TR297; DECISIONS D791).

They read the flat pattern as the DXF export draws it (``flat_drawing``): cut
lines and arcs, and bend lines. Distances use the profile's values as multiples
of the sheet thickness, as sheet metal rules usually are; ``kerf`` is a length.

Layout rules (item 1): ``hole_small`` (a hole under ``min_hole`` times the
thickness), ``hole_edge`` (a hole or cut-out nearer the outside edge than
``hole_to_edge``), ``hole_bend`` (nearer a bend line than ``hole_to_bend``,
slots and cut-outs included), ``hole_hole`` (two holes nearer each other than
``hole_to_hole``) and ``short_flange`` (a bend line nearer the outside edge,
along its length, than ``min_flange``).

Preflight (item 2): ``open_contour`` (cut line ends that meet nothing),
``duplicate`` (the same line twice), ``tiny`` (lines or arcs shorter than
``TINY``), ``island`` (a closed piece inside a cut-out, which falls out, as in the
middle of an O) and ``units`` (an outline so small or large that the units are
likely wrong). Pure Python, no Qt.
"""

from __future__ import annotations

import math
from typing import Any

from fdcad.core.manufacturing import Finding

Vec2 = tuple[float, float]
#: Ends closer than this meet.
JOIN = 1e-4
#: Lines shorter than this are tiny (mm).
TINY = 0.05


def _ends(item: Any) -> tuple[Vec2, Vec2] | None:
    """The two ends of a segment or a part arc; None for a whole circle."""
    from fdcad.core.features.sheetmetal.export import ArcPiece

    if isinstance(item, ArcPiece):
        if item.full:
            return None
        c, r = item.centre, item.radius
        a0, a1 = math.radians(item.start), math.radians(item.end)
        return (c[0] + r * math.cos(a0), c[1] + r * math.sin(a0)), (
            c[0] + r * math.cos(a1),
            c[1] + r * math.sin(a1),
        )
    return item.a, item.b


def _length(item: Any) -> float:
    from fdcad.core.features.sheetmetal.export import ArcPiece

    if isinstance(item, ArcPiece):
        sweep = 360.0 if item.full else (item.end - item.start) % 360.0
        return math.radians(sweep) * item.radius
    return math.dist(item.a, item.b)


def _points(item: Any) -> list[Vec2]:
    """Points along the item, for polygons and distances."""
    from fdcad.core.features.sheetmetal.export import ArcPiece

    if isinstance(item, ArcPiece):
        sweep = 360.0 if item.full else (item.end - item.start) % 360.0
        steps = max(4, int(sweep / 10))
        return [
            (
                item.centre[0]
                + item.radius * math.cos(math.radians(item.start + sweep * k / steps)),
                item.centre[1]
                + item.radius * math.sin(math.radians(item.start + sweep * k / steps)),
            )
            for k in range(steps + 1)
        ]
    return [item.a, item.b]


def _key(p: Vec2) -> tuple[int, int]:
    return (round(p[0] / JOIN), round(p[1] / JOIN))


def loops(outline: list[Any]) -> tuple[list[list[Vec2]], int]:
    """Closed loops as point lists, and the number of open ends left over."""
    loose = list(outline)
    out: list[list[Vec2]] = []
    open_ends = 0
    for item in [i for i in loose if _ends(i) is None]:
        out.append(_points(item))
    loose = [i for i in loose if _ends(i) is not None]
    while loose:
        first = loose.pop(0)
        a, b = _ends(first)  # type: ignore[misc]
        chain = _points(first)
        start, end = a, b
        grew = True
        while grew and math.dist(start, end) > JOIN:
            grew = False
            for i, item in enumerate(loose):
                p, q = _ends(item)  # type: ignore[misc]
                pts = _points(item)
                if math.dist(p, end) <= JOIN:
                    chain += pts[1:]
                    end = q
                elif math.dist(q, end) <= JOIN:
                    chain += list(reversed(pts))[1:]
                    end = p
                else:
                    continue
                loose.pop(i)
                grew = True
                break
        if math.dist(start, end) <= JOIN:
            out.append(chain)
        else:
            open_ends += 2
    return out, open_ends


def _area(poly: list[Vec2]) -> float:
    return 0.5 * abs(
        sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1], strict=True))
    )


def _inside(p: Vec2, poly: list[Vec2]) -> bool:
    x, y = p
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1], strict=True):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def _seg_dist(p: Vec2, a: Vec2, b: Vec2) -> float:
    ax, ay = b[0] - a[0], b[1] - a[1]
    size = ax * ax + ay * ay
    t = 0.0 if size == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / size))
    return math.dist(p, (a[0] + ax * t, a[1] + ay * t))


def _poly_dist(a: list[Vec2], b: list[Vec2]) -> float:
    """Nearest distance between two point loops (by their points and edges)."""
    best = math.inf
    for p in a:
        for s, e in zip(b, b[1:] + b[:1], strict=True):
            best = min(best, _seg_dist(p, s, e))
    for p in b:
        for s, e in zip(a, a[1:] + a[:1], strict=True):
            best = min(best, _seg_dist(p, s, e))
    return best


def sheet_checks(drawing: Any, thickness: float, profile: dict[str, Any]) -> list[Finding]:
    """The sheet metal and laser findings for one flat pattern (see the module notes)."""
    from fdcad.core.features.sheetmetal.export import ArcPiece

    def k(key: str, default: float) -> float:
        v = profile.get(key, default)
        return float(v) if isinstance(v, (int, float)) else default

    t = thickness
    out: list[Finding] = []
    outline = list(drawing.outline)
    found, open_ends = loops(outline)
    if open_ends:
        out.append(
            Finding(
                "open_contour",
                f"{open_ends} cut line ends meet nothing, so the cutter path is open. "
                "Close the outline before cutting.",
            )
        )
    seen: set[tuple[Any, ...]] = set()
    for item in outline:
        ends = _ends(item)
        if ends is not None:
            key: tuple[Any, ...] = tuple(sorted((_key(ends[0]), _key(ends[1]))))
            if isinstance(item, ArcPiece):
                key = (*key, (round(item.radius / JOIN), 0))
            if key in seen:
                out.append(Finding("duplicate", "A cut line is drawn twice. Remove the copy."))
            seen.add(key)
        if _length(item) < TINY:
            out.append(
                Finding(
                    "tiny",
                    f"A cut line {_length(item):.3g} mm long is too small to cut. Remove it or "
                    "make the feature larger.",
                )
            )
    if not found:
        return out
    # The outside loop is the largest; the rest are cut-outs or islands.
    found.sort(key=_area, reverse=True)
    outer, inner = found[0], found[1:]
    depth = [sum(1 for o in found if o is not poly and _inside(poly[0], o)) for poly in found]
    for d in depth:
        if d >= 2:
            out.append(
                Finding(
                    "island",
                    "A closed piece sits inside a cut-out and falls out when cut, like the "
                    "middle of an O. Add bridges to hold it, or remove it.",
                )
            )
    w, h = (
        max(p[0] for p in outer) - min(p[0] for p in outer),
        max(p[1] for p in outer) - min(p[1] for p in outer),
    )
    if max(w, h) < 2.0 or max(w, h) > 5000.0:
        out.append(
            Finding(
                "units",
                f"The flat pattern is {w:.4g} by {h:.4g} mm, which suggests the wrong units. "
                "Check the part's units before export.",
            )
        )
    holes = [item for item in outline if isinstance(item, ArcPiece) and item.full]
    min_hole = k("min_hole", 1.0) * t
    for hole in holes:
        if 2 * hole.radius < min_hole - 1e-9:
            out.append(
                Finding(
                    "hole_small",
                    f"A {2 * hole.radius:g} mm hole is under {min_hole:g} mm ("
                    f"{k('min_hole', 1.0):g} times the thickness) and may not cut or punch "
                    "cleanly. Make it larger.",
                )
            )
    edge_gap = k("hole_to_edge", 1.5) * t
    bend_gap = k("hole_to_bend", 2.5) * t
    hole_gap = k("hole_to_hole", 2.0) * t
    for poly in inner:
        if _poly_dist(poly, outer) < edge_gap - 1e-9:
            out.append(
                Finding(
                    "hole_edge",
                    f"A hole or cut-out is {_poly_dist(poly, outer):.3g} mm from the edge, under "
                    f"{edge_gap:g} mm. Move it inwards.",
                )
            )
        for bend in drawing.bends:
            gap = min(_seg_dist(p, bend.a, bend.b) for p in poly)
            if gap < bend_gap - 1e-9:
                out.append(
                    Finding(
                        "hole_bend",
                        f"A hole, slot or cut-out is {gap:.3g} mm from a bend line, under "
                        f"{bend_gap:g} mm, so it will stretch when bent. Move it away from the "
                        "bend.",
                    )
                )
                break
    for i, a in enumerate(inner):
        for b in inner[i + 1 :]:
            gap = _poly_dist(a, b)
            if gap < hole_gap - 1e-9:
                out.append(
                    Finding(
                        "hole_hole",
                        f"Two holes are {gap:.3g} mm apart, under {hole_gap:g} mm. Move them "
                        "apart.",
                    )
                )
    flange = k("min_flange", 4.0) * t
    for bend in drawing.bends:
        mid = ((bend.a[0] + bend.b[0]) / 2, (bend.a[1] + bend.b[1]) / 2)
        ax, ay = bend.b[0] - bend.a[0], bend.b[1] - bend.a[1]
        size = math.hypot(ax, ay) or 1.0
        nx, ny = -ay / size, ax / size
        for sign in (1.0, -1.0):
            reach = _ray(mid, (nx * sign, ny * sign), outer)
            if reach is not None and reach < flange - 1e-9:
                out.append(
                    Finding(
                        "short_flange",
                        f"A flange is {reach:.3g} mm long past its bend line, under {flange:g} "
                        "mm, too short for the brake to hold. Make the flange longer.",
                    )
                )
    return out


def _ray(origin: Vec2, d: Vec2, poly: list[Vec2]) -> float | None:
    """How far from ``origin`` along ``d`` the ray meets the loop, or None."""
    best: float | None = None
    for a, b in zip(poly, poly[1:] + poly[:1], strict=True):
        ex, ey = b[0] - a[0], b[1] - a[1]
        den = d[0] * ey - d[1] * ex
        if abs(den) < 1e-12:
            continue
        tx, ty = a[0] - origin[0], a[1] - origin[1]
        s = (tx * ey - ty * ex) / den
        u = (tx * d[1] - ty * d[0]) / den
        if s > 1e-9 and -1e-9 <= u <= 1 + 1e-9 and (best is None or s < best):
            best = s
    return best
