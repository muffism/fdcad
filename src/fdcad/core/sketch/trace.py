"""Trace a sketch picture into curves (TUTORIAL_REVIEW_SPEC_2 TR116 item 2, D1711).

The user picks a region of the picture by colour (a click: every touching pixel of
about that colour) or by a box (the pixels inside it that differ from the box's
corner colour, the background). The region's outline becomes closed loops of
sketch lines the user can edit. No Qt: the user interface hands over the pixels
as a numpy array.

Pixel work is whole array numpy (CLAUDE.md 5A.2). Images are first reduced so
the longer side is at most ``MAX_SIDE`` pixels, which bounds the outline walk.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

import numpy as np
from numpy.typing import NDArray

from fdcad.core.sketch.model import Line, Sketch
from fdcad.core.sketch.picture import Picture

Vec = tuple[float, float]
Mask = NDArray[np.bool_]
#: The longest image side the trace works on, in pixels.
MAX_SIDE = 400
#: Loops with fewer pixels than this are specks and are left out.
MIN_PIXELS = 4


class TraceError(ValueError):
    """Nothing to trace; the message says what to do."""


def reduce(pixels: Any) -> tuple[NDArray[np.float32], int]:
    """RGB pixels with the longer side at most ``MAX_SIDE``, and the step taken."""
    rgb = np.asarray(pixels, dtype=np.float32)[..., :3]
    h, w = rgb.shape[:2]
    step = max(1, math.ceil(max(h, w) / MAX_SIDE))
    return rgb[::step, ::step], step


def similar(rgb: NDArray[np.float32], colour: NDArray[np.float32], tolerance: float) -> Mask:
    """True where a pixel is within ``tolerance`` (0 to 1) of ``colour``."""
    d = np.sqrt(((rgb - colour) ** 2).sum(axis=-1)) / (255.0 * math.sqrt(3.0))
    out: Mask = d <= max(0.0, min(1.0, tolerance))
    return out


def grow(mask: Mask, seed: tuple[int, int]) -> Mask:
    """The part of ``mask`` joined to pixel ``seed`` (row, column), by sides."""
    region = np.zeros_like(mask)
    if not mask[seed]:
        return region
    region[seed] = True
    while True:
        more = region.copy()
        more[1:] |= region[:-1]
        more[:-1] |= region[1:]
        more[:, 1:] |= region[:, :-1]
        more[:, :-1] |= region[:, 1:]
        more &= mask
        if np.array_equal(more, region):
            return region
        region = more


def colour_region(pixels: Any, at: tuple[int, int], tolerance: float) -> tuple[Mask, int]:
    """The touching pixels of about the colour at pixel ``at`` (row, column of the full
    image), on the reduced image, and its step."""
    rgb, step = reduce(pixels)
    r = min(at[0] // step, rgb.shape[0] - 1)
    c = min(at[1] // step, rgb.shape[1] - 1)
    return grow(similar(rgb, rgb[r, c], tolerance), (r, c)), step


def box_region(
    pixels: Any, a: tuple[int, int], b: tuple[int, int], tolerance: float
) -> tuple[Mask, int]:
    """The pixels inside the box from ``a`` to ``b`` (rows, columns of the full image)
    that differ from the colour at the box's first corner, and the step."""
    rgb, step = reduce(pixels)
    h, w = rgb.shape[:2]
    r0, r1 = sorted((min(a[0] // step, h - 1), min(b[0] // step, h - 1)))
    c0, c1 = sorted((min(a[1] // step, w - 1), min(b[1] // step, w - 1)))
    inside = np.zeros((h, w), dtype=bool)
    inside[r0 : r1 + 1, c0 : c1 + 1] = True
    background = rgb[r0, c0]
    out: Mask = inside & ~similar(rgb, background, tolerance)
    return out, step


def outline_loops(region: Mask) -> list[list[Vec]]:
    """Closed outlines of ``region`` as pixel corner points (x is the column, y the row
    from the top), each with the region on its left when walked in screen axes."""
    pad = np.pad(region, 1)
    inner = pad[1:-1, 1:-1]
    edges: list[NDArray[np.int64]] = []
    # Each side of a region pixel with no region pixel beyond it is an edge piece.
    for dr, dc, start, end in (
        (-1, 0, (0, 1), (0, 0)),  # top side, walked right to left
        (1, 0, (1, 0), (1, 1)),  # bottom side, left to right
        (0, -1, (0, 0), (1, 0)),  # left side, down
        (0, 1, (1, 1), (0, 1)),  # right side, up
    ):
        beyond = pad[1 + dr : pad.shape[0] - 1 + dr, 1 + dc : pad.shape[1] - 1 + dc]
        rows, cols = np.nonzero(inner & ~beyond)
        seg = np.stack(
            [cols + start[1], rows + start[0], cols + end[1], rows + end[0]], axis=1
        ).astype(np.int64)
        edges.append(seg)
    all_edges = np.concatenate(edges) if edges else np.zeros((0, 4), dtype=np.int64)
    nexts: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, (x0, y0, _x1, _y1) in enumerate(all_edges.tolist()):
        nexts[(x0, y0)].append(i)
    used = np.zeros(len(all_edges), dtype=bool)
    loops: list[list[Vec]] = []
    for first in range(len(all_edges)):
        if used[first]:
            continue
        loop: list[Vec] = []
        i = first
        while not used[i]:
            used[i] = True
            x0, y0, x1, y1 = (int(v) for v in all_edges[i])
            loop.append((float(x0), float(y0)))
            choices = [k for k in nexts[(x1, y1)] if not used[k]]
            if not choices:
                break
            i = choices[0]
        if len(loop) >= MIN_PIXELS:
            loops.append(loop)
    return loops


def simplify(loop: list[Vec], tolerance: float) -> list[Vec]:
    """``loop`` with points dropped while the outline stays within ``tolerance``
    (Douglas and Peucker), as an open list whose last point joins the first."""
    if len(loop) < 4:
        return loop
    # Start at an extreme point, which is always a true corner of the outline.
    first = min(range(len(loop)), key=lambda k: (loop[k][0] + loop[k][1], loop[k][0]))
    loop = loop[first:] + loop[:first]
    pts = np.array([*loop, loop[0]], dtype=float)
    keep = np.zeros(len(pts), dtype=bool)
    keep[0] = keep[-1] = True
    # Split at the point furthest from the first, so the loop has two ends.
    far = int(np.argmax(np.hypot(*(pts - pts[0]).T)))
    keep[far] = True
    stack = [(0, far), (far, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        seg = pts[b] - pts[a]
        n = math.hypot(*seg)
        rel = pts[a + 1 : b] - pts[a]
        d = np.abs(rel[:, 0] * seg[1] - rel[:, 1] * seg[0]) / n if n > 0 else np.hypot(*rel.T)
        k = int(np.argmax(d))
        if d[k] > tolerance:
            m = a + 1 + k
            keep[m] = True
            stack += [(a, m), (m, b)]
    out = [(float(x), float(y)) for x, y in pts[keep][:-1]]
    # The loop's start was kept only as a split point: drop it (and any other point)
    # where the outline runs straight on through it.
    changed = True
    while changed and len(out) > 3:
        changed = False
        for k in range(len(out)):
            pa, pm, pb = out[k - 1], out[k], out[(k + 1) % len(out)]
            n = math.dist(pa, pb)
            if n <= 0:
                continue
            off = abs((pm[0] - pa[0]) * (pb[1] - pa[1]) - (pm[1] - pa[1]) * (pb[0] - pa[0])) / n
            if off <= tolerance:
                del out[k]
                changed = True
                break
    return out if len(out) >= 3 else loop


def to_sketch(pic: Picture, size: tuple[int, int], p: Vec) -> Vec:
    """A pixel corner point (column, row from the top) of an image of ``size``
    (width, height in pixels) in sketch mm, with the picture's flips and turn."""
    w, h = size
    u = p[0] / w * pic.width
    v = (h - p[1]) / h * pic.height
    if pic.flip_h:
        u = pic.width - u
    if pic.flip_v:
        v = pic.height - v
    c, s = math.cos(pic.angle), math.sin(pic.angle)
    return pic.origin[0] + u * c - v * s, pic.origin[1] + u * s + v * c


def trace(
    sketch: Sketch,
    pic: Picture,
    region: Mask,
    step: int,
    full_size: tuple[int, int],
    tolerance_px: float = 1.0,
) -> list[str]:
    """Add the outline of ``region`` (on the image reduced by ``step``) to ``sketch`` as
    closed loops of lines. Returns the new line ids."""
    loops = outline_loops(region)
    if not loops:
        raise TraceError(
            "Nothing to trace there. Click on the shape's colour, or draw a box around it."
        )
    made: list[str] = []
    for loop in loops:
        pts = [
            to_sketch(pic, full_size, (x * step, y * step)) for x, y in simplify(loop, tolerance_px)
        ]
        ids = [sketch.add_point(*p) for p in pts]
        for k, pid in enumerate(ids):
            nid = ids[(k + 1) % len(ids)]
            lid = sketch.new_id()
            sketch.entities[lid] = Line(lid, pid, nid)
            made.append(lid)
    return made
