"""Checks for the second UI pass of 2026-11-19 (review items P1, P4, P5 and P9; D2700 on).

Each test pins one thing the pass changed, in FDCAD's own style.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import QApplication, QMenu
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.preferences.settings import Theme
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.panel import SketchPanel
from fdcad.ui.themes import contrast, theme
from tests.ui.sketch_tools.test_tool_panels_wp9 import (  # noqa: F401  (fixtures)
    _click,
    canvas,
    panel,
)
from tests.ui.test_ui_polish_controls import styled  # noqa: F401  (fixture)
from tests.ui.test_workflow import (  # noqa: F401  (fixtures)
    _folders,
    new_part,
    rectangle_sketch,
    window,
)

THEMES = [Theme.LIGHT, Theme.BEIGE, Theme.DARK, Theme.STEALTH]


# P1, D2700: the information bar's edge ------------------------------------------------


@pytest.mark.parametrize("choice", THEMES, ids=[t.value for t in THEMES])
def test_information_bar_has_a_neutral_edge(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    choice: Theme,
) -> None:
    """D2700: a notice has the muted text colour on its edge, not the green of
    ``state_ok``, which now means success only. A warning keeps the warning colour."""
    from fdcad.ui.main_window.message_bars import MessageBars

    theme.apply_theme(styled, choice)
    colours, chrome, _dark = theme.SCHEMES[choice]
    bars = MessageBars()
    qtbot.addWidget(bars)
    info = bars.show_message("i", "This part was opened to look at.")
    warning = bars.show_message("w", "Careful", "warning")
    assert info is not None and warning is not None
    bars.resize(600, bars.sizeHint().height())
    bars.show()
    qtbot.wait(20)

    def edge(bar: object) -> QColor:
        return bar.grab().toImage().pixelColor(1, bar.height() // 2)  # type: ignore[attr-defined]

    assert edge(info) == QColor(chrome.muted)
    assert edge(info) != QColor(colours.state_ok)
    assert edge(warning) == QColor(colours.state_warning)
    assert colours.state_ok not in info.styleSheet()


@pytest.mark.parametrize("choice", THEMES, ids=[t.value for t in THEMES])
def test_the_neutral_edge_is_a_measured_pair(choice: Theme) -> None:
    """D2700: the edge reads at 3:1 on its card and on the top of the view, and the
    contrast helper measures it with every other pair of the theme."""
    colours, chrome, dark = theme.SCHEMES[choice]
    found = {x.what: x for x in contrast.pairs(colours, chrome, dark)}
    for name in ("notice edge on raised", "notice edge on view top"):
        assert name in found, name
        assert found[name].minimum == contrast.MARK
        assert found[name].value >= contrast.MARK, (choice, name)


# P5, D2701: icons for three small buttons ---------------------------------------------


def _same(a: object, b: object, side: int = 16) -> bool:
    size = QSize(side, side)
    return bool(a.pixmap(size).toImage() == b.pixmap(size).toImage())  # type: ignore[attr-defined]


def test_message_bar_close_is_a_cross(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
) -> None:
    """D2701: Close shows the cross of a part's tab, not the word. The word is its
    accessible name and starts its tooltip, and it is 24 px or more each way."""
    from fdcad.ui import icons, strings
    from fdcad.ui.main_window.message_bars import MessageBars

    bars = MessageBars()
    qtbot.addWidget(bars)
    bar = bars.show_message("demo", "A notice", "info", ("Save", lambda: None))
    assert bar is not None
    bars.resize(600, bars.sizeHint().height())
    bars.show()
    qtbot.wait(20)
    close = bar.close_button
    assert close.text() == "" and _same(close.icon(), icons.icon("ui.close_tab"))
    assert close.accessibleName() == strings.MESSAGE_CLOSE == "Close"
    assert close.toolTip().startswith("Close")
    assert close.width() >= 24 and close.height() >= 24
    assert close.width() < bar.never_button.width()  # the cross saves the word's width
    close.click()
    assert "demo" not in bars.bars


def test_panel_help_and_pin_are_icons_with_names(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
) -> None:
    """D2701: Help shows the icon of Help for This Tool and Pin shows a pin. Each
    keeps its word as the accessible name and in the tooltip, and a 24 px target."""
    from fdcad.ui import icons, strings, strings_help
    from fdcad.ui.property_panel.panel import PropertyPanel

    header = PropertyPanel()
    qtbot.addWidget(header)
    header.resize(260, 600)
    header.show()
    qtbot.wait(20)
    help_button, pin = header.help_button, header.pin_button
    assert help_button.text() == "" and pin.text() == ""
    assert _same(help_button.icon(), icons.icon("help.tool"))
    assert help_button.accessibleName() == strings_help.PANEL_HELP == "Help"
    assert "Help" in help_button.toolTip() and "F1" in help_button.toolTip()
    assert pin.accessibleName() == strings.PANEL_PIN == "Pin"
    assert pin.toolTip().startswith("Pin")
    for button in (help_button, pin):
        assert button.width() >= 24 and button.height() >= 24
    assert help_button.height() == pin.height()


def test_pin_shows_that_it_is_pinned(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
) -> None:
    """D2701: pinned is seen twice, so not by colour alone (U4.4): the button has
    the checked look, and its drawing changes to a pin pushed in."""
    from fdcad.ui import icons
    from fdcad.ui.property_panel.panel import PropertyPanel

    header = PropertyPanel()
    qtbot.addWidget(header)
    header.setEnabled(True)  # the panel is greyed until a feature is open
    header.show()
    qtbot.wait(20)
    pin = header.pin_button
    assert pin.isCheckable() and not pin.isChecked()
    assert _same(pin.icon(), icons.icon("ui.pin"))
    loose = pin.grab().toImage()
    pin.click()
    qtbot.wait(20)
    assert pin.isChecked() and _same(pin.icon(), icons.icon("ui.pin_on"))
    assert not _same(icons.icon("ui.pin"), icons.icon("ui.pin_on"))
    pushed = pin.grab().toImage()
    assert pushed != loose
    assert pushed.pixelColor(2, pin.height() // 2) == QColor(theme.chrome().selected)
    pin.click()
    assert _same(pin.icon(), icons.icon("ui.pin"))


def test_header_icons_follow_a_change_of_theme(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """D2701: Help, Pin and a bar's cross are drawn again in the new theme's text
    colour when the theme changes."""
    tab = new_part(qtbot, window)
    assert window.panel is not None
    bar = tab.message_bars.show_message("demo", "A notice")
    assert bar is not None
    size = QSize(16, 16)
    before = [
        b.icon().pixmap(size).toImage()
        for b in (window.panel.help_button, window.panel.pin_button, bar.close_button)
    ]
    theme.apply_theme(styled, Theme.DARK)
    window.command_tabs.theme_changed()
    qtbot.wait(20)
    after = [
        b.icon().pixmap(size).toImage()
        for b in (window.panel.help_button, window.panel.pin_button, bar.close_button)
    ]
    assert all(a != b for a, b in zip(before, after, strict=True))


# P9, D2702: empty states ---------------------------------------------------------------


def test_left_panel_says_that_no_part_is_open(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """D2702: with no part open the tree's place holds one centred, muted line in a
    dashed outline, as on the start page, and the filter boxes are greyed. It was a
    filter box over a blank panel. A part brings the tree back."""
    from PySide6.QtCore import QPoint, Qt

    from fdcad.ui import strings_feedback

    assert window.tree is not None
    box = window.tree_filter
    qtbot.wait(20)
    assert box.empty.isVisible() and not window.tree.isVisible()
    assert box.empty.text() == strings_feedback.NO_PART_OPEN
    assert box.empty.objectName() == "empty_box"
    assert box.empty.alignment() == Qt.AlignmentFlag.AlignCenter
    assert box.empty.height() > box.height() // 2  # it takes the tree's place
    assert not box.text.isEnabled() and not box.state.isEnabled()
    assert window.left is not None
    image = window.left.grab().toImage()  # the page itself paints no background
    inside = box.empty.mapTo(window.left, QPoint(12, box.empty.height() // 2))
    assert image.pixelColor(inside) == QColor(theme.chrome().surface)
    new_part(qtbot, window)
    qtbot.wait(20)
    assert window.tree.isVisible() and not box.empty.isVisible()
    assert box.text.isEnabled() and box.state.isEnabled()
    window.close_tab(0, ask=False)
    qtbot.wait(20)
    assert box.empty.isVisible() and not window.tree.isVisible()


def test_variables_table_says_what_to_do_while_it_is_empty(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """D2702: a table with no variables shows one muted line in its middle, which
    goes when the first variable is added and comes back when the last one goes."""
    from PySide6.QtCore import Qt

    from fdcad.ui import strings_feedback

    assert window.left is not None and window.variables is not None
    variables = window.variables
    window.left.setCurrentWidget(variables)
    qtbot.wait(20)
    empty = variables.empty
    assert empty.isVisible() and empty.text() == strings_feedback.NO_PART_VARIABLES
    new_part(qtbot, window)
    window.left.setCurrentWidget(variables)
    qtbot.wait(20)
    assert empty.isVisible() and empty.text() == strings_feedback.NO_VARIABLES
    assert empty.objectName() == "empty_state"
    assert empty.alignment() == Qt.AlignmentFlag.AlignCenter
    assert empty.geometry() == variables.table.viewport().rect()  # the middle of the table
    assert empty.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    variables.add_row()
    assert variables.table.rowCount() == 1 and not empty.isVisible()
    variables.table.selectRow(0)
    variables.remove_row()
    assert variables.table.rowCount() == 0 and empty.isVisible()
    window.left.setCurrentIndex(0)


def test_empty_sketch_relation_cards_say_what_they_will_show(
    qtbot: QtBot,
    canvas: SketchCanvas,  # noqa: F811
    panel: SketchPanel,  # noqa: F811
) -> None:
    """D2702: the Add Relation card stays in view while nothing is selected (as
    ``test_tool_panel_shows_while_a_tool_is_active`` pins) and says what will show
    in it; so does the list of relations. Each line goes when its content comes."""
    from fdcad.core.sketch.model import Point
    from fdcad.ui import strings

    assert panel.relation_box.isVisibleTo(panel) and not panel.relation_buttons
    assert panel.relation_empty.isVisibleTo(panel)
    assert panel.relation_empty.text() == strings.RELATIONS_NONE_PICKED
    assert panel.relation_empty.parentWidget() is panel.relation_box
    assert panel.existing.count() == 0 and panel.existing_empty.isVisibleTo(panel)
    assert panel.existing_empty.text() == strings.EXISTING_NONE_PICKED
    canvas.set_tool("point")
    _click(qtbot, canvas, (12, 7))
    canvas.set_tool(None)
    sk = canvas.edit.sketch
    pid = next(e.id for e in sk.entities.values() if isinstance(e, Point) and e.x > 1)
    canvas.selection = [pid]
    canvas.selection_changed.emit()
    assert list(panel.relation_buttons) == ["fixed"]
    assert not panel.relation_empty.isVisibleTo(panel)  # the buttons took its place
    assert panel.existing.count() == 0 and panel.existing_empty.isVisibleTo(panel)
    assert panel.existing_empty.text() == strings.EXISTING_NONE
    panel.add_relation("fixed")
    assert panel.existing.count() == 1 and not panel.existing_empty.isVisibleTo(panel)
    if not panel.relation_buttons:  # nothing more fits a fixed point
        assert panel.relation_empty.isVisibleTo(panel)
        assert panel.relation_empty.text() == strings.RELATIONS_NONE_FIT
    canvas.selection = []
    canvas.selection_changed.emit()
    assert panel.relation_empty.isVisibleTo(panel)
    assert panel.relation_empty.text() == strings.RELATIONS_NONE_PICKED
    assert panel.existing_empty.isVisibleTo(panel)


# P4, D2703: icons in the right click menus ----------------------------------------------


def _entry(menu: QMenu, key: str = "", label: str = "") -> QAction:
    """The entry of ``menu`` (submenus too) with this key or label."""
    for action in menu.actions():
        if (key and action.data() == key) or (label and action.text() == label):
            return action
        sub = action.menu()
        if isinstance(sub, QMenu):
            try:
                return _entry(sub, key, label)
            except AssertionError:
                continue
    raise AssertionError(f"no entry {key or label}")


def test_every_menu_icon_is_one_that_exists() -> None:
    """D2703: nothing is drawn for the right click menus; every name in the maps is an
    icon that is listed already, and most are the icon of a command."""
    from fdcad.ui import icons, menu_icons
    from fdcad.ui.input.commands import BY_ID

    listed = set(icons.listed_names())
    names = set(menu_icons.KEYS.values()) | set(menu_icons.LABELS.values())
    assert names <= listed
    # The rest are the context toolbar's icons, the confirmation corner's, a relation's
    # and the panel's Reverse Direction button's.
    assert {n for n in names if n not in BY_ID} <= {
        "context.edit",
        "context.edit_sketch",
        "context.hide",
        "context.show",
        "corner.ok",
        "corner.cancel",
        "relation.fixed",
        "ui.reverse_direction",
    }


def test_menu_icon_lookup() -> None:
    """D2703: by key, by a key that is a command, by family, then by the label when
    one command has it. An entry with no icon gets none."""
    from fdcad.ui import menu_icons

    find = menu_icons.icon_name
    assert find("zoom_fit", "Zoom to Fit") == "view.fit"
    assert find("view.front", "Front") == "view.front"
    assert find("edit.appearance") == "edit.appearance"
    assert find("tool.line", "Line") == "sketch.line"
    assert find("relation.parallel", "Parallel") == "relation.parallel"
    assert find("style.wireframe", "Wireframe") == "view.wireframe"
    assert find(label="Delete") == "edit.delete"
    assert find(label="&Delete...") == "edit.delete"
    assert find(label="Edit Feature") == "context.edit"
    assert find(label="Hide") == "context.hide" and find(label="Show") == "context.show"
    assert find(label="Rename") is None
    assert find("grid_spacing", "Grid Spacing") is None
    assert find("tool.no_such_tool", "No Such Tool") is None
    assert find(label="Box 12") is None  # a part's own names never pick an icon


def test_view_menu_shows_the_icons_of_the_menu_bar(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """D2703: Zoom to Fit, Previous View and Front in the view's right click menu
    show the picture the same commands have in the menu bar and command tabs."""
    tab = new_part(qtbot, window)
    menu = window.context_menus.build_view_menu(tab, [])
    actions = window.commands.actions
    pairs = {
        "zoom_fit": "view.fit",
        "previous_view": "view.previous",
        "view.front": "view.front",
        "normal_to": "view.normal_to",
        "appearance": "edit.appearance",
        "style.wireframe": "view.wireframe",
    }
    for key, cid in pairs.items():
        entry = _entry(menu, key)
        assert not entry.icon().isNull(), key
        assert not actions[cid].icon().isNull(), cid
        assert _same(entry.icon(), actions[cid].icon()), key


def test_tree_menu_shows_icons_and_keeps_rows_without_one_in_line(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """D2703: Edit Sketch, Hide or Show and Delete in the tree's menu have the icons
    of the context toolbar and the Edit menu; Rename has no icon to show and gets
    none. Every row keeps the icon column, so the words start on one line."""
    from PySide6.QtWidgets import QStyle, QStyleOptionMenuItem

    from fdcad.ui import icons

    tab = new_part(qtbot, window)
    sid = rectangle_sketch(qtbot, window, tab)
    tree = window.tree
    assert tree is not None
    item = tree.item_for(sid)
    assert item is not None
    menu = tree._context_menu(tab.session, item)
    assert menu is not None
    edit, delete = _entry(menu, label="Edit Sketch"), _entry(menu, label="Delete")
    rename = _entry(menu, label="Rename")
    assert _same(edit.icon(), icons.icon("context.edit_sketch"))
    assert _same(delete.icon(), window.commands.actions["edit.delete"].icon())
    shown = next(a for a in menu.actions() if a.text() in ("Hide", "Show"))
    assert _same(shown.icon(), icons.icon(f"context.{shown.text().lower()}"))
    assert rename.icon().isNull()
    # One icon column in every row: a row is as wide with an icon as without one,
    # and the rows share their left edge.
    style = menu.style()
    option = QStyleOptionMenuItem()
    option.menuItemType = QStyleOptionMenuItem.MenuItemType.Normal
    option.text = "Rename"
    kind = QStyle.ContentsType.CT_MenuItem
    bare = style.sizeFromContents(kind, option, QSize(60, 16), menu)
    option.icon = icons.icon("edit.delete")
    assert style.sizeFromContents(kind, option, QSize(60, 16), menu) == bare
    assert menu.actionGeometry(rename).left() == menu.actionGeometry(delete).left()
    assert menu.actionGeometry(rename).width() == menu.actionGeometry(delete).width()


def test_sketch_menu_shows_the_icons_of_its_commands(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """D2703: Exit Sketch, Smart Dimension and Select in the sketch's right click menu
    show the icons of the Sketch tab; Grid Spacing has no command icon and gets none."""
    from tests.ui.test_workflow import canvas_of

    tab = new_part(qtbot, window)
    sid = rectangle_sketch(qtbot, window, tab)
    window.edit_feature(sid)
    qtbot.wait(50)
    menu = window.context_menus.build_sketch_menu(canvas_of(window))
    actions = window.commands.actions
    pairs = {
        "exit_sketch": "sketch.exit",
        "dimension": "sketch.dimension",
        "select": "sketch.select",
    }
    for key, cid in pairs.items():
        assert _same(_entry(menu, key).icon(), actions[cid].icon()), key
    assert _entry(menu, "grid_spacing").icon().isNull()
    assert window.sketch_mode is not None
    window.sketch_mode.cancel()
