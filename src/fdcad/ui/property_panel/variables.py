"""Variables tab: a basic list of global variables (PLAN Phase 1; full manager in Phase 4)."""

from __future__ import annotations

import copy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fdcad.core import configurations as configs
from fdcad.core.document.model import Document, Variable
from fdcad.core.equations import solve
from fdcad.core.units import Kind
from fdcad.ui.empty_state import EmptyOverlay
from fdcad.ui.equations.commands import DocumentChange
from fdcad.ui.property_panel.panel import format_value
from fdcad.ui.session import DocumentSession
from fdcad.ui.strings_feedback import NO_PART_VARIABLES, NO_VARIABLES

#: The name a row had when the table was filled (None for a new row).
_ORIGINAL_ROLE = Qt.ItemDataRole.UserRole
UNDO_TEXT = "Edit Variables"

ADD = "Add Variable"
REMOVE = "Remove Variable"
HEADERS = ["Name", "Kind", "Expression", "Value"]
KINDS = {Kind.LENGTH: "Length", Kind.ANGLE: "Angle", Kind.NUMBER: "Number"}


class VariablesPanel(QWidget):
    """Edits the active part's variables. Every change is one undoable command."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session: DocumentSession | None = None
        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        # Every column in view, also in a narrow panel (D1034): the kind is as wide
        # as its box, the other three share the rest. No row numbers.
        from PySide6.QtWidgets import QHeaderView

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setMinimumSectionSize(48)
        self.table.verticalHeader().hide()
        #: What the blank table says while it has no rows (D2702).
        self.empty = EmptyOverlay(self.table, NO_PART_VARIABLES)
        #: The left panel widens to this while the tab shows (``MainWindow``).
        self.preferred_width = 380
        self.message = QLabel()
        self.message.setWordWrap(True)
        add, remove = QPushButton(ADD), QPushButton(REMOVE)
        add.clicked.connect(self.add_row)
        remove.clicked.connect(self.remove_row)
        buttons = QHBoxLayout()
        buttons.addWidget(add)
        buttons.addWidget(remove)
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addWidget(self.message)
        layout.addLayout(buttons)
        self.table.itemChanged.connect(self._edited)
        self._filling = False

    def set_session(self, session: DocumentSession | None) -> None:
        """Show ``session``'s variables."""
        if self.session is not None:
            self.session.rebuilt.disconnect(self.refresh)
        self.session = session
        if session is not None:
            session.rebuilt.connect(self.refresh)
        self.refresh()

    def refresh(self, *_args: object) -> None:
        """Fill the table from the document."""
        self._filling = True
        self.table.setRowCount(0)
        if self.session is not None:
            units = self.session.document.units
            for var in self.session.document.variables:
                shown = format_value(var.value, var.kind, units)
                self._append(var.name, var.kind, var.expr, shown, var.name)
        self._filling = False
        self.empty.setText(NO_VARIABLES if self.session is not None else NO_PART_VARIABLES)

    def _append(
        self, name: str, kind: Kind, expr: str, value: str, original: str | None = None
    ) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        name_item = QTableWidgetItem(name)
        name_item.setData(_ORIGINAL_ROLE, original)
        self.table.setItem(row, 0, name_item)
        box = QComboBox()
        for k, label in KINDS.items():
            box.addItem(label, k)
        box.setCurrentIndex(box.findData(kind))
        box.currentIndexChanged.connect(lambda _i: self._edited())
        self.table.setCellWidget(row, 1, box)
        self.table.setItem(row, 2, QTableWidgetItem(expr))
        shown = QTableWidgetItem(value)
        shown.setFlags(shown.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, 3, shown)

    def _rows(self) -> list[tuple[Variable, str | None]]:
        """The rows as variables (old comments kept) with the name each row started with."""
        assert self.session is not None
        old = {v.name: v for v in self.session.document.variables}
        out = []
        for row in range(self.table.rowCount()):
            name_item, expr_item = self.table.item(row, 0), self.table.item(row, 2)
            box = self.table.cellWidget(row, 1)
            kind = box.currentData() if isinstance(box, QComboBox) else Kind.LENGTH
            original = name_item.data(_ORIGINAL_ROLE) if name_item is not None else None
            original = original if isinstance(original, str) else None
            before = old.get(original) if original is not None else None
            out.append(
                (
                    Variable(
                        name_item.text().strip() if name_item else "",
                        kind,
                        expr_item.text().strip() if expr_item else "",
                        before.value if before is not None else 0.0,
                        before.comment if before is not None else "",
                    ),
                    original,
                )
            )
        return out

    def add_row(self) -> None:
        """Add a new variable with a free name."""
        names = {v.name for v, _original in self._rows()} if self.session is not None else set()
        n = 1
        while f"Var{n}" in names:
            n += 1
        self._filling = True
        self._append(f"Var{n}", Kind.LENGTH, "10", "")
        self._filling = False
        self._edited()

    def remove_row(self) -> None:
        """Remove the selected variable."""
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self._edited()

    def _edited(self, *_args: object) -> None:
        if self._filling or self.session is None:
            return
        rows = self._rows()
        variables = [v for v, _original in rows]
        # Solve with the whole part, so formulas may use feature values (D390).
        work = copy.copy(self.session.document)
        work.variables = variables
        solution = solve(work)
        for var in variables:
            error = solution.errors.get(f"var:{var.name}")
            if error is not None:
                self.message.setText(f"Variable '{var.name}': {error}")
                return
            var.value = solution.values.get(f"var:{var.name}", var.value)
        self.message.clear()
        doc = self.session.document
        kept = {original: v.name for v, original in rows if original is not None}
        renamed = {v.name: kept.get(v.name) for v in doc.variables}

        def change(d: Document) -> None:
            d.variables = copy.deepcopy(variables)
            configs.follow_variables(d, renamed)

        command = DocumentChange(self.session, UNDO_TEXT, change)
        if command.changes_anything:
            self.session.undo.push(command)
        self._filling = True
        for row in range(self.table.rowCount()):  # later edits start from the new names
            item = self.table.item(row, 0)
            if item is not None:
                item.setData(_ORIGINAL_ROLE, item.text().strip())
        self._filling = False
