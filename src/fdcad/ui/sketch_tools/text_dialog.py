"""The sketch Text dialog (PHASE4_SPEC P4.8, DECISIONS D323).

Adds a text item to the open sketch or edits one: the text, font, height, bold
and italic, the base line (from a point at an angle, or along a sketch line or
arc), the text box width and alignment, width and spacing percent, the turn of
each character and flips. OK makes one undoable sketch change.
"""

from __future__ import annotations

import copy
import math
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFontComboBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.sketch.model import Arc, Circle, Line, Sketch, Spline
from fdcad.core.sketch.text import ALIGNS, SketchText, char_style, set_style
from fdcad.ui import strings_phase4 as text

if TYPE_CHECKING:
    from fdcad.ui.sketch_tools.canvas import SketchCanvas


def _spin(low: float, high: float, value: float, suffix: str, decimals: int = 3) -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(low, high)
    box.setDecimals(decimals)
    box.setValue(value)
    box.setSuffix(suffix)
    return box


def next_text_id(sketch: Sketch) -> str:
    """A text id not used yet in the sketch (``t1``, ``t2`` ...)."""
    used = {t.id for t in sketch.texts}
    k = 1
    while f"t{k}" in used:
        k += 1
    return f"t{k}"


class TextDialog(QDialog):
    """Edits the text items of one sketch."""

    def __init__(self, sketch: Sketch, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(text.TEXT_TITLE)
        self.sketch = sketch
        self.texts = copy.deepcopy(sketch.texts)
        self.pick = QComboBox()
        self.pick.setToolTip(text.TEXT_TIPS["pick"])
        self.content = QLineEdit()
        self.content.setToolTip(text.TEXT_TIPS["text"])
        self.font_box = QFontComboBox()
        self.font_box.setToolTip(text.TEXT_TIPS["font"])
        self.height_box = _spin(0.01, 10000, 5.0, " mm")
        self.bold = QCheckBox(text.TEXT_BOLD)
        self.italic = QCheckBox(text.TEXT_ITALIC)
        self.x_box = _spin(-1e6, 1e6, 0.0, " mm")
        self.y_box = _spin(-1e6, 1e6, 0.0, " mm")
        self.angle = _spin(-360, 360, 0.0, " deg", 2)
        self.curve = QComboBox()
        self.curve.setToolTip(text.TEXT_TIPS["curve"])
        self.curve.addItem(text.TEXT_NO_CURVE, "")
        for entity in sketch.entities.values():
            if isinstance(entity, Line | Arc | Circle | Spline):  # TR230
                kind = {
                    Line: text.TEXT_LINE,
                    Arc: text.TEXT_ARC,
                    Circle: text.TEXT_CIRCLE,
                    Spline: text.TEXT_SPLINE,
                }[type(entity)]
                self.curve.addItem(f"{kind} {entity.id}", entity.id)
        self.align = QComboBox()
        for value in ALIGNS:
            self.align.addItem(text.TEXT_ALIGNS[value], value)
        self.offset = _spin(-1e6, 1e6, 0.0, " mm")  # TR230 (D976)
        self.offset.setObjectName("text_offset")
        self.offset.setToolTip(text.TEXT_OFFSET_TIP)
        self.box = _spin(0, 1e6, 0.0, " mm")
        self.box.setToolTip(text.TEXT_TIPS["box"])
        self.width_box = _spin(1, 1000, 100.0, " %", 1)
        self.spacing = _spin(1, 1000, 100.0, " %", 1)
        self.char_angle = _spin(-360, 360, 0.0, " deg", 2)
        self.flip_h = QCheckBox(text.TEXT_FLIP_H)
        self.flip_v = QCheckBox(text.TEXT_FLIP_V)
        self.stencil = QCheckBox(text.TEXT_STENCIL)  # TR297 item 3 (D802)
        self.stencil.setToolTip(text.TEXT_STENCIL_TIP)
        self.bridge = _spin(0, 1000, 0.0, " mm")
        self.bridge.setToolTip(text.TEXT_BRIDGE_TIP)
        # TR121 item 2 (D2202): styles for the characters selected in the text box.
        self.styles: list[dict[str, object]] = []
        self.style_bold = QPushButton(text.TEXT_STYLE_BOLD)
        self.style_bold.setObjectName("text_style_bold")
        self.style_italic = QPushButton(text.TEXT_STYLE_ITALIC)
        self.style_italic.setObjectName("text_style_italic")
        self.style_turn = QPushButton(text.TEXT_STYLE_TURN)
        self.style_turn.setObjectName("text_style_turn")
        self.style_angle = _spin(-360, 360, 90.0, " deg", 2)
        self.style_angle.setObjectName("text_style_angle")
        self.style_clear = QPushButton(text.TEXT_STYLE_CLEAR)
        self.style_clear.setObjectName("text_style_clear")
        style_row = QWidget()
        style_row.setToolTip(text.TEXT_STYLE_TIP)
        row = QHBoxLayout(style_row)
        row.setContentsMargins(0, 0, 0, 0)
        for widget in (
            self.style_bold,
            self.style_italic,
            self.style_turn,
            self.style_angle,
            self.style_clear,
        ):
            row.addWidget(widget)
        self.style_bold.clicked.connect(lambda: self.style_selection("bold"))
        self.style_italic.clicked.connect(lambda: self.style_selection("italic"))
        self.style_turn.clicked.connect(lambda: self.style_selection("angle"))
        self.style_clear.clicked.connect(self.styles.clear)
        self.delete = QPushButton(text.TEXT_DELETE)
        self.delete.clicked.connect(self.delete_current)
        form = QFormLayout()
        form.addRow(text.TEXT_ITEM, self.pick)
        form.addRow(text.TEXT_TEXT, self.content)
        form.addRow(text.TEXT_FONT, self.font_box)
        form.addRow(text.TEXT_HEIGHT, self.height_box)
        form.addRow(self.bold)
        form.addRow(self.italic)
        form.addRow(text.TEXT_STYLE_ROW, style_row)
        form.addRow(text.TEXT_CURVE, self.curve)
        form.addRow(text.TEXT_OFFSET, self.offset)
        form.addRow("X", self.x_box)
        form.addRow("Y", self.y_box)
        form.addRow(text.TEXT_ANGLE, self.angle)
        form.addRow(text.TEXT_ALIGN, self.align)
        form.addRow(text.TEXT_BOX, self.box)
        form.addRow(text.TEXT_WIDTH, self.width_box)
        form.addRow(text.TEXT_SPACING, self.spacing)
        form.addRow(text.TEXT_CHAR_ANGLE, self.char_angle)
        form.addRow(self.flip_h)
        form.addRow(self.flip_v)
        form.addRow(self.stencil)
        form.addRow(text.TEXT_BRIDGE, self.bridge)
        form.addRow(self.delete)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.current: str | None = None
        self._fill_pick()
        self.pick.currentIndexChanged.connect(self._picked)
        self._picked()

    def _fill_pick(self) -> None:
        self.pick.blockSignals(True)
        self.pick.clear()
        self.pick.addItem(text.TEXT_NEW, None)
        for t in self.texts:
            self.pick.addItem(f"{t.id}: {t.text}", t.id)
        self.pick.blockSignals(False)

    def _picked(self) -> None:
        tid = self.pick.currentData()
        self._store()
        self._fill_pick()  # a text typed before switching is listed now
        self.pick.blockSignals(True)
        self.pick.setCurrentIndex(max(self.pick.findData(tid), 0))
        self.pick.blockSignals(False)
        self.current = tid if isinstance(tid, str) else None
        found = next((t for t in self.texts if t.id == self.current), None)
        self.load(found or SketchText("", "", height=self.height_box.value()))
        self.delete.setEnabled(found is not None)

    def load(self, t: SketchText) -> None:
        """Show ``t`` in the fields."""
        self.content.setText(t.text)
        self.font_box.setCurrentText(
            t.font if t.font != "sans-serif" else self.font_box.currentText()
        )
        self.height_box.setValue(t.height)
        self.bold.setChecked(t.bold)
        self.italic.setChecked(t.italic)
        self.x_box.setValue(t.x)
        self.y_box.setValue(t.y)
        self.angle.setValue(math.degrees(t.angle))
        self.curve.setCurrentIndex(max(self.curve.findData(t.curve), 0))
        self.offset.setValue(t.offset)
        self.align.setCurrentIndex(max(self.align.findData(t.align), 0))
        self.box.setValue(t.box)
        self.width_box.setValue(t.width)
        self.spacing.setValue(t.spacing)
        self.char_angle.setValue(math.degrees(t.char_angle))
        self.flip_h.setChecked(t.flip_h)
        self.flip_v.setChecked(t.flip_v)
        self.stencil.setChecked(t.stencil)
        self.bridge.setValue(t.bridge)
        self.styles[:] = [dict(run) for run in t.styles]

    def value(self, tid: str) -> SketchText:
        """The fields as a text item called ``tid``."""
        return SketchText(
            tid,
            self.content.text(),
            x=self.x_box.value(),
            y=self.y_box.value(),
            height=self.height_box.value(),
            angle=math.radians(self.angle.value()),
            font=self.font_box.currentText() or "sans-serif",
            bold=self.bold.isChecked(),
            italic=self.italic.isChecked(),
            align=str(self.align.currentData()),
            box=self.box.value(),
            width=self.width_box.value(),
            spacing=self.spacing.value(),
            char_angle=math.radians(self.char_angle.value()),
            flip_h=self.flip_h.isChecked(),
            flip_v=self.flip_v.isChecked(),
            curve=str(self.curve.currentData() or ""),
            offset=self.offset.value(),
            stencil=self.stencil.isChecked(),
            bridge=self.bridge.value(),
            styles=[dict(run) for run in self.styles],
        )

    def style_selection(self, key: str) -> bool:
        """Style the characters selected in the text box (TR121, D2202): ``bold`` and
        ``italic`` switch the style of the first selected character; ``angle`` turns
        them by the Turn angle. False when nothing is selected."""
        start = self.content.selectionStart()
        count = len(self.content.selectedText())
        if start < 0 or count == 0:
            return False
        item = self.value("")
        if key == "angle":
            set_style(item, start, start + count, angle=math.radians(self.style_angle.value()))
        else:
            bold, italic, _turn = char_style(item, start)
            now = {"bold": bold, "italic": italic}[key]
            set_style(item, start, start + count, **{key: not now})
        self.styles[:] = item.styles
        return True

    def _store(self) -> None:
        """Keep the fields in the item being edited (or add a new one with text)."""
        if not hasattr(self, "current"):
            return
        if self.current is None:
            if self.content.text().strip():
                tid = next_text_id(Sketch(texts=self.texts))
                self.texts.append(self.value(tid))
                self.current = tid
            return
        for i, t in enumerate(self.texts):
            if t.id == self.current:
                self.texts[i] = self.value(t.id)

    def delete_current(self) -> None:
        """Remove the text item being edited."""
        self.texts = [t for t in self.texts if t.id != self.current]
        self.current = None
        self.content.clear()  # so the deleted text is not kept as a new one
        self._fill_pick()
        self._picked()

    def _ok(self) -> None:
        self._store()
        self.texts = [t for t in self.texts if t.text.strip()]
        self.accept()


def edit_texts(canvas: SketchCanvas, parent: QWidget | None = None) -> bool:
    """Open the Text dialog on the canvas's sketch; OK is one undoable sketch change."""
    dialog = TextDialog(canvas.edit.sketch, parent)
    accepted = dialog.exec() == QDialog.DialogCode.Accepted
    texts = dialog.texts
    dialog.deleteLater()  # closed dialogs stayed alive (D637)
    if not accepted:
        return False

    def change() -> None:
        canvas.edit.sketch.texts = copy.deepcopy(texts)

    canvas.run(change)
    return True
