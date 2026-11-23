"""The guide shown during a right drag gesture (TOOL_SPEC T10.2, SHORTCUTS.md 7).

After a short drag a ring of the context's gesture commands appears around the
press point. The direction the cursor points to is highlighted once the drag
is long enough to run it. Releasing inside the inner circle runs nothing, as
before (``GESTURE_MIN_PX``). The guide is a small see-through window, so it
also shows over the native 3D view, and it never takes the mouse.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from fdcad.ui.input.commands import DIRECTIONS_8, GESTURE_MIN_PX, gesture_direction
from fdcad.ui.themes.typography import Role, type_font

#: The guide appears once the drag is this long (pixels).
SHOW_PX = 10.0
#: Distance of the command labels from the press point (pixels).
LABEL_RADIUS = 92.0
_SIZE = 320

#: Gives the commands to show: {direction: label} and 4 or 8 directions.
GuideSource = Callable[[], tuple[dict[str, str], int]]


def direction_angle(direction: str) -> float:
    """Screen angle of a direction, counter clockwise from the right, in radians."""
    return DIRECTIONS_8.index(direction) * math.pi / 4


class GestureGuide(QWidget):
    """A ring of gesture commands around the press point."""

    def __init__(self, labels: dict[str, str], sectors: int, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("gesture_guide")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.labels = labels
        self.sectors = sectors
        self.active: str | None = None
        self.resize(_SIZE, _SIZE)

    def place(self, centre: QPoint) -> None:
        """Centre the guide on a screen point and show it."""
        self.move(centre - QPoint(_SIZE // 2, _SIZE // 2))
        self.show()

    def point_to(self, dx: float, dy: float) -> None:
        """Highlight the command the drag points to, or none inside the inner circle."""
        active = gesture_direction(dx, dy, self.sectors)
        if active != self.active:
            self.active = active
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Draw the inner circle and the command labels."""
        from fdcad.ui.themes.theme import chrome

        colors = chrome()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(_SIZE / 2, _SIZE / 2)
        ring = QColor(colors.accent)
        ring.setAlpha(150)
        painter.setPen(QPen(ring, 1.5, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(c, GESTURE_MIN_PX, GESTURE_MIN_PX)
        painter.setFont(type_font(Role.BODY, self.font()))
        metrics = painter.fontMetrics()
        for direction, label in self.labels.items():
            if direction not in DIRECTIONS_8:
                continue
            a = direction_angle(direction)
            p = c + QPointF(math.cos(a) * LABEL_RADIUS, -math.sin(a) * LABEL_RADIUS)
            w = metrics.horizontalAdvance(label) + 12
            h = metrics.height() + 6
            rect = QRectF(p.x() - w / 2, p.y() - h / 2, w, h)
            on = direction == self.active
            fill = QColor(colors.accent if on else colors.raised)
            fill.setAlpha(235)
            painter.setPen(QPen(QColor(colors.accent if on else colors.border), 1))
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, 4, 4)
            painter.setPen(QColor(colors.on_accent if on else colors.text))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
        painter.end()


class GestureTracker:
    """Follows one right drag on ``owner`` and shows the guide for it."""

    def __init__(self, owner: QWidget) -> None:
        self.owner = owner
        #: Set by the window; without it the drag still works, with no guide.
        self.source: GuideSource | None = None
        self.guide: GestureGuide | None = None
        self._press: QPointF | None = None

    def press(self, pos: QPointF) -> None:
        """A gesture drag starts at ``pos`` (widget pixels)."""
        self.release()
        self._press = pos

    def move(self, pos: QPointF) -> None:
        """The drag moved: show the guide after a short drag and highlight the direction."""
        if self._press is None:
            return
        d = pos - self._press
        if self.guide is None:
            if math.hypot(d.x(), d.y()) < SHOW_PX or self.source is None:
                return
            labels, sectors = self.source()
            self.guide = GestureGuide(labels, sectors, self.owner)
            self.guide.place(self.owner.mapToGlobal(self._press.toPoint()))
        self.guide.point_to(d.x(), d.y())

    def release(self) -> None:
        """The drag ended: hide the guide."""
        self._press = None
        if self.guide is not None:
            self.guide.hide()
            self.guide.deleteLater()
            self.guide = None
