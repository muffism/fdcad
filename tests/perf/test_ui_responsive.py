"""The window stays responsive while a long rebuild runs (round 10e, D631)."""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, QTimer
from pytestqt.qtbot import QtBot

from fdcad.samples.make import SAMPLE_DIR
from fdcad.ui import ui_turns as turns_module
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.ui_turns import BLOCKED, STALE, UiTurns

#: The longest the UI thread may go without a turn. Before the fix the window froze
#: for 1.2 s to 3.3 s while the 200 feature part opened.
WORST_GAP = 0.6


@pytest.fixture(autouse=True)
def _folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("FDCAD_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> Iterator[MainWindow]:
    settings = Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))
    win = MainWindow(settings)
    win.resize(1600, 1000)
    win.show()
    win.finish_setup()
    yield win
    while win.tabs.count():
        tab = win.tabs.widget(0)
        assert isinstance(tab, DocumentTab)
        tab.session.cancel_rebuild()
        tab.session.wait()
        tab.autosaver.discard()
        win.tabs.removeTab(0)
    win.close()


def test_window_keeps_painting_while_200_features_rebuild(qtbot: QtBot, window: MainWindow) -> None:
    gaps: list[float] = []
    last = [time.perf_counter()]

    def tick() -> None:
        now = time.perf_counter()
        gaps.append(now - last[0])
        last[0] = now

    timer = QTimer()
    timer.timeout.connect(tick)
    window.open_path(SAMPLE_DIR / "generated_200.fdprt")
    tab = window.current
    assert tab is not None
    last[0] = time.perf_counter()
    timer.start(10)
    qtbot.waitUntil(lambda: tab.session.report is not None, timeout=60000)
    timer.stop()
    assert tab.session.report is not None and tab.session.report.body is not None
    assert len(gaps) > 10
    assert max(gaps) < WORST_GAP, sorted(gaps)[-5:]


def test_rebuild_waits_only_for_a_busy_ui(qapp: object, monkeypatch: pytest.MonkeyPatch) -> None:
    turns = UiTurns()
    assert not turns.starved()  # no rebuild queued
    turns.begin()
    assert not turns.starved()  # the UI just had a turn
    now = time.perf_counter()
    monkeypatch.setattr(turns, "_last", now - (STALE + BLOCKED) / 2)
    assert turns.starved()
    with turns.hold():  # the UI thread waits for the rebuild on purpose
        assert not turns.starved()
    monkeypatch.setattr(turns, "_last", now - BLOCKED * 2)
    assert not turns.starved()  # blocked, not busy: never wait for it
    turns.end()
    monkeypatch.setattr(turns, "_last", now - (STALE + BLOCKED) / 2)
    assert not turns.starved()  # no rebuild runs any more


def test_give_way_stops_after_the_longest_pause(
    qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    turns = UiTurns()
    turns.begin()
    monkeypatch.setattr(turns, "starved", lambda: True)
    monkeypatch.setattr(turns_module, "MAX_PAUSE", 0.05)
    start = time.perf_counter()
    turns.give_way()
    assert 0.04 < time.perf_counter() - start < 0.5
    turns.end()


def test_session_wait_does_not_slow_the_rebuild(qtbot: QtBot) -> None:
    from fdcad.core.io import fdef
    from fdcad.ui.session import DocumentSession

    session = DocumentSession(fdef.load(SAMPLE_DIR / "generated_200.fdprt"))
    start = time.perf_counter()
    session.request_rebuild()
    assert session.wait(60000)
    # Waiting blocks the UI thread on purpose; the rebuild must not pause for it.
    assert time.perf_counter() - start < 15
