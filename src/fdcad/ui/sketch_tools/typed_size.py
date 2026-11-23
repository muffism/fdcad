"""Sizes typed while a shape is being drawn (TOOL_SPEC T15.6, DECISIONS D444).

Typing a number while a line, rectangle, circle, arc or slot is being drawn
opens the value box for its length, size or radius. Enter locks that size:
the shape keeps following the cursor for its direction, but its size stays.
When the shape is finished (the next click, or Enter again) it gets the
matching driving dimension with the typed text, in the same undo step, as if
Smart Dimension had been used.

The locks live on the tool (``tool.locks``: target name to Param). Pure
Python, no Qt.
"""

from __future__ import annotations

import math
from typing import Any

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Arc, Line
from fdcad.ui.sketch_tools.geometry import Vec, dist
from fdcad.ui.sketch_tools.inference import Snap

LINES = ("line", "centerline", "midpoint_line")
RECTANGLES = ("corner_rectangle", "center_rectangle")
ROUND = ("circle", "center_arc")
STRAIGHT_SLOTS = ("straight", "centre_straight")
#: Three click shapes (D511): the width after the first click, the height after the second.
THREE_POINT = ("three_point_corner_rectangle", "three_point_center_rectangle", "parallelogram")


def size_target(tool: Any) -> str | None:
    """What a typed number sets now: "length", "width", "height", "radius" or None."""
    if tool is None:
        return None
    count = len(tool.clicks)
    locks = tool.locks
    name = tool.name
    if name in LINES:
        return "length" if count == 1 and not getattr(tool, "arc_mode", False) else None
    if name in RECTANGLES and count == 1:
        return "height" if "width" in locks and "height" not in locks else "width"
    if name in ROUND and count == 1:
        return "radius"
    if name in THREE_POINT:
        return {1: "width", 2: "height"}.get(count)
    if name == "slot" and getattr(tool, "kind", "") in STRAIGHT_SLOTS:
        return {1: "length", 2: "width"}.get(count)
    return None


def next_target(tool: Any) -> str | None:
    """The size to ask for after one was locked: a rectangle's height, else None."""
    if tool.name in RECTANGLES and len(tool.clicks) == 1 and "height" not in tool.locks:
        return "height"
    return None


def _along(start: Vec, snap: Snap, length: float) -> Snap:
    """The point ``length`` from ``start`` towards the cursor (along +X when on it)."""
    dx, dy = snap.x - start[0], snap.y - start[1]
    n = math.hypot(dx, dy)
    if n < 1e-12:
        dx, dy, n = 1.0, 0.0, 1.0
    at = (start[0] + dx / n * length, start[1] + dy / n * length)
    if dist(at, snap.xy) < 1e-9:
        return snap
    return Snap("free", at[0], at[1])


def _slot_ends(tool: Any) -> tuple[Vec, Vec]:
    first, second = tool.clicks[0].xy, tool.clicks[1].xy
    if tool.kind == "centre_straight":
        return (2 * first[0] - second[0], 2 * first[1] - second[1]), second
    return first, second


