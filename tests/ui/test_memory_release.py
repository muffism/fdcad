"""Closed parts and finished background jobs are freed (round 10e, D633)."""

from __future__ import annotations

import gc
import time
import weakref
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QObject, QRunnable, QSettings, QThreadPool, Signal
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from fdcad.core.io import fdef
from fdcad.samples.make import SAMPLE_DIR
from fdcad.ui.background import start_job
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.session import DocumentSession, _RebuildJob


@pytest.fixture(autouse=True)
def _folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("FDCAD_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> Iterator[MainWindow]:
    settings = Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))
    win = MainWindow(settings)
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


def _flush(qtbot: QtBot) -> None:
    qtbot.wait(20)
    app = QApplication.instance()
    assert app is not None
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    gc.collect()


def _alive(kind: type) -> int:
    gc.collect()
    return sum(isinstance(o, kind) for o in gc.get_objects())


def test_rebuild_jobs_are_freed(qtbot: QtBot) -> None:
    # The thread pool owned every rebuild job, so each rebuild kept its copy of
    # the document until the app quit.
    session = DocumentSession(fdef.load(SAMPLE_DIR / "plate_with_holes.fdprt"))
    before = _alive(_RebuildJob)
    for _ in range(5):
        with qtbot.waitSignal(session.rebuilt, timeout=30000):
            session.request_rebuild()
    session.wait()
    _flush(qtbot)
    assert _alive(_RebuildJob) <= before


def test_closing_a_part_frees_its_session_and_shapes(qtbot: QtBot, window: MainWindow) -> None:
    # The window owned every session, so a closed part kept its last rebuild
    # with every feature's shapes, its undo history and its tab.
    window.open_path(SAMPLE_DIR / "plate_with_holes.fdprt")
    tab = window.current
    assert tab is not None
    live = tab.session
    session = weakref.ref(live)

    def rebuilt() -> bool:
        current = session()
        return current is not None and current.report is not None

    qtbot.waitUntil(rebuilt, timeout=30000)
    report = live.report
    assert report is not None
    report_ref = weakref.ref(report)
    index = window.tabs.indexOf(tab)
    del report, live, tab
    assert window.close_tab(index)
    _flush(qtbot)
    assert report_ref() is None
    assert session() is None


def test_close_leaves_a_safe_empty_session(qtbot: QtBot) -> None:
    # A panel that still holds the session for a moment sees an empty part.
    session = DocumentSession(fdef.load(SAMPLE_DIR / "plate_with_holes.fdprt"))
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        session.request_rebuild()
    session.close()
    assert session.report is None
    assert session.undo.count() == 0
    assert session.parent() is None
    assert session.document.features  # the document itself stays readable


class _Signals(QObject):
    done = Signal(int)


class _Payload:
    """Stands for the document copy and shapes a job holds."""


class _Job(QRunnable):
    def __init__(self) -> None:
        super().__init__()
        self.payload = _Payload()
        self.signals = _Signals()

    def run(self) -> None:
        self.signals.done.emit(1)


def test_started_jobs_are_freed_after_they_ran(qtbot: QtBot) -> None:
    before = _alive(_Payload)
    pool = QThreadPool.globalInstance()
    for _ in range(10):
        start_job(pool, _Job())
    pool.waitForDone(10000)
    deadline = time.perf_counter() + 2
    while _alive(_Payload) > before and time.perf_counter() < deadline:
        _flush(qtbot)
    assert _alive(_Payload) == before
