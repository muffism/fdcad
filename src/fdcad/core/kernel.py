"""Global kernel settings (PLAN 11.3 item 3: parallel booleans, meshing and shape checks)."""

from __future__ import annotations

import functools
import threading
from collections.abc import Callable

from OCP.BOPAlgo import BOPAlgo_Options

_configured = False


def configure() -> None:
    """Turn on OpenCascade's parallel modes once per process."""
    global _configured
    if _configured:
        return
    BOPAlgo_Options.SetParallelMode_s(True)
    _configured = True


# One kernel job at a time -------------------------------------------------------------

#: Background jobs share the last rebuild's shapes. OpenCascade may write to a shape
#: while it reads it (meshing, naming), so two jobs on the same shapes at once can
#: crash. Every background job that calls the kernel holds this lock while it runs
#: (DECISIONS D400). The kernel's own parallel modes run inside one job and are not
#: affected. Re-entrant, so a job may call code that takes it again.
KERNEL_LOCK = threading.RLock()


def kernel_job[S, R](run: Callable[[S], R]) -> Callable[[S], R]:
    """Decorate a background job's ``run`` so it holds ``KERNEL_LOCK`` while it runs."""

    @functools.wraps(run)
    def locked(self: S) -> R:
        with KERNEL_LOCK:
            return run(self)

    return locked
