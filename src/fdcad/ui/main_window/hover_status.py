"""The hovered item in the status bar (TR221 item 3, D1611)."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab

LENGTH = "Length {length}"
RADIUS = "Radius {radius}"
ANGLE = "Angle {angle} deg"


def hover_text(tab: DocumentTab) -> str:
    """Length and radius of the edge under the pointer, or the angle between the flat
    face under it and the one picked flat face; "" otherwise."""
    from fdcad.core.hover_info import hover_info
    from fdcad.ui.sketch_tools.canvas import format_length

    under = getattr(tab.viewport, "shape_under_cursor", None)
    shape = under() if under is not None else None
    if shape is None:
        return ""
    try:
        info = hover_info(shape, list(tab.selection))
    except Exception:
        return ""
    if info is None:
        return ""
    units = tab.session.document.units
    parts = []
    if info.length is not None:
        parts.append(LENGTH.format(length=format_length(info.length, units)))
    if info.radius is not None:
        parts.append(RADIUS.format(radius=format_length(info.radius, units)))
    if info.angle is not None:
        parts.append(ANGLE.format(angle=f"{math.degrees(info.angle):.4g}"))
    return "  ".join(parts)
