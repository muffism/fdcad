"""Run Python's garbage collector on the UI thread only (round 10e, D639).

Python collects reference cycles in whichever thread happens to allocate at the
time, often a background rebuild. When a cycle holds Qt objects, they were then
destroyed off the UI thread while the UI thread used Qt, and the app could crash
(a segmentation fault in the slow app sweep). Automatic collection is turned off
and a UI timer collects instead, using the same generation thresholds.
"""

from __future__ import annotations

import gc

from PySide6.QtCore import QCoreApplication, QObject, QTimer

#: How often the UI thread checks whether a collection is due, in milliseconds.
INTERVAL_MS = 500

_collector: _Collector | None = None


class _Collector(QObject):
    def __init__(self, app: QCoreApplication) -> None:
        super().__init__(app)
        self.threshold = gc.get_threshold()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check)
        self.timer.start(INTERVAL_MS)

    def check(self) -> None:
        """Collect the generations whose counts passed their thresholds."""
        first, second, third = gc.get_count()
        if first <= self.threshold[0]:
            return
        generation = 0
        if second > self.threshold[1]:
            generation = 2 if third > self.threshold[2] else 1
        gc.collect(generation)


def install() -> None:
    """Collect only on the UI thread from now on. Call on the UI thread; runs once."""
    global _collector
    app = QCoreApplication.instance()
    if app is None or _collector is not None:
        return
    _collector = _Collector(app)
    gc.disable()


def installed() -> bool:
    """True once the UI thread collects instead of Python's automatic collection."""
    return _collector is not None and not gc.isenabled()
