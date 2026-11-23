"""Remove History (TR158, D983).

Turns the whole part into one plain body: the built shape is written to STEP off
the UI thread, then every feature after the origin and planes is replaced by one
Imported STEP feature holding it, as one undo step. Variables, configurations and
appearance stay; values that pointed at the old features have nothing to drive.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import QMessageBox

from fdcad.core.kernel import kernel_job
from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow
    from fdcad.ui.session import DocumentSession


class _Signals(QObject):
    done = Signal(object)


class StepJob(QRunnable):
    """Writes the part's shape as STEP data off the UI thread; never raises."""

    def __init__(self, shape: Any) -> None:
        super().__init__()
        self.shape = shape
        self.signals = _Signals()

    @kernel_job
    def run(self) -> None:
        """Emit the STEP bytes, or None when the kernel failed."""
        from fdcad.core.io.save_bodies import step_bytes

        try:
            data: bytes | None = step_bytes(self.shape)
        except Exception:
            data = None
        self.signals.done.emit(data)


def confirm(window: Any, count: int) -> bool:
    """Ask first (a seam for tests); No is the default."""
    answer = QMessageBox.question(
        window,
        strings.REMOVE_HISTORY_TITLE,
        strings.REMOVE_HISTORY_PROMPT.format(count=count),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return answer == QMessageBox.StandardButton.Yes


class RemoveHistory:
    """The Remove History command of the main window."""

    def __init__(self, window: MainWindow) -> None:
        self.window = window
        self._jobs: set[StepJob] = set()

    def run(self) -> bool:
        """Ask, then start the STEP export; the swap happens when it is done."""
        from fdcad.core.document.dependencies import BUILT_IN_COUNT

        tab = self.window.current
        if tab is None:
            return False
        session = tab.session
        report = session.report
        count = len(session.document.features) - BUILT_IN_COUNT
        if report is None or report.body is None or count <= 0:
            self.window.status.setText(strings.REMOVE_HISTORY_NOTHING)
            return False
        if not confirm(self.window, count):
            return False
        job = StepJob(report.body.shape)
        self._jobs.add(job)
        job.signals.done.connect(lambda data, j=job, s=session: self._written(s, j, data))
        QThreadPool.globalInstance().start(job)
        return True

    def _written(self, session: DocumentSession, job: StepJob, data: bytes | None) -> None:
        self._jobs.discard(job)
        if not data:
            self.window.status.setText(strings.REMOVE_HISTORY_FAILED)
            return
        swap(session, data)
        self.window.status.setText(strings.REMOVE_HISTORY_DONE)

    def wait(self, timeout_ms: int = 30000) -> bool:
        """Wait for a running export (tests)."""
        return QThreadPool.globalInstance().waitForDone(timeout_ms)


def swap(session: DocumentSession, data: bytes) -> str:
    """Replace every feature after the built in ones with one Imported STEP feature
    holding ``data``, as one undo step. Returns the new feature's id."""
    from fdcad.core.document.dependencies import BUILT_IN_COUNT
    from fdcad.core.features.import_step import new_step_import
    from fdcad.ui.commands.document import DeleteFeature, SetRollback
    from fdcad.ui.commands.imports import AddImport

    doc = session.document
    name = (session.path.stem if session.path else "Part") + ".step"
    session.undo.beginMacro(strings.REMOVE_HISTORY_TITLE)
    if doc.rollback is not None:
        session.undo.push(SetRollback(session, None))
    for feature in reversed(doc.features[BUILT_IN_COUNT:]):
        session.undo.push(DeleteFeature(session, feature.id))
    bid, block, feature = new_step_import(doc, name, data)
    feature.name = strings.REMOVE_HISTORY_NAME
    session.undo.push(AddImport(session, feature, bid, block))
    session.undo.endMacro()
    return feature.id
