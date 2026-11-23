"""Background jobs for the print and evaluate tools (CLAUDE.md rule 2).

Kernel work runs on the thread pool. Its result, or the message of the
exception it raised as a clause without a final full stop (D550), comes back
on the UI thread through a signal, so a failed tool never crashes the app
(CLAUDE.md rule 7).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from fdcad.core.kernel import kernel_job
from fdcad.ui.background import start_job
from fdcad.ui.strings import clause

_RUNNING: set[Job] = set()


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(str)


class Job(QRunnable):
    """Runs ``work`` off the UI thread and reports its result or failure."""

    def __init__(self, work: Callable[[], Any]) -> None:
        super().__init__()
        self.work = work
        self.signals = _Signals()

    @kernel_job
    def run(self) -> None:
        """Called by the thread pool."""
        try:
            result = self.work()
        except Exception as exc:  # report, never crash
            self.signals.failed.emit(clause(exc))
        else:
            self.signals.done.emit(result)


def start(
    work: Callable[[], Any],
    done: Callable[[Any], None],
    failed: Callable[[str], None],
) -> Job:
    """Run ``work`` in the background; ``done`` or ``failed`` is called on the UI thread."""
    job = Job(work)
    _RUNNING.add(job)

    def finish_ok(result: Any) -> None:
        _RUNNING.discard(job)
        job.signals.deleteLater()  # these slots hold the job: let both go (D633)
        done(result)

    def finish_failed(message: str) -> None:
        _RUNNING.discard(job)
        job.signals.deleteLater()
        failed(message)

    job.signals.done.connect(finish_ok)
    job.signals.failed.connect(finish_failed)
    start_job(QThreadPool.globalInstance(), job)
    return job
