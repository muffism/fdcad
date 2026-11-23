"""The one type scale for the whole app (UI polish spec U2.1, U2.4, D660).

Every text uses the system UI font at one of four roles:

* caption: 11 px, for captions, units and small labels
* body: 13 px, for labels, fields, lists and the tree
* title: 13 px semibold, for panel and group titles
* dialog title: 15 px semibold

Sizes are logical pixels, so Qt scales them with the display setting. They are
stored as point sizes (pixels times 72 over the screen's logical dots per inch)
so code that scales ``pointSizeF()`` keeps working. No widget picks its own
font size: it asks :func:`type_font` for a role.
"""

from __future__ import annotations

from enum import StrEnum

from PySide6.QtGui import QFont, QGuiApplication

CAPTION_PX = 11
BODY_PX = 13
TITLE_PX = 13
DIALOG_TITLE_PX = 15
#: The brand name on the start picture and in About (D1034). Not part of the scale
#: for the working UI.
DISPLAY_PX = 34
#: Every size the app uses, for the scale test (U11.1).
SCALE_PX = (CAPTION_PX, BODY_PX, TITLE_PX, DIALOG_TITLE_PX)


class Role(StrEnum):
    """A place in the type scale."""

    CAPTION = "caption"
    BODY = "body"
    TITLE = "title"
    DIALOG_TITLE = "dialog_title"
    DISPLAY = "display"


_SIZES = {
    Role.CAPTION: (CAPTION_PX, False),
    Role.BODY: (BODY_PX, False),
    Role.TITLE: (TITLE_PX, True),
    Role.DIALOG_TITLE: (DIALOG_TITLE_PX, True),
    Role.DISPLAY: (DISPLAY_PX, True),
}


def logical_dpi() -> float:
    """Logical dots per inch of the main screen (96 on Windows, 72 on macOS)."""
    screen = QGuiApplication.primaryScreen() if QGuiApplication.instance() else None
    dpi = screen.logicalDotsPerInchY() if screen is not None else 96.0
    return dpi if dpi > 0 else 96.0


def points(px: float) -> float:
    """Point size that draws ``px`` logical pixels tall on the main screen."""
    return px * 72.0 / logical_dpi()


def type_font(role: Role, base: QFont | None = None) -> QFont:
    """The UI font (or ``base``) at a role of the type scale."""
    font = QFont(base) if base is not None else QGuiApplication.font()
    px, semibold = _SIZES[role]
    font.setPointSizeF(points(px))
    font.setWeight(QFont.Weight.DemiBold if semibold else QFont.Weight.Normal)
    return font


def tabular(font: QFont) -> QFont:
    """``font`` with tabular figures, where the font has them (U2.4)."""
    result = QFont(font)
    result.setFeature(QFont.Tag("tnum"), 1)
    return result


def apply_type_scale(app: QGuiApplication) -> None:
    """Set the application font to the body size of the system UI font."""
    font = app.font()
    wanted = points(BODY_PX)
    if abs(font.pointSizeF() - wanted) > 0.01:
        font.setPointSizeF(wanted)
        app.setFont(font)
