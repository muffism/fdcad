"""Sketch, Shapes (TR228, D927): a triangle, trapezoid, keyhole, Reuleaux triangle, egg
or superellipse centred on the sketch origin, as one sketch undo step."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.units import Kind, UnitSystem
from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.sketch_tools.canvas import SketchCanvas

L, A, N = Kind.LENGTH, Kind.ANGLE, Kind.NUMBER
#: The values each shape asks for: (label key, kind, default text).
FIELDS: dict[str, list[tuple[str, Kind, str]]] = {
    "triangle_sss": [("side_a", L, "30"), ("side_b", L, "40"), ("side_c", L, "50")],
    "triangle_sas": [("side_a", L, "30"), ("side_b", L, "40"), ("angle_between", A, "90deg")],
    "triangle_asa": [("side_a", L, "40"), ("angle_1", A, "60deg"), ("angle_2", A, "60deg")],
    "trapezoid": [("bottom", L, "40"), ("top", L, "20"), ("height", L, "20")],
    "keyhole": [("hole", L, "10"), ("slot", L, "5"), ("slot_length", L, "12")],
    "reuleaux": [("width", L, "30")],
    "egg": [("width", L, "30"), ("height", L, "40")],
    "superellipse": [("width", L, "40"), ("height", L, "30"), ("exponent", N, "4")],
    # TR367 (D991): standard sections, sizes as typed (a catalogue size or any other)
    "angle": [("leg_a", L, "40"), ("leg_b", L, "40"), ("thickness", L, "4")],
    "channel": [("height", L, "50"), ("flange_width", L, "25"), ("thickness", L, "3")],
    "i_beam": [("height", L, "100"), ("width", L, "55"), ("web", L, "4.1"), ("flange", L, "5.7")],
    "rect_tube": [("width", L, "40"), ("height", L, "20"), ("wall", L, "2")],
    "round_tube": [("outside", L, "20"), ("wall", L, "2")],
    "din_rail": [("thickness", L, "1")],
}


class ShapeDialog(QDialog):
    """The shape and its sizes."""

    def __init__(self, units: UnitSystem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.units = units
        self.setWindowTitle(strings.PRESET_TITLE)
        self.kind = QComboBox()
        for key, label in strings.PRESET_KINDS.items():
            self.kind.addItem(label, key)
        self.form = QFormLayout()
        self.form.addRow(strings.PRESET_KIND, self.kind)
        self.boxes: list[QLineEdit] = []
        self.labels: list[QLabel] = []
        for _ in range(4):  # TR367: an I beam has four sizes
            box, caption = QLineEdit(), QLabel()
            self.boxes.append(box)
            self.labels.append(caption)
            self.form.addRow(caption, box)
        self.message = QLabel(strings.PRESET_NOTE)
        self.message.setWordWrap(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(self.form)
        layout.addWidget(self.message)
        layout.addWidget(buttons)
        self.kind.currentIndexChanged.connect(lambda _i: self._show())
        self._show()

    def _show(self) -> None:
        fields = FIELDS[str(self.kind.currentData())]
        for i, (box, label) in enumerate(zip(self.boxes, self.labels, strict=True)):
            used = i < len(fields)
            self.form.setRowVisible(box, used)
            if used:
                key, kind, default = fields[i]
                label.setText(strings.PRESET_FIELDS[key])
                text = default
                if kind is Kind.LENGTH and self.units is UnitSystem.IN:
                    text = f"{float(default) / 25.4:.4g}in"
                box.setText(text)

    def loops(self) -> list[list[Any]] | None:
        """The closed outlines (a tube has two), or None with the reason shown."""
        from fdcad.core.sketch import shapes, std_profiles
        from fdcad.core.units import ExpressionError, evaluate

        kind = str(self.kind.currentData())
        if kind not in std_profiles.PROFILES:
            one = self.pieces()
            return None if one is None else [one]
        try:
            values = [
                evaluate(box.text(), vkind, self.units)
                for (_key, vkind, _d), box in zip(FIELDS[kind], self.boxes, strict=False)
            ]
            return list(getattr(std_profiles, kind)(*values))
        except (ExpressionError, shapes.ShapeError) as exc:
            self.message.setText(str(exc))
            return None

    def pieces(self) -> list[Any] | None:
        """The outline, or None with the reason shown."""
        from fdcad.core.sketch import shapes, std_profiles
        from fdcad.core.units import ExpressionError, evaluate

        kind = str(self.kind.currentData())
        if kind in std_profiles.PROFILES:
            loops = self.loops()
            return None if loops is None else [p for loop in loops for p in loop]
        values: list[float] = []
        try:
            for (_key, vkind, _d), box in zip(FIELDS[kind], self.boxes, strict=False):
                values.append(evaluate(box.text(), vkind, self.units))
            maker: Any = {
                "triangle_sss": shapes.triangle,
                "triangle_sas": shapes.triangle_sas,
                "triangle_asa": shapes.triangle_asa,
                "trapezoid": shapes.trapezoid,
                "keyhole": shapes.keyhole,
                "reuleaux": shapes.reuleaux,
                "egg": shapes.egg,
                "superellipse": shapes.superellipse,
            }[kind]
            return list(maker(*values))
        except (ExpressionError, shapes.ShapeError) as exc:
            self.message.setText(str(exc))
            return None

    def _ok(self) -> None:
        if self.loops() is not None:
            self.accept()


def run(dialog: QDialog) -> bool:
    """Show the dialog; tests replace this."""
    return dialog.exec() == QDialog.DialogCode.Accepted


def insert_shape(canvas: SketchCanvas) -> list[str]:
    """Ask, then add the shape centred on the sketch origin. Returns the new curves."""
    from fdcad.core.sketch.gear import add_to_sketch

    dialog = ShapeDialog(canvas.units, canvas)
    accepted = run(dialog)
    loops = dialog.loops() if accepted else None
    dialog.deleteLater()
    if loops is None:
        return []
    made: list[str] = []

    def change() -> None:
        for loop in loops:  # TR367: each outline of a tube on its own
            made.extend(add_to_sketch(canvas.edit.sketch, loop))

    canvas.run(change)
    return made
