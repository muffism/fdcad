"""Select Other: choose among everything under the cursor (TOOL_SPEC T9.13, T14.3.1).

A small list at the cursor shows each item under it in depth order, nearest
first, with a type icon. Hovering a row (or stepping with Tab, the arrows or the
mouse wheel) marks that item in the view; clicking a row or pressing Enter
selects it. A right click on a face row hides that face for the moment, so the
items behind it are easier to see; closing the list shows it again.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QCursor, QKeyEvent, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QFrame, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from fdcad.ui import strings_extra as text

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab, MainWindow

#: Item kinds, in the words and icons the list uses.
KIND_LABELS = {
    "face": "Face",
    "edge": "Edge",
    "vertex": "Vertex",
    "plane": "Plane",
    "sketch": "Sketch",
}


@dataclass
class Candidate:
    """One row of the list: what it is, its label and the thing to select."""

    kind: str
    label: str
    payload: Any


def kind_of(shape: Any) -> str:
    """ "face", "edge" or "vertex" for a picked shape (anything else counts as a face)."""
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_VERTEX

    kind = shape.ShapeType()
    if kind == TopAbs_EDGE:
        return "edge"
    if kind == TopAbs_VERTEX:
        return "vertex"
    return "face"


def step(index: int, delta: int, count: int) -> int:
    """The row ``delta`` rows on from ``index``, wrapping round."""
    if count <= 0:
        return -1
    return (index + delta) % count


class _List(QListWidget):
    """The rows; passes right clicks and the wheel to the popup."""

    right_clicked = Signal(int)
    wheel_steps = Signal(int)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Right click hides a face row for the moment."""
        if event.button() == Qt.MouseButton.RightButton:
            item = self.itemAt(event.position().toPoint())
            if item is not None:
                self.right_clicked.emit(self.row(item))
            event.accept()
            return
        super().mousePressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        """The wheel steps through the rows instead of scrolling."""
        delta = event.angleDelta().y()
        if delta:
            self.wheel_steps.emit(-1 if delta > 0 else 1)
        event.accept()


