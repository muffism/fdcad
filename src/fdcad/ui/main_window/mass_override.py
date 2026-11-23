"""Override Mass Properties (TR80, D1021): type a mass, and optionally a centre of mass and
an inertia tensor, for a part whose bodies are imported or simplified. Values are in the
part's unit (grams and mm, or pounds and inches); they are saved in the part."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.mass import MassOverride, check_override
from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.session import DocumentSession

#: Tensor cells as typed: Ixx, Iyy, Izz, Ixy, Ixz, Iyz.
_CELLS = ((0, 0), (1, 1), (2, 2), (0, 1), (0, 2), (1, 2))
_NAMES = ("Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz")


def _box(low: float = -1e12) -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(low, 1e12)
    box.setDecimals(6)
    return box


class MassOverrideDialog(QDialog):
    """Mass, an optional centre and an optional inertia; OK, Cancel or Clear Override."""

    CLEAR = 2  # the dialog result for Clear Override

    def __init__(self, session: DocumentSession, parent: QWidget | None = None) -> None:
        from fdcad.core.mass import part_override

        super().__init__(parent)
        self.setWindowTitle(strings.MASS_OVERRIDE_TITLE)
        inch = session.document.units.value == "in"
        self.k = 1 / 25.4 if inch else 1.0  # mm to the shown length
        self.m = 1 / 453.59237 if inch else 1.0  # g to the shown mass
        length, mass = ("in", "lb") if inch else ("mm", "g")
        self.mass = _box(0.0)
        self.mass.setSuffix(f" {mass}")
        self.use_centre = QCheckBox(strings.MASS_OVERRIDE_CENTRE)
        self.centre = [_box() for _ in range(3)]
        for b in self.centre:
            b.setSuffix(f" {length}")
        self.use_inertia = QCheckBox(strings.MASS_OVERRIDE_INERTIA)
        self.inertia = [_box() for _ in _CELLS]
        for b in self.inertia:
            b.setSuffix(f" {mass} {length}^2")
        self.note = QLabel(strings.MASS_OVERRIDE_NOTE)
        self.note.setWordWrap(True)
        form = QFormLayout()
        form.addRow(strings.MASS_OVERRIDE_MASS, self.mass)
        form.addRow(self.use_centre)
        grid = QGridLayout()
        for i, (name, b) in enumerate(zip("XYZ", self.centre, strict=True)):
            grid.addWidget(QLabel(name), 0, 2 * i)
            grid.addWidget(b, 0, 2 * i + 1)
        form.addRow(grid)
        form.addRow(self.use_inertia)
        tensor = QGridLayout()
        for i, (name, b) in enumerate(zip(_NAMES, self.inertia, strict=True)):
            tensor.addWidget(QLabel(name), i // 3, 2 * (i % 3))
            tensor.addWidget(b, i // 3, 2 * (i % 3) + 1)
        form.addRow(tensor)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.clear_button = buttons.addButton(
            strings.MASS_OVERRIDE_CLEAR, QDialogButtonBox.ButtonRole.ResetRole
        )
        self.clear_button.clicked.connect(lambda: self.done(self.CLEAR))
        buttons.accepted.connect(self.try_accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.note)
        layout.addWidget(buttons)
        self.use_centre.toggled.connect(lambda _on: self._enable())
        self.use_inertia.toggled.connect(lambda _on: self._enable())
        found = part_override(session.document)
        self.clear_button.setEnabled(found is not None)
        if found is not None:
            self.mass.setValue(found.mass * self.m)
            if found.centre is not None:
                self.use_centre.setChecked(True)
                for b, v in zip(self.centre, found.centre, strict=True):
                    b.setValue(v * self.k)
            if found.inertia is not None:
                self.use_inertia.setChecked(True)
                for b, (r, c) in zip(self.inertia, _CELLS, strict=True):
                    b.setValue(found.inertia[r][c] * self.m * self.k**2)
        self._enable()

    def _enable(self) -> None:
        for b in self.centre:
            b.setEnabled(self.use_centre.isChecked())
        for b in self.inertia:
            b.setEnabled(self.use_inertia.isChecked())

    def value(self) -> MassOverride:
        """The typed values in grams and millimetres."""
        centre = None
        if self.use_centre.isChecked():
            x, y, z = (b.value() / self.k for b in self.centre)
            centre = (x, y, z)
        inertia = None
        if self.use_inertia.isChecked():
            t = [[0.0] * 3 for _ in range(3)]
            for b, (r, c) in zip(self.inertia, _CELLS, strict=True):
                t[r][c] = t[c][r] = b.value() / (self.m * self.k**2)
            inertia = (
                (t[0][0], t[0][1], t[0][2]),
                (t[1][0], t[1][1], t[1][2]),
                (t[2][0], t[2][1], t[2][2]),
            )
        return MassOverride(self.mass.value() / self.m, centre, inertia)

    def try_accept(self) -> None:
        """Accept when the values can belong to a real body; otherwise say why."""
        problem = check_override(self.value())
        if problem is not None:
            self.note.setText(strings.MASS_OVERRIDE_BAD.format(reason=problem))
            return
        self.accept()


def run(dialog: QDialog) -> int:
    """Show the dialog; tests replace this."""
    return dialog.exec()


def edit_override(session: DocumentSession, parent: QWidget | None = None) -> bool:
    """Open the dialog and store what the user chose as one undo step. True when the
    override changed."""
    from fdcad.ui.commands.print_setup import SetMassOverride

    dialog = MassOverrideDialog(session, parent)
    result = run(dialog)
    value = dialog.value()
    dialog.deleteLater()
    if result == MassOverrideDialog.CLEAR:
        if not session.document.mass_override:
            return False
        session.undo.push(SetMassOverride(session, {}, strings.MASS_OVERRIDE_CLEAR))
        return True
    if result != QDialog.DialogCode.Accepted:
        return False
    session.undo.push(SetMassOverride(session, value.to_data(), strings.MASS_OVERRIDE_TITLE))
    return True
