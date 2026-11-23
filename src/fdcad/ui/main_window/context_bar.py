"""Context toolbar (TOOL_SPEC T8, D106): a small row of buttons by the cursor after a click.

Contents by selection (T8.2): a plane gives Sketch, Normal To and Hide or Show;
a flat face Sketch and Normal To (hiding bodies is Phase 3, D116 item 4); a
feature Edit Feature, Edit Sketch, Hide or Show of its sketch and Delete; a
finished sketch Edit Sketch, Extrude, Revolve and Hide or Show; sketch items in
an open sketch the fitting relations, Construction Geometry and Smart Dimension.
The bar never takes focus and hides when the cursor moves away. A right click
while it shows opens the full menu just below it (T8.3).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QToolButton

from fdcad.ui import strings
from fdcad.ui import strings_extra as text
from fdcad.ui.strings_phase3 import HIDE_BODY

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow
    from fdcad.ui.sketch_tools.canvas import SketchCanvas

#: Hide the bar when the cursor is this far from it, in pixels.
FADE_PX = 160

#: Icon of each offer: the command icons where one fits, else a context icon.
ICONS = {
    "sketch": "sketch.sketch",
    "extrude": "feature.extrude",
    "revolve": "feature.revolve",
    "normal_to": "view.normal_to",
    "edit": "context.edit",
    "edit_sketch": "context.edit_sketch",
    "hide": "context.hide",
    "show": "context.show",
    "delete": "edit.delete",
    "construction": "sketch.construction",
    "dimension": "sketch.dimension",
}

Offer = tuple[str, str, Callable[[], object]]


class ContextBar(QFrame):
    """Floating buttons for the current selection."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.window_ = window
        self.setObjectName("context_bar")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)  # round corners
        self.setFrameShape(QFrame.Shape.NoFrame)
        from fdcad.ui.themes.style import unit

        u = unit(self.font())
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(u, u, u, u)
        self.row.setSpacing(u // 2)
        self.buttons: dict[str, QToolButton] = {}
        self._timer = QTimer(self)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._fade)

    # What to offer -------------------------------------------------------------------

    def for_tree(self, *_args: object) -> None:
        """Show the bar for the feature selected in the tree."""
        w = self.window_
        tab = w.current
        fid = w.tree.selected_id() if w.tree is not None else None
        if tab is None or fid is None or self._busy():
            self.hide()
            return
        feature = tab.session.document.feature(fid)
        tree = w.tree
        assert tree is not None
        items: list[Offer] = []
        if feature.type == "plane":
            shown = fid in tab.visible_plane_ids()
            items = [
                ("sketch", strings.SKETCH, lambda: self._run(w.sketch_mode.start)),  # type: ignore[union-attr]
                ("normal_to", strings.NORMAL_TO, lambda: self._run(w.normal_to)),
                self._hide_offer(shown, lambda: tree.set_visible(fid, not shown)),
            ]
        elif feature.type == "sketch":
            shown = fid in tab.visible_sketch_ids()
            items = [
                (
                    "edit_sketch",
                    strings.EDIT_SKETCH,
                    lambda: self._run(lambda: w.edit_feature(fid)),
                ),
                ("extrude", strings.EXTRUDED_BOSS, lambda: self._feature("extrude")),
                ("revolve", strings.REVOLVED_BOSS, lambda: self._feature("revolve")),
                self._hide_offer(shown, lambda: tree.set_sketch_visible(fid, not shown)),
            ]
        elif feature.type != "origin":
            # Every feature, not only extrude and revolve (T8.2, audit D11 item 6, D719).
            from fdcad.ui.main_window.visibility import sketch_of

            items = [("edit", strings.EDIT_FEATURE, lambda: self._run(lambda: w.edit_feature(fid)))]
            sid = sketch_of(feature)
            if sid is not None and any(f.id == sid for f in tab.session.document.features):
                shown = sid in tab.visible_sketch_ids()
                items += [
                    (
                        "edit_sketch",
                        strings.EDIT_SKETCH,
                        lambda: self._run(lambda: w.edit_feature(sid)),
                    ),
                    self._hide_offer(shown, lambda: tree.set_sketch_visible(sid, not shown)),
                ]
            items.append(("delete", strings.DELETE, lambda: self._run(lambda: tree.delete(fid))))
        self.offer(items)

    def _relate(self, canvas: SketchCanvas, rtype: str) -> Callable[[], object]:
        from fdcad.ui.main_window import context_menu as cm

        return lambda *_a: self._run(lambda: cm.relate(canvas, rtype))

    def _hide_offer(self, shown: bool, slot: Callable[[], object]) -> Offer:
        return ("hide", strings.HIDE if shown else strings.SHOW, lambda: self._run(slot))

    def for_faces(self, shapes: list[Any]) -> None:
        """Show the bar for faces picked in the 3D view."""
        from fdcad.ui.main_window.plane_pick import flat_face

        w = self.window_
        tab = w.current
        if tab is None or not shapes or self._busy():
            self.hide()
            return
        tab.selection = list(shapes)
        if flat_face(tab) is None:
            self.hide()
            return
        self.offer(
            [
                ("sketch", strings.SKETCH, lambda: self._run(w.sketch_mode.start)),  # type: ignore[union-attr]
                ("normal_to", strings.NORMAL_TO, lambda: self._run(w.normal_to)),
                # Body hiding existed but was not offered here (T8.2, audit D11 item 8).
                ("hide", HIDE_BODY, lambda: self._run(w.body_display.hide_or_show)),
            ]
        )

    def for_sketch(self, canvas: SketchCanvas) -> None:
        """Show the bar for sketch items selected with no tool active (T8.2, T3.2.2)."""
        from fdcad.ui.main_window import context_menu as cm
        from fdcad.ui.sketch_tools.edit import relations_for

        ids = cm.selected_entities(canvas)
        if not ids or canvas.tool is not None or canvas.dimension_mode:
            self.hide()
            return
        items: list[Offer] = []
        for rtype in relations_for(canvas.edit.sketch, ids):
            items.append(
                (f"relation.{rtype}", strings.RELATION_NAMES[rtype], self._relate(canvas, rtype))
            )
        items.append(
            (
                "construction",
                text.CONSTRUCTION,
                lambda: self._run(lambda: cm.toggle_construction(canvas)),
            )
        )
        items.append(
            (
                "dimension",
                text.SMART_DIMENSION,
                lambda: self._run(lambda: cm.dimension_selection(canvas)),
            )
        )
        self.offer(items)

    def offer(self, items: list[tuple[str, str, Callable[[], object]]]) -> None:
        """Fill the bar and show it by the cursor (hidden when there is nothing)."""
        from fdcad.ui.command_tabs.ribbon import small_icon_size
        from fdcad.ui.icons import icon

        while self.row.count():
            item = self.row.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        self.buttons = {}
        for key, label, slot in items:
            button = QToolButton(self)
            shown_key = "show" if key == "hide" and label == strings.SHOW else key
            button.setIcon(icon(ICONS.get(shown_key, f"context.{key}")))
            size = small_icon_size(button)
            button.setIconSize(QSize(size, size))
            if button.icon().isNull():
                button.setText(label)
            button.setToolTip(label)
            button.setAutoRaise(True)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(slot)
            self.row.addWidget(button)
            self.buttons[key] = button
        if not items:
            self.hide()
            return
        self.adjustSize()
        self.move(QCursor.pos() + QPoint(16, 16))
        if self.window_.isVisible():
            self.show()
        self._timer.start()

    def _busy(self) -> bool:
        """True while editing or picking a sketch plane: no bar then."""
        w = self.window_
        picking = w.sketch_mode is not None and w.sketch_mode.picker.active
        return bool(w.editing) or picking

    # Actions -------------------------------------------------------------------------

    def _run(self, action: Callable[[], object]) -> None:
        self.hide()
        action()

    def _feature(self, ftype: str = "extrude") -> None:
        self._run(lambda: self.window_.insert_feature(ftype, "boss"))

    def _fade(self) -> None:
        if not self.isVisible():
            self._timer.stop()
            return
        cursor = QCursor.pos()
        rect = self.frameGeometry().adjusted(-FADE_PX, -FADE_PX, FADE_PX, FADE_PX)
        if not rect.contains(cursor):
            self.hide()

    def paintEvent(self, _event: Any) -> None:  # noqa: N802
        """A rounded plate in the theme colours (the window itself is see through)."""
        from fdcad.ui.themes.style import unit
        from fdcad.ui.themes.theme import chrome

        c = chrome()
        radius = round(unit(self.font()) * 1.5)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(c.border_strong), 1))
        painter.setBrush(QColor(c.raised))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
        painter.end()

    def hideEvent(self, event: Any) -> None:  # noqa: N802
        """Stop watching the cursor."""
        self._timer.stop()
        super().hideEvent(event)
