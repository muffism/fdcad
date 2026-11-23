"""Value box stepping for typed fields (TOOL_SPEC T4.2.3, T5.1.2, T5.1.3; DECISIONS D144).

The mouse wheel over a field, or the Up and Down keys in it, change a plain
number by one step: 1 mm or 1 degree (0.1 in for inch parts). Ctrl makes the
step ten times larger, Alt ten times smaller. A typed unit is kept. Formulas
and variable names are never replaced by a number, so stepping leaves them alone.
A step that would make the value zero or less is not taken.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent, QWheelEvent
from PySide6.QtWidgets import QLineEdit

from fdcad.core.units import Kind, UnitSystem

_PLAIN = re.compile(r"^\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)\s*([A-Za-z]*)\s*$")
_LENGTH_UNITS = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "ft": 304.8}
_ANGLE_UNITS = {"deg": 1.0, "rad": 180.0 / math.pi}  # degrees per unit


def base_step(kind: Kind, units: UnitSystem) -> float:
    """One step in the part's display unit: 1 mm, 0.1 in or 1 degree."""
    if kind is Kind.LENGTH and units is UnitSystem.IN:
        return 0.1
    return 1.0


def modifier_factor(modifiers: Qt.KeyboardModifier) -> float:
    """Ctrl steps ten times further, Alt a tenth as far."""
    if modifiers & Qt.KeyboardModifier.ControlModifier:
        return 10.0
    if modifiers & Qt.KeyboardModifier.AltModifier:
        return 0.1
    return 1.0


def step_text(text: str, kind: Kind, units: UnitSystem, steps: float, factor: float = 1.0) -> str:
    """``text`` after ``steps`` steps (negative goes down). Unchanged when it cannot step."""
    match = _PLAIN.match(text)
    if match is None or kind not in (Kind.LENGTH, Kind.ANGLE):
        return text
    number, unit = float(match.group(1)), match.group(2)
    table = _LENGTH_UNITS if kind is Kind.LENGTH else _ANGLE_UNITS
    if unit and unit not in table:
        return text
    # One step in the written unit (a bare number is in the part's unit, or degrees).
    if kind is Kind.LENGTH:
        part = 25.4 if units is UnitSystem.IN else 1.0
        step = base_step(kind, units) * part / (table[unit] if unit else part)
    else:
        step = base_step(kind, units) / (table[unit] if unit else 1.0)
    value = number + steps * step * factor
    if value <= 0:
        return text
    shown = f"{value:.6f}".rstrip("0").rstrip(".")
    return f"{shown} {unit}" if unit else shown


class Stepper(QObject):
    """Event filter that steps a line edit's value on wheel and Up and Down keys."""

    def __init__(self, edit: QLineEdit, kind: Kind, units: Callable[[], UnitSystem]) -> None:
        super().__init__(edit)
        self.edit, self.kind, self.units = edit, kind, units
        edit.installEventFilter(self)

    def step(self, steps: float, factor: float = 1.0) -> bool:
        """Step the value. Returns True when the text changed."""
        before = self.edit.text()
        after = step_text(before, self.kind, self.units(), steps, factor)
        if after == before:
            return False
        self.edit.setText(after)
        self.edit.selectAll()
        return True

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Wheel and Up and Down keys step; everything else passes on."""
        if watched is self.edit and isinstance(event, QWheelEvent):
            delta = event.angleDelta()
            amount = delta.y() or delta.x()  # Alt turns the wheel sideways on some systems
            if amount:
                self.step(amount / 120.0, modifier_factor(event.modifiers()))
            return True
        arrows = (Qt.Key.Key_Up, Qt.Key.Key_Down)
        if (
            watched is self.edit
            and isinstance(event, QKeyEvent)
            and event.type() == QEvent.Type.KeyPress
            and event.key() in arrows
        ):
            up = event.key() == Qt.Key.Key_Up
            self.step(1.0 if up else -1.0, modifier_factor(event.modifiers()))
            return True
        return False