class SelectOtherList(QFrame):
    """The popup list. ``hovered`` and ``chosen`` give a row; ``hide_requested`` a face row."""

    hovered = Signal(int)
    chosen = Signal(int)
    hide_requested = Signal(int)
    closed = Signal()

    def __init__(self, candidates: list[Candidate], parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        from fdcad.ui.icons import icon

        self.setObjectName("select_other")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.candidates = list(candidates)
        self.rows = _List(self)
        self.rows.setObjectName("select_other_rows")
        self.rows.setMouseTracking(True)
        for c in self.candidates:
            item = QListWidgetItem(icon(f"select.{c.kind}"), c.label)
            self.rows.addItem(item)
        self.rows.itemEntered.connect(lambda item: self.set_current(self.rows.row(item)))
        self.rows.itemClicked.connect(lambda item: self.choose(self.rows.row(item)))
        self.rows.right_clicked.connect(self.hide_row)
        self.rows.wheel_steps.connect(self.step)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.rows)
        self.setFocusProxy(self.rows)
        self.rows.installEventFilter(self)
        self.set_current(0 if self.candidates else -1)

    def current(self) -> int:
        """The marked row, or -1."""
        return self.rows.currentRow()

    def set_current(self, index: int) -> None:
        """Mark a row and tell the view to highlight its item."""
        if not 0 <= index < self.rows.count():
            return
        if index != self.rows.currentRow():
            self.rows.setCurrentRow(index)
        self.hovered.emit(index)

    def step(self, delta: int) -> None:
        """Move the mark by ``delta`` rows (Tab, arrows, wheel)."""
        index = step(self.current(), delta, self.rows.count())
        if index >= 0:
            self.set_current(index)

    def choose(self, index: int) -> None:
        """Select a row's item and close."""
        if 0 <= index < len(self.candidates):
            self.chosen.emit(index)
        self.close()

    def hide_row(self, index: int) -> None:
        """Hide a face for the moment (T14.3.1). Other kinds are left alone."""
        if 0 <= index < len(self.candidates) and self.candidates[index].kind == "face":
            self.hide_requested.emit(index)
            item = self.rows.item(index)
            if item is not None:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.step(1)

    def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802
        """Tab and Shift+Tab step through the rows, Enter selects."""
        if isinstance(event, QKeyEvent) and event.type() == QKeyEvent.Type.KeyPress:
            return self._key(event)
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Keys sent to the popup itself."""
        if not self._key(event):
            super().keyPressEvent(event)

    def _key(self, event: QKeyEvent) -> bool:
        key = event.key()
        if key == Qt.Key.Key_Tab:
            self.step(1)
        elif key == Qt.Key.Key_Backtab:
            self.step(-1)
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.choose(self.current())
        elif key == Qt.Key.Key_Escape:
            self.close()
        else:
            return False
        return True

    def open_at(self, pos: QPoint) -> None:
        """Show with its top left at a screen point."""
        self.adjustSize()
        self.move(pos)
        self.show()
        self.rows.setFocus()

    def closeEvent(self, event: Any) -> None:  # noqa: N802
        """Tell the view to show hidden faces again."""
        self.closed.emit()
        super().closeEvent(event)

    def hideEvent(self, event: Any) -> None:  # noqa: N802
        """A popup closed by a click outside is hidden, not closed: same clean up."""
        self.closed.emit()
        super().hideEvent(event)


def candidates_for(tab: DocumentTab, shapes: list[Any], plane: str | None) -> list[Candidate]:
    """List rows for shapes under the cursor (nearest first), then a plane under it."""
    from fdcad.ui.main_window.context_menu import ContextMenus

    doc = tab.session.document
    out: list[Candidate] = []
    counts: dict[str, int] = {}
    for shape in shapes:
        kind = kind_of(shape)
        counts[kind] = counts.get(kind, 0) + 1
        fid = ContextMenus.feature_of(tab, shape)
        owner = doc.feature(fid).name if fid is not None else ""
        label = f"{KIND_LABELS[kind]} {counts[kind]}"
        out.append(Candidate(kind, f"{label} ({owner})" if owner else label, shape))
    if plane is not None:
        out.append(Candidate("plane", doc.feature(plane).name, plane))
    return out


def open_select_other(
    window: MainWindow, tab: DocumentTab, pos: QPointF, shapes: list[Any] | None = None
) -> SelectOtherList | None:
    """Open the list for what lies under ``pos`` in ``tab``'s 3D view."""
    view = tab.viewport
    if shapes is None:
        detect = getattr(view, "detected_at", None)
        shapes = list(detect(pos)) if detect is not None else []
    under = getattr(view, "plane_under", None)
    plane = under(pos) if under is not None else None
    rows = candidates_for(tab, shapes, plane)
    if not rows:
        window.status.setText(text.SELECT_OTHER_EMPTY)
        return None
    popup = SelectOtherList(rows, window)

    def mark(index: int) -> None:
        c = rows[index]
        fn = getattr(view, "preview_shapes", None)
        if fn is not None:
            fn([c.payload] if c.kind != "plane" else [])

    def pick(index: int) -> None:
        c = rows[index]
        if c.kind == "plane":
            if window.tree is not None:
                window.tree.select(str(c.payload))
            return
        select = getattr(view, "select_shapes", None)
        if select is not None:
            select([c.payload])
        tab.selection = [c.payload]

    def hide(index: int) -> None:
        fn = getattr(view, "hide_face_for_now", None)
        if fn is not None:
            fn(rows[index].payload)

    def done() -> None:
        for name, args in (("preview_shapes", ([],)), ("show_hidden_faces", ())):
            fn = getattr(view, name, None)
            if fn is not None:
                fn(*args)

    popup.hovered.connect(mark)
    popup.chosen.connect(pick)
    popup.hide_requested.connect(hide)
    popup.closed.connect(done)
    popup.set_current(0)  # mark the nearest item at once
    window.select_other = popup  # type: ignore[attr-defined]
    at = view.mapToGlobal(pos.toPoint()) if hasattr(view, "mapToGlobal") else QCursor.pos()
    if window.isVisible():
        popup.open_at(at)
    return popup
