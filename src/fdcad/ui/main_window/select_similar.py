"""Select Similar and selection conversion in the 3D view (TR303, D943).

Select Similar asks which rules to use, then finds the faces in a background job
(CLAUDE.md rule 2) and picks them. Conversion picks the edges, faces or bodies of
the current picks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.kernel import kernel_job
from fdcad.core.select_similar import RULES, convert, similar_faces
from fdcad.ui import strings_extra as text

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow

#: The choice per rule: not used, must match, or takes faces out.
IGNORE, MUST, EXCEPT = "ignore", "must", "except"
Rules = tuple[list[str], bool, list[str]]


class SimilarDialog(QDialog):
    """One choice per rule, and whether all or any of the must rules match."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("select_similar")
        self.setWindowTitle(text.SIMILAR_TITLE)
        form = QFormLayout()
        self.choices: dict[str, QComboBox] = {}
        for rule in RULES:
            box = QComboBox()
            box.setObjectName(f"similar_{rule}")
            for key, label in text.SIMILAR_CHOICES.items():
                box.addItem(label, key)
            box.setCurrentIndex(box.findData(MUST if rule == "kind_size" else IGNORE))
            self.choices[rule] = box
            form.addRow(text.SIMILAR_RULES[rule], box)
        self.match = QComboBox()
        self.match.setObjectName("similar_match")
        self.match.addItem(text.SIMILAR_ALL, False)
        self.match.addItem(text.SIMILAR_ANY, True)
        form.addRow(text.SIMILAR_MATCH, self.match)
        hint = QLabel(text.SIMILAR_HINT)
        hint.setWordWrap(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def rules(self) -> Rules:
        """The must rules, whether any of them is enough, and the except rules."""
        chosen = {rule: box.currentData() for rule, box in self.choices.items()}
        must = [r for r in RULES if chosen[r] == MUST]
        excepts = [r for r in RULES if chosen[r] == EXCEPT]
        return must, bool(self.match.currentData()), excepts


def ask_rules(parent: QWidget | None) -> Rules | None:
    """The rules from the dialog, or None when cancelled (a seam for tests)."""
    dialog = SimilarDialog(parent)
    accepted = bool(dialog.exec())
    rules = dialog.rules()
    dialog.deleteLater()
    return rules if accepted else None


class _Signals(QObject):
    done = Signal(object)


class SimilarJob(QRunnable):
    """Finds the similar faces off the UI thread; never raises (CLAUDE.md rule 7)."""

    def __init__(self, part: Any, face: Any, rules: Rules) -> None:
        super().__init__()
        self.part, self.face, self.rules = part, face, rules
        self.signals = _Signals()

    @kernel_job
    def run(self) -> None:
        """Run the rules; emit the faces, or None when the kernel failed."""
        must, match_any, excepts = self.rules
        try:
            found: list[Any] | None = similar_faces(self.part, self.face, must, match_any, excepts)
        except Exception:
            found = None
        self.signals.done.emit(found)


class SelectSimilar:
    """The Select Similar and conversion commands of the main window."""

    def __init__(self, window: MainWindow) -> None:
        self.window = window
        self._jobs: set[SimilarJob] = set()

    def _view(self) -> Any:
        w = self.window
        tab = w.current
        if tab is None or w.editing == "sketch" or not hasattr(tab.viewport, "_part_shape"):
            return None
        return tab.viewport

    def similar(self, rules: Rules | None = None) -> bool:
        """Select Similar: pick the faces like the first picked face. False when nothing
        started (no face picked, no rule, or cancelled)."""
        from OCP.TopAbs import TopAbs_FACE

        view = self._view()
        if view is None:
            return False
        part = view._part_shape
        faces = [s for s in view.selected() if s.ShapeType() == TopAbs_FACE]
        if part is None or not faces:
            self.window.status.setText(text.SIMILAR_NEEDS_FACE)
            return False
        if rules is None:
            rules = ask_rules(self.window)
            if rules is None:
                return False
        if not rules[0]:
            self.window.status.setText(text.SIMILAR_NO_RULE)
            return False
        job = SimilarJob(part, faces[0], rules)
        self._jobs.add(job)
        job.signals.done.connect(lambda found, j=job, v=view: self._found(j, v, part, found))
        QThreadPool.globalInstance().start(job)
        return True

    def _found(self, job: SimilarJob, view: Any, part: Any, found: list[Any] | None) -> None:
        self._jobs.discard(job)
        if found is None:
            self.window.status.setText(text.SIMILAR_FAILED)
            return
        if view._part_shape is not part:
            return  # the part rebuilt meanwhile: these faces are gone
        view.select_shapes(found)
        self.window.status.setText(text.INVERTED.format(count=len(found)))

    def convert(self, to: str) -> int:
        """Pick the edges, faces or bodies of the current picks. Returns the count."""
        view = self._view()
        if view is None or view._part_shape is None:
            return 0
        picks = view.selected()
        if not picks:
            self.window.status.setText(text.CONVERT_NOTHING)
            return 0
        found = convert(view._part_shape, picks, to)
        view.select_shapes(found)
        self.window.status.setText(text.INVERTED.format(count=len(found)))
        return len(found)

    def wait(self, timeout_ms: int = 20000) -> bool:
        """Wait for running jobs (tests)."""
        return QThreadPool.globalInstance().waitForDone(timeout_ms)
