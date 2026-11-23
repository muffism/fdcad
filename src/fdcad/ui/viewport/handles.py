"""Drag handle logic without drawing (TOOL_SPEC T5.2.2 to T5.2.5, T6.3; DECISIONS D146, D147).

Everything here is plain arithmetic on screen points and handle values, so it
is tested without a GPU. The 3D view only measures the cursor, calls these
functions and moves its arrow.

- The ruler runs along a length handle from a little behind its start, or
  round an angle handle's circle. While the cursor is near it, the value snaps
  to the tick step; away from it the value is free.
- A handle that ``flips`` and is dragged back past its start turns into a
  drag the other way: the value stays positive and ``flipped`` says the
  direction is reversed.
- The value beside the handle is a label; clicking inside its box opens the
  value box there.
- With Alt held, a handle that ``snaps`` takes its end from a part vertex or
  face under the cursor (T5.2.4, D525): the travel is the distance from the
  handle's base along its direction to that point.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise

from fdcad.core.features.base import PreviewHandle

#: How near the ruler the cursor must be for ticks to snap (logical pixels).
RULER_PICK_PX = 14.0
#: Ticks drawn behind the start of a length ruler, so a flip can be seen coming.
RULER_BEHIND_TICKS = 2
#: Most ticks a ruler shows (the drag still works past its end).
RULER_MAX_TICKS = 200
#: The smallest value a drag may set: mm for lengths.
MIN_LENGTH = 0.01
#: A dragged angle stays between these (radians).
MIN_ANGLE = math.radians(0.1)
MAX_ANGLE = 2 * math.pi

Point = tuple[float, float]


def snap(value: float, step: float) -> float:
    """``value`` rounded to the nearest whole number of steps (never below one step)."""
    if step <= 0:
        return value
    return max(round(value / step), 1) * step


def segment_distance(p: Point, a: Point, b: Point) -> float:
    """Distance from ``p`` to the segment ``a`` to ``b``."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    squared = dx * dx + dy * dy
    t = 0.0 if squared == 0 else ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / squared
    t = min(max(t, 0.0), 1.0)
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


def polyline_distance(p: Point, points: list[Point]) -> float:
    """Distance from ``p`` to a chain of screen points."""
    if not points:
        return math.inf
    if len(points) == 1:
        return math.hypot(p[0] - points[0][0], p[1] - points[0][1])
    return min(segment_distance(p, a, b) for a, b in pairwise(points))


def ruler_span(handle: PreviewHandle) -> tuple[float, float]:
    """Where a ruler starts and ends, as travel from the handle's base (mm or radians).

    A length ruler starts a few ticks behind the base and reaches at least ten
    ticks or twice the current travel. An angle ruler is the full circle.
    """
    step = handle.step
    if handle.is_angle:
        return 0.0, 2 * math.pi
    if step <= 0:
        return 0.0, abs(handle.travel)
    reach = max(2 * abs(handle.travel), 10 * step)
    reach = min(math.ceil(reach / step), RULER_MAX_TICKS) * step
    return -RULER_BEHIND_TICKS * step if handle.flips else 0.0, reach


def ruler_ticks(handle: PreviewHandle) -> list[tuple[float, bool]]:
    """Tick positions along the ruler (travel from the base) and whether each is a major tick.

    Every fifth tick is major (every 45 degrees on an angle ruler would be nine,
    so angle rulers mark every 45 degrees instead).
    """
    step = handle.step
    if step <= 0:
        return []
    start, end = ruler_span(handle)
    first, last = math.ceil(start / step - 1e-9), math.floor(end / step + 1e-9)
    if handle.is_angle:
        last = min(last, round(2 * math.pi / step) - 1)
    ticks = []
    for k in range(first, last + 1):
        t = k * step
        major = (k % 9 == 0) if handle.is_angle else (k % 5 == 0)
        ticks.append((t, major))
    return ticks


