"""Warning bar in the sketch editor for part copies that no longer match the part (D250).

The copies never move on their own (CLAUDE.md rule 12): the bar says what changed
and the Update button moves them, as one undoable step of the sketch.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from fdcad.core.sketch.links import LinkUpdate
from fdcad.ui import strings


class LinkBar(QFrame):
    """A small bar at the top of the sketch editor with the Update button."""

    update_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("linkBar")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setAutoFillBackground(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 4, 4)
        self.label = QLabel(self)
        self.button = QPushButton(strings.LINKS_UPDATE, self)
        self.button.setToolTip(strings.LINKS_UPDATE_TIP)
        self.button.clicked.connect(self.update_requested.emit)
        layout.addWidget(self.label)
        layout.addWidget(self.button)
        self.updates: list[LinkUpdate] = []
        self.hide()

    def set_updates(self, updates: list[LinkUpdate]) -> None:
        """Show the bar for these updates, or hide it when there are none."""
        self.updates = list(updates)
        moved = sum(1 for u in updates if not u.lost)
        lost = len(updates) - moved
        lines = []
        if moved:
            text = strings.LINKS_STALE_ONE if moved == 1 else strings.LINKS_STALE
            lines.append(text.format(count=moved))
        if lost:
            lines.append(strings.LINKS_LOST.format(count=lost))
        self.label.setText("\n".join(lines))
        self.button.setVisible(moved > 0)
        self.setVisible(bool(lines))
        if lines:
            self.adjustSize()
            self.move(8, 8)
            self.raise_()
