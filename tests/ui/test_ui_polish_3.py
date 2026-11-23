"""Checks for the third UI pass of 2026-11-19 (review items P2, P3, P6, P7, P8 and P10;
D2740 on).

Each test pins one thing the pass changed, in FDCAD's own style. P2 is checked in
``test_theme_contrast.py``, beside the pairs it measures.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDockWidget,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)
from pytestqt.qtbot import QtBot

from fdcad.core.units import UnitSystem
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.preferences.settings import Theme
from fdcad.ui.themes import contrast, theme
from fdcad.ui.themes.style import unit
from tests.ui.test_ui_polish_controls import styled  # noqa: F401  (fixture)
from tests.ui.test_workflow import (  # noqa: F401  (fixtures)
    _folders,
    new_part,
    rectangle_sketch,
    window,
)

THEMES = [Theme.LIGHT, Theme.BEIGE, Theme.DARK, Theme.STEALTH]
IDS = [t.value for t in THEMES]


# P3, D2741: the unit selector's outline -----------------------------------------------


@pytest.mark.parametrize("choice", THEMES, ids=IDS)
def test_unit_selector_outline_reads_at_three_to_one(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    choice: Theme,
) -> None:
    """D2741: the drop down at the right of the status bar has the outline of every
    other input, 3:1 or more against the status bar (U1.2). It was the quiet divider
    colour, 1.2:1 to 1.5:1."""
    from fdcad.ui.main_window.status_bar import UnitSelector

    theme.apply_theme(styled, choice)
    _colours, chrome, _dark = theme.SCHEMES[choice]
    selector = UnitSelector()
    qtbot.addWidget(selector)
    selector.set_unit(UnitSystem.MM)
    selector.resize(selector.sizeHint())
    selector.show()
    qtbot.wait(20)
    u = unit(selector.font())
    # The style sheet gives the selector a margin of one step at each side; the
    # outline is the first pixel inside it.
    edge = selector.grab().toImage().pixelColor(u, selector.height() // 2)
    assert edge == QColor(chrome.input_border), (choice, edge.name())
    assert contrast.ratio(edge.name(), chrome.window) >= contrast.MARK
    assert contrast.ratio(chrome.border, chrome.window) < contrast.MARK  # what it was


# P6, D2742: one label column for a whole panel ---------------------------------------


def _mixed_panel(qtbot: QtBot) -> tuple[QWidget, dict[str, QWidget]]:
    """Two groups with every kind of row: a word, a field icon, a small button, and a
    word whose field has an icon too."""
    from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

    from fdcad.ui.property_panel.groups import Group, tool_button, with_icon

    root = QWidget()
    root.setObjectName("property_panel")
    qtbot.addWidget(root)
    box = QVBoxLayout(root)
    first, second = Group("Direction 1", "tip"), Group("Hole", "tip")
    box.addWidget(first)
    box.addWidget(second)
    fields: dict[str, QWidget] = {}

    def field(name: str) -> QWidget:
        fields[name] = QLineEdit(name)
        return fields[name]

    reverse_row = QWidget()
    row = QHBoxLayout(reverse_row)
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(tool_button("ui.reverse_direction", "Reverse", "tip", checkable=True))
    row.addWidget(field("end"), 1)
    first.form.addRow(reverse_row)
    first.form.addRow(with_icon("field.depth", "tip", field("depth")))
    first.form.addRow("Along", field("along"))
    drop = QComboBox()
    drop.addItems(["Square to the sketch", "A much longer entry than the panel has room for"])
    fields["drop"] = drop
    second.form.addRow("Type", drop)
    second.form.addRow(LONGEST, with_icon("field.depth", "tip", field("thread")))
    second.form.addRow(with_icon("field.angle", "tip", field("angle")))
    return root, fields


def _lefts(root: QWidget, fields: dict[str, QWidget], names: list[str]) -> set[int]:
    return {fields[name].mapTo(root, QPoint(0, 0)).x() for name in names}


def _label(field: QWidget) -> QLabel:
    """The word in front of ``field`` in its form."""
    holder = field.parentWidget()
    assert holder is not None
    form = holder.layout()
    assert isinstance(form, QFormLayout)
    found = form.labelForField(field)
    assert isinstance(found, QLabel)
    return found


NAMES = ["end", "depth", "along", "drop", "thread", "angle"]
#: The longest word of the test panel: inside the widest column in any font.
LONGEST = "Diameter"


def test_word_rows_and_icon_rows_start_their_fields_at_one_x(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
) -> None:
    """D2742: a row with a word in front, a row with a field icon and a row with a small
    button all start their fields at one x, in every group of the panel. Before, the
    icon rows began one small button in and each group had its own word column."""
    from fdcad.ui.property_panel import columns

    root, fields = _mixed_panel(qtbot)
    root.resize(340, 420)
    root.show()
    qtbot.wait(20)
    assert len(_lefts(root, fields, NAMES)) > 1  # as it was: two columns or more
    width = columns.keep_aligned(root)
    qtbot.wait(20)
    assert len(_lefts(root, fields, NAMES)) == 1
    # The column is as wide as the widest word on show, and no wider.
    longest = _label(fields["thread"].parentWidget())  # type: ignore[arg-type]
    assert longest.text() == LONGEST and width == longest.sizeHint().width()
    assert width <= columns.MAX_STEPS * unit(root.font())
    for name in NAMES:
        box = fields[name]
        assert box.mapTo(root, QPoint(box.width(), 0)).x() <= root.width(), name
    # No field went under its word: the drop down is level with "Type".
    drop, word = fields["drop"], _label(fields["drop"])
    assert abs(drop.geometry().center().y() - word.geometry().center().y()) <= 2


def test_a_word_row_shows_no_field_icon_as_well(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
) -> None:
    """D2742: a row that leads with a word leaves its field icon out, since the icon
    pushed that field out of line; a row with no word keeps its icon."""
    from fdcad.ui.property_panel import columns

    root, fields = _mixed_panel(qtbot)
    root.resize(340, 420)
    root.show()
    columns.keep_aligned(root)
    qtbot.wait(20)

    def icon_of(name: str) -> QLabel:
        row = fields[name].parentWidget()
        assert row is not None
        found = row.findChild(QLabel, "field_icon")
        assert isinstance(found, QLabel)
        return found

    assert not icon_of("thread").isVisible()
    assert icon_of("depth").isVisible() and icon_of("angle").isVisible()


def test_the_column_follows_the_rows_on_show(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
) -> None:
    """D2742: the column is only as wide as the rows on show need. Hiding the row with
    the longest word moves every field left together, and showing it moves them back."""
    from fdcad.ui.property_panel import columns
    from fdcad.ui.property_panel.groups import Group

    root, fields = _mixed_panel(qtbot)
    root.resize(340, 420)
    root.show()
    wide = columns.keep_aligned(root)
    qtbot.wait(20)
    names = [name for name in NAMES if name != "thread"]
    before = _lefts(root, fields, names)
    form = root.findChildren(Group)[1].form
    row = fields["thread"].parentWidget()
    assert row is not None
    form.setRowVisible(row, False)
    qtbot.wait(50)
    after = _lefts(root, fields, names)
    assert len(after) == 1 and max(after) < min(before)
    assert columns.column_width(root) < wide
    form.setRowVisible(row, True)
    qtbot.wait(50)
    assert _lefts(root, fields, NAMES) == before


def test_a_word_longer_than_the_column_moves_only_its_own_group(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
) -> None:
    """D2742: the column stops at 32 spacing steps. A longer word keeps its width, the
    rows of its own group line up with it, and the other groups stay at the column."""
    from fdcad.ui.property_panel import columns
    from fdcad.ui.property_panel.groups import Group

    root, fields = _mixed_panel(qtbot)
    form = root.findChildren(Group)[1].form
    cap = columns.MAX_STEPS * unit(root.font())
    word = "Countersink Diameter"
    while root.fontMetrics().horizontalAdvance(word) <= cap:
        word += " and Depth"
    form.addRow(word, QLineEdit("long"))
    root.resize(4 * cap + root.fontMetrics().horizontalAdvance(word), 500)
    root.show()
    width = columns.keep_aligned(root)
    qtbot.wait(20)
    assert width == cap
    first, second = ["end", "depth", "along"], ["drop", "thread", "angle"]
    assert len(_lefts(root, fields, first)) == 1 and len(_lefts(root, fields, second)) == 1
    assert max(_lefts(root, fields, first)) < min(_lefts(root, fields, second))


def test_a_drop_down_beside_a_word_may_be_narrow_and_its_list_stays_wide(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
) -> None:
    """D2742: a wider column must not push a drop down under its word, so the drop down
    may be narrower than its longest entry; the list that drops down is not."""
    from fdcad.ui.property_panel import columns

    root, fields = _mixed_panel(qtbot)
    drop = fields["drop"]
    assert isinstance(drop, QComboBox)
    longest = drop.fontMetrics().horizontalAdvance(drop.itemText(1))
    assert drop.minimumSizeHint().width() > longest
    columns.keep_aligned(root)
    assert drop.minimumSizeHint().width() < longest
    assert drop.view().minimumWidth() >= longest
    drop.addItem("An entry added later that is longer than every entry that was there before")
    assert drop.view().minimumWidth() >= drop.fontMetrics().horizontalAdvance(drop.itemText(2))


def test_extrude_panel_has_one_field_column(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """D2742 in the real panel: Along, a row with a word, starts its field where the
    rows with an icon and the row with Reverse Direction start theirs."""
    tab = new_part(qtbot, window)
    sid = rectangle_sketch(qtbot, window, tab)
    assert window.tree is not None and window.panel is not None
    window.tree.select(sid)
    window.insert_feature("extrude", "boss")
    qtbot.wait(50)
    panel = window.panel

    def left(widget: QWidget) -> int:
        return widget.mapTo(panel, QPoint(0, 0)).x()

    along = panel.direction_box
    assert along is not None and along.isVisible()
    lefts = {
        left(along),
        left(panel.choices["end_condition"]),
        left(panel.values["depth"]),
        left(panel.sketch_box),
    }
    assert len(lefts) == 1, lefts
    panel.reject()


# P7, D2745: the node editor's title bar ----------------------------------------------


def _editor_dock(qtbot: QtBot, win: MainWindow) -> QDockWidget:
    from fdcad.ui.node_editor import install

    new_part(qtbot, win)
    install.show(win, True)
    qtbot.wait(50)
    dock = win.node_editor_dock  # type: ignore[attr-defined]
    assert isinstance(dock, QDockWidget) and dock.isVisible()
    return dock


def _bar(dock: QDockWidget) -> object:
    from fdcad.ui.node_editor.title_bar import DockTitleBar

    bar = dock.titleBarWidget()
    assert isinstance(bar, DockTitleBar)
    return bar


def _stop_editor(win: MainWindow) -> None:
    from fdcad.ui.node_editor import install

    install.show(win, False)
    install.shutdown(win)


def test_node_editor_title_buttons_are_24_px_and_named(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """D2745: Float and Close are FDCAD's own buttons, 24 px or more each way (U3.3),
    with a name for screen readers and a tooltip that starts with it. Qt's own two
    were 10 px wide."""
    from fdcad.ui.node_editor import strings
    from fdcad.ui.node_editor.title_bar import DockTitleBar

    dock = _editor_dock(qtbot, window)
    bar = _bar(dock)
    assert isinstance(bar, DockTitleBar)
    assert bar.title.text() == strings.PANEL_TITLE
    for button, name in ((bar.float_button, "Float"), (bar.close_button, "Close")):
        assert button.isVisible()
        assert button.width() >= 24 and button.height() >= 24, name
        assert button.accessibleName() == name
        assert button.toolTip().startswith(name)
        assert not button.icon().isNull()
    # The two stand apart, inside the bar, at its right.
    assert bar.float_button.geometry().right() < bar.close_button.geometry().left()
    assert bar.rect().contains(bar.close_button.geometry())
    _stop_editor(window)


def test_node_editor_floats_docks_and_closes_from_its_title_bar(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """D2745: the first button floats the panel and then docks it where it was; Close
    hides it and unticks the Node Editor command, which shows it again."""
    from fdcad.ui.node_editor.title_bar import DockTitleBar

    dock = _editor_dock(qtbot, window)
    bar = _bar(dock)
    assert isinstance(bar, DockTitleBar)
    assert not dock.isFloating()
    assert window.dockWidgetArea(dock) == Qt.DockWidgetArea.RightDockWidgetArea
    qtbot.mouseClick(bar.float_button, Qt.MouseButton.LeftButton)
    qtbot.wait(50)
    assert dock.isFloating() and dock.isVisible()
    assert dock.titleBarWidget() is bar and bar.isVisible()  # the same bar while floating
    assert bar.float_button.accessibleName() == "Dock"
    assert bar.float_button.toolTip().startswith("Dock")
    qtbot.mouseClick(bar.float_button, Qt.MouseButton.LeftButton)
    qtbot.wait(50)
    assert not dock.isFloating() and dock.isVisible()
    assert window.dockWidgetArea(dock) == Qt.DockWidgetArea.RightDockWidgetArea
    assert bar.float_button.accessibleName() == "Float"
    toggle = window.commands.actions["graph.editor"]
    assert toggle.isChecked()
    qtbot.mouseClick(bar.close_button, Qt.MouseButton.LeftButton)
    qtbot.wait(50)
    assert not dock.isVisible() and not toggle.isChecked()
    toggle.trigger()
    qtbot.wait(50)
    assert dock.isVisible() and not dock.isFloating()
    _stop_editor(window)


def test_node_editor_title_bar_keeps_qt_dragging_and_double_click(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """D2745: the bar takes no mouse press itself, so Qt still floats the panel on a
    double click of its name, docks it on the next, and floats it when it is dragged
    off by the bar."""
    from fdcad.ui.node_editor.title_bar import DockTitleBar

    dock = _editor_dock(qtbot, window)
    bar = _bar(dock)
    assert isinstance(bar, DockTitleBar)
    name = bar.title.geometry().center()
    qtbot.mouseDClick(bar, Qt.MouseButton.LeftButton, pos=name)
    qtbot.wait(50)
    assert dock.isFloating()
    qtbot.mouseDClick(bar, Qt.MouseButton.LeftButton, pos=name)
    qtbot.wait(50)
    assert not dock.isFloating()
    assert window.dockWidgetArea(dock) == Qt.DockWidgetArea.RightDockWidgetArea
    # A drag by the name, further than the start distance, pulls the panel off.
    qtbot.mousePress(bar, Qt.MouseButton.LeftButton, pos=name)
    for step in range(1, 8):
        qtbot.mouseMove(bar, name + QPoint(-30 * step, 20 * step))
        qtbot.wait(10)
    assert dock.isFloating()
    qtbot.mouseRelease(bar, Qt.MouseButton.LeftButton, pos=name + QPoint(-210, 140))
    qtbot.wait(50)
    assert dock.isVisible()
    dock.setFloating(False)
    _stop_editor(window)


def test_node_editor_title_icons_follow_the_theme(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """D2745: the two icons are drawn again when the theme changes, so they never keep
    the old theme's text colour."""
    from fdcad.ui.node_editor.title_bar import DockTitleBar

    dock = _editor_dock(qtbot, window)
    bar = _bar(dock)
    assert isinstance(bar, DockTitleBar)
    light = bar.close_button.icon().pixmap(16, 16).toImage()
    theme.apply_theme(styled, Theme.DARK)
    qtbot.wait(50)
    dark = bar.close_button.icon().pixmap(16, 16).toImage()
    assert light != dark
    _stop_editor(window)


