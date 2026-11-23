"""Pickable cut faces while a section is on, so Measure works on them (TR213, D2502).

The faces are built on the kernel worker a moment after the section stops
changing and after each rebuild. The 3D view draws them see through over the
caps and lets them be picked like part faces.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal

from fdcad.core.kernel import kernel_job
from fdcad.core.section import SectionState

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab

#: Wait this long after the last section change before building faces (ms).
DELAY_MS = 200


class _Signals(QObject):
    done = Signal(object, int)


class _Job(QRunnable):
    def __init__(self, shape: Any, state: SectionState, generation: int) -> None:
        super().__init__()
        self.shape, self.state, self.generation = shape, state, generation
        self.signals = _Signals()

    @kernel_job
    def run(self) -> None:
        from fdcad.core.section_faces import cut_faces

        faces = cut_faces(self.shape, self.state)
        self.signals.done.emit(faces, self.generation)


class CutFaces(QObject):
    """Keeps the pickable cut faces of each part's section up to date."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._generation = 0
        self._wanted: tuple[DocumentTab, SectionState] | None = None
        self._jobs: set[_Job] = set()
        self._watched: set[int] = set()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(DELAY_MS)
        self.timer.timeout.connect(self._start)

    def update(self, tab: DocumentTab, state: SectionState | None) -> None:
        """Build the faces for ``state`` soon, or remove them with None."""
        self._generation += 1
        if state is None:
            self._wanted = None
            self.timer.stop()
            self._show(tab, [])
            return
        self._wanted = (tab, state)
        if id(tab) not in self._watched:
            self._watched.add(id(tab))
            tab.session.rebuilt.connect(lambda _r, t=tab: self._rebuilt(t))
        self.timer.start()

    def _rebuilt(self, tab: DocumentTab) -> None:
        wanted = self._wanted
        if wanted is not None and wanted[0] is tab:
            self.update(tab, wanted[1])

    def _start(self) -> None:
        wanted = self._wanted
        if wanted is None:
            return
        tab, state = wanted
        if not hasattr(tab.viewport, "set_section_faces"):
            return
        report = tab.session.report
        shape = getattr(report.body if report is not None else None, "shape", None)
        if shape is None:
            self._show(tab, [])
            return
        job = _Job(shape, state, self._generation)
        self._jobs.add(job)
        job.signals.done.connect(lambda faces, gen, j=job, t=tab: self._ready(faces, gen, j, t))
        QThreadPool.globalInstance().start(job)

    def _ready(self, faces: list[Any], generation: int, job: _Job, tab: DocumentTab) -> None:
        self._jobs.discard(job)
        if generation == self._generation:
            self._show(tab, faces)

    def _show(self, tab: DocumentTab, faces: list[Any]) -> None:
        fn = getattr(tab.viewport, "set_section_faces", None)
        if fn is not None:
            with contextlib.suppress(RuntimeError):  # the tab was closed
                fn(faces)

    def wait(self) -> None:
        """Wait for running jobs (tests)."""
        QThreadPool.globalInstance().waitForDone()
