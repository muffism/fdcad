"""Checks for the UI review of 2026-11-19 (docs/UI_REVIEW_2026-11-19.md, D2690 to D2699).

Each test pins one thing the review changed, in FDCAD's own style and Light theme.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QWidget
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.themes.style import unit
from tests.ui.test_ui_polish_controls import styled  # noqa: F401  (fixture)
from tests.ui.test_workflow import (  # noqa: F401  (fixtures)
    _folders,
    new_part,
    rectangle_sketch,
    window,
)


def skip_where_the_style_is_scaled(app: QApplication) -> None:
    """Skip a pixel check where Qt scales the Fusion style's own sizes (D2710).

    On macOS the Fusion style takes 72 dots per inch as its base. A Mac screen
    reports 72, but Qt's offscreen platform reports 96, so there every Fusion size
    is a third larger than on a real Mac screen: a spin box frame is 4 px, not 3.
    The checks below pass on a real Mac screen (``QT_QPA_PLATFORM=cocoa``).
    """
    screen = app.primaryScreen()
    if sys.platform == "darwin" and screen is not None and screen.logicalDotsPerInch() != 72:
        pytest.skip("Fusion's sizes are scaled on this Qt platform; run with a real Mac screen")


def test_search_box_is_level_with_the_tabs_and_clear_of_the_edge(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """D2691: the box is centred on the row of tab names, not on its foot, and it
    stops short of the window's edge, in line with the card of tools under it."""
    search, tabs = window.command_search, window.command_tabs
    bar = tabs.tabBar()
    u = unit(search.font())
    margin = u + u // 2  # below and right of the box, from the style sheet
    box = search.geometry().adjusted(0, 0, -margin, -margin)
    # A tab's pill: its rect less the margins the style sheet gives it.
    pill = bar.tabRect(tabs.currentIndex()).adjusted(0, u, 0, -margin)
    pill.translate(bar.geometry().topLeft())
    assert abs(box.center().y() - pill.center().y()) <= 1
    assert tabs.width() - box.right() >= margin
    button = tabs.tabs_button.geometry().adjusted(0, 0, 0, -margin)
    assert abs(button.center().y() - pill.center().y()) <= 1


