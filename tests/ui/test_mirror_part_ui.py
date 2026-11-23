"""File, Mirror Part (TR73, D899)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window import mirror_part as mp
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_configurations_ui import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_mirror_saves_and_opens_a_new_part(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _open(qtbot, window)
    target = tmp_path / "left.fdprt"
    monkeypatch.setattr(mp, "ask_path", lambda _w, _s: str(target))
    count = window.tabs.count()
    assert mp.mirror_part(window)
    qtbot.waitUntil(lambda: window.tabs.count() == count + 1, timeout=30000)
    assert target.exists()
    assert "mirrored" in window.status.text() or window.tabs.count() == count + 1
