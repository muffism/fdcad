"""Suction Cups and Islands (TR409, D1213)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.print_tools import islands_tool
from tests.ui.test_body_display import _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def test_check_runs_and_marks(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tab = _open(qtbot, window)
    asked: list[str] = []
    monkeypatch.setattr(islands_tool, "ask", lambda _w, message, _c: asked.append(message) or "")
    assert islands_tool.cups_and_islands(window) is not None
    qtbot.waitUntil(
        lambda: islands_tool.LAYER in getattr(tab.viewport, "print_layers", {}), timeout=30000
    )
    assert "suction cups" in window.status.text().lower()
