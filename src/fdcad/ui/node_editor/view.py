"""The node canvas view: wheel zoom about the cursor, middle drag or Space drag pan,
box selection, and double click on empty canvas to add a node."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPoint, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QShowEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import QGraphicsView, QWidget

from fdcad.ui.node_editor.scene import NodeItem, NodeScene, PortItem

MIN_ZOOM = 0.15
MAX_ZOOM = 3.0
ZOOM_STEP = 1.15


class NodeView(QGraphicsView):
    """Shows a ``NodeScene``."""

    #: Double click on empty canvas, with the scene point.
    add_requested = Signal(QPointF)

    def __init__(self, scene: NodeScene, parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)
        self.setObjectName("node_view")
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.setSceneRect(-20000, -20000, 40000, 40000)
        self._pan_from: QPoint | None = None
        self._space = False
        #: Keys that delete the selection here too (the app's Delete command).
        self.delete_keys: Callable[[], list[QKeySequence]] = list
        self.on_delete: Callable[[], object] = lambda: None
        #: A fit asked for while the view was hidden or had no size yet: done when it
        #: is shown at its real size, so the graph does not open as a speck (D1034).
        self._fit_when_shown = False

    @property
    def zoom(self) -> float:
        """Current zoom factor."""
        return float(self.transform().m11())

    def zoom_by(self, factor: float) -> None:
        """Zoom by ``factor``, kept between the limits."""
        target = min(max(self.zoom * factor, MIN_ZOOM), MAX_ZOOM)
        step = target / self.zoom
        self.scale(step, step)

    def fit(self) -> None:
        """Show every node."""
        if not self.isVisible():
            self._fit_when_shown = True
        scene = self.scene()
        rect = scene.itemsBoundingRect()
        if rect.isEmpty():
            self.resetTransform()
            self.centerOn(0, 0)
            return
        self.fitInView(rect.adjusted(-40, -40, 40, 40), Qt.AspectRatioMode.KeepAspectRatio)
        if self.zoom > 1.0:
            self.zoom_by(1.0 / self.zoom)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802  (Qt override)
        """Do a fit that was asked for while hidden, once the size is known."""
        super().showEvent(event)
        if self._fit_when_shown:
            self._fit_when_shown = False
            QTimer.singleShot(0, self.fit)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802  (Qt override)
        steps = event.angleDelta().y() / 120.0
        if steps:
            self.zoom_by(ZOOM_STEP**steps)
        event.accept()

    def _start_pan(self, pos: QPoint) -> None:
        self._pan_from = pos
        self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802  (Qt override)
        if event.button() == Qt.MouseButton.MiddleButton or (
            self._space and event.button() == Qt.MouseButton.LeftButton
        ):
            self._start_pan(event.position().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802  (Qt override)
        if self._pan_from is not None:
            pos = event.position().toPoint()
            delta = pos - self._pan_from
            self._pan_from = pos
            self.pan_by(delta.x(), delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def pan_by(self, dx: int, dy: int) -> None:
        """Move the canvas by screen pixels."""
        h, v = self.horizontalScrollBar(), self.verticalScrollBar()
        h.setValue(h.value() - dx)
        v.setValue(v.value() - dy)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802  (Qt override)
        if self._pan_from is not None:
            self._pan_from = None
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802  (Qt override)
        item = self.itemAt(event.position().toPoint())
        while item is not None and not isinstance(item, NodeItem | PortItem):
            item = item.parentItem()
        if item is None and event.button() == Qt.MouseButton.LeftButton:
            self.add_requested.emit(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _is_delete(self, event: QKeyEvent) -> bool:
        pressed = QKeySequence(event.keyCombination())
        return any(
            k.matches(pressed) == QKeySequence.SequenceMatch.ExactMatch for k in self.delete_keys()
        )

    def event(self, event: object) -> bool:
        """Take the app's Delete key while the canvas has focus (DECISIONS D378)."""
        from PySide6.QtCore import QEvent

        if (
            isinstance(event, QKeyEvent)
            and event.type() == QEvent.Type.ShortcutOverride
            and self._is_delete(event)
        ):
            event.accept()
            return True
        return super().event(event)  # type: ignore[arg-type]

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802  (Qt override)
        if self._is_delete(event):
            self.on_delete()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space = True
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:  # noqa: N802  (Qt override)
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space = False
        super().keyReleaseEvent(event)
