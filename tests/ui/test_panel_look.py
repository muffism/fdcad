"""How tool panels look at the left panel's default width (D2800 to D2804).

The Windows look review of D2790 and D2791: tabs that fill their row, a tidy
Favourites box, drop downs under long words at the full width, no entry cut in
the middle of a letter, and no sideways scroll bar in the Hole Tool's points table.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QComboBox, QFormLayout, QGridLayout, QTabBar, QWidget

from fdcad.samples.make import SAMPLE_DIR
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.property_panel import columns
from fdcad.ui.property_panel.elide import is_cut
from fdcad.ui.property_panel.favourites import FavouritesBox
from fdcad.ui.property_panel.groups import icon_cell
from tests.ui.sweep_support import open_part, pump, select, settle, shapes_of
from tests.ui.test_panel_widths import _folders, _open_groups, window  # noqa: F401  (fixtures)

PART = SAMPLE_DIR / "enclosure.fdprt"


def _start(win: MainWindow, tab: DocumentTab, command: str, kind: str) -> Any:
    """Start ``command`` with one item of ``kind`` selected; every group open and fitted."""
    settle(win, tab)
    assert select(win, tab, kind, shapes_of(tab))
    win.commands.trigger(command)
    pump(30)
    assert win.panel is not None and win.panel.is_editing, command
    _open_groups(win)
    pump(20)
    assert win.fit_panels(), command
    pump(20)
    return win.panel.form


def _left(win: MainWindow, widget: QWidget) -> int:
    assert win.panel is not None
    return int(widget.mapTo(win.panel, QPoint(0, 0)).x())


def _label_of(box: QWidget) -> QWidget | None:
    """The word of the form row that ``box`` is the field of."""
    field: QWidget | None = box
    while field is not None:
        holder = field.parentWidget()
        form = holder.layout() if holder is not None else None
        if isinstance(form, QFormLayout):
            label = form.labelForField(field)
            if label is not None:
                return label
        field = holder
    return None


def test_the_tabs_of_fillet_share_the_width_of_the_panel(window: MainWindow) -> None:  # noqa: F811
    """D2803: the tabs fill their row, as the Hole Tool's two tabs fill theirs."""
    tab = open_part(window, PART)
    _start(window, tab, "feature.fillet", "edge")
    assert window.panel is not None and window.panel.page_tabs is not None
    bar = window.panel.page_tabs.bar
    assert bar.isVisible() and bar.expanding()
    shown = [i for i in range(bar.count()) if bar.isTabVisible(i)]
    assert len(shown) == 3
    assert bar.tabRect(shown[0]).left() <= 4
    assert bar.tabRect(shown[-1]).right() >= bar.width() - 4
    # A face fillet has no More tab: the two that are left share the row.
    form = window.panel.form
    form.kind.setCurrentIndex(form.kind.findData("face"))
    pump(30)
    shown = [i for i in range(bar.count()) if bar.isTabVisible(i)]
    assert len(shown) == 2
    assert bar.tabRect(shown[0]).left() <= 4
    assert bar.tabRect(shown[-1]).right() >= bar.width() - 4
    # Offscreen on Windows the font is too wide for the two tabs to be alike.
    if bar.sizeHint().width() <= bar.width():
        first, last = (bar.tabRect(i).width() for i in shown)
        assert min(first, last) > bar.width() // 3


def test_favourites_has_apply_under_the_list_and_three_pairs(window: MainWindow) -> None:  # noqa: F811
    """D2803: no button alone on a row."""
    tab = open_part(window, PART)
    _start(window, tab, "feature.fillet", "edge")
    assert window.panel is not None
    box = window.panel.findChild(FavouritesBox)
    assert box is not None
    grid = box.layout()
    assert isinstance(grid, QGridLayout)

    def place(key: str) -> tuple[int, int, int, int]:
        at: Any = grid.getItemPosition(grid.indexOf(box.buttons[key]))
        return (int(at[0]), int(at[1]), int(at[2]), int(at[3]))

    assert place("apply") == (1, 0, 1, 2)
    rows: dict[int, list[str]] = {}
    for key in ("save", "update", "rename", "delete", "export", "import"):
        row, _column, _rows, columns_taken = place(key)
        assert columns_taken == 1
        rows.setdefault(row, []).append(key)
    assert sorted(rows.values()) == [["export", "import"], ["rename", "delete"], ["save", "update"]]


def test_the_three_ways_to_add_edges_stand_apart(window: MainWindow) -> None:  # noqa: F811
    """D2803: more room between two ways to add edges than inside one."""
    tab = open_part(window, PART)
    form = _start(window, tab, "feature.fillet", "edge")
    inside = form.rules.layout().verticalSpacing()
    between = form.add_group.form.verticalSpacing()
    assert inside > 0 and between >= 3 * inside


