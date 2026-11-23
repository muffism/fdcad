"""Right click in the view moves to the next pick box (TR207, D831)."""

from __future__ import annotations

from PySide6.QtCore import QPointF
from pytestqt.qtbot import QtBot

from fdcad.ui.body_tools import flow
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_right_click_steps_through_pick_boxes_then_offers_ok(
    qtbot: QtBot, window: MainWindow
) -> None:
    tab, _ids = _open(qtbot, window)
    assert flow.start(window, "feature.linear_pattern")
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    form = panel.body_form
    first = form.active_pick
    assert first is not None
    menus = window.context_menus
    seen = [first]
    while (label := menus.next_pick_box()) is not None:
        seen.append(form.active_pick)
        assert label
    assert len(seen) >= 2 and len(set(seen)) == len(seen)
    menu = menus.view_menu(tab, QPointF(5, 5))  # the last box: the menu offers OK
    assert menu is not None
    from fdcad.ui.main_window.context_menu import keys

    assert keys(menu)[:2] == ["ok", "cancel"]
    panel.reject()