def _beside(a: Vec, b: Vec, snap: Snap, gap: float) -> Snap:
    """The point ``gap`` to the cursor's side of the line through ``a`` and ``b``."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy)
    if n < 1e-12:
        return snap
    ux, uy = dx / n, dy / n
    t = (snap.x - a[0]) * ux + (snap.y - a[1]) * uy
    side = (snap.x - a[0]) * -uy + (snap.y - a[1]) * ux
    sign = 1.0 if side >= 0 else -1.0
    at = (a[0] + t * ux - uy * gap * sign, a[1] + t * uy + ux * gap * sign)
    return Snap("free", at[0], at[1])


def constrain(tool: Any, snap: Snap) -> Snap:
    """``snap`` moved so the shape has the locked sizes. Unchanged without locks."""
    locks: dict[str, Param] = tool.locks
    if not locks or not tool.clicks:
        return snap
    count = len(tool.clicks)
    start = tool.clicks[0].xy
    name = tool.name
    if name in LINES and count == 1 and "length" in locks and not getattr(tool, "arc_mode", False):
        # A midpoint line starts at its middle, so its end is half the length away.
        share = 0.5 if name == "midpoint_line" else 1.0
        return _along(start, snap, locks["length"].value * share)
    if name in ROUND and count == 1 and "radius" in locks:
        return _along(start, snap, locks["radius"].value)
    if name in RECTANGLES and count == 1:
        half = 0.5 if name == "center_rectangle" else 1.0
        x, y = snap.xy
        if "width" in locks:
            x = start[0] + math.copysign(locks["width"].value * half, (x - start[0]) or 1.0)
        if "height" in locks:
            y = start[1] + math.copysign(locks["height"].value * half, (y - start[1]) or 1.0)
        return snap if (x, y) == snap.xy else Snap("free", x, y)
    if name in THREE_POINT:
        return _three_point(tool, snap, locks)
    if name == "slot" and getattr(tool, "kind", "") in STRAIGHT_SLOTS:
        if count == 1 and "length" in locks:
            share = 0.5 if tool.kind == "centre_straight" else 1.0
            return _along(start, snap, locks["length"].value * share)
        if count == 2 and "width" in locks:
            a, b = _slot_ends(tool)
            return _beside(a, b, snap, locks["width"].value / 2)
    return snap


def _three_point(tool: Any, snap: Snap, locks: dict[str, Param]) -> Snap:
    """The second or third point of a D511 shape moved to its locked width or height."""
    count = len(tool.clicks)
    share = 0.5 if tool.name == "three_point_center_rectangle" else 1.0
    if count == 1 and "width" in locks:
        return _along(tool.clicks[0].xy, snap, locks["width"].value * share)
    if count == 2 and "height" in locks:
        a, b = tool.clicks[0].xy, tool.clicks[1].xy
        if tool.name == "parallelogram":
            return _along(b, snap, locks["height"].value)
        return _beside(a, b, snap, locks["height"].value * share)
    return snap


def dimensions(tool: Any) -> list[tuple[str, list[str], Param]]:
    """The dimensions a just finished shape gets for its locked sizes: (type, ids, value)."""
    locks: dict[str, Param] = tool.locks
    drawn: list[str] = tool.drawn
    sk = tool.edit.sketch
    if not locks or not drawn:
        return []
    out: list[tuple[str, list[str], Param]] = []
    name = tool.name
    if name in LINES and "length" in locks and isinstance(sk.entities.get(drawn[0]), Line):
        out.append(("distance", [drawn[0]], locks["length"]))
    elif (name in RECTANGLES or name in THREE_POINT) and len(drawn) >= 2:
        if "width" in locks:
            out.append(("distance", [drawn[0]], locks["width"]))
        if "height" in locks:
            out.append(("distance", [drawn[1]], locks["height"]))
    elif name in ROUND and "radius" in locks:
        out.append(("radius", [drawn[0]], locks["radius"]))
    elif name == "slot":
        axis = getattr(tool, "axis", None)
        if "length" in locks and isinstance(axis, str) and axis in sk.entities:
            out.append(("distance", [axis], locks["length"]))
        arcs = [cid for cid in drawn if isinstance(sk.entities.get(cid), Arc)]
        if "width" in locks and arcs:
            out.append(("diameter", [arcs[0]], locks["width"]))
    return out


def add_dimensions(tool: Any) -> list[str]:
    """Add the dimensions of the locked sizes to the sketch. The caller checkpoints.

    A dimension that would over define the sketch becomes a reference one (T11.5).
    Returns the new dimension ids.
    """
    added: list[str] = []
    failed = made_reference = 0
    for dtype, ids, param in dimensions(tool):
        try:
            dim = tool.edit.add_dimension(dtype, ids, Param(param.expr, param.value))
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            failed += 1
            continue
        if tool.edit.make_reference_if_over(dim.id):
            made_reference += 1
        added.append(dim.id)
    # Both happened without a word (audit D2 item 13, D743).
    from fdcad.ui.sketch_tools.tool_text import TYPED_NOT_DIMENSIONED, TYPED_REFERENCE

    if failed:
        tool.edit.note = TYPED_NOT_DIMENSIONED.format(n=failed)
    elif made_reference:
        tool.edit.note = TYPED_REFERENCE.format(n=made_reference)
    return added
