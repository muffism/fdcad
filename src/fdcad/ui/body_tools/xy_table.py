"""The X and Y table of Table Driven Pattern (TR58, D821).

Rows have a Use tick, X and Y in mm. Paste takes rows copied from a
spreadsheet; Load File and Save File read and write a text file with two
columns. The table is kept in the part, so it never needs the file to rebuild.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.features.table_pattern import read_rows, write_rows
from fdcad.ui import strings


class XYTable(QWidget):
    """Rows of X and Y with a Use tick each."""

    changed = Signal()

    def __init__(self, rows: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.table = QTableWidget(0, 3)
        self.table.setObjectName("xy_table")
        self.table.setHorizontalHeaderLabels([strings.TABLE_USE, "X", "Y"])
        # The tick column takes what it needs; X and Y share the rest, so the table
        # never scrolls sideways at the left panel's default width (D2804).
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(True)
        self.table.setMinimumHeight(140)
        self.table.itemChanged.connect(lambda _i: self.changed.emit())
        buttons = QHBoxLayout()
        for label, slot in (
            (strings.POINTS_ADD, self.add_row),
            (strings.POINTS_REMOVE, self.remove_row),
            (strings.TABLE_PASTE, self.paste),
            (strings.POINTS_LOAD, self.load_file),
            (strings.TABLE_SAVE, self.save_file),
        ):
            button = QPushButton(label)
            button.clicked.connect(lambda _c=False, s=slot: s())
            buttons.addWidget(button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)
        layout.addLayout(buttons)
        self.set_rows(rows)

    def set_rows(self, rows: Any) -> None:
        """Fill the table from stored rows (``[x, y]`` or ``[x, y, false]``)."""
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        if isinstance(rows, list):
            for item in rows:
                if isinstance(item, list | tuple) and len(item) in (2, 3):
                    self._append(item[0], item[1], not (len(item) == 3 and item[2] is False))
        self.table.blockSignals(False)
        self.changed.emit()

    def _append(self, x: Any, y: Any, used: bool = True) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        tick = QTableWidgetItem()
        tick.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        tick.setCheckState(Qt.CheckState.Checked if used else Qt.CheckState.Unchecked)
        self.table.setItem(row, 0, tick)
        self.table.setItem(row, 1, QTableWidgetItem(f"{x:g}" if isinstance(x, float) else str(x)))
        self.table.setItem(row, 2, QTableWidgetItem(f"{y:g}" if isinstance(y, float) else str(y)))

    def value(self) -> list[list[Any]] | None:
        """The rows, or None when a cell is not a number."""
        out: list[list[Any]] = []
        for row in range(self.table.rowCount()):
            cells = [self.table.item(row, c) for c in range(3)]
            try:
                x = float(cells[1].text()) if cells[1] is not None else None
                y = float(cells[2].text()) if cells[2] is not None else None
            except ValueError:
                return None
            if x is None or y is None:
                return None
            used = cells[0] is None or cells[0].checkState() == Qt.CheckState.Checked
            out.append([x, y] if used else [x, y, False])
        return out

    def add_row(self) -> None:
        """Add a row at 0, 0."""
        self._append(0.0, 0.0)
        self.changed.emit()

    def remove_row(self) -> None:
        """Remove the current row, or the last one."""
        row = self.table.currentRow()
        if row < 0:
            row = self.table.rowCount() - 1
        if row >= 0:
            self.table.removeRow(row)
            self.changed.emit()

    def paste(self, text: str | None = None) -> int:
        """Add rows copied from a spreadsheet. Returns how many were added."""
        if text is None:
            text = QApplication.clipboard().text()
        rows = read_rows(text)
        self.table.blockSignals(True)
        for x, y in rows:
            self._append(x, y)
        self.table.blockSignals(False)
        self.changed.emit()
        return len(rows)

    def load_file(self, path: str | None = None) -> int:
        """Replace the rows with those of a text file. Returns how many were read."""
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self, strings.POINTS_LOAD, "", strings.TABLE_FILTER
            )
        if not path:
            return 0
        try:
            rows = read_rows(Path(path).read_text(encoding="utf-8", errors="replace"))
        except OSError:
            return 0
        self.set_rows(rows)
        return len(rows)

    def save_file(self, path: str | None = None) -> bool:
        """Write the rows to a text file with two columns."""
        rows = self.value()
        if rows is None:
            return False
        if path is None:
            path, _ = QFileDialog.getSaveFileName(
                self, strings.TABLE_SAVE, "", strings.TABLE_FILTER
            )
        if not path:
            return False
        try:
            Path(path).write_text(write_rows([r[:2] for r in rows]), encoding="utf-8")
        except OSError:
            return False
        return True
