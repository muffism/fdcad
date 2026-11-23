"""The start picture (DECISIONS D1033, D1034): shown at once, while the window is made.

Loading the window takes a second or more, and before this nothing was on screen
during that time. The picture is FDCAD's brand tile: the mark, the name, what
FDCAD is and the version, in the brand colours (the same in every theme). It goes
away when the main window appears.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen, QWidget

from fdcad import __version__
from fdcad.ui.themes.theme import BRAND
from fdcad.ui.themes.typography import Role, type_font

NAME = "FDCAD"
WHAT = "Parametric part modeler"
STARTING = "Starting..."
VERSION = "Version {version}"
#: Size in logical pixels: the picture, the mark, the outer gap and the corner radius.
WIDTH, HEIGHT, ICON, GAP, RADIUS = 480, 240, 112, 36, 14


def splash_pixmap(icon: QIcon, ratio: float = 1.0) -> QPixmap:
    """The picture: the mark on the left, the name and what FDCAD is beside it, the
    version and a short line along the bottom."""
    pixmap = QPixmap(round(WIDTH * ratio), round(HEIGHT * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    fill = QLinearGradient(QPointF(0, 0), QPointF(WIDTH, HEIGHT))
    fill.setColorAt(0, QColor(BRAND["tile_top"]))
    fill.setColorAt(1, QColor(BRAND["tile_bottom"]))
    plate = QPainterPath()
    plate.addRoundedRect(QRectF(0.5, 0.5, WIDTH - 1, HEIGHT - 1), RADIUS, RADIUS)
    painter.fillPath(plate, fill)
    painter.setPen(QPen(QColor(BRAND["tile_line"]), 1))
    painter.drawPath(plate)
    top = (HEIGHT - ICON) // 2 - 12
    icon.paint(painter, QRect(GAP, top, ICON, ICON))
    left = GAP + ICON + 28
    words = QRect(left, top, WIDTH - left - GAP, ICON)
    painter.setFont(type_font(Role.DISPLAY))
    painter.setPen(QColor(BRAND["on_tile"]))
    flags = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    painter.drawText(words.adjusted(0, 0, 0, -26), flags, NAME)
    painter.setFont(type_font(Role.BODY))
    painter.setPen(QColor(BRAND["on_tile_soft"]))
    painter.drawText(words.adjusted(1, 46, 0, 0), flags, WHAT)
    foot = QRect(GAP, HEIGHT - 44, WIDTH - 2 * GAP, 24)
    painter.setFont(type_font(Role.CAPTION))
    painter.drawText(foot, flags, STARTING)
    painter.drawText(
        foot,
        int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
        VERSION.format(version=__version__),
    )
    painter.end()
    return pixmap


def show_splash(icon: QIcon) -> QSplashScreen:
    """Show the start picture now and return it; call ``finish`` when the window is up."""
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    screen = app.primaryScreen()
    ratio = screen.devicePixelRatio() if screen is not None else 1.0
    splash = QSplashScreen(splash_pixmap(icon, ratio))
    splash.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)  # rounded corners
    splash.show()
    app.processEvents()  # painted before the slow imports start
    return splash


def finish(splash: QSplashScreen | None, window: QWidget) -> None:
    """Close the picture once ``window`` is shown."""
    if splash is not None:
        splash.finish(window)
        splash.deleteLater()
