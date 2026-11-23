"""The question shown beside a new dimension that over defines the sketch (TOOL_SPEC T1.4.4).

A small frame inside the sketch view, like the value box, so the sketch stays
visible and nothing blocks: "This dimension over defines the sketch. Make it a
reference dimension?" with Make Reference and Keep Driving. Escape cancels.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from fdcad.ui import strings
from fdcad.ui.themes.style import unit


class OverDefinePrompt(QFrame):
    """Make Reference or Keep Driving for a new over defining dimension."""

    make_reference = Signal()
    keep_driving = Signal()
    cancelled = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("value_box")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        u = unit(self.font())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(u, u, u, u)
        layout.setSpacing(u)
        self.question = QLabel(strings.OVER_DEFINE_QUESTION)
        self.question.setWordWrap(True)
        self.question.setMaximumWidth(self.fontMetrics().horizontalAdvance("0") * 36)
        layout.addWidget(self.question)
        row = QHBoxLayout()
        row.setSpacing(u)
        self.reference = QPushButton(strings.MAKE_REFERENCE)
        self.driving = QPushButton(strings.KEEP_DRIVING)
        self.reference.setDefault(True)
        # Signal to signal, as the value box does.
        self.reference.clicked.connect(self.make_reference)
        self.driving.clicked.connect(self.keep_driving)
        row.addWidget(self.reference)
        row.addWidget(self.driving)
        layout.addLayout(row)

    def open_at(self, x: int, y: int) -> None:
        """Show with its top left at ``x``, ``y``."""
        self.adjustSize()
        self.move(x, y)
        self.show()
        self.raise_()
        self.reference.setFocus()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Escape cancels the new dimension."""
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            return
        super().keyPressEvent(event)
