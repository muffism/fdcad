"""O Ring Groove from the command (TR250, D886)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.body_tools import flow
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_command_opens_with_defaults(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window)
    assert flow.start(window, "feature.oring_groove")
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    feature = panel.feature
    assert feature.type == "oring_groove" and feature.params["use"] == "static"
    assert feature.params["position"].value == 2.0
    assert panel.body_form.active_pick == "face"
    panel.reject()
