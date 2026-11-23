"""Mould Cavity from the command (TR85 item 1, D2111)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.body_tools import flow
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_command_opens_with_defaults(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window)
    assert flow.start(window, "feature.mould_cavity")
    panel = window.panel
    assert panel is not None and panel.feature is not None
    assert panel.feature.type == "mould_cavity"
    assert panel.feature.params["factor"].value == 1.02
    panel.reject()
