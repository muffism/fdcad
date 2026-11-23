"""Background graph evaluation with cancel (PLAN Phase 7). No Qt: the editor wraps it.

One worker thread runs evaluations in turn. Submitting a new evaluation cancels
the one still running, so the newest edit always wins.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable
from concurrent.futures import Future, ThreadPoolExecutor

from fdcad.core.graph.engine import SHARED, Evaluator, GraphResult
from fdcad.core.graph.model import Graph
from fdcad.core.graph.nodes.base import GraphEnv
from fdcad.core.kernel import KERNEL_LOCK


class GraphWorker:
    """Runs graph evaluations off the calling thread."""

    def __init__(self, evaluator: Evaluator | None = None) -> None:
        self.evaluator = evaluator or SHARED
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="fdcad-graph")
        self._cancel: threading.Event | None = None

    def submit(
        self,
        graph: Graph,
        env: GraphEnv | None = None,
        done: Callable[[GraphResult], None] | None = None,
        targets: Iterable[str] | None = None,
    ) -> Future[GraphResult]:
        """Start evaluating a copy of ``graph``; ``done`` is called on the worker thread."""
        self.cancel()
        event = threading.Event()
        self._cancel = event
        snapshot = graph.copy()
        wanted = list(targets) if targets is not None else None

        def job() -> GraphResult:
            with KERNEL_LOCK:  # one kernel job at a time (D400)
                result = self.evaluator.evaluate(snapshot, env, event.is_set, wanted)
            if event.is_set():
                result.cancelled = True
            if done is not None:
                done(result)
            return result

        return self._pool.submit(job)

    def cancel(self) -> None:
        """Ask the running evaluation to stop at the next node."""
        if self._cancel is not None:
            self._cancel.set()

    def shutdown(self) -> None:
        """Cancel and wait for the worker thread to end."""
        self.cancel()
        self._pool.shutdown(wait=True)
