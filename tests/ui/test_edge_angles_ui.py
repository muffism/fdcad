"""Edge Angle Analysis in the app (TR420, D929)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.print_tools import edge_angles as ea
from tests.ui.test_phase2_flow import _folders, plate_tab, window

__all__ = ["_folders", "window"]


def test_plate_edges_are_sharp_and_cancel_keeps_it_off(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    tab, _ext = plate_tab(qtbot, window)
    action = window.commands.actions["evaluate.edge_angles"]
    monkeypatch.setattr(ea, "ask_limit", lambda _w, _s: None)
    action.trigger()
    assert not action.isChecked() and not window.edge_angle_analysis.on
    monkeypatch.setattr(ea, "ask_limit", lambda _w, _s: 30.0)
    action.trigger()
    qtbot.waitUntil(lambda: "12 sharp edges" in window.status.text(), timeout=20000)
    layers = tab.viewport.print_layers  # type: ignore[attr-defined]
    assert len(layers["edge_angle_sharp"]) == 12 and layers["edge_angle_near"] == []
    assert "30 degrees" in window.status.text()
    action.trigger()
    assert tab.viewport.print_layers["edge_angle_sharp"] == []  # type: ignore[attr-defined]