@dataclass
class HandleDrag:
    """One drag of a handle, from press to release.

    ``handle`` is the handle as it was when the drag started; distances are
    always measured along it, even after the preview flips. ``offset`` is
    where the cursor grabbed the arrow, relative to its value.
    """

    handle: PreviewHandle
    offset: float = 0.0
    flipped: bool = False

    def update(self, distance: float, on_ruler: bool) -> float:
        """The value for a cursor ``distance`` along the handle; also sets ``flipped``."""
        h = self.handle
        raw = h.value_at(distance) - self.offset
        if h.is_angle:
            value = snap(raw, h.step * h.scale) if on_ruler else raw
            return min(max(value, MIN_ANGLE), MAX_ANGLE)
        self.flipped = h.flips and raw < 0
        value = -raw if self.flipped else raw
        if on_ruler:
            value = snap(value, h.step * h.scale)
        return max(value, MIN_LENGTH)

    def snap_to(self, travel: float) -> float:
        """The value that puts the end ``travel`` mm along the handle (Alt snap, D525).

        Behind the base a handle that ``flips`` flips; others stop at their
        smallest value. Also sets ``flipped``.
        """
        h = self.handle
        raw = h.value_at(travel)
        self.flipped = h.flips and raw < 0
        value = -raw if self.flipped else raw
        return max(value, MIN_LENGTH)

    def travel(self, value: float) -> float:
        """Signed travel along the starting handle for ``value`` (negative once flipped)."""
        t = value / self.handle.scale
        return -t if self.flipped else t


Vec3 = tuple[float, float, float]


def travel_to(handle: PreviewHandle, target: Vec3) -> float:
    """Signed distance from ``handle``'s base along its direction to ``target`` (mm)."""
    b, d = handle.base, handle.direction
    n = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2) or 1.0
    return sum((target[i] - b[i]) * d[i] for i in range(3)) / n


def snap_point(
    handle: PreviewHandle,
    picked: Vec3,
    plane: tuple[Vec3, Vec3] | None = None,
) -> Vec3:
    """Where an Alt snap ends for a face picked at ``picked`` (T5.2.4, D525).

    ``plane`` is the face's (point, unit normal) when the face is flat. A flat
    face parallel to the sketch plane (square to the handle) gives its plane,
    so the depth is exactly its distance; any other face gives the point under
    the cursor.
    """
    if plane is not None:
        point, normal = plane
        d = handle.direction
        n = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2) or 1.0
        along = abs(sum(normal[i] * d[i] for i in range(3))) / n
        if along > 1 - 1e-9:
            return point
    return picked


def label_box(anchor: Point, text: str, height: float) -> tuple[float, float, float, float]:
    """Screen box (left, top, right, bottom) of a value label drawn at ``anchor``.

    The label's text starts at the anchor and sits on it. Its width is
    estimated from the character count, with a margin, so a click on or just
    around the text counts.
    """
    width = max(len(text), 1) * height * 0.62
    margin = height * 0.4
    x, y = anchor
    return x - margin, y - height - margin, x + width + margin, y + margin


def label_hit(anchor: Point, text: str, height: float, cursor: Point) -> bool:
    """True when ``cursor`` is on the value label."""
    left, top, right, bottom = label_box(anchor, text, height)
    return left <= cursor[0] <= right and top <= cursor[1] <= bottom


Box = tuple[float, float, float, float]


def boxes_overlap(a: Box, b: Box) -> bool:
    """True when two screen boxes (left, top, right, bottom) overlap."""
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def spread_labels(boxes: list[Box], taken: list[Box] | None = None) -> list[float]:
    """How far down (pixels) each label moves so it covers no earlier one (T15.2).

    Labels are placed in order; a label that overlaps one already placed (or a
    box in ``taken``, such as the drag handle's value) moves down by its own
    height until it is clear.
    """
    placed = list(taken or [])
    out: list[float] = []
    for left, top, right, bottom in boxes:
        height = max(bottom - top, 1.0)
        dy = 0.0
        for _ in range(len(placed) + 1):
            moved = (left, top + dy, right, bottom + dy)
            if not any(boxes_overlap(moved, other) for other in placed):
                break
            dy += height
        placed.append((left, top + dy, right, bottom + dy))
        out.append(dy)
    return out
