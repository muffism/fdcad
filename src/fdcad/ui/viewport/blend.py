"""Before and after slider for a feature preview (TR224 item 4, D1610).

While a preview shows the finished part (Fillet, Chamfer, Shell, Draft), a small
slider floats over the lower right of the 3D view. Moving it fades from the new
part (left, the default) to the part before the feature (right). It is a small
frameless tool window, since widgets inside the kernel's native view are hidden
by the drawing.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSlider, QWidget

AFTER = "After"
BEFORE = "Before"
TIP = "Drag to fade between the part with this feature and the part before it."


class BlendSlider(QFrame):
    """The slider: 0 shows the new part, 100 the old one."""

    def __init__(self, view: QWidget, changed: Callable[[float], None]) -> None:
        super().__init__(view.window())
        self.view = view
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setObjectName("preview_blend")
        self.setToolTip(TIP)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.addWidget(QLabel(AFTER))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setFixedWidth(120)
        layout.addWidget(self.slider)
        layout.addWidget(QLabel(BEFORE))
        self.slider.valueChanged.connect(lambda v: changed(v / 100))
        self.hide()

    def place(self) -> None:
        """Keep it over the lower right corner of the view."""
        self.adjustSize()
        margin = 12
        corner = self.view.mapToGlobal(QPoint(self.view.width(), self.view.height()))
        self.move(corner.x() - self.width() - margin, corner.y() - self.height() - margin)

    def open(self) -> None:
        """Show it at After (when the view is on screen)."""
        self.slider.blockSignals(True)
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        if self.view.isVisible():
            self.place()
            self.show()
