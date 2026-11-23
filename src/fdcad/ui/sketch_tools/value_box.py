"""The small value box of Smart Dimension and of dimensions on the model (W4).

It opens beside the dimension text with the current value selected. Enter or
the check button accepts, Escape or the cross cancels, and the rebuild arrow
applies the value while the box stays open. Values accept expressions and
units (PLAN section 7). The mouse wheel and the up and down arrows step the
value by the spin step; Ctrl steps ten times as far and Alt a tenth (T4.2.3).
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping

from PySide6.QtCore import Qt, Signal, SignalInstance
from PySide6.QtGui import QKeyEvent, QWheelEvent
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QToolButton,
    QWidget,
)

from fdcad.core.units import ExpressionError, Kind, UnitSystem, evaluate
from fdcad.core.units.expressions import MM_PER_UNIT
from fdcad.ui import strings
from fdcad.ui.themes.style import unit
from fdcad.ui.themes.typography import tabular


def default_step(kind: Kind, units: UnitSystem) -> float:
    """The spin step in the shown unit: 1 mm, 0.1 in or 1 degree (D117)."""
    if kind is Kind.LENGTH and units is UnitSystem.IN:
        return 0.1
    return 1.0


def step_factor(modifiers: Qt.KeyboardModifier) -> float:
    """Ctrl steps ten times as far, Alt a tenth."""
    if modifiers & Qt.KeyboardModifier.ControlModifier:
        return 10.0
    if modifiers & Qt.KeyboardModifier.AltModifier:
        return 0.1
    return 1.0


#: A plain number with its own length unit, as typed: "5mm", "0.25 in".
_UNIT_TEXT = re.compile(r"^\s*([-+]?(?:\d+\.?\d*|\.\d+))\s*([A-Za-z]+)\s*$")
_OWN_UNITS = ("mm", "cm", "m", "in", "ft")


def step_refusal(text: str, kind: Kind | None) -> str:
    """Why the value cannot step, for the tooltip (audit D2 item 5, D734)."""
    if text.strip().startswith("="):
        return STEP_FORMULA
    if kind is Kind.LENGTH:
        return STEP_ZERO
    return STEP_UNREADABLE


STEP_FORMULA = "A formula does not step. Type a new value, or change what the formula uses."
STEP_ZERO = "A length cannot step to zero or below. Use a smaller step, or type the value."
STEP_UNREADABLE = "The value cannot be read, so it cannot step. Type a value."


def stepped_text(
    text: str,
    delta: float,
    kind: Kind,
    units: UnitSystem,
    variables: Mapping[str, tuple[Kind, float]] | None = None,
) -> str | None:
    """``text`` changed by ``delta`` in the shown unit, or None when it cannot step.

    Formulas (text starting with "=") are not stepped, so a link to a variable is
    never replaced by a number. Lengths never step to zero or below.
    """
    if text.strip().startswith("="):
        return None
    own = _UNIT_TEXT.match(text)
    if kind is Kind.LENGTH and own is not None and own.group(2).lower() in _OWN_UNITS:
        # "5mm" keeps its unit (audit D2 item 5, D734): the step, set in the part unit,
        # is turned into the typed unit.
        per = evaluate("1" + own.group(2), Kind.LENGTH, units)
        new = round(float(own.group(1)) + delta * MM_PER_UNIT[units] / per, 6)
        if new <= 0:
            return None
        return f"{new:.6f}".rstrip("0").rstrip(".") + own.group(2)
    try:
        value = evaluate(text, kind, units, variables)
    except ExpressionError:
        return None
    if kind is Kind.ANGLE:
        shown = math.degrees(value)
    elif kind is Kind.LENGTH:
        shown = value / MM_PER_UNIT[units]
    else:
        shown = value
    new = round(shown + delta, 6)
    if kind is Kind.LENGTH and new <= 0:
        return None
    return f"{new:.6f}".rstrip("0").rstrip(".")


class ValueBox(QFrame):
    """A line edit with OK, cancel and rebuild buttons and a spin step."""

    accepted = Signal()
    rejected = Signal()
    applied = Signal()
    #: Tab (+1) or Shift+Tab (-1) while ``tab_moves`` is on (T15.3).
    tabbed = Signal(int)

    def __init__(
        self,
        text: str,
        parent: QWidget | None = None,
        kind: Kind | None = None,
        units: UnitSystem = UnitSystem.MM,
        variables: Mapping[str, tuple[Kind, float]] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("value_box")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.kind = kind
        self.units = units
        self.variables = dict(variables or {})
        #: Tab and Shift+Tab emit ``tabbed`` instead of moving the focus.
        self.tab_moves = False
        self.edit = QLineEdit(text)
        self.edit.setObjectName("dimension_editor")
        self.edit.setFont(tabular(self.edit.font()))  # digits don't jump (U2.4)
        self.edit.setMinimumWidth(self.fontMetrics().horizontalAdvance("0") * 12)
        self.edit.returnPressed.connect(self.accepted)
        self.edit.installEventFilter(self)
        u = unit(self.font())
        layout = QHBoxLayout(self)
        layout.setContentsMargins(u, u, u, u)
        layout.setSpacing(u // 2)
        layout.addWidget(self.edit)
        self.ok = self._button(strings.VALUE_OK, strings.VALUE_OK_TIP, self.accepted)
        self.cancel = self._button(strings.VALUE_CANCEL, strings.VALUE_CANCEL_TIP, self.rejected)
        self.rebuild = self._button(strings.VALUE_REBUILD, strings.VALUE_REBUILD_TIP, self.applied)
        for name, button in (("ok", self.ok), ("cancel", self.cancel), ("rebuild", self.rebuild)):
            button.setObjectName(f"value_{name}")
            layout.addWidget(button)
        self.step = QDoubleSpinBox()
        self.step.setObjectName("value_step")
        self.step.setToolTip(strings.VALUE_STEP_TIP)
        self.step.setDecimals(3)
        self.step.setRange(0.001, 1000.0)
        self.step.setValue(default_step(kind or Kind.NUMBER, units))
        self.step.setVisible(kind is not None)
        layout.addWidget(self.step)
        self.edit.selectAll()

    def _button(self, text: str, tip: str, signal: SignalInstance) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setToolTip(tip)
        button.setAutoRaise(True)
        # Signal to signal: connecting to a bound emit can crash during garbage collection.
        button.clicked.connect(signal)
        return button

    def text(self) -> str:
        """The typed value."""
        return self.edit.text()

    def show_error(self, message: str) -> None:
        """Mark the value as wrong."""
        self.edit.setToolTip(message)
        self.edit.setProperty("error", True)
        self.edit.style().unpolish(self.edit)
        self.edit.style().polish(self.edit)

    def open_at(self, x: int, y: int) -> None:
        """Show with its top left at ``x``, ``y`` and focus the value."""
        self.adjustSize()
        self.move(x, y)
        self.show()
        self.raise_()
        self.edit.setFocus()
        self.edit.selectAll()

    def start_typing(self, text: str) -> None:
        """Replace the value with ``text`` and put the cursor after it (a typed key, T15.4)."""
        self.edit.setText(text)
        self.edit.deselect()
        self.edit.end(False)

    def step_by(self, steps: float, modifiers: Qt.KeyboardModifier) -> bool:
        """Change the value by ``steps`` spin steps. Returns True when it changed."""
        if self.kind is None:
            return False
        delta = steps * self.step.value() * step_factor(modifiers)
        new = stepped_text(self.edit.text(), delta, self.kind, self.units, self.variables)
        if new is None:
            # Say why instead of doing nothing (audit D2 item 5, D734).
            from PySide6.QtWidgets import QToolTip

            self.last_refusal = step_refusal(self.edit.text(), self.kind)
            QToolTip.showText(
                self.edit.mapToGlobal(self.edit.rect().bottomLeft()), self.last_refusal, self.edit
            )
            return False
        self.last_refusal = ""
        self.edit.setText(new)
        self.edit.selectAll()
        return True

    def eventFilter(self, watched: object, event: object) -> bool:  # noqa: N802
        """Up and down arrows in the value field step it; Tab moves on when asked."""
        if (
            watched is self.edit
            and self.tab_moves
            and isinstance(event, QKeyEvent)
            and event.type() == QKeyEvent.Type.KeyPress
            and event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab)
        ):
            back = event.key() == Qt.Key.Key_Backtab or bool(
                event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            )
            self.tabbed.emit(-1 if back else 1)
            return True
        if (
            watched is self.edit
            and isinstance(event, QKeyEvent)
            and event.type() == QKeyEvent.Type.KeyPress
            and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down)
            and self.kind is not None
        ):
            self.step_by(1 if event.key() == Qt.Key.Key_Up else -1, event.modifiers())
            return True
        return super().eventFilter(watched, event)  # type: ignore[arg-type]

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        """The wheel over the box steps the value."""
        delta = event.angleDelta()
        # Some platforms turn Alt + wheel into a sideways scroll.
        amount = delta.y() or delta.x()
        if self.kind is None or not amount:
            super().wheelEvent(event)
            return
        self.step_by(amount / 120.0, event.modifiers())
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Escape cancels. Enter stays here, so it does not also reach the view behind."""
        if event.key() == Qt.Key.Key_Escape:
            self.rejected.emit()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            event.accept()
            return
        super().keyPressEvent(event)