# P8, D2743: the header of the Plane and Section View panels --------------------------


def _header_facts(header: QWidget, ok: QPushButton, cancel: QPushButton) -> dict[str, object]:
    """What makes the header of D2692: checked the same way on every panel."""
    return {
        "name": header.objectName(),
        "ok": ok.objectName(),
        "ok_has_no_icon": ok.icon().isNull(),
        "cancel_has_no_icon": cancel.icon().isNull(),
        "ok_left": ok.x(),
        "cancel_right": header.width() - cancel.geometry().right() - 1,
        "equal": abs(ok.width() - cancel.width()) <= 1,
        "one_row": ok.y() == cancel.y(),
        "height": ok.height(),
        "gap": cancel.x() - ok.geometry().right() - 1,
    }


def test_plane_and_section_panels_have_the_property_panel_header(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """D2743: the Plane panel and the Section View panel open with the header of the
    property panel: icon and name, then OK and Cancel at equal width across the panel,
    words only, OK the main button, 12 px padding. They had OK and Cancel with icons
    beside the name."""
    from fdcad.ui.property_panel.header import PanelHeader

    tab = new_part(qtbot, window)
    sid = rectangle_sketch(qtbot, window, tab)
    assert window.tree is not None and window.panel is not None
    window.tree.select(sid)
    window.insert_feature("extrude", "boss")
    qtbot.wait(50)
    panel = window.panel
    header = panel.ok_button.parentWidget()
    assert header is not None
    wanted = _header_facts(header, panel.ok_button, panel.cancel_button)
    weight = panel.title.font().weight()
    assert wanted["name"] == "panel_header" and wanted["ok"] == "panel_ok"
    assert wanted["ok_left"] == 12 and wanted["cancel_right"] == 12
    assert wanted["ok_has_no_icon"] and wanted["cancel_has_no_icon"] and wanted["equal"]
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        panel.accept()
    qtbot.wait(50)

    window.reference_tool.start("ref_plane")
    qtbot.wait(50)
    reference = window.reference_tool.panel
    assert reference is not None and isinstance(reference.header, PanelHeader)
    found = _header_facts(reference.header, reference.ok_button, reference.cancel_button)
    assert found == wanted
    assert reference.header.title.text() == reference.feature.name
    assert reference.header.title.font().weight() == weight
    assert reference.header.icon.isVisible() and not reference.header.icon.pixmap().isNull()
    assert reference.method.x() == 12  # the body has the header's padding
    assert reference.ok_button.toolTip() and reference.cancel_button.toolTip()
    reference.cancel_button.click()
    assert window.reference_tool.panel is None

    window.section_tool.open(tab)
    qtbot.wait(50)
    section = window.section_tool.panel
    assert section is not None and isinstance(section.header, PanelHeader)
    assert _header_facts(section.header, section.ok_button, section.cancel_button) == wanted
    assert section.header.icon.isVisible() and not section.header.icon.pixmap().isNull()
    assert section.rows[0].x() == 12
    section.cancel_button.click()
    assert window.section_tool.panel is None


def test_panel_header_icon_follows_the_theme(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
) -> None:
    """D2743: the header draws its icon again when the theme changes, and shows a
    name as it was typed."""
    from fdcad.ui.property_panel.header import PanelHeader

    header = PanelHeader("Section View", "view.section")
    qtbot.addWidget(header)
    header.show()
    qtbot.wait(20)
    light = header.icon.pixmap().toImage()
    theme.apply_theme(styled, Theme.DARK)
    qtbot.wait(50)
    assert header.icon.pixmap().toImage() != light
    header.set_title("<b>Plane</b> 1")
    assert header.title.textFormat() == Qt.TextFormat.PlainText
    assert header.title.text() == "<b>Plane</b> 1"


# P10, D2744: the arrow under a one line label ----------------------------------------


def test_dropdown_arrow_sits_under_the_last_line_of_its_label(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
) -> None:
    """D2744, RIBBON_SPEC R3B: the arrow is the same gap under a one line label (Fillet,
    Plane) as under a two line label. It was a whole empty line lower under one line."""
    from fdcad.ui.command_tabs.ribbon import LargeButton, RibbonPanel

    owner = QWidget()
    qtbot.addWidget(owner)
    panel = RibbonPanel()
    qtbot.addWidget(panel)
    group = panel.add_group("Modify")
    one = group.add_large(QAction("Fillet", owner), QAction("Chamfer", owner))
    two = group.add_large(QAction("Linear Pattern", owner), QAction("Circular Pattern", owner))
    plain = group.add_large(QAction("Shell", owner))
    panel.show()
    qtbot.waitExposed(panel)
    assert isinstance(one, LargeButton) and isinstance(two, LargeButton)
    line = one.fontMetrics().lineSpacing()
    assert one.text_rect().height() == line and two.text_rect().height() == 2 * line
    gap_one = one.arrow_rect().top() - one.text_rect().bottom()
    gap_two = two.arrow_rect().top() - two.text_rect().bottom()
    assert gap_one == gap_two and 0 < gap_one < line
    # Under one line the arrow is where the second line would be, one line higher.
    assert two.arrow_rect().top() - one.arrow_rect().top() == line
    assert one.arrow_rect().bottom() <= one.label_rect().bottom()
    # What R3 still asks: labels start on one line, the arrow is centred, inside the
    # button and inside the strip that opens the list, and a plain button has none.
    assert one.label_rect().top() == two.label_rect().top() == plain.label_rect().top()
    for button in (one, two):
        arrow = button.arrow_rect()
        assert button.rect().contains(arrow) and button.menu_rect().contains(arrow)
        assert not arrow.intersects(button.text_rect())
        assert abs(arrow.center().x() - button.rect().center().x()) <= 1
    assert plain.arrow_rect().isEmpty()
    # The arrow follows the tool the button shows.
    one.setDefaultAction(one.group_actions[1])
    assert one.arrow_rect().top() - one.text_rect().bottom() == gap_one


def test_dropdown_arrow_is_painted_under_a_one_line_label(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
) -> None:
    """D2744: the pixels agree with the rectangle: the arrow's ink is in the second
    line's place, and the row below the label area is empty."""
    from fdcad.ui.command_tabs.ribbon import RibbonPanel

    owner = QWidget()
    qtbot.addWidget(owner)
    panel = RibbonPanel()
    qtbot.addWidget(panel)
    button = panel.add_group("Modify").add_large(QAction("Fillet", owner), QAction("Rib", owner))
    panel.show()
    qtbot.waitExposed(panel)
    image = button.grab().toImage()  # the button is see through but for its drawing

    def has_ink(top: int, bottom: int) -> bool:
        middle = button.width() // 2
        return any(
            image.pixelColor(x, y).alpha() > 128
            for y in range(top, bottom + 1)
            for x in range(middle - 4, middle + 5)
        )

    arrow = button.arrow_rect()
    assert has_ink(arrow.top(), arrow.bottom())
    assert not has_ink(button.label_rect().bottom() + 1, button.height() - 3)
