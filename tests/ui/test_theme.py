"""Light and dark themes, the style sheet and the polish pass layout (C7, D111)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QApplication, QWidget
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature
from fdcad.ui import icons
from fdcad.ui.command_tabs.ribbon import COLUMN_ROWS, LABEL_LINES, CompactButton, LargeButton
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.preferences.settings import Theme
from fdcad.ui.property_panel.panel import feature_icon_name
from fdcad.ui.sketch_tools.value_box import ValueBox
from fdcad.ui.themes import theme
from fdcad.ui.themes.style import image, stylesheet, unit
from tests.ui.test_command_tabs import _buttons
from tests.ui.test_main_window import _folders, _open_plate, window

__all__ = ["_folders", "window"]


@pytest.fixture
def themed(qapp: QApplication) -> Iterator[QApplication]:
    """Apply themes in a test, then put the plain test look back."""
    yield qapp
    theme._forced_dark = None
    qapp.setStyleSheet("")
    qapp.setPalette(qapp.style().standardPalette())


def test_apply_theme_sets_palette_style_sheet_and_scheme(themed: QApplication) -> None:
    theme.apply_theme(themed, Theme.DARK)
    assert theme.is_dark() and theme.palette() is theme.DARK
    window_color = themed.palette().color(QPalette.ColorRole.Window).name().upper()
    assert window_color == theme.DARK_CHROME.window
    assert theme.DARK_CHROME.accent in themed.styleSheet()
    theme.apply_theme(themed, Theme.LIGHT)
    assert not theme.is_dark() and theme.chrome() is theme.LIGHT_CHROME
    assert theme.LIGHT_CHROME.accent in themed.styleSheet()


def test_one_accent_matches_the_icons() -> None:
    assert theme.LIGHT_CHROME.accent == icons.ACCENT[False]
    assert theme.DARK_CHROME.accent == icons.ACCENT[True]


def test_sizes_follow_the_font(qapp: QApplication) -> None:
    small, large = QFont(qapp.font()), QFont(qapp.font())
    small.setPixelSize(12)
    large.setPixelSize(24)
    assert unit(small) == 4
    assert unit(large) > unit(small)  # font metrics differ per platform, so only check it grows
    sheet = stylesheet(theme.LIGHT_CHROME, theme.LIGHT, large)
    assert f"min-height: {6 * unit(large)}px" in sheet  # tree rows grow with the font


def test_style_sheet_images_exist(qapp: QApplication) -> None:
    from pathlib import Path

    path = Path(image("chevron", "#123456"))
    assert path.is_file() and "#123456" in path.read_text(encoding="utf-8")
    assert image("chevron", "#123456") == str(path).replace("\\", "/")


def test_features_tab_has_sketch_and_compact_sweeps(window: MainWindow) -> None:
    features = _buttons(window, "features")
    assert isinstance(features["sketch.sketch"], LargeButton)
    assert isinstance(features["feature.sweep"], CompactButton)
    assert isinstance(features["feature.loft"], CompactButton)


def _top(widget: QWidget, window: MainWindow) -> int:
    return widget.mapTo(window, widget.rect().topLeft()).y()


def _centre(widget: QWidget, window: MainWindow) -> float:
    return _top(widget, window) + widget.height() / 2


def test_compact_columns_are_centred_on_shared_rows(qtbot: QtBot, window: MainWindow) -> None:
    window.resize(1400, 800)
    tabs = window.command_tabs
    tabs.setCurrentIndex(tabs.index_of("features"))
    qtbot.wait(10)
    features = _buttons(window, "features")
    rebuild, force = features["feature.sweep"], features["feature.loft"]
    boss = features["feature.extrude"]
    assert rebuild.height() == force.height()
    # The two compact tools are centred on the large buttons beside them.
    pair = (_top(rebuild, window) + _top(force, window) + force.height()) / 2
    assert abs(pair - _centre(boss, window)) <= 2
    assert rebuild.height() * COLUMN_ROWS <= boss.height() + COLUMN_ROWS
    tabs.setCurrentIndex(tabs.index_of("sketch"))
    qtbot.wait(10)
    sketch = _buttons(window, "sketch")
    # A group's small tools flow into columns filled from the top, so the first tool
    # of each column sits on the same row (D1034).
    first, other = sketch["sketch.construction"], sketch["sketch.convert"]
    assert abs(_top(first, window) - _top(other, window)) <= 1
    assert first.height() == other.height() == sketch["sketch.corner_rectangle"].height()


def test_large_buttons_share_icon_and_label_rows(qtbot: QtBot, window: MainWindow) -> None:
    window.resize(1400, 800)
    tabs = window.command_tabs
    for name in ("features", "sketch"):
        tabs.setCurrentIndex(tabs.index_of(name))
        qtbot.wait(10)
        large = [b for b in _buttons(window, name).values() if isinstance(b, LargeButton)]
        assert len(large) >= 2
        labels = {(_top(b, window) + b.label_rect().top(), b.label_rect().height()) for b in large}
        # One line labels ("Sketch") start on the same line as two line labels.
        assert len(labels) == 1, labels
        assert len({_top(b, window) for b in large}) == 1
        assert len({b.height() for b in large}) == 1
        for b in large:
            assert b.label_rect().height() >= LABEL_LINES * b.fontMetrics().height()


def test_cut_features_have_panel_icons() -> None:
    listed = set(icons.listed_names())
    for ftype in ("extrude", "revolve"):
        for operation in ("boss", "cut"):
            feature = Feature(id="f1", type=ftype, name="F", params={"operation": operation})
            assert feature_icon_name(feature) in listed


def test_document_tab_close_button_follows_the_theme(qtbot: QtBot, window: MainWindow) -> None:
    _open_plate(qtbot, window)
    bar = window.tabs.tabBar()
    close = bar.tabButton(0, window._close_side())
    assert close is not None and close.objectName() == "tab_close"
    window.command_tabs.theme_changed()
    assert not close.icon().isNull()  # type: ignore[attr-defined]


def test_value_box_marks_errors_with_a_property(qapp: QApplication) -> None:
    box = ValueBox("10 mm")
    box.show_error("Bad value")
    assert box.edit.property("error") is True
    assert box.edit.styleSheet() == ""  # the theme draws the error border
    box.deleteLater()


def _luminance(color: str) -> float:
    r, g, b = (int(color[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


@pytest.mark.parametrize("pal", [theme.LIGHT, theme.DARK])
def test_view_gradient_is_vertical_and_exact(pal: theme.Palette) -> None:
    from OCP.Aspect import Aspect_GradientFillMethod_Vertical
    from OCP.Quantity import Quantity_TOC_sRGB

    from fdcad.ui.viewport.widget import background

    top, bottom, method = background(pal)
    # Top to bottom, not left to right (the kernel's default fill).
    assert method == Aspect_GradientFillMethod_Vertical
    # The hex colours are sRGB, so the strip above the view shows the same top colour.
    for color, hex_color in ((top, pal.viewport_top), (bottom, pal.viewport_bottom)):
        expected = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        assert color.Values(Quantity_TOC_sRGB) == pytest.approx(expected, abs=1e-3)
    # Lighter at the top and clearly visible, in both themes.
    assert _luminance(pal.viewport_top) - _luminance(pal.viewport_bottom) > 0.1


def test_view_strip_matches_the_view_top(
    qtbot: QtBot, themed: QApplication, window: MainWindow
) -> None:
    from fdcad.ui.main_window.view_bar import refresh_view_bar

    for choice, pal in ((Theme.DARK, theme.DARK), (Theme.LIGHT, theme.LIGHT)):
        theme.apply_theme(themed, choice)
        if window.current is None:
            _open_plate(qtbot, window)
        tab = window.current
        assert tab is not None
        refresh_view_bar(tab)
        qtbot.wait(10)
        strip = tab.view_bar.grab().toImage()
        assert strip.pixelColor(1, 1).name().upper() == pal.viewport_top


def test_left_and_document_tab_bars_line_up(
    qtbot: QtBot, themed: QApplication, window: MainWindow
) -> None:
    for choice in (Theme.DARK, Theme.LIGHT):
        theme.apply_theme(themed, choice)
        if window.current is None:
            _open_plate(qtbot, window)
        window.resize(1400, 800)
        qtbot.wait(20)
        assert window.left is not None
        left, docs = window.left.tabBar(), window.tabs.tabBar()
        first_left, first_doc = left.tabRect(0), docs.tabRect(0)
        assert first_left.height() == first_doc.height()
        top_left = left.mapTo(window, first_left.topLeft()).y()
        top_doc = docs.mapTo(window, first_doc.topLeft()).y()
        assert top_left == top_doc
        assert left.height() == docs.height()


def test_tree_arrows_are_muted_and_padded(themed: QApplication) -> None:
    for choice, c in ((Theme.DARK, theme.DARK_CHROME), (Theme.LIGHT, theme.LIGHT_CHROME)):
        theme.apply_theme(themed, choice)
        sheet = themed.styleSheet()
        for name in ("branch_closed", "branch_open"):
            assert f"url({image(name, c.muted)})" in sheet
        assert "QTreeView {" in sheet and "QTreeView::item { padding-left" in sheet


def test_status_bar_has_a_top_border(
    qtbot: QtBot, themed: QApplication, window: MainWindow
) -> None:
    for choice, c in ((Theme.DARK, theme.DARK_CHROME), (Theme.LIGHT, theme.LIGHT_CHROME)):
        theme.apply_theme(themed, choice)
        qtbot.wait(10)
        bar = window.statusBar().grab().toImage()
        assert bar.pixelColor(bar.width() // 2, 0).name().upper() == c.border
        assert bar.pixelColor(bar.width() // 2, bar.height() // 2).name().upper() == c.window
