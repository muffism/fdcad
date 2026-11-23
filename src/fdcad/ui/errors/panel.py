"""Errors panel: every warning and error, its cause, fixes and feature (PLAN 5A item 7).

A table with the kind, the feature and the message, sorted by clicking a header,
with Show Errors and Show Warnings ticks (TR202, D820). Fixes are offered as
buttons and only run when clicked (CLAUDE.md rule 12).
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.features.base import FeatureState, Fix, Issue
from fdcad.ui import strings
from fdcad.ui.icons import icon
from fdcad.ui.session import DocumentSession
from fdcad.ui.themes.theme import palette


@dataclass(frozen=True)
class Entry:
    """One row of the panel."""

    fid: str
    feature: str
    issue: Issue


def entries(session: DocumentSession) -> list[Entry]:
    """Issues of the last rebuild in tree order, errors first, without dismissed ones."""
    report = session.report
    if report is None:
        return []
    out: list[Entry] = []
    for feature in session.document.features:
        result = report.results.get(feature.id)
        if result is None:
            continue
        for issue in result.issues:
            if issue.state is FeatureState.OK:
                continue
            if (feature.id, issue.code) in session.dismissed and issue.code:
                continue
            out.append(Entry(feature.id, feature.name, issue))
    # Errors first; among them, those with a known cause first, in the cause's tree order,
    # so fixing the first row often fixes the ones after it (TR288).
    from fdcad.core.rebuild.causes import cause_in

    order = {f.id: i for i, f in enumerate(session.document.features)}

    def key(e: Entry) -> tuple[bool, int]:
        cause = cause_in(e.issue)
        return e.issue.state is not FeatureState.ERROR, order.get(
            cause, len(order)
        ) if cause else len(order)

    return sorted(out, key=key)


class ErrorsPanel(QWidget):
    """Lists problems; picking one highlights its geometry and shows its fixes."""

    highlight_requested = Signal(list)  # names of faces, edges and vertices
    feature_requested = Signal(str)  # feature id to open
    fix_requested = Signal(str, object)  # feature id, Fix
    count_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session: DocumentSession | None = None
        self.table = QTableWidget(0, 3)
        self.table.setObjectName("errors_table")
        self.table.setHorizontalHeaderLabels(
            [strings.ERRORS_KIND, strings.ERRORS_FEATURE, strings.ERRORS_MESSAGE]
        )
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        # Kind is one short word: as wide as it needs, so the message, the column
        # that matters, gets the room in a narrow panel (D2693).
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setWordWrap(True)
        self.table.currentCellChanged.connect(lambda row, *_a: self._picked(self._entry_at(row)))
        self.show_errors = QCheckBox(strings.ERRORS_SHOW_ERRORS)
        self.show_warnings = QCheckBox(strings.ERRORS_SHOW_WARNINGS)
        for box in (self.show_errors, self.show_warnings):
            box.setChecked(True)
            box.toggled.connect(lambda _on: self.refresh())
        ticks = QHBoxLayout()
        ticks.addWidget(self.show_errors)
        ticks.addWidget(self.show_warnings)
        ticks.addStretch(1)
        self.detail = QLabel()
        self.detail.setWordWrap(True)
        self.detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.fix_row = QHBoxLayout()
        self.open_button = QPushButton(strings.OPEN_FEATURE)
        self.open_button.clicked.connect(self._open)
        # The empty state (D2693): centred near the top in the muted colour, like the
        # tree's own hint, and it takes the table's room so the ticks stay at the top.
        self.empty = QLabel(strings.NO_PROBLEMS)
        self.empty.setObjectName("empty_state")
        self.empty.setWordWrap(True)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        layout = QVBoxLayout(self)
        layout.addLayout(ticks)
        layout.addWidget(self.empty, 1)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.detail)
        layout.addLayout(self.fix_row)
        layout.addWidget(self.open_button)
        self.items: list[Entry] = []
        self.fix_buttons: list[QPushButton] = []
        self.refresh()

    def set_session(self, session: DocumentSession | None) -> None:
        """Show ``session``'s problems."""
        if self.session is not None:
            self.session.rebuilt.disconnect(self.refresh)
        self.session = session
        if session is not None:
            session.rebuilt.connect(self.refresh)
        self.refresh()

    def refresh(self, *_args: object) -> None:
        """Fill the table from the last rebuild, with the kinds ticked."""
        found = entries(self.session) if self.session is not None else []
        errors_on, warnings_on = self.show_errors.isChecked(), self.show_warnings.isChecked()
        self.items = [
            e for e in found if (errors_on if e.issue.state is FeatureState.ERROR else warnings_on)
        ]
        colors = palette()
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.items))
        for row, entry in enumerate(self.items):
            error = entry.issue.state is FeatureState.ERROR
            kind = QTableWidgetItem(strings.ERROR if error else strings.WARNING)
            # An icon too, so the state never shows by colour alone (U4.4).
            kind.setIcon(icon("tree.error_mark" if error else "tree.warning_mark"))
            kind.setForeground(QColor(colors.state_error if error else colors.state_warning))
            kind.setData(Qt.ItemDataRole.UserRole, row)
            name = QTableWidgetItem(entry.feature)
            message = QTableWidgetItem(entry.issue.message)
            message.setToolTip(entry.issue.message)
            for col, cell in enumerate((kind, name, message)):
                self.table.setItem(row, col, cell)
        self.table.setSortingEnabled(True)
        self.table.blockSignals(False)
        has = bool(found)
        self.empty.setVisible(not has)
        self.table.setVisible(has)
        self._picked(None)
        self.count_changed.emit(len(found))

    def _entry_at(self, row: int) -> Entry | None:
        """The entry shown in table row ``row`` (rows move when sorted)."""
        cell = self.table.item(row, 0) if row >= 0 else None
        index = cell.data(Qt.ItemDataRole.UserRole) if cell is not None else None
        return self.items[index] if isinstance(index, int) and index < len(self.items) else None

    def _clear_fixes(self) -> None:
        for button in self.fix_buttons:
            self.fix_row.removeWidget(button)
            button.deleteLater()
        self.fix_buttons = []

    def _picked(self, entry: Entry | None) -> None:
        self._clear_fixes()
        self.open_button.setVisible(entry is not None)
        if entry is None:
            self.detail.setText("")
            self.highlight_requested.emit([])
            return
        kind = strings.ERROR if entry.issue.state is FeatureState.ERROR else strings.WARNING
        self.detail.setText(f"<b>{kind}: {entry.feature}</b><br>{entry.issue.message}")
        for fix in entry.issue.fixes:
            button = QPushButton(fix.label)
            button.clicked.connect(lambda _c=False, f=fix, fid=entry.fid: self._fix(fid, f))
            self.fix_row.addWidget(button)
            self.fix_buttons.append(button)
        self.highlight_requested.emit(list(entry.issue.highlight))

    def select(self, row: int) -> None:
        """Pick the ``row``th problem in the panel's own order (errors first)."""
        for r in range(self.table.rowCount()):
            cell = self.table.item(r, 0)
            if cell is not None and cell.data(Qt.ItemDataRole.UserRole) == row:
                self.table.setCurrentCell(r, 0)
                return

    def _fix(self, fid: str, fix: Fix) -> None:
        self.fix_requested.emit(fid, fix)

    def _open(self) -> None:
        entry = self._entry_at(self.table.currentRow())
        if entry is not None:
            self.feature_requested.emit(entry.fid)
