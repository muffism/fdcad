"""Select Loop, Partial Loop and Tangent from the 3D right click menu (TR92, D823)."""

from __future__ import annotations

from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_loop_flip_partial_and_tangent(qtbot: QtBot, window: MainWindow) -> None:
    tab, ids = _open(qtbot, window)
    menus = window.context_menus
    report = tab.session.report
    assert report is not None and report.body is not None
    top = report.body.face(f"{ids['boss']}/cap/end")
    edges = []
    explorer = TopExp_Explorer(top, TopAbs_EDGE)
    while explorer.More():
        edges.append(explorer.Current())
        explorer.Next()
    first = menus.select_loop(tab, edges[0])
    assert len(first) >= 3 and tab.selection == first
    second = menus.select_loop(tab, edges[0])  # again: the next face
    assert second and not all(any(a.IsSame(b) for b in first) for a in second)
    menus.start_partial_loop(tab, edges[0])
    assert menus.loop_start is not None
    part = menus.end_partial_loop(tab, edges[1])
    assert len(part) >= 2 and menus.loop_start is None
    assert menus.select_tangent(tab, top) == [top] or len(menus.select_tangent(tab, top)) >= 1