def test_chamfer_flip_stays_in_the_lead_column(window: MainWindow) -> None:  # noqa: F811
    """D2803: Angle Distance hides the list beside Flip; Flip does not move to the middle."""
    tab = open_part(window, PART)
    form = _start(window, tab, "feature.chamfer", "edge")
    form.kind.setCurrentIndex(form.kind.findData("distance_distance"))
    pump(20)
    assert form.method.isVisible()
    beside = form.flip.x()
    form.kind.setCurrentIndex(form.kind.findData("angle_distance"))
    pump(20)
    assert not form.method.isVisible() and form.flip.isVisible()
    assert form.flip.x() == beside == 0


def test_hole_points_table_has_no_sideways_scroll_bar(window: MainWindow) -> None:  # noqa: F811
    """D2804: X and Y share the width of the table, and the bolt circle's start angle
    has room for its placeholder."""
    tab = open_part(window, PART)
    form = _start(window, tab, "feature.hole", "face")
    form.tabs.setCurrentIndex(1)  # Positions
    pump(30)
    _open_groups(window)
    assert window.fit_panels()
    pump(30)
    table = form.table
    assert table.isVisible()
    bar = table.horizontalScrollBar()
    assert bar.maximum() == 0 and not bar.isVisible()
    header = table.horizontalHeader()
    assert abs(header.sectionSize(0) - header.sectionSize(1)) <= 1
    for edit in (form.bolt_text, form.bolt_start):
        needed = edit.fontMetrics().horizontalAdvance(edit.placeholderText())
        assert edit.isVisible() and edit.contentsRect().width() > needed
    inner = [bar for bar in window.panel.findChildren(QTabBar) if bar.objectName() == "hole_tabs"]
    assert inner and inner[0].expanding()


def test_no_table_of_a_panel_scrolls_sideways(window: MainWindow) -> None:  # noqa: F811
    """D2804: the tables of Vent, Curve Through Points and Table Pattern share their
    width between their columns, as the Hole Tool's does. The sweep of every command
    checks every table; these are the ones that scrolled."""
    from PySide6.QtWidgets import QTableView

    tab = open_part(window, PART)
    seen = 0
    for command in ("feature.vent", "feature.point_curve", "feature.table_pattern"):
        settle(window, tab)
        assert select(window, tab, "sketch", shapes_of(tab))
        window.commands.trigger(command)
        pump(30)
        _open_groups(window)
        pump(20)
        assert window.fit_panels(), command
        pump(20)
        assert window.properties is not None
        shown = window.properties.currentWidget()
        for table in shown.findChildren(QTableView):
            if table.isVisibleTo(shown):
                seen += 1
                assert table.horizontalScrollBar().maximum() == 0, (command, table.objectName())
    assert seen >= 3


def test_drop_downs_under_long_words_fill_their_group(window: MainWindow) -> None:  # noqa: F811
    """D2801 in real panels: in Sweep and the Hole Tool every drop down that follows a
    word sits under it, flush with it and as wide as the group's rows, and none shows
    a cut entry. The fields after an icon start one icon cell in, not 72 px in."""
    tab = open_part(window, PART)
    for command, kind in (("feature.sweep", "sketch"), ("feature.hole", "face")):
        _start(window, tab, command, kind)
        assert window.panel is not None
        root = window.panel.groups_box
        under = [
            box
            for box in root.findChildren(QComboBox)
            if box.isVisibleTo(root) and columns.is_under(box)
        ]
        # How many depends on the font: a drop down goes under its word only in a
        # group with a word wider than the lead column (D2801). In the Mac's font the
        # Hole Tool has two such drop downs, in the Windows font three (D2810).
        assert len(under) >= 2, command
        for box in under:
            label = _label_of(box)
            assert label is not None, command
            assert _left(window, box) == _left(window, label), command
            assert box.mapTo(root, QPoint(0, 0)).y() > label.mapTo(root, QPoint(0, 0)).y()
            assert not is_cut(box) or box.property("elides_entry"), command
        assert len({box.width() for box in under}) == 1, command
        if command == "feature.sweep":  # its only word beside a field is a long one
            assert columns.column_width(root) <= icon_cell(root)
        window.panel.reject()
        pump(20)


def test_every_cut_entry_ends_with_an_ellipsis(window: MainWindow) -> None:  # noqa: F811
    """D2800: Loft's start and end constraints are longer than the room beside their
    icon. They are drawn with an ellipsis, not cut in the middle of a letter."""
    tab = open_part(window, PART)
    _start(window, tab, "feature.loft", "sketch")
    assert window.panel is not None
    root = window.panel.groups_box
    for box in root.findChildren(QComboBox):
        if not box.isVisibleTo(root) or box.isEditable():
            continue
        for index in range(box.count()):
            box.setCurrentIndex(index)
            pump(2)
            if is_cut(box):
                assert box.property("elides_entry"), box.currentText()
    assert window.left_dock.width() == window.default_left_width()
