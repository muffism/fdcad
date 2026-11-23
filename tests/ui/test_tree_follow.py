"""The tree follows the view and the view the tree (TR200, D808)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_picks_scroll_the_tree_and_go_to_feature(qtbot: QtBot, window: MainWindow) -> None:
    tab, ids = _open(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None and window.tree is not None
    top = report.body.face(f"{ids['boss']}/cap/end")
    follow = window.tree_follow
    assert follow.picked(tab, [top]) == ids["boss"]
    assert follow.saved_scroll is not None
    follow.picked(tab, [])
    assert follow.saved_scroll is None
    window.settings.tree_follows_selection = False
    assert follow.picked(tab, [top]) is None
    window.settings.tree_follows_selection = True
    assert follow.go_to(tab, top)
    assert window.tree.selected_id() == ids["boss"]
    assert any(n.startswith(f"{ids['boss']}/") for n in follow.names_of(ids["boss"]))
    menu = window.context_menus.build_view_menu(tab, [top])
    assert any(a.text() == "Go To Feature" for a in menu.actions())
