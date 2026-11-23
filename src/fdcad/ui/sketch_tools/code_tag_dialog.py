"""Sketch, Code Tag (TR311, DECISIONS D1215): a QR code of a text as sketch lines."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QWidget,
)

from fdcad.core.sketch.code_tag import MIN_MODULE
from fdcad.ui import strings_print as text

if TYPE_CHECKING:
    from fdcad.ui.sketch_tools.canvas import SketchCanvas


class CodeTagDialog(QDialog):
    """The text and the module size."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("code_tag_dialog")
        self.setWindowTitle(text.CODE_TAG_TITLE)
        form = QFormLayout(self)
        self.text = QLineEdit()
        self.text.setPlaceholderText(text.CODE_TAG_PLACEHOLDER)
        self.module = QDoubleSpinBox()
        self.module.setRange(MIN_MODULE, 20.0)
        self.module.setDecimals(2)
        self.module.setSuffix(" mm")
        self.module.setValue(1.0)
        self.size_label = QLabel()
        form.addRow(text.CODE_TAG_TEXT, self.text)
        form.addRow(text.CODE_TAG_MODULE, self.module)
        form.addRow(self.size_label)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.text.textChanged.connect(lambda _t: self._show())
        self.module.valueChanged.connect(lambda _v: self._show())
        self._show()

    def _show(self) -> None:
        from fdcad.core.sketch.code_tag import size_of

        words = self.text.text()
        if not words:
            self.size_label.setText(text.CODE_TAG_EMPTY)
            return
        try:
            side = size_of(words, self.module.value())
        except ValueError:
            self.size_label.setText(text.CODE_TAG_TOO_LONG)
            return
        self.size_label.setText(text.CODE_TAG_SIZE.format(size=f"{side:.1f}"))


def run(dialog: QDialog) -> bool:
    """Show the dialog; tests replace this."""
    return dialog.exec() == QDialog.DialogCode.Accepted


def insert_code_tag(canvas: SketchCanvas) -> list[str]:
    """Ask, then add the code with its bottom left corner at the sketch origin."""
    from fdcad.core.sketch.code_tag import add_code_tag

    dialog = CodeTagDialog(canvas if isinstance(canvas, QWidget) else None)
    accepted = run(dialog)
    words, module = dialog.text.text(), dialog.module.value()
    dialog.deleteLater()
    if not accepted or not words:
        return []
    made: list[str] = []
    try:
        canvas.run(lambda: made.extend(add_code_tag(canvas.edit.sketch, words, module)))
    except ValueError:
        return []
    return made
