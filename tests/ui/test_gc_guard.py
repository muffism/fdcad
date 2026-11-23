"""Python's garbage collector runs on the UI thread only (round 10e, D639)."""

from __future__ import annotations

import gc
import threading
import weakref

from pytestqt.qtbot import QtBot

from fdcad.ui import gc_guard


class _Node:
    def __init__(self) -> None:
        self.other: _Node | None = None


def test_cycles_are_collected_by_the_ui_timer(qtbot: QtBot) -> None:
    gc_guard.install()
    assert gc_guard.installed()
    a, b = _Node(), _Node()
    a.other, b.other = b, a
    probe = weakref.ref(a)
    del a, b
    # Enough new objects to pass the first threshold; then the UI timer's check
    # collects them. Called directly so no earlier tick can age the cycle.
    keep = [_Node() for _ in range(gc.get_threshold()[0] + 10)]
    collector = gc_guard._collector
    assert collector is not None
    collector.check()
    assert probe() is None
    assert collector.timer.isActive()
    del keep


def test_background_threads_never_collect(qtbot: QtBot) -> None:
    # A rebuild thread that allocated could run a collection that destroyed Qt
    # objects off the UI thread: a segmentation fault in the slow app sweep.
    gc_guard.install()
    collected: list[str] = []

    def watch(phase: str, _info: dict[str, int]) -> None:
        if phase == "start":
            collected.append(threading.current_thread().name)

    gc.callbacks.append(watch)
    try:
        worker = threading.Thread(
            target=lambda: [_Node() for _ in range(gc.get_threshold()[0] * 20)], name="worker"
        )
        worker.start()
        worker.join()
    finally:
        gc.callbacks.remove(watch)
    assert "worker" not in collected
