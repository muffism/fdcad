"""Insert DXF in an open sketch (TUTORIAL_REVIEW_SPEC TR5, D695).

Choose a file, then the units, scale, angle, base point and layers. The drawing
then follows the cursor (held by its base point) until a click places it, like
a paste; Escape cancels.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.sketch.dxf_import import (
    UNIT_MM,
    UNIT_NAMES,
    DxfDrawing,
    DxfError,
    Placement,
    build,
    extent,
    parse,
)

if TYPE_CHECKING:
    from fdcad.ui.sketch_tools.canvas import SketchCanvas

TITLE = "Insert DXF"
FILTER = "DXF drawing (*.dxf)"
FROM_FILE = "From the file ({unit})"
NO_FILE_UNIT = "The file gives no unit: choose one"
UNITS = "Units"
SCALE = "Scale"
ANGLE = "Angle (degrees)"
BASE = "Base point"
BASE_ORIGIN = "Drawing origin"
BASE_MIDDLE = "Middle of the drawing"
LAYERS = "Layers"
LEFT_OUT = "Left out of the insert: {what}. The rest was inserted."
SKIPPED = "Not inserted: {what}."
PLACE = "Move the drawing and click to place it. Escape cancels."
READ_FAILED = "{name} could not be read: {reason}"
#: Unit choices offered, as (code, label).
CHOICES = ((4, "mm"), (5, "cm"), (6, "m"), (1, "in"), (2, "ft"))


class DxfOptions(QDialog):
    """Units, scale, angle, base point and layers for one drawing."""

    def __init__(self, drawing: DxfDrawing, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.drawing = drawing
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.units = QComboBox()
        if drawing.units in UNIT_MM:
            self.units.addItem(FROM_FILE.format(unit=UNIT_NAMES[drawing.units]), drawing.units)
        for code, label in CHOICES:
            self.units.addItem(label, code)
        form.addRow(UNITS, self.units)
        if drawing.units not in UNIT_MM:
            form.addRow(QLabel(NO_FILE_UNIT))
            if drawing.measurement == 0:
                # The file says imperial: start on inches (audit D item 18, D742).
                self.units.setCurrentIndex(self.units.findData(1))
        self.scale = QDoubleSpinBox()
        self.scale.setRange(1e-6, 1e6)
        self.scale.setDecimals(6)
        self.scale.setValue(1.0)
        form.addRow(SCALE, self.scale)
        self.angle = QDoubleSpinBox()
        self.angle.setRange(-360.0, 360.0)
        self.angle.setDecimals(3)
        form.addRow(ANGLE, self.angle)
        self.base = QComboBox()
        self.base.addItem(BASE_ORIGIN, "origin")
        self.base.addItem(BASE_MIDDLE, "middle")
        form.addRow(BASE, self.base)
        layout.addLayout(form)
        self.layer_boxes: dict[str, QCheckBox] = {}
        layers = drawing.layers
        if len(layers) > 1:
            group = QGroupBox(LAYERS)
            inner = QVBoxLayout(group)
            for name in layers:
                box = QCheckBox(name)
                box.setChecked(True)
                inner.addWidget(box)
                self.layer_boxes[name] = box
            layout.addWidget(group)
        if drawing.skipped:
            what = ", ".join(f"{n} {k.lower()}" for k, n in sorted(drawing.skipped.items()))
            note = QLabel(SKIPPED.format(what=what))
            note.setWordWrap(True)
            layout.addWidget(note)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def placement(self) -> tuple[Placement, str]:
        """The placement (mm per drawing unit, turn, layers) and the base point."""
        mm = UNIT_MM.get(int(self.units.currentData()), 1.0)
        layers = (
            {n for n, box in self.layer_boxes.items() if box.isChecked()}
            if self.layer_boxes
            else None
        )
        place = Placement(
            scale=mm * self.scale.value(), angle=math.radians(self.angle.value()), layers=layers
        )
        return place, str(self.base.currentData())


def drawing_clip_with_notes(drawing: DxfDrawing, place: Placement, base: str) -> tuple[object, str]:
    """The drawing as copied sketch entities, held by its base point, and a list of what
    the build left out (D733), or empty. Raises DxfError."""
    from fdcad.core.sketch.model import Sketch, sketch_to_data
    from fdcad.core.sketch.ops.clipboard import Clip

    sk = Sketch()
    built = build(drawing, sk, place)
    anchor = (0.0, 0.0)
    if base == "middle":
        box = extent(drawing)
        if box is not None:
            (x0, y0), (x1, y1) = box
            anchor = place.at((x0 + x1) / 2, (y0 + y1) / 2)
    else:
        anchor = place.at(0.0, 0.0)
    what = ", ".join(f"{n} {k.lower()}" for k, n in sorted(built.skipped.items()))
    return Clip(sketch_to_data(sk), anchor, 0, list(built.entities)), what


def drawing_clip(drawing: DxfDrawing, place: Placement, base: str) -> object:
    """The drawing as copied sketch entities, held by its base point. Raises DxfError."""
    return drawing_clip_with_notes(drawing, place, base)[0]


SVG_TITLE = "Insert SVG"
SVG_FILTER = "SVG drawing (*.svg)"


def insert_svg(canvas: SketchCanvas, path: str | None = None) -> bool:
    """Insert SVG (TR117, D863): the same options and placement as Insert DXF."""
    from fdcad.core.sketch.svg_import import parse as parse_svg

    if path is None:
        path, _filter = QFileDialog.getOpenFileName(canvas.window(), SVG_TITLE, "", SVG_FILTER)
        if not path:
            return False
    return insert_dxf(canvas, path, parse_svg)


def insert_dxf(canvas: SketchCanvas, path: str | None = None, reader: object = None) -> bool:
    """Ask for a DXF file and its options, then let the user place it. ``reader`` turns
    the file's text into a drawing (Insert SVG passes its own)."""
    parent = canvas.window()
    if path is None:
        path, _filter = QFileDialog.getOpenFileName(parent, TITLE, "", FILTER)
        if not path:
            return False
    name = Path(path).name
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        canvas.status_message.emit(READ_FAILED.format(name=name, reason=exc.strerror or exc))
        return False
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    try:
        drawing = reader(text) if callable(reader) else parse(text)
    except DxfError as exc:
        canvas.status_message.emit(str(exc))
        return False
    dialog = DxfOptions(drawing, parent)
    accepted = dialog.exec() == QDialog.DialogCode.Accepted
    dialog.deleteLater()  # closed dialogs stayed alive (D637, audit D8 item 2)
    if not accepted:
        return False
    place, base = dialog.placement()  # the widgets live until the event loop runs
    try:
        clip, left = drawing_clip_with_notes(drawing, place, base)
    except DxfError as exc:
        canvas.status_message.emit(str(exc))
        return False
    started = canvas.start_paste(clip, verb="Inserted")  # type: ignore[arg-type,unused-ignore]
    if left:
        # What the insert left out (blocks, hidden layers, 3D items; D733).
        canvas.status_message.emit(LEFT_OUT.format(what=left))
    return bool(started)
