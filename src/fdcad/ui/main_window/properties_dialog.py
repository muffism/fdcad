"""Custom Properties (TR82, DECISIONS D810).

A table of the part's properties: name, kind, value (or a formula starting
with "="), the value for the active configuration only (blank: the value), and
what it works out to. Add and Remove change rows; OK sets them as one undo step.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.properties import KINDS, Row, name_problem, rows
from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.core.document.model import Document

NAME, KIND, VALUE, CONFIG, RESULT = range(5)


class PropertiesDialog(QDialog):
    """The table; ``data()`` holds the rows after OK."""

    def __init__(self, doc: Document, parent: QWidget | None = None) -> None:
        from fdcad.core import configurations as configs

        super().__init__(parent)
        self.setObjectName("properties_dialog")
        self.setWindowTitle(strings.PROPS_TITLE)
        self.doc = doc
        self.active = configs.active_name(doc)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            [
                strings.PROPS_NAME,
                strings.PROPS_KIND,
                strings.PROPS_VALUE,
                strings.PROPS_CONFIG.format(name=self.active),
                strings.PROPS_RESULT,
            ]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.resize(680, 440)  # all five columns in view (it opened 288 px wide, D1034)
        self.message = QLabel()
        self.message.setWordWrap(True)
        add, remove, work = (
            QPushButton(strings.PROPS_ADD),
            QPushButton(strings.PROPS_REMOVE),
            QPushButton(strings.PROPS_WORK),
        )
        add.clicked.connect(lambda: self.add_row(Row(self._free_name(), "text", "")))
        remove.clicked.connect(self.remove_row)
        work.clicked.connect(self.refresh)
        row = QHBoxLayout()
        for button in (add, remove, work):
            row.addWidget(button)
        row.addStretch(1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        hint = QLabel(strings.PROPS_HINT)
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addWidget(self.table)
        layout.addLayout(row)
        layout.addWidget(self.message)
        layout.addWidget(buttons)
        for item in rows(doc):
            self.add_row(item)
        self.refresh()

    def _free_name(self) -> str:
        taken = {self._text(r, NAME) for r in range(self.table.rowCount())}
        k = 1
        while f"Property {k}" in taken:
            k += 1
        return f"Property {k}"

    def add_row(self, item: Row) -> None:
        """Add a row showing ``item``."""
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, NAME, QTableWidgetItem(item.name))
        kind = QComboBox()
        for key in KINDS:
            kind.addItem(strings.PROPS_KINDS[key], key)
        kind.setCurrentIndex(max(kind.findData(item.kind), 0))
        self.table.setCellWidget(r, KIND, kind)
        self.table.setItem(r, VALUE, QTableWidgetItem(item.value))
        own = dict(item.configs).get(self.active, "")
        self.table.setItem(r, CONFIG, QTableWidgetItem(own))
        result = QTableWidgetItem("")
        result.setFlags(result.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(r, RESULT, result)

    def remove_row(self) -> None:
        """Remove the selected row."""
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    def _text(self, r: int, column: int) -> str:
        item = self.table.item(r, column)
        return item.text().strip() if item is not None else ""

    def data(self) -> list[dict[str, Any]] | str:
        """The rows in the part's form, or why they cannot be used."""
        out: list[dict[str, Any]] = []
        names: list[str] = []
        old = {row.name: row for row in rows(self.doc)}
        for r in range(self.table.rowCount()):
            name = self._text(r, NAME)
            problem = name_problem(name, names)
            if problem:
                return problem
            names.append(name)
            box = self.table.cellWidget(r, KIND)
            kind = str(box.currentData()) if isinstance(box, QComboBox) else "text"
            configs = dict(old[name].configs) if name in old else {}
            own = self._text(r, CONFIG)
            if own:
                configs[self.active] = own
            else:
                configs.pop(self.active, None)
            out.append(Row(name, kind, self._text(r, VALUE), tuple(configs.items())).to_data())
        return out

    def refresh(self) -> None:
        """Work the rows out and show the results."""
        import copy

        from fdcad.core.properties import shown

        found = self.data()
        if isinstance(found, str):
            self.message.setText(found)
            return
        work = copy.deepcopy(self.doc)
        work.properties = found
        work.measured = dict(self.doc.measured)
        results = shown(work)
        errors = []
        for r, result in enumerate(results):
            cell = self.table.item(r, RESULT)
            if cell is not None:
                cell.setText(strings.PROPS_SEE_BELOW if result.error else result.text)
            if result.error:
                errors.append(f"{result.name}: {result.error}")
        self.message.setText("\n".join(errors))

    def _ok(self) -> None:
        found = self.data()
        if isinstance(found, str):
            self.message.setText(found)
            return
        self.accept()


def run(dialog: PropertiesDialog) -> bool:
    """Show the dialog and wait; True on OK (a seam for tests)."""
    return bool(dialog.exec())