def test_panel_fields_share_one_left_edge_and_icons_sit_level(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """D2692: a row that starts with a field icon and a row that starts with a button
    (Reverse Direction) put their fields on one left edge, and a field icon is level
    with its field, not 4 px above its middle."""
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QLabel

    skip_where_the_style_is_scaled(styled)
    tab = new_part(qtbot, window)
    sid = rectangle_sketch(qtbot, window, tab)
    assert window.tree is not None and window.panel is not None
    window.tree.select(sid)
    window.insert_feature("extrude", "boss")
    qtbot.wait(50)
    panel = window.panel

    def left(widget: QWidget) -> int:
        return widget.mapTo(panel, QPoint(0, 0)).x()

    def middle(widget: QWidget) -> int:
        return widget.mapTo(panel, widget.rect().center()).y()

    end, depth = panel.choices["end_condition"], panel.values["depth"]
    assert left(end) == left(depth) == left(panel.sketch_box)
    reverse = panel.flags["reverse"]
    icons = [label for label in panel.findChildren(QLabel, "field_icon") if label.isVisible()]
    assert icons
    assert {label.width() for label in icons} == {reverse.width()}
    icon = next(label for label in icons if label.parentWidget() is depth.parentWidget())
    assert abs(middle(icon) - middle(depth.edit)) <= 1
    panel.reject()


def test_sketch_panel_has_the_property_panel_header(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """D2692: OK and Cancel share the width of the sketch panel, OK is the main
    button, and the body has the header's 12 px padding."""
    from fdcad.ui.sketch_tools.panel import SketchPanel

    tab = new_part(qtbot, window)
    sid = rectangle_sketch(qtbot, window, tab)
    window.edit_feature(sid)
    qtbot.wait(50)
    panel = window.findChild(SketchPanel)
    assert panel is not None
    ok, cancel = panel.ok_button, panel.cancel_button
    assert ok.objectName() == "panel_ok" and abs(ok.width() - cancel.width()) <= 1
    header = ok.parentWidget()
    assert header is not None and header.objectName() == "panel_header"
    assert ok.x() == 12 and header.width() - cancel.geometry().right() - 1 == 12
    assert panel.status.x() == 12
    assert window.sketch_mode is not None
    window.sketch_mode.cancel()


def test_left_panel_is_one_colour_on_every_tab(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """D2693: the Errors tab is the panel colour, like the tree (it was the window's
    darker grey), and its empty state is a centred line in the muted colour."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QColor

    from fdcad.ui.themes import theme

    new_part(qtbot, window)
    assert window.left is not None and window.errors is not None
    window.left.setCurrentWidget(window.errors)
    qtbot.wait(20)
    errors = window.errors
    image = window.left.grab().toImage()  # the page itself paints no background
    surface = QColor(theme.chrome().surface)
    corner = errors.mapTo(window.left, QPoint(2, errors.height() - 3))
    assert image.pixelColor(corner) == surface
    assert errors.empty.isVisible() and errors.empty.objectName() == "empty_state"
    assert errors.empty.alignment() & Qt.AlignmentFlag.AlignHCenter
    window.left.setCurrentIndex(0)


def test_tree_swatch_fills_the_row_icon_cell(qapp: QApplication) -> None:
    """D2693: a colour swatch is as wide as the other row icons, so the name beside it
    starts where its neighbours' names do, and it has a sharp picture for high DPI."""
    from PySide6.QtCore import QSize

    from fdcad.ui.appearance.tree_rows import swatch
    from fdcad.ui.tree.row_icons import ROW_ICON_SIZE

    icon = swatch("#FFFFFF", cell=ROW_ICON_SIZE)
    side = QSize(ROW_ICON_SIZE, ROW_ICON_SIZE)
    assert icon.actualSize(side) == side
    sharp = icon.pixmap(side, 2.0)
    assert sharp.width() == 2 * ROW_ICON_SIZE
    image = icon.pixmap(side, 1.0).toImage()
    middle = ROW_ICON_SIZE // 2
    assert image.pixelColor(middle, middle).name() == "#ffffff"
    assert image.pixelColor(0, 0).alpha() == 0  # the cell round the square is clear
    # A white swatch still has an edge to see on a white panel.
    assert image.pixelColor(middle, 2).name() != "#ffffff"


def test_message_bar_has_a_mark_and_one_leading_button(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
) -> None:
    """D2694: each bar shows a mark for its kind (not colour alone, U4.4), the button
    that does what the message asks is the only outlined one, and the gaps are on the
    4 px grid."""
    from fdcad.ui.main_window.message_bars import MessageBars

    bars = MessageBars()
    qtbot.addWidget(bars)
    warning = bars.show_message("w", "Careful", "warning", ("Save", lambda: None))
    info = bars.show_message("i", "For your information")
    assert warning is not None and info is not None
    for bar in (warning, info):
        assert not bar.mark.pixmap().isNull()
        assert bar.never_button.isFlat() and bar.close_button.isFlat()
        margins = bar.layout().contentsMargins()
        edges = (margins.left(), margins.top(), margins.right(), margins.bottom())
        assert all(edge % 4 == 0 for edge in edges) and bar.layout().spacing() % 4 == 0
    assert warning.mark.pixmap().toImage() != info.mark.pixmap().toImage()
    assert warning.action_button is not None and not warning.action_button.isFlat()
    assert bars.box.spacing() == 4 and bars.box.contentsMargins().left() == 8


def test_start_page_empty_state_takes_the_place_of_the_list(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    """D2695: with no recent part the words sit in the middle of the list's place and
    no empty card shows; the page is the panel colour, and its two buttons are the
    size of main buttons."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor

    from fdcad.core.document.model import new_document
    from fdcad.core.io import fdef
    from fdcad.ui.themes import theme

    page = window.start_page
    page.refresh()
    qtbot.wait(20)
    assert page.isVisible() and page.empty.isVisible()
    assert not page.list.isVisible() and not page.drop_hint.isVisible()
    assert page.empty.alignment() == Qt.AlignmentFlag.AlignCenter
    assert page.empty.height() > page.height() // 2
    assert page.grab().toImage().pixelColor(4, 4) == QColor(theme.chrome().surface)
    assert page.new_button.height() >= 28 and page.open_button.height() >= 28
    part = tmp_path / "bracket.fdprt"
    fdef.save(new_document(), part)
    window.settings.add_recent(str(part))
    page.refresh()
    assert page.list.isVisible() and page.drop_hint.isVisible() and not page.empty.isVisible()


def test_message_windows_show_fdcad_marks(styled: QApplication) -> None:  # noqa: F811
    """D2696: the picture in a message window is FDCAD's own mark in the theme's
    colours, the same drawing as in the tree and the Errors tab, not Qt's stock one."""
    from PySide6.QtCore import QSize
    from PySide6.QtWidgets import QStyle

    from fdcad.ui import icons

    side = QSize(48, 48)
    pairs = {
        QStyle.StandardPixmap.SP_MessageBoxWarning: "tree.warning_mark",
        QStyle.StandardPixmap.SP_MessageBoxCritical: "tree.error_mark",
        QStyle.StandardPixmap.SP_MessageBoxInformation: "ui.info_mark",
        QStyle.StandardPixmap.SP_MessageBoxQuestion: "ui.question_mark",
    }
    shown = []
    for standard, name in pairs.items():
        ours = icons.icon(name).pixmap(side).toImage()
        assert styled.style().standardIcon(standard).pixmap(side).toImage() == ours
        shown.append(ours)
    assert all(a != b for i, a in enumerate(shown) for b in shown[i + 1 :])  # four shapes


def test_spin_box_matches_a_text_field(styled: QApplication, qtbot: QtBot) -> None:  # noqa: F811
    """D2697: a spin box is as tall as a text field to within 1 px (it was 3 px
    taller), keeps its size with the focus ring, and its number starts as far from
    the edge as a text field's text."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QDoubleSpinBox, QHBoxLayout, QLineEdit

    skip_where_the_style_is_scaled(styled)
    host = QWidget()
    qtbot.addWidget(host)
    row = QHBoxLayout(host)
    spin, field = QDoubleSpinBox(), QLineEdit("25 mm")
    row.addWidget(spin)
    row.addWidget(field)
    host.show()
    qtbot.wait(20)
    assert abs(spin.sizeHint().height() - field.sizeHint().height()) <= 1
    edit = spin.findChild(QLineEdit)
    assert edit is not None and edit.textMargins().left() == 6
    before = spin.sizeHint().height()
    spin.setFocus(Qt.FocusReason.TabFocusReason)
    qtbot.wait(20)
    assert spin.sizeHint().height() == before


def test_status_bar_progress_is_a_slim_bar_and_the_filter_is_on_the_grid(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """D2697: the progress bar shows no percent over its fill and is a slim 10 px; the
    tree's filter box and state choice are one 4 px step apart."""
    assert not window.progress.isTextVisible()
    window.progress.setRange(0, 10)
    window.progress.setValue(4)
    window.progress.show()
    qtbot.wait(20)
    assert window.progress.height() <= 10  # 8 px and its outline
    window.progress.hide()
    filters = window.tree_filter
    assert filters.state.y() - filters.text.geometry().bottom() - 1 == 4
    assert filters.text.x() == 4


def test_label_pictures_ask_for_the_screen_pixel_ratio() -> None:
    """D2698 (CLAUDE.md section 9 item 5): an icon put on a label is asked for at the
    screen's pixel ratio. ``icon.pixmap(16, 16)`` gives the 100 percent picture, which
    Qt stretches, soft, at 150 and 200 percent."""
    import re

    src = Path(__file__).resolve().parents[2] / "src" / "fdcad" / "ui"
    call = re.compile(r"setPixmap\(\s*[^\n]*?\.pixmap\((?:[^()]|\([^()]*\))*\)", re.DOTALL)
    soft = []
    for path in sorted(src.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for found in call.finditer(text):
            if "atio" not in found.group(0):  # devicePixelRatioF() or a ratio argument
                line = text.count("\n", 0, found.start()) + 1
                soft.append(f"{path.relative_to(src)}:{line}")
    assert soft == []


def test_pick_lists_are_outlined_and_drop_down_lists_are_not(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
) -> None:
    """D2692: a list in a window has the colour and outline of a field, and the list
    that drops from a drop down in the same window keeps its raised, quiet look.
    Checked in Dark, where the field and the raised colours differ."""
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QComboBox, QDialog, QListWidget, QVBoxLayout

    from fdcad.ui.preferences.settings import Theme
    from fdcad.ui.themes import theme

    theme.apply_theme(styled, Theme.DARK)
    chrome = theme.chrome()
    dialog = QDialog()
    qtbot.addWidget(dialog)
    layout = QVBoxLayout(dialog)
    picks, choice = QListWidget(), QComboBox()
    picks.addItems(["Edge of Box"])
    choice.addItems(["Blind", "Through All", "Up to Face"])
    layout.addWidget(picks)
    layout.addWidget(choice)
    dialog.show()
    qtbot.wait(20)
    image = picks.grab().toImage()
    assert image.pixelColor(picks.width() // 2, picks.height() - 6) == QColor(chrome.field)
    assert image.pixelColor(picks.width() // 2, 0) == QColor(chrome.input_border)
    choice.showPopup()
    qtbot.wait(20)
    popup = choice.view().window()
    dropped = popup.grab().toImage()
    assert dropped.pixelColor(popup.width() // 2, popup.height() - 8) == QColor(chrome.raised)
    choice.hidePopup()


def test_gestures_page_fits_the_preferences_window(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    """D2699: both cards of the Gestures page are inside the window (the second was
    cut off, with no way to scroll to it), and a drop down's list is still as wide as
    its longest command."""
    from PySide6.QtCore import QPoint, QSettings

    from fdcad.ui.preferences.dialog import PreferencesDialog
    from fdcad.ui.preferences.settings import Settings

    settings = Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))
    dialog = PreferencesDialog(settings)
    qtbot.addWidget(dialog)
    dialog.show()
    pages = range(dialog.tabs.count())
    index = next(i for i in pages if dialog.tabs.widget(i).isAncestorOf(dialog.gestures))
    dialog.tabs.setCurrentIndex(index)
    qtbot.wait(20)
    boxes = list(dialog.gestures.boxes.values())
    assert boxes
    for box in boxes:
        right = box.mapTo(dialog, QPoint(box.width(), 0)).x()
        assert right <= dialog.width() - 16
        assert box.view().minimumWidth() >= box.view().sizeHintForColumn(0)


@pytest.mark.parametrize("view", ["QListView", "QTreeView", "QTableView"])
def test_ticks_in_lists_match_check_boxes(view: str) -> None:
    """D2699: a tick box in a list, tree or table row is drawn like a check box: the
    accent fill with the tick, in every theme. Before, rows showed Fusion's own box."""
    from PySide6.QtGui import QFont

    from fdcad.ui.preferences.settings import Theme
    from fdcad.ui.themes import theme
    from fdcad.ui.themes.style import stylesheet

    for scheme in (Theme.LIGHT, Theme.BEIGE, Theme.DARK, Theme.STEALTH):
        colors, chrome, _dark = theme.SCHEMES[scheme]
        sheet = stylesheet(chrome, colors, QFont())
        start = sheet.index(f"{view}::indicator:checked")
        rule = sheet[start : sheet.index("}", start)]
        assert f"background: {chrome.accent}" in rule and "image: url(" in rule


def test_message_bars_follow_a_change_of_theme(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """D2694: the stack of bars sits on the view's top colour and takes the new
    theme's colour, with the strip of view tools, when the theme changes."""
    from PySide6.QtGui import QColor

    from fdcad.ui.preferences.settings import Theme
    from fdcad.ui.themes import theme

    tab = new_part(qtbot, window)
    bars = tab.message_bars
    bar = bars.show_message("demo", "A notice")
    assert bar is not None
    qtbot.wait(20)

    def corner() -> QColor:
        return bars.grab().toImage().pixelColor(2, bars.height() - 2)

    assert corner() == QColor(theme.palette().viewport_top)
    light_mark = bar.mark.pixmap().toImage()
    theme.apply_theme(styled, Theme.DARK)
    window.command_tabs.theme_changed()
    qtbot.wait(20)
    assert corner() == QColor(theme.palette().viewport_top) == QColor(theme.DARK.viewport_top)
    assert bar.mark.pixmap().toImage() != light_mark  # drawn again in the new text colour
