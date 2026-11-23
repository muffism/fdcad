"""Deform Point, Curve to Curve and Surface Push from their commands (TR67, D2412)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.ui.body_tools import flow
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


@pytest.mark.parametrize("ftype", ["deform_point", "deform_curve", "surface_push"])
def test_command_opens_with_defaults(qtbot: QtBot, window: MainWindow, ftype: str) -> None:
    _open(qtbot, window)
    assert flow.start(window, f"feature.{ftype}")
    panel = window.panel
    assert panel is not None and panel.feature is not None
    assert panel.feature.type == ftype
    panel.reject()
