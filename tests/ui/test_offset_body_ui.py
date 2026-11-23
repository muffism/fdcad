"""Offset Body from the command and Shell corners in the panel (TR129, D825)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.body_tools import flow
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_offset_body_command_opens_with_defaults(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window)
    assert flow.start(window, "feature.offset_body")
    panel = window.panel
    assert panel is not None and panel.is_editing
    feature = panel.feature
    assert feature.type == "offset_body" and feature.name == "Offset Body 1"
    assert feature.params["distance"].value == 1.0 and feature.params["corners"] == "sharp"
    panel.reject()
