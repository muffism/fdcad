"""Shaft Shape from the command (TR247, D841)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.body_tools import flow
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_command_opens_with_defaults(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window)
    assert flow.start(window, "feature.shaft_shape")
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    feature = panel.feature
    assert feature.type == "shaft_shape" and feature.params["shaft_form"] == "d_flat"
    assert feature.params["clearance"].value == 0.1
    assert panel.body_form.active_pick == "face"
    panel.reject()
