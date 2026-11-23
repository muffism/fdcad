"""The Flat Pattern Output dialog (TR173, DECISIONS D1108).

Shown before a flat pattern is written as DXF or SVG: which items to write, the
origin and axis directions, the DXF colours of up and down bend lines, and a list
of the bend lines and marks where single items can be left out. Pure widgets; the
export itself runs on the thread pool (CLAUDE.md rule 2).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.features.sheetmetal.export import FlatDrawing
from fdcad.core.features.sheetmetal.flat_output import ORIGINS, FlatOutput, preview_items
from fdcad.ui import strings_sheetmetal as text


class FlatOutputDialog(QDialog):
    """Choose what a 2D flat pattern file holds and how it is placed."""

    def __init__(self, drawing: FlatDrawing, box: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("flat_output_dialog")
        self.setWindowTitle(text.FLAT_OUTPUT_TITLE)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.outline = self._tick(text.FLAT_OUTPUT_ITEMS["outline"], True)
        self.bends = self._tick(text.FLAT_OUTPUT_ITEMS["bend_lines"], True)
        self.marks = self._tick(text.FLAT_OUTPUT_ITEMS["marks"], True)
        self.box = self._tick(text.FLAT_OUTPUT_ITEMS["box"], box)
        for widget in (self.outline, self.bends, self.marks, self.box):
            form.addRow(widget)
        self.origin = QComboBox()
        for key in ORIGINS:
            self.origin.addItem(text.FLAT_ORIGINS[key], key)
        form.addRow(text.FLAT_OUTPUT_ORIGIN, self.origin)
        self.rotate = QDoubleSpinBox()
        self.rotate.setRange(-360.0, 360.0)
        self.rotate.setSuffix(" deg")
        form.addRow(text.FLAT_OUTPUT_ROTATE, self.rotate)
        self.flip_x = self._tick(text.FLAT_OUTPUT_FLIP_X, False)
        self.flip_y = self._tick(text.FLAT_OUTPUT_FLIP_Y, False)
        form.addRow(self.flip_x)
        form.addRow(self.flip_y)
        self.up_colour = self._colour(1)
        self.down_colour = self._colour(5)
        form.addRow(text.FLAT_OUTPUT_UP, self.up_colour)
        form.addRow(text.FLAT_OUTPUT_DOWN, self.down_colour)
        layout.addLayout(form)
        layout.addWidget(QLabel(text.FLAT_OUTPUT_PREVIEW))
        self.items = QListWidget()
        self.items.setObjectName("flat_output_items")
        for kind, index, label in preview_items(drawing):
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, (kind, index))
            self.items.addItem(item)
        layout.addWidget(self.items)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _tick(label: str, on: bool) -> QCheckBox:
        box = QCheckBox(label)
        box.setChecked(on)
        return box

    @staticmethod
    def _colour(start: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(1, 255)
        spin.setValue(start)
        spin.setToolTip(text.FLAT_OUTPUT_COLOUR_TIP)
        return spin

    def options(self) -> FlatOutput:
        """The choices made."""
        removed = set()
        for row in range(self.items.count()):
            item = self.items.item(row)
            if item.checkState() != Qt.CheckState.Checked:
                kind, index = item.data(Qt.ItemDataRole.UserRole)
                removed.add((str(kind), int(index)))
        return FlatOutput(
            outline=self.outline.isChecked(),
            bend_lines=self.bends.isChecked(),
            marks=self.marks.isChecked(),
            box=self.box.isChecked(),
            origin=str(self.origin.currentData()),
            flip_x=self.flip_x.isChecked(),
            flip_y=self.flip_y.isChecked(),
            rotate=self.rotate.value(),
            up_colour=self.up_colour.value(),
            down_colour=self.down_colour.value(),
            removed=frozenset(removed),
        )
