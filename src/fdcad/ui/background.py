"""Start background jobs so Python can free them (round 10e, D633)."""

from __future__ import annotations

from PySide6.QtCore import QRunnable, QThreadPool


def start_job(pool: QThreadPool, job: QRunnable) -> None:
    """Run ``job`` on ``pool``; the job is freed once nothing else holds it.

    ``pool.start(job)`` hands the job to Qt, and Python never frees it: every
    rebuild and preview kept its document copy and shapes until the app quit.
    Starting the job's ``run`` method gives the pool a task of its own, which the
    pool frees when ``run`` returns. Keep the job in a set until its result signal
    arrives, as before.
    """
    pool.start(job.run)
