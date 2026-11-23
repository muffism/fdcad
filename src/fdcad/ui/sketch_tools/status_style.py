"""Sketch status shown by line and point shape as well as colour (TR292, D769).

Each status has its own line, so it reads without telling colours apart:

- under defined: a thin solid line, hollow points;
- fully defined: a heavier solid line, filled points;
- over defined (conflicting): a heavy dotted line, square points.

Construction geometry keeps its dash and dot line, unlike every status. A
selected curve is drawn a little heavier as well as in the accent. Pure Python
apart from the Qt pen style names.
"""

from __future__ import annotations

from PySide6.QtCore import Qt

#: Pen width and style per status.
_LINES: dict[str, tuple[float, Qt.PenStyle]] = {
    "under": (1.2, Qt.PenStyle.SolidLine),
    "full": (2.0, Qt.PenStyle.SolidLine),
    "over": (2.2, Qt.PenStyle.DotLine),
}
#: Point mark per status: a ring, a dot or a square.
POINT_SHAPES = {"under": "ring", "full": "dot", "over": "square"}


def line_style(
    status: str, construction: bool, selected: bool = False
) -> tuple[float, Qt.PenStyle]:
    """The pen width and style of a curve with this status."""
    if construction:
        return (1.4 if selected else 1.0), Qt.PenStyle.DashDotLine
    width, style = _LINES.get(status, _LINES["under"])
    return (width + 0.6 if selected else width), style
