"""Point Pattern from the command (TR365, D887)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.body_tools import flow
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_command_opens_with_defaults(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window)
    assert flow.start(window, "feature.point_pattern")
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    feature = panel.feature
    assert feature.type == "point_pattern"
    panel.reject()
