"""More room for the part (D1033): short command tabs, a narrow tree panel, and no
spare Untitled tab after opening a part."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QAction
from pytestqt.qtbot import QtBot

from fdcad.core.units import UnitSystem
from fdcad.ui.command_tabs.ribbon import COLUMN_ROWS, LargeButton, RibbonGroup
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.session import DocumentSession
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]

SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "bracket.fdprt"


def test_long_column_flows_into_columns_of_four(qtbot: QtBot) -> None:
    group = RibbonGroup("Tools")
    qtbot.addWidget(group)
    large = group.add_large(QAction("Main Tool", group))
    made = group.add_column([QAction(f"Tool {i}", group) for i in range(7)])
    assert len(made) == 7
    group.resize(group.sizeHint())
    group.show()
    qtbot.waitExposed(group)
    columns = sorted({b.x() for b in made})
    assert COLUMN_ROWS == 4
    assert len(columns) == 2  # 4 + 3: balanced, each filled from the top
    tops = {x: min(b.y() for b in made if b.x() == x) for x in columns}
    assert len(set(tops.values())) == 1
    for x in columns:
        assert len([b for b in made if b.x() == x]) <= COLUMN_ROWS
    assert isinstance(large, LargeButton)
    tallest = max(b.geometry().bottom() for b in made) - min(b.geometry().top() for b in made)
    assert tallest <= large.height() + 2  # never taller than a main tool


def test_no_tab_is_taller_than_its_main_tools(window: MainWindow) -> None:
    tabs = window.command_tabs
    large = [b for b in tabs.findChildren(LargeButton)]
    assert large
    limit = max(b.sizeHint().height() for b in large)
    for group in tabs.findChildren(RibbonGroup):
        rows: dict[int, int] = {}
        for i in range(group.row.count()):
            column = group.row.itemAt(i).layout()
            if column is not None:
                rows[i] = sum(1 for j in range(column.count()) if column.itemAt(j).widget())
        assert all(n <= COLUMN_ROWS for n in rows.values()), group.caption.text()
    assert limit > 0


def test_tree_panel_can_be_narrow_and_filter_is_stacked(window: MainWindow) -> None:
    assert window.left.minimumWidth() < 300
    box = window.tree_filter
    window.show()
    assert box.state.y() > box.text.y()  # one above the other (IDEAS 19)
    assert box.state.x() == box.text.x()


def test_unused_start_part_is_replaced_by_an_opened_part(qtbot: QtBot, window: MainWindow) -> None:
    blank = DocumentSession.new(UnitSystem.MM, window)
    blank.auto_blank = True
    window.add_session(blank)
    assert window.tabs.count() == 1
    window.open_path(SAMPLE)
    assert window.tabs.count() == 1
    tab = window.tabs.widget(0)
    assert isinstance(tab, DocumentTab) and tab.session.path is not None
    tab.session.wait()


def test_new_part_made_by_the_user_is_kept(qtbot: QtBot, window: MainWindow) -> None:
    window.add_session(DocumentSession.new(UnitSystem.MM, window))  # File, New: not auto
    window.open_path(SAMPLE)
    assert window.tabs.count() == 2
    for i in range(window.tabs.count()):
        window.tabs.widget(i).session.wait()


def test_start_picture_is_the_brand_tile(qtbot: QtBot) -> None:
    from PySide6.QtGui import QColor

    from fdcad.ui.help.paths import app_icon
    from fdcad.ui.splash import HEIGHT, WIDTH, finish, show_splash, splash_pixmap

    picture = splash_pixmap(app_icon(), 2.0)
    assert (picture.width(), picture.height()) == (WIDTH * 2, HEIGHT * 2)
    image = picture.toImage()
    from fdcad.ui.themes.theme import BRAND

    # The tile runs from one brand colour to the other, corner to corner.
    top, bottom = QColor(BRAND["tile_top"]), QColor(BRAND["tile_bottom"])
    near, far = image.pixelColor(40, 40), image.pixelColor(2 * WIDTH - 40, 2 * HEIGHT - 40)
    assert abs(near.blue() - top.blue()) < 24 and abs(far.blue() - bottom.blue()) < 24
    assert image.pixelColor(0, 0).alpha() == 0  # rounded corners
    splash = show_splash(app_icon())
    assert splash.isVisible()
    from PySide6.QtWidgets import QWidget

    shown = QWidget()
    qtbot.addWidget(shown)
    shown.show()
    finish(splash, shown)
    assert not splash.isVisible()


def test_left_panel_widens_for_the_variables_tab_and_goes_back(
    qtbot: QtBot, window: MainWindow
) -> None:
    from PySide6.QtCore import Qt

    window.resize(1400, 800)
    window.show()
    qtbot.waitExposed(window)
    dock = window.left_dock
    window.resizeDocks([dock], [260], Qt.Orientation.Horizontal)
    qtbot.wait(20)
    before = dock.width()
    variables = window.left.indexOf(window.variables)
    window.left.setCurrentIndex(variables)
    qtbot.wait(20)
    assert dock.width() >= window.variables.preferred_width - 2
    header = window.variables.table.horizontalHeader()
    assert header.length() <= window.variables.table.viewport().width() + 1  # no column cut off
    window.left.setCurrentIndex(0)
    qtbot.wait(20)
    assert abs(dock.width() - before) <= 2


def test_an_open_part_leaves_the_left_panel_at_its_default_width(
    qtbot: QtBot, window: MainWindow
) -> None:
    """D2805: offscreen the 3D view is a message. As one line it was the least width of
    the part's tab (1209 px on Windows), the window grew past its size and the left
    panel was left at its least width: 234 px where the default is 286."""
    from PySide6.QtWidgets import QLabel

    from fdcad.ui import strings

    window.resize(1200, 800)
    window.show()
    qtbot.waitExposed(window)
    default = window.default_left_width()
    assert window.left_dock.width() == default
    window.open_path(SAMPLE)
    tab = window.tabs.widget(0)
    assert isinstance(tab, DocumentTab)
    tab.session.wait()
    qtbot.wait(50)
    message = tab.viewport
    assert isinstance(message, QLabel) and message.wordWrap()
    one_line = message.fontMetrics().horizontalAdvance(strings.NO_3D_VIEW)
    assert tab.minimumSizeHint().width() < one_line
    assert window.width() == 1200
    assert window.left_dock.width() == default
