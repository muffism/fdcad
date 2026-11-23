"""Ring Groove from the command (TR249, D874)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.body_tools import flow
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_command_opens_with_defaults(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window)
    assert flow.start(window, "feature.ring_groove")
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    feature = panel.feature
    assert feature.type == "ring_groove" and feature.params["ring_type"] == "ring"
    assert feature.params["position"].value == 2.0
    assert panel.body_form.active_pick == "face"
    panel.reject()
