"""Sketch Square to Edge (TR51, D898)."""

from __future__ import annotations

from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from pytestqt.qtbot import QtBot

from fdcad.core.features.base import FeatureState
from fdcad.ui.main_window.context_menu import sketch_normal_to
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_configurations_ui import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_a_plane_square_to_the_edge_and_a_sketch_on_it(qtbot: QtBot, window: MainWindow) -> None:
    tab = _open(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    edge = TopExp_Explorer(report.body.shape, TopAbs_EDGE).Current()
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        fid = sketch_normal_to(window, tab, edge, (0.0, 0.0, 0.0))
    assert fid is not None
    plane = tab.session.document.feature(fid)
    assert plane.type == "ref_plane" and plane.params["method"] == "normal_to_curve"
    after = tab.session.report
    assert after is not None and after.results[fid].state is FeatureState.OK
    qtbot.waitUntil(
        lambda: window.sketch_mode is not None and window.sketch_mode.canvas is not None,
        timeout=10000,
    )
    window.sketch_mode.cancel()  # type: ignore[union-attr]
