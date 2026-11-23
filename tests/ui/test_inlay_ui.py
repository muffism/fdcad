"""Inlay from the command (TR184, D867)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.body_tools import flow
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_command_opens_with_a_depth(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window)
    assert flow.start(window, "feature.inlay")
    panel = window.panel
    assert panel is not None and panel.feature is not None
    assert panel.feature.type == "inlay" and panel.feature.params["depth"].value == 1.0
    panel.reject()
