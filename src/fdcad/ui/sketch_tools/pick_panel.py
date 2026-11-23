"""The small panel of a Phase 2 sketch tool (PHASE2_SPEC P2.8): a prompt and the
tool's own options, built from ``tool.options``."""

from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.units import ExpressionError, Kind, UnitSystem, evaluate
from fdcad.ui.sketch_tools import tool_text as strings_picture
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.tool_options import Option


def _image_format(data: bytes) -> str | None:
    """``png``, ``jpeg`` or ``bmp`` from the file's first bytes, or None."""
    if data.startswith(b"\x89PNG"):
        return "png"
    if data.startswith(b"\xff\xd8"):
        return "jpeg"
    if data.startswith(b"BM"):
        return "bmp"
    return None


class PickToolPanel(QGroupBox):
    """Fields for the active Phase 2 tool. Hidden for other tools."""

    def __init__(self, canvas: SketchCanvas, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pick_tool_panel")
        self.canvas = canvas
        layout = QVBoxLayout(self)
        self.prompt = QLabel()
        self.prompt.setWordWrap(True)
        layout.addWidget(self.prompt)
        self.body = QWidget()
        self.form = QFormLayout(self.body)
        self.form.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.body)
        #: The field of each option, by option key.
        self.fields: dict[str, QWidget] = {}
        self._tool: object | None = None
        canvas.tool_changed.connect(lambda _name: self.refresh())
        canvas.edited.connect(self.sync)
        canvas.tool_values_changed.connect(self.sync)
        self.refresh()

    def refresh(self) -> None:
        """Rebuild for the active tool."""
        tool = self.canvas.tool
        options: tuple[Option, ...] = getattr(tool, "options", ())
        prompt = str(getattr(tool, "prompt", ""))
        show = tool is not None and (bool(options) or bool(prompt))
        self.setVisible(show)
        if tool is self._tool:
            self.sync()
            return
        self._tool = tool
        while self.form.rowCount():
            self.form.removeRow(0)
        self.fields = {}
        if not show or tool is None:
            return
        self.setTitle(tool.label)
        for opt in options:
            widget = self._field(opt)
            widget.setObjectName(f"tool_{opt.key}")
            if opt.tip:
                widget.setToolTip(opt.tip)
                widget.setProperty("tip", opt.tip)
            self.fields[opt.key] = widget
            if opt.kind in ("bool", "button", "file"):
                self.form.addRow(widget)
            else:
                self.form.addRow(opt.label, widget)
        self.sync()

    def _field(self, opt: Option) -> QWidget:
        if opt.kind == "bool":
            box = QCheckBox(opt.label)
            box.toggled.connect(lambda on, k=opt.key: self._set(k, bool(on)))
            return box
        if opt.kind == "choice":
            combo = QComboBox()
            for value, label in opt.choices:
                combo.addItem(label, value)
            combo.currentIndexChanged.connect(
                lambda _i, k=opt.key, c=combo: self._set(k, str(c.currentData()))
            )
            return combo
        if opt.kind == "int":
            spin = QSpinBox()
            spin.setRange(opt.low, opt.high)
            spin.valueChanged.connect(lambda v, k=opt.key: self._set(k, int(v)))
            return spin
        if opt.kind == "button":
            button = QPushButton(opt.label)
            button.clicked.connect(lambda _c=False, k=opt.key: self._press(k))
            return button
        if opt.kind == "file":
            button = QPushButton(opt.label)
            button.clicked.connect(lambda _c=False: self.choose_image())
            return button
        if opt.kind == "text":  # kept as typed; the tool reads it (TR28)
            line = QLineEdit()
            line.editingFinished.connect(lambda k=opt.key, e=line: self._set(k, e.text()))
            return line
        edit = QLineEdit()
        kind = {"angle": Kind.ANGLE, "number": Kind.NUMBER}.get(opt.kind, Kind.LENGTH)
        edit.returnPressed.connect(lambda k=opt.key, e=edit, kd=kind: self._typed(k, e, kd))
        edit.editingFinished.connect(lambda k=opt.key, e=edit, kd=kind: self._typed(k, e, kd))
        return edit

    def sync(self) -> None:
        """Show the tool's current option values (the cursor can change them)."""
        tool = self.canvas.tool
        if tool is None:
            return
        self.prompt.setText(str(getattr(tool, "prompt", "")))
        for opt in getattr(tool, "options", ()):
            widget = self.fields.get(opt.key)
            if widget is None or opt.kind in ("button", "file"):
                continue
            value = getattr(tool, opt.key)
            widget.blockSignals(True)
            if isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QComboBox):
                widget.setCurrentIndex(max(widget.findData(value), 0))
            elif isinstance(widget, QSpinBox):
                widget.setValue(int(value))
            elif isinstance(widget, QLineEdit) and not widget.hasFocus():
                text = str(value) if opt.kind == "text" else self._text(opt, float(value))
                widget.setText(text)
            widget.blockSignals(False)

    def _text(self, opt: Option, value: float) -> str:
        if opt.kind == "number":
            return f"{value:.6g}"
        if opt.kind == "angle":
            return f"{math.degrees(value):.6g}deg"
        if self.canvas.units is UnitSystem.IN:
            return f"{value / 25.4:.6g}in"
        return f"{value:.6g}mm"

    def _typed(self, key: str, edit: QLineEdit, kind: Kind) -> None:
        try:
            value = evaluate(edit.text(), kind, self.canvas.units)
        except ExpressionError as exc:
            # Show what is wrong: red field, the reason as its tip and in the status bar.
            _mark(edit, str(exc))
            self.canvas.status_message.emit(str(exc))
            return
        _mark(edit, "")
        tool = self.canvas.tool
        if tool is not None and getattr(tool, key, None) != value:
            self._set(key, value)

    def _set(self, key: str, value: object) -> None:
        if self.canvas.tool is not None:
            self.canvas.set_tool_option(key, value)  # the same path as the canvas labels

    def _press(self, key: str) -> None:
        tool = self.canvas.tool
        if tool is not None and hasattr(tool, "option_changed"):
            self._after(tool.option_changed(key))

    def choose_image(self) -> None:
        """Ask for an image file and insert it (P2.9 item 1)."""
        path, _filter = QFileDialog.getOpenFileName(
            self, strings_picture.PICK_TITLE, "", strings_picture.PICK_FILTER
        )
        if path:
            self.insert_image(path)

    def insert_image(self, path: str) -> bool:
        """Read an image file and hand it to the Picture tool. False when it cannot be
        read; the status bar then says why."""
        tool = self.canvas.tool
        insert = getattr(tool, "insert", None)
        if insert is None:
            return False
        try:
            data = Path(path).read_bytes()
        except OSError:
            self.canvas.status_message.emit(strings_picture.UNREADABLE.format(name=path))
            return False
        image = QImage.fromData(data)
        fmt = _image_format(data)
        if image.isNull() or fmt is None:
            self.canvas.status_message.emit(strings_picture.NOT_IMAGE.format(name=Path(path).name))
            return False
        ok = bool(insert(data, Path(path).name, fmt, image.width(), image.height()))
        self._after(ok)
        return ok

    def _after(self, changed: bool) -> None:
        if changed:
            self.canvas.changed()
        self.canvas._tool_note()
        self.canvas.update()
        self.sync()


def _mark(edit: QLineEdit, error: str) -> None:
    """Show ``error`` on a field (red, as its tip), or clear it when empty."""
    edit.setProperty("error", bool(error))
    edit.setToolTip(error or edit.property("tip") or "")
    edit.style().unpolish(edit)
    edit.style().polish(edit)
