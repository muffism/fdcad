"""Extra views of the part for Split View (TUTORIAL_REVIEW_SPEC TR16, D699).

A pane is a second (third, fourth) kernel view on the main 3D view's viewer, so
it shows the same part, previews and highlights, and picks go through the same
interactive context: a face picked in any pane is selected in all of them. Each
pane has its own camera and standard view. Navigation is the main view's mouse
scheme: middle drag rotates (Ctrl pans, Shift zooms), the wheel zooms at the
cursor, a left click picks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import (
    QMouseEvent,
    QPaintEngine,
    QPaintEvent,
    QResizeEvent,
    QShowEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import QWidget

from fdcad.ui.viewport import keynav, look
from fdcad.ui.viewport.views import STANDARD_VIEWS

if TYPE_CHECKING:
    from fdcad.ui.viewport.widget import ViewportWidget

_WHEEL_ZOOM_STEP = 0.15
_DRAG_PX = 4


class ViewPane(QWidget):
    """One more view of the main view's part."""

    #: The pane was clicked: it is now the active view.
    activated = Signal(object)

    def __init__(self, main: ViewportWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_PaintOnScreen)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumSize(120, 90)
        self.main = main
        self._view: Any = None
        self._window: Any = None
        self._dpr = 1.0
        self._drag: str | None = None
        self._last = QPointF()
        self._press: QPointF | None = None
        #: The standard view to take when the kernel view first exists.
        self.pending_view = "iso"

    # Kernel view ------------------------------------------------------------------

    def paintEngine(self) -> QPaintEngine | None:  # type: ignore[override]  # noqa: N802
        """The kernel draws the pane, not Qt."""
        return None

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """Make the kernel view the first time the pane shows."""
        super().showEvent(event)
        if self._view is None:
            self._init_view()

    def _init_view(self) -> None:
        from OCP.Aspect import Aspect_NeutralWindow

        from fdcad.ui.viewport.native import set_native_handle
        from fdcad.ui.viewport.widget import background

        view = self.main._viewer.CreateView()
        window = Aspect_NeutralWindow()
        set_native_handle(window, int(self.winId()))
        self._window, self._view = window, view
        self._sync_size()
        view.SetWindow(window)
        look.apply_rendering(view)
        view.SetBgGradientColors(*background(self.main._palette), False)
        look.show_triad(view, self.main._palette, self._dpr)  # D2822
        view.SetComputedMode(self.main.display_style in ("hidden_lines", "hidden_lines_visible"))
        self.set_view(self.pending_view)

    def _sync_size(self) -> None:
        if self._window is None:
            return
        dpr = self.devicePixelRatioF()
        self._dpr = dpr
        self._window.SetSize(max(1, round(self.width() * dpr)), max(1, round(self.height() * dpr)))
        if self._view is not None:
            self._view.MustBeResized()
            self._view.Redraw()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Redraw the kernel view."""
        if self._view is not None:
            self._view.Redraw()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Follow the pane's size."""
        super().resizeEvent(event)
        self._sync_size()

    def close_view(self) -> None:
        """Remove the kernel view from the viewer (the pane is going away)."""
        if self._view is not None:
            self._view.Remove()
            self._view = None
        self._window = None

    # View commands (the active pane takes them) ------------------------------------

    def set_view(self, name: str) -> None:
        """Look along a standard direction and fit the part."""
        if name not in STANDARD_VIEWS:
            return
        if self._view is None:
            self.pending_view = name
            return
        eye, up = STANDARD_VIEWS[name]
        self._view.SetProj(*eye)
        self._view.SetUp(*up)
        self.fit_all()

    def look(self, eye: tuple[float, float, float], up: tuple[float, float, float]) -> None:
        """Look from ``eye`` with ``up`` and fit (Normal To)."""
        if self._view is not None:
            self._view.SetProj(*eye)
            self._view.SetUp(*up)
            self.fit_all()

    def fit_all(self, remember: bool = True) -> None:
        """Fit the part (everything shown when there is none)."""
        if self._view is None:
            return
        shape = self.main._part_shape
        if shape is None or shape.IsNull():
            self._view.FitAll(look.FIT_MARGIN, False)
        else:
            from OCP.Bnd import Bnd_Box
            from OCP.BRepBndLib import BRepBndLib

            box = Bnd_Box()
            BRepBndLib.Add_s(shape, box)
            if box.IsVoid():
                self._view.FitAll(look.FIT_MARGIN, False)
            else:
                self._view.FitAll(box, look.FIT_MARGIN)
        self._view.Redraw()

    def zoom_to_fit(self) -> None:
        """Zoom to Fit."""
        self.fit_all()

    def redraw(self) -> None:
        """Redraw."""
        if self._view is not None:
            self._view.Redraw()

    # Mouse ------------------------------------------------------------------------

    def _px(self, pos: QPointF) -> tuple[int, int]:
        return round(pos.x() * self._dpr), round(pos.y() * self._dpr)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Make this the active view; start a rotate, pan or zoom, or a pick."""
        self.setFocus()
        self.activated.emit(self)
        if self._view is None:
            return
        button, mods = event.button(), event.modifiers()
        self._last = self._press = event.position()
        if button == Qt.MouseButton.MiddleButton:
            if mods & Qt.KeyboardModifier.ShiftModifier:
                self._drag = "zoom"
            elif mods & Qt.KeyboardModifier.ControlModifier:
                self._drag = "pan"
            else:
                self._drag = "rotate"
                self._view.StartRotation(*self._px(event.position()))
        elif button == Qt.MouseButton.LeftButton:
            self._drag = "pick"
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Rotate, pan or zoom, or highlight what is under the cursor."""
        if self._view is None:
            return
        pos = event.position()
        if self._drag == "rotate":
            self._view.Rotation(*self._px(pos))
        elif self._drag == "pan":
            d = pos - self._last
            self._view.Pan(round(d.x() * self._dpr), round(-d.y() * self._dpr))
        elif self._drag == "zoom" and self._press is not None:
            self._zoom_at(self._press, keynav.zoom_factor(pos.y() - self._press.y()))
        elif self._drag is None:
            x, y = self._px(pos)
            self.main._context.MoveTo(x, y, self._view, True)
            self.main.sync_hover_rim()
        self._last = pos

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """A left click picks, as in the main view; the selection is shared."""
        drag, self._drag = self._drag, None
        if drag != "pick" or self._view is None or self._press is None:
            return
        if (event.position() - self._press).manhattanLength() > _DRAG_PX:
            return
        self.pick_at(
            event.position(), bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        )

    def pick_at(self, pos: QPointF, add: bool = False) -> None:
        """Pick what is under ``pos`` in this pane (shared with every view)."""
        from OCP.AIS import AIS_SelectionScheme_Replace, AIS_SelectionScheme_XOR

        if self._view is None:
            return
        ctx = self.main._context
        x, y = self._px(pos)
        ctx.MoveTo(x, y, self._view, False)
        ctx.SelectDetected(AIS_SelectionScheme_XOR if add else AIS_SelectionScheme_Replace)
        ctx.UpdateCurrentViewer()
        self.main.selection_changed.emit(self.main.selected())

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        """The wheel zooms at the cursor."""
        steps = event.angleDelta().y() / 120.0
        if steps and self._view is not None:
            self._zoom_at(event.position(), (1.0 + _WHEEL_ZOOM_STEP) ** steps)
        event.accept()

    def _zoom_at(self, pos: QPointF, factor: float) -> None:
        if self._view is None or factor <= 0:
            return
        d = 100.0 * (factor - 1.0) if factor >= 1.0 else -100.0 * (1.0 / factor - 1.0)
        x, y = self._px(pos)
        self._view.StartZoomAtPoint(x, y)
        self._view.ZoomAtPoint(x, y, x + round(d), y)
