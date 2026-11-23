"""The cursor while selection filters are on: an arrow with a small funnel (T14.3.2).

Drawn in code, an original design, so it needs no image file and scales with
the display.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QPainter, QPen, QPixmap, QPolygonF

_CACHE: dict[tuple[float, str], QCursor] = {}


def filter_pixmap(ratio: float = 1.0, funnel_colour: str | None = None) -> QPixmap:
    """The cursor picture: 32 by 32 logical pixels at ``ratio`` device pixels each.

    The funnel uses the theme's selection colour unless ``funnel_colour`` is given.
    """
    from fdcad.ui.themes.theme import DATA, palette

    fill, line = QColor(DATA["cursor_fill"]), QColor(DATA["cursor_line"])
    size = round(32 * ratio)
    pixmap = QPixmap(size, size)
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    arrow = QPolygonF(
        [
            QPointF(1, 1),
            QPointF(1, 17),
            QPointF(5, 13),
            QPointF(8, 20),
            QPointF(11, 19),
            QPointF(8, 12),
            QPointF(13, 12),
        ]
    )
    painter.setPen(QPen(line, 1))
    painter.setBrush(fill)
    painter.drawPolygon(arrow)
    funnel = QPolygonF(
        [
            QPointF(15, 17),
            QPointF(27, 17),
            QPointF(23, 23),
            QPointF(23, 29),
            QPointF(19, 31),
            QPointF(19, 23),
        ]
    )
    painter.setPen(QPen(fill, 1))
    painter.setBrush(QColor(funnel_colour or palette().selection))
    painter.drawPolygon(funnel)
    painter.end()
    return pixmap


def filter_cursor() -> QCursor:
    """The filter cursor for the main screen's pixel ratio, with its hot spot at the tip."""
    screen = QGuiApplication.primaryScreen()
    ratio = screen.devicePixelRatio() if screen is not None else 1.0
    from fdcad.ui.themes.theme import palette

    key = (ratio, palette().selection)
    if key not in _CACHE:
        _CACHE[key] = QCursor(filter_pixmap(ratio, key[1]), 1, 1)
    return _CACHE[key]
