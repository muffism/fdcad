"""Fillet and Chamfer fit the left panel's default width, with tabs (D2790).

The left panel widens itself for a property panel that needs more room (D1033).
Fillet needed 531 px and Chamfer 349 px where the panel is 260 px by default.
Their rows are now stacked, their drop downs may be narrower than their longest
entry, and their groups sit on three tabs, so neither ever asks for more than
the default width: in every type, on every tab, with every group open.
"""

from __future__ import annotations

from typing import Any

import pytest
from PySide6.QtWidgets import QApplication, QComboBox
from pytestqt.qtbot import QtBot

from fdcad.core.features.modify import edges_of
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.property_panel.groups import Group
from fdcad.ui.property_panel.tabs import PanelTabs
from tests.ui.test_main_window import _open_plate
from tests.ui.test_ui_polish_controls import styled  # noqa: F401  (fixture)
from tests.ui.test_workflow import _folders, window  # noqa: F401  (fixtures)


def _open_all(window: MainWindow) -> None:  # noqa: F811
    """Open every group on show and tick the ones with a tick box."""
    assert window.panel is not None
    for group in window.panel.groups_box.findChildren(Group):
        if not group.isHidden():
            group.set_checked(True)
            group.set_expanded(True)


def _widths(qtbot: QtBot, window: MainWindow) -> dict[str, int]:  # noqa: F811
    """The width the left panel needs on each tab on show, by the tab's title."""
    panel = window.panel
    assert panel is not None and panel.page_tabs is not None
    tabs: PanelTabs = panel.page_tabs
    out: dict[str, int] = {}
    for index, key in enumerate(tabs.keys):
        if not tabs.bar.isTabVisible(index):
            continue
        tabs.show_tab(key)
        _open_all(window)
        qtbot.wait(20)
        out[tabs.bar.tabText(index)] = window.panel_width_needed()
    tabs.show_tab(tabs.keys[0])
    return out


def _pick_edges(window: MainWindow, count: int) -> None:  # noqa: F811
    tab = window.current
    assert tab is not None and window.panel is not None
    report = tab.session.report
    assert report is not None and report.body is not None
    edges = edges_of(report.body.shape)[:count]
    assert window.panel.form.take_shapes(report.body, edges) is None


@pytest.mark.parametrize("kind", ["fillet", "chamfer"])
def test_the_panel_never_needs_more_than_the_default_width(
    kind: str,
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    _open_plate(qtbot, window)
    default = window.default_left_width()
    assert window.left_dock.width() == default
    window.insert_feature(kind, "boss")
    qtbot.wait(50)
    panel = window.panel
    assert panel is not None and panel.is_editing and panel.page_tabs is not None
    form: Any = panel.form
    _pick_edges(window, 3)
    types: QComboBox = form.kind
    seen: dict[str, dict[str, int]] = {}
    for index in range(types.count()):
        types.setCurrentIndex(index)
        qtbot.wait(20)
        if kind == "fillet":
            form.multiple.setChecked(True)  # a radius row for each edge
            form.controls.setValue(2)  # variable size: two points on each edge
        partial: QComboBox = form.partial_kind
        for choice in range(partial.count()):
            partial.setCurrentIndex(choice)
            qtbot.wait(20)
            for title, need in _widths(qtbot, window).items():
                name = f"{types.itemText(index)}, {partial.itemText(choice)}, {title}"
                seen[name] = {"needs": need}
    wide = {name: found for name, found in seen.items() if found["needs"] > default}
    assert not wide, f"wider than the default {default} px: {wide}"
    # So the left panel kept its width while the panel was open, and after it.
    assert window.left_dock.width() == default
    panel.cancel()
    qtbot.wait(20)
    assert window.left_dock.width() == default


def test_fillet_groups_sit_on_three_tabs(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    _open_plate(qtbot, window)
    window.insert_feature("fillet", "boss")
    qtbot.wait(50)
    panel = window.panel
    assert panel is not None and panel.page_tabs is not None
    tabs = panel.page_tabs
    assert [tabs.bar.tabText(i) for i in range(tabs.bar.count())] == [
        "Main",
        "More",
        "Favourites",
    ]
    where = {key: tabs.key_of(group) for key, group in panel.groups.items()}
    assert where["fillet_type"] == where["items"] == where["parameters"] == "main"
    assert where["add_edges"] == where["partial"] == where["limits"] == "more"
    assert where["favourites"] == "favourites"
    # One page shows at a time, and the first field keeps the focus on Main.
    assert tabs.current() == "main"
    assert panel.groups["items"].isVisible() and not panel.groups["limits"].isVisible()
    tabs.show_tab("more")
    assert panel.groups["limits"].isVisible() and not panel.groups["items"].isVisible()
    assert tabs.bar.isVisible()


def test_a_tab_with_nothing_to_show_is_hidden(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """A face fillet has no Add Edges, Partial Edges or Limits: More has nothing left."""
    _open_plate(qtbot, window)
    window.insert_feature("fillet", "boss")
    qtbot.wait(50)
    panel = window.panel
    assert panel is not None and panel.page_tabs is not None
    tabs, form = panel.page_tabs, panel.form
    more = tabs.keys.index("more")
    assert tabs.bar.isTabVisible(more)
    tabs.show_tab("more")
    form.kind.setCurrentIndex(form.kind.findData("face"))
    qtbot.wait(20)
    assert not tabs.bar.isTabVisible(more)
    assert tabs.current() == "main"  # it left the tab that went away
    form.kind.setCurrentIndex(form.kind.findData("constant"))
    qtbot.wait(20)
    assert tabs.bar.isTabVisible(more)


def test_a_panel_without_tabs_is_as_before(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """Tabs are taken off when the next panel has none."""
    _open_plate(qtbot, window)
    window.insert_feature("fillet", "boss")
    qtbot.wait(50)
    panel = window.panel
    assert panel is not None and panel.page_tabs is not None
    assert not panel.tab_bar_box.isHidden()
    panel.cancel()
    qtbot.wait(20)
    window.insert_feature("shell", "boss")
    qtbot.wait(50)
    assert panel.page_tabs is None and panel.tab_bar_box.isHidden()
    assert panel.groups and all(g.parentWidget() is panel.groups_box for g in panel.groups.values())
