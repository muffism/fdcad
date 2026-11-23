"""Background kernel jobs run one at a time (DECISIONS D400)."""

from __future__ import annotations

import threading
import time

from fdcad.core.kernel import KERNEL_LOCK, kernel_job


class _Job:
    def __init__(self, log: list[str], name: str) -> None:
        self.log, self.name = log, name

    @kernel_job
    def run(self) -> None:
        self.log.append(f"{self.name} start")
        time.sleep(0.05)
        self.log.append(f"{self.name} end")


def test_jobs_do_not_overlap() -> None:
    log: list[str] = []
    threads = [threading.Thread(target=_Job(log, n).run) for n in ("a", "b", "c")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    starts = [i for i, e in enumerate(log) if e.endswith("start")]
    assert all(log[i + 1] == log[i].replace("start", "end") for i in starts)


def test_lock_is_reentrant_and_released() -> None:
    @kernel_job
    def outer(_self: object) -> bool:
        with KERNEL_LOCK:  # code called from a job may take the lock again
            return True

    assert outer(object())
    assert KERNEL_LOCK.acquire(blocking=False)
    KERNEL_LOCK.release()
