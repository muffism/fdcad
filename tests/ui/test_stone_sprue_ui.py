"""Stone Setting and Sprue Tree from their commands (TR408 items 2 and 3, D2410, D2411)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.ui.body_tools import flow
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


@pytest.mark.parametrize("ftype", ["stone_setting", "sprue_tree", "roof"])
def test_command_opens_with_defaults(qtbot: QtBot, window: MainWindow, ftype: str) -> None:
    _open(qtbot, window)
    assert flow.start(window, f"feature.{ftype}")
    panel = window.panel
    assert panel is not None and panel.feature is not None
    assert panel.feature.type == ftype
    panel.reject()
