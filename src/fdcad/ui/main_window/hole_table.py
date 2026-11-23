"""Tools, Hole Table (TR316, D924): every hole and thread of the last rebuild, with
Copy (tab separated, for a spreadsheet) and Save CSV."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.hole_table import COLUMNS, HoleRow, cells, rows, to_csv
from fdcad.core.units import UnitSystem
from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow


class HoleTableDialog(QDialog):
    """The table and its buttons."""

    def __init__(
        self, found: list[HoleRow], units: UnitSystem, folder: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.found, self.units, self.folder = found, units, folder
        self.setWindowTitle(strings.HOLE_TABLE_TITLE)
        self.table = QTableWidget(len(found), len(COLUMNS))
        self.table.setHorizontalHeaderLabels(list(COLUMNS))
        for r, row in enumerate(found):
            for c, text in enumerate(cells(row, units)):
                self.table.setItem(r, c, QTableWidgetItem(text))
        self.table.resizeColumnsToContents()
        unit = "in" if units is UnitSystem.IN else "mm"
        note = strings.HOLE_TABLE_NOTE.format(count=len(found), unit=unit)
        self.message = QLabel(note if found else strings.HOLE_TABLE_EMPTY)
        self.message.setWordWrap(True)
        copy = QPushButton(strings.HOLE_TABLE_COPY)
        copy.clicked.connect(self.copy)
        save = QPushButton(strings.HOLE_TABLE_SAVE)
        save.clicked.connect(self.save)
        close = QPushButton(strings.HOLE_TABLE_CLOSE)
        close.clicked.connect(self.accept)
        for button in (copy, save):
            button.setEnabled(bool(found))
        buttons = QHBoxLayout()
        buttons.addWidget(copy)
        buttons.addWidget(save)
        buttons.addStretch(1)
        buttons.addWidget(close)
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addWidget(self.message)
        layout.addLayout(buttons)
        self.resize(820, 420)

    def text(self) -> str:
        """The table as tab separated text with a header row."""
        lines = ["\t".join(COLUMNS)]
        lines += ["\t".join(cells(row, self.units)) for row in self.found]
        return "\n".join(lines) + "\n"

    def copy(self) -> None:
        """Put the table on the clipboard."""
        board = QApplication.clipboard()
        if board is not None:
            board.setText(self.text())
        self.message.setText(strings.HOLE_TABLE_COPIED)

    def save(self, path: str | None = None) -> bool:
        """Write the table as CSV to ``path`` or a file the user picks."""
        if path is None:
            path, _ = QFileDialog.getSaveFileName(
                self, strings.HOLE_TABLE_SAVE, self.folder, strings.HOLE_TABLE_FILTER
            )
        if not path:
            return False
        try:
            Path(path).write_text(to_csv(self.found, self.units), encoding="utf-8")
        except OSError as exc:
            self.message.setText(strings.HOLE_TABLE_FAILED.format(reason=exc))
            return False
        self.message.setText(strings.HOLE_TABLE_SAVED.format(name=Path(path).name))
        return True


def run(dialog: QDialog) -> None:
    """Show the dialog; tests replace this."""
    dialog.exec()


def open_table(window: MainWindow) -> HoleTableDialog | None:
    """Show the holes and threads of the open part's last rebuild."""
    tab = window.current
    if tab is None:
        return None
    session = tab.session
    report = session.report
    if report is None:
        window.status.setText(strings.HOLE_TABLE_WAIT)
        return None
    found = rows(session.document, report.results)
    folder = str(session.path.parent) if session.path is not None else str(Path.home())
    dialog = HoleTableDialog(found, session.document.units, folder, window)
    run(dialog)
    dialog.deleteLater()
    return dialog
