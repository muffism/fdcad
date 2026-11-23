"""Layer Preview in the 3D view (TR315, D993)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_layer_preview_draws_and_counts(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window)
    window.commands.actions["evaluate.layer_preview"].trigger()
    qtbot.waitUntil(lambda: "layers of" in window.status.text(), timeout=30000)
    result = window.layer_preview.result
    assert result is not None and result.layers > 0 and result.edges
    window.commands.actions["evaluate.layer_preview"].trigger()
    assert not window.layer_preview.on


def test_layer_preview_says_why_it_has_no_lines(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    # D2635: a part whose mesh failed showed no lines and no word.
    from fdcad.core.printing import layer_lines as module

    problem = "Layer Preview failed: the part's mesh is incomplete. Rebuild it and try again."
    monkeypatch.setattr(
        module, "layer_lines", lambda *_a: module.LayerLines(layers=5, problem=problem)
    )
    _open(qtbot, window)
    window.commands.actions["evaluate.layer_preview"].trigger()
    qtbot.waitUntil(lambda: window.status.text() == problem, timeout=30000)
    window.commands.actions["evaluate.layer_preview"].trigger()
