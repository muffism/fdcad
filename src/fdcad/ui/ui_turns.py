"""Give the UI thread a turn while a background rebuild runs (D631).

The kernel bindings keep Python's global lock (the GIL) while one kernel call runs,
which can take tens of milliseconds for a boolean. Every Qt call the UI makes from
Python gives the GIL up, so while a rebuild runs each such call waits for the next
kernel call to end. A repaint makes hundreds of them, and the window froze for
seconds while a large part opened.

While a rebuild runs, a timer on the UI thread beats every few milliseconds. Between
features the rebuild checks the beat. When the UI has not had a turn for a while, the
rebuild sleeps briefly, which lets the UI finish its work at full speed.
"""

from __future__ import annotations

import contextlib
import threading
import time
from collections.abc import Iterator

from PySide6.QtCore import QObject, QTimer

#: How often the UI thread beats while a rebuild runs, in milliseconds.
TICK_MS = 15
#: The UI counts as starved when its last beat is older than this, in seconds.
STALE = 0.05
#: A beat older than this means the UI thread is blocked, not busy: do not wait for it.
BLOCKED = 0.5
#: The longest one pause between two features, in seconds.
MAX_PAUSE = 0.1


class UiTurns(QObject):
    """A heartbeat from the UI thread that background rebuilds give way to."""

    def __init__(self) -> None:
        super().__init__()
        self._last = time.perf_counter()
        self._jobs = 0
        self._holds = 0
        self._lock = threading.Lock()
        self._timer: QTimer | None = None

    # UI thread ----------------------------------------------------------------------

    def begin(self) -> None:
        """A rebuild is queued (UI thread): beat until it calls ``end``."""
        with self._lock:
            self._jobs += 1
        self.beat()
        if self._timer is None:
            self._timer = QTimer(self)
            self._timer.setInterval(TICK_MS)
            self._timer.timeout.connect(self._tick)
        if not self._timer.isActive():
            self._timer.start()

    def beat(self) -> None:
        """Record that the UI thread had a turn."""
        self._last = time.perf_counter()

    def _tick(self) -> None:
        self.beat()
        if self._jobs == 0 and self._timer is not None:
            self._timer.stop()

    @contextlib.contextmanager
    def hold(self) -> Iterator[None]:
        """The UI thread blocks on purpose (waiting for a job): rebuilds must not wait."""
        with self._lock:
            self._holds += 1
        try:
            yield
        finally:
            with self._lock:
                self._holds -= 1
            self.beat()

    # Rebuild thread -----------------------------------------------------------------

    def end(self) -> None:
        """The rebuild that ``begin`` counted has finished (any thread)."""
        with self._lock:
            self._jobs = max(0, self._jobs - 1)

    def starved(self) -> bool:
        """True when the UI thread is busy and waiting for the GIL."""
        if self._holds or self._jobs == 0:
            return False
        age = time.perf_counter() - self._last
        return STALE < age < BLOCKED

    def give_way(self) -> None:
        """Sleep while the UI thread catches up, at most ``MAX_PAUSE`` seconds."""
        end = time.perf_counter() + MAX_PAUSE
        while self.starved() and time.perf_counter() < end:
            time.sleep(0.002)


_TURNS: UiTurns | None = None


def ui_turns() -> UiTurns:
    """The app wide heartbeat. Create it on the UI thread first."""
    global _TURNS
    if _TURNS is None:
        _TURNS = UiTurns()
    return _TURNS
