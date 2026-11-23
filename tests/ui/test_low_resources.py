"""Low disk space and memory warnings with a Save button (TR220, D968)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.resources import Shortage
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_bars_come_and_go_with_the_shortage(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    tab, _ids = _open(qtbot, window)
    saved: list[bool] = []
    monkeypatch.setattr(window, "save_all", lambda: saved.append(True) or 1)
    window.check_resources([Shortage("disk", 100 * 1024 * 1024, "C:/parts"), Shortage("memory", 1)])
    bars = tab.message_bars.bars
    assert set(bars) == {"low_disk", "low_memory"}
    assert "100 MB" in bars["low_disk"].label.text()
    button = bars["low_disk"].action_button
    assert button is not None
    button.click()
    assert saved == [True]
    window.check_resources([])
    assert not tab.message_bars.bars


def test_a_real_check_runs(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window)
    assert isinstance(window.check_resources(), list)
    assert window.resource_timer.isActive()
