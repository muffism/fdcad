"""Taskbar and Dock progress for long work (TR380 item 4, D2506)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.taskbar_progress import (
    BUSY,
    OFF,
    STEPS,
    TaskbarProgress,
    badge_text,
    platform_backend,
)
from tests.ui.test_main_window import _folders, window

__all__ = ["_folders", "window"]


class _Record:
    def __init__(self) -> None:
        self.seen: list[tuple[str, int, int]] = []

    def show(self, state: str, done: int, total: int) -> None:
        self.seen.append((state, done, total))


class _Broken:
    def show(self, state: str, done: int, total: int) -> None:
        raise OSError("no taskbar")


def test_badge_text() -> None:
    assert badge_text(OFF, 0, 0) == ""
    assert badge_text(BUSY, 0, 0) == "..."
    assert badge_text(STEPS, 1, 4) == "25%"
    assert badge_text(STEPS, 9, 4) == "100%"
    assert badge_text(STEPS, 1, 0) == "..."


def test_repeats_are_skipped_and_failures_ignored() -> None:
    record = _Record()
    bar = TaskbarProgress(record)
    bar.busy()
    bar.busy()
    bar.steps(1, 3)
    bar.steps(0, 0)
    bar.clear()
    assert record.seen == [(BUSY, 0, 0), (STEPS, 1, 3), (BUSY, 0, 0), (OFF, 0, 0)]
    TaskbarProgress(_Broken()).busy()  # never raises


def test_off_unless_the_integration_is_on(window: MainWindow) -> None:
    assert platform_backend(window, "win32") is None
    from fdcad.ui import system_integration

    system_integration.enable(True)
    try:
        assert platform_backend(window, "linux") is None
    finally:
        system_integration.enable(False)


def test_status_progress_reaches_the_taskbar(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = _Record()
    from fdcad.ui import taskbar_progress

    monkeypatch.setattr(taskbar_progress, "platform_backend", lambda _w: record)
    feedback = window.feedback
    feedback.begin("export")
    qtbot.waitUntil(lambda: window.progress.isVisible(), timeout=2000)
    assert record.seen[-1] == (BUSY, 0, 0)
    feedback.step(2, 5)
    assert record.seen[-1] == (STEPS, 2, 5)
    feedback.end("export")
    assert record.seen[-1] == (OFF, 0, 0)
