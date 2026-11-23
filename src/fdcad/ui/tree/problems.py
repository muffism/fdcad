"""Errors and warnings in the feature tree (TOOL_SPEC T14.5.3).

A feature with an error has red text and a red mark; the part name row gets
the same mark. A feature with a warning has the warning colour and mark, and
its parents get a smaller mark. Clicking a marked feature shows a small box
beside its row with the message (which says what to do next) and Edit Feature
or Edit Sketch buttons. Clicking the part name lists every error and warning;
clicking a row there selects that feature.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.document import dependencies
from fdcad.core.features.base import FeatureState
from fdcad.ui import strings_extra as text

if TYPE_CHECKING:
    from fdcad.core.document.model import Document
    from fdcad.core.rebuild.engine import RebuildReport


@dataclass(frozen=True)
class Problem:
    """One warning or error of one feature."""

    fid: str
    name: str
    state: str  # "error" or "warning"
    message: str


def all_problems(doc: Document, report: RebuildReport) -> list[Problem]:
    """Every error and warning of the part, errors first, then in tree order."""
    out: list[Problem] = []
    for feature in doc.features:
        result = report.results.get(feature.id)
        if result is None:
            continue
        for issue in result.issues:
            if issue.state is FeatureState.OK:
                continue
            out.append(Problem(feature.id, feature.name, issue.state.value, issue.message))
    return sorted(out, key=lambda p: p.state != "error")


def worst_state(report: RebuildReport) -> str | None:
    """ "error" when any feature has an error, else "warning" when any has one, else None."""
    states = {r.state for r in report.results.values()}
    if FeatureState.ERROR in states:
        return "error"
    if FeatureState.WARNING in states:
        return "warning"
    return None


def warned_parents(doc: Document, report: RebuildReport) -> set[str]:
    """Features used by a feature that has a warning (they get a smaller mark)."""
    out: set[str] = set()
    for feature in doc.features:
        result = report.results.get(feature.id)
        if result is not None and result.state is FeatureState.WARNING:
            out |= {p.id for p in dependencies.parents_of(doc, feature.id)}
    return out


class ProblemBox(QFrame):
    """The small box beside a marked feature: its messages and the edit buttons."""

    edit_feature = Signal(str)
    edit_sketch = Signal(str)

    def __init__(
        self, fid: str, problems: list[Problem], sketch_id: str | None, parent: QWidget | None
    ) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        from fdcad.ui.icons import icon

        self.setObjectName("problem_box")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.fid = fid
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.labels: list[QLabel] = []
        for p in problems:
            row = QHBoxLayout()
            mark = QLabel()
            mark.setPixmap(
                icon(f"tree.{p.state}_mark").pixmap(QSize(16, 16), self.devicePixelRatioF())
            )
            label = QLabel(p.message)
            label.setWordWrap(True)
            label.setMaximumWidth(360)
            row.addWidget(mark, 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(label, 1)
            layout.addLayout(row)
            self.labels.append(label)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.edit_button = QPushButton(text.EDIT_FEATURE)
        self.edit_button.clicked.connect(lambda: self._done(self.edit_feature, fid))
        buttons.addWidget(self.edit_button)
        self.sketch_button: QPushButton | None = None
        if sketch_id is not None:
            self.sketch_button = QPushButton(text.EDIT_SKETCH)
            self.sketch_button.clicked.connect(lambda: self._done(self.edit_sketch, sketch_id))
            buttons.addWidget(self.sketch_button)
        layout.addLayout(buttons)

    def _done(self, signal: Any, fid: str) -> None:
        self.close()
        signal.emit(fid)

    def open_at(self, pos: QPoint) -> None:
        """Show with its top left at a screen point."""
        self.adjustSize()
        self.move(pos)
        self.show()


class ProblemList(QFrame):
    """Every error and warning of the part; clicking a row selects its feature."""

    chosen = Signal(str)

    def __init__(self, problems: list[Problem], parent: QWidget | None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        from fdcad.ui.icons import icon

        self.setObjectName("problem_list")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self.rows = QListWidget()
        for p in problems:
            item = QListWidgetItem(icon(f"tree.{p.state}_mark"), f"{p.name}: {p.message}")
            item.setData(Qt.ItemDataRole.UserRole, p.fid)
            self.rows.addItem(item)
        if not problems:
            empty = QListWidgetItem(text.NO_PROBLEMS)
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self.rows.addItem(empty)
        self.rows.itemClicked.connect(self._clicked)
        layout.addWidget(self.rows)
        self.setMinimumWidth(380)

    def _clicked(self, item: QListWidgetItem) -> None:
        fid = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(fid, str):
            self.close()
            self.chosen.emit(fid)

    def open_at(self, pos: QPoint) -> None:
        """Show with its top left at a screen point."""
        self.adjustSize()
        self.move(pos)
        self.show()
