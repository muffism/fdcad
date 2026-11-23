"""Print, Settings by Height (TR384, DECISIONS D1208).

A table of Z heights above the bed, each a pause, a colour change, or a change of
layer height, infill density or wall count. OK stores the list in the part's
print setup, as one undo step; 3MF export and Open in Slicer write it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.printing.heights import HEIGHT_CHANGES, KINDS, SETTING_KEYS, clean
from fdcad.ui import strings_print as text

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow

_COLUMNS = 5


class HeightsDialog(QDialog):
    """The list of height changes; ``changes`` holds it after OK."""

    def __init__(self, start: list[dict[str, Any]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("heights_dialog")
        self.setWindowTitle(text.HEIGHTS_TITLE)
        layout = QVBoxLayout(self)
        note = QLabel(text.HEIGHTS_NOTE)
        note.setWordWrap(True)
        layout.addWidget(note)
        self.table = QTableWidget(0, _COLUMNS)
        self.table.setObjectName("heights_table")
        self.table.setHorizontalHeaderLabels(text.HEIGHTS_COLUMNS)
        layout.addWidget(self.table)
        row = QHBoxLayout()
        add = QPushButton(text.HEIGHTS_ADD)
        add.clicked.connect(lambda: self.add_row({"z": 1.0, "kind": "pause"}))
        remove = QPushButton(text.HEIGHTS_REMOVE)
        remove.clicked.connect(self.remove_row)
        row.addWidget(add)
        row.addWidget(remove)
        row.addStretch(1)
        layout.addLayout(row)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        for entry in start:
            self.add_row(entry)

    def add_row(self, entry: dict[str, Any]) -> int:
        """Add a change; returns its row."""
        r = self.table.rowCount()
        self.table.insertRow(r)
        z = QDoubleSpinBox()
        z.setRange(0.01, 10000.0)
        z.setDecimals(2)
        z.setSuffix(" mm")
        z.setValue(float(entry.get("z", 1.0)))
        kind = QComboBox()
        for key in KINDS:
            kind.addItem(text.HEIGHT_KINDS[key], key)
        kind.setCurrentIndex(max(kind.findData(entry.get("kind", "pause")), 0))
        setting = QComboBox()
        for key in SETTING_KEYS:
            setting.addItem(text.HEIGHT_SETTINGS[key], key)
        setting.setCurrentIndex(max(setting.findData(entry.get("key", "layer_height")), 0))
        value = QDoubleSpinBox()
        value.setRange(0.0, 100.0)
        value.setDecimals(3)
        value.setValue(float(entry.get("value", 0.2)))
        note = QLineEdit(str(entry.get("note", "")))
        for col, widget in enumerate((z, kind, setting, value, note)):
            self.table.setCellWidget(r, col, widget)

        def shown() -> None:
            on = kind.currentData() == "setting"
            setting.setEnabled(on)
            value.setEnabled(on)

        kind.currentIndexChanged.connect(lambda _i: shown())
        shown()
        return r

    def remove_row(self) -> None:
        """Take off the current change."""
        r = self.table.currentRow()
        if r < 0:
            r = self.table.rowCount() - 1
        if r >= 0:
            self.table.removeRow(r)

    def widget(self, row: int, col: int) -> Any:
        """The editor in a cell."""
        return self.table.cellWidget(row, col)

    @property
    def changes(self) -> list[dict[str, Any]]:
        """The changes as stored, sorted by height."""
        out = []
        for r in range(self.table.rowCount()):
            entry: dict[str, Any] = {
                "z": self.widget(r, 0).value(),
                "kind": self.widget(r, 1).currentData(),
            }
            if entry["kind"] == "setting":
                entry["key"] = self.widget(r, 2).currentData()
                entry["value"] = self.widget(r, 3).value()
            note = self.widget(r, 4).text().strip()
            if note:
                entry["note"] = note
            out.append(entry)
        return clean(out)


def run(dialog: HeightsDialog) -> bool:
    """Show the dialog and wait; True on OK (a seam for tests, which cannot click it)."""
    return bool(dialog.exec())


def edit_heights(window: MainWindow) -> None:
    """Open the list for the active part and store it as one undo step."""
    from fdcad.ui.commands.print_setup import SetPrintSetupKey

    tab = window.current
    if tab is None:
        window.status.setText(text.HEIGHTS_NO_PART)
        return
    doc = tab.session.document
    now = clean((doc.print_setup or {}).get(HEIGHT_CHANGES))
    dialog = HeightsDialog(now, window)
    accepted = run(dialog)
    changes = dialog.changes
    dialog.deleteLater()
    if not accepted or changes == now:
        return
    tab.session.undo.push(SetPrintSetupKey(tab.session, HEIGHT_CHANGES, changes, text.HEIGHTS_UNDO))
    window.status.setText(text.HEIGHTS_DONE.format(count=len(changes)))
