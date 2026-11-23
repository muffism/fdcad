"""Status bar widgets: sketch status and the unit selector (PHASE1_CORRECTIONS L6)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QLabel, QMenu, QToolButton, QWidget

from fdcad.core.units import UnitSystem
from fdcad.ui import strings
from fdcad.ui.themes import theme


def sketch_state(text: str) -> str | None:
    """The state of a sketch status text: under, full, over, or None."""
    for state, template in strings.SKETCH_STATUS.items():
        prefix = template.split("{", 1)[0]
        if prefix and text.startswith(prefix):
            return state
    return None


class SketchStatusLabel(QLabel):
    """Under, fully or over defined, in the sketch colours (W3.4). Hidden when empty.
    A click opens the sketch problem list (TR38, D1301)."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sketch_status")
        self.state: str | None = None
        self.setToolTip(strings.PROBLEMS_TIP)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hide()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802  (Qt override)
        """A left click opens the problem list."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def setText(self, text: str) -> None:  # noqa: N802  (Qt override)
        """Show the text in the colour of its state."""
        super().setText(text)
        self.state = sketch_state(text)
        self.restyle()
        self.setVisible(bool(text))

    def restyle(self) -> None:
        """Pick the colour again, for example after the theme changed."""
        colors = theme.palette()
        color = {
            "under": colors.sketch_under,
            "full": colors.sketch_full,
            "over": colors.sketch_over,
            "dangling": colors.state_warning,  # TR38 (D1301)
            "invalid": colors.sketch_over,
            "no_solution": colors.sketch_over,
        }.get(self.state or "")
        self.setStyleSheet(f"QLabel {{ color: {color}; font-weight: 600; }}" if color else "")


class UnitSelector(QToolButton):
    """The part's display units at the bottom right. A click opens the list."""

    unit_chosen = Signal(object)  # UnitSystem

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("unit_selector")
        self.setMinimumHeight(24)  # the U3.3 hit area
        self.setAutoRaise(True)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setToolTip(strings.UNIT_SELECTOR_TIP)
        menu = QMenu(self)
        self.unit_actions = {}
        for unit in UnitSystem:
            action = menu.addAction(strings.UNIT_NAMES.get(unit.value, unit.value))
            action.setCheckable(True)
            action.triggered.connect(lambda _c=False, u=unit: self.unit_chosen.emit(u))
            self.unit_actions[unit] = action
        self.setMenu(menu)

    def set_unit(self, unit: UnitSystem) -> None:
        """Show ``unit`` as the current one."""
        self.setText(unit.value)
        for other, action in self.unit_actions.items():
            action.setChecked(other is unit)
