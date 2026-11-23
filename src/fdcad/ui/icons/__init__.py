"""Original FDCAD icon set (PHASE1_CORRECTIONS C5).

Icons are SVG files in this folder, drawn on a 24 x 24 grid. Strokes and fills
use the colour ``currentColor`` (plus the literals ``#ACCENT`` for the active
part, ``#DANGER`` for the red cancel and error marks and ``#WARNING`` for the
warning mark), which ``icon()`` replaces with the current theme's tokens, so
one file serves all four themes. Disabled icons are drawn whole in the theme's
disabled colour (U5.4, D671). ``NAMES.md`` lists every icon and ``audit.py``
holds the drawing rules (U5.1, D670).

Use ``icon("sketch.line")`` anywhere in the UI. The name maps to
``sketch.line.svg``. A missing file gives an empty icon, never an error.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QIconEngine, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from fdcad.ui.preferences.settings import Theme
from fdcad.ui.themes.theme import SCHEMES, current, scheme_for

ICON_DIR = Path(__file__).parent

ACCENT = {False: SCHEMES[Theme.LIGHT][1].accent, True: SCHEMES[Theme.DARK][1].accent}
SIZES = (16, 20, 24, 32, 48)


def listed_names() -> list[str]:
    """Every icon name listed in ``NAMES.md``, in file order."""
    text = (ICON_DIR / "NAMES.md").read_text(encoding="utf-8")
    return [
        line[2:].strip()
        for line in text.splitlines()
        if line.startswith("- ") and " " not in line[2:].strip()
    ]


def icon_path(name: str) -> Path:
    """The SVG file for an icon name."""
    return ICON_DIR / f"{name}.svg"


def colours(theme: Theme | None = None) -> dict[str, str]:
    """The colour each icon placeholder becomes in ``theme`` (default: the current one)."""
    scheme, chrome, _dark = scheme_for(theme or current())
    return {
        "currentColor": chrome.text,
        "#ACCENT": chrome.accent,
        "#CUT": str(getattr(chrome, "cut", chrome.accent)),  # material taken away (D1034)
        "#DANGER": chrome.danger,
        "#WARNING": scheme.state_warning,
    }


def disabled_colour(theme: Theme | None = None) -> str:
    """The theme's colour for disabled icons: its disabled token, else its muted text."""
    chrome = scheme_for(theme or current())[1]
    return str(getattr(chrome, "disabled", chrome.muted))


def themed_text(
    name: str, theme: Theme | None = None, disabled: bool = False, plain: bool = False
) -> str | None:
    """The icon's SVG in ``theme``'s colours, or None when it is missing.

    ``disabled`` draws it all in the disabled colour; ``plain`` all in the text
    colour (a status mark with nothing to report, such as an Errors tab with no errors).
    """
    path = icon_path(name)
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    palette = colours(theme)
    one = disabled_colour(theme) if disabled else (palette["currentColor"] if plain else None)
    for key, value in palette.items():
        text = text.replace(key, one or value)
    return text


def svg_text(name: str, dark: bool) -> str | None:
    """The icon's SVG in the Light or Dark theme's colours, or None if it is missing."""
    return themed_text(name, Theme.DARK if dark else Theme.LIGHT)


class SvgIconEngine(QIconEngine):
    """Draws an icon from its themed SVG only when a size is asked for, and keeps it.

    Rendering every size of every command icon at start cost about 90 KB per
    icon (PLAN 11 memory budget); most sizes are never shown. Disabled icons
    use ``disabled``, the same drawing in the theme's disabled colour (U5.4);
    without it they fall back to reduced opacity.
    """

    def __init__(self, data: QByteArray, disabled: QByteArray | None = None) -> None:
        super().__init__()
        self.data = data
        self.disabled = disabled
        self.pixmaps: dict[tuple[int, int, float, bool], QPixmap] = {}

    def _draw(self, painter: QPainter, rect: QRectF, disabled: bool) -> None:
        if disabled and self.disabled is not None:
            QSvgRenderer(self.disabled).render(painter, rect)
            return
        if disabled:
            painter.setOpacity(painter.opacity() * 0.4)
        QSvgRenderer(self.data).render(painter, rect)

    def _render(self, size: QSize, scale: float, disabled: bool) -> QPixmap:
        key = (size.width(), size.height(), scale, disabled)
        found = self.pixmaps.get(key)
        if found is not None:
            return found
        pixmap = QPixmap(QSize(round(size.width() * scale), round(size.height() * scale)))
        pixmap.setDevicePixelRatio(scale)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._draw(painter, QRectF(0, 0, size.width(), size.height()), disabled)
        painter.end()
        self.pixmaps[key] = pixmap
        return pixmap

    def pixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QPixmap:
        """The icon at ``size`` device independent pixels, scale 1."""
        return self._render(size, 1.0, mode == QIcon.Mode.Disabled)

    def scaledPixmap(  # noqa: N802
        self, size: QSize, mode: QIcon.Mode, state: QIcon.State, scale: float
    ) -> QPixmap:
        """The icon at ``size`` for a screen with this pixel ratio (sharp on high DPI)."""
        return self._render(size, max(scale, 1.0), mode == QIcon.Mode.Disabled)

    def paint(self, painter: QPainter, rect: QRect, mode: QIcon.Mode, state: QIcon.State) -> None:
        """Draw straight from the SVG into ``rect``."""
        painter.save()
        self._draw(painter, QRectF(rect), mode == QIcon.Mode.Disabled)
        painter.restore()

    def clone(self) -> QIconEngine:
        """A copy for Qt (icons share engines until one is changed)."""
        return SvgIconEngine(self.data, self.disabled)


@cache
def _icon(name: str, theme: Theme, plain: bool = False) -> QIcon:
    text = themed_text(name, theme, plain=plain)
    off = themed_text(name, theme, disabled=True)
    if text is None or off is None:
        from fdcad.applog import log

        log.info("Missing icon %s", name)  # in the log file (U10.2); some commands have none
        return QIcon()
    return QIcon(SvgIconEngine(QByteArray(text.encode("utf-8")), QByteArray(off.encode("utf-8"))))


def icon(name: str, plain: bool = False) -> QIcon:
    """The named icon in the current theme's colours (empty if missing).

    ``plain`` draws it all in the text colour, without accent or state colours.
    """
    return _icon(name, current(), plain)


def clear_cache() -> None:
    """Forget rendered icons, for example after the theme changes."""
    _icon.cache_clear()
