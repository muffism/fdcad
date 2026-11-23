"""Selection filter bar (TOOL_SPEC T14.3.2).

A toolbar with one toggle per item type (vertices, edges, faces, solid bodies,
planes, axes, sketches, sketch segments, sketch points, dimensions), Clear All,
Select All and a switch that turns the chosen filters on or off at once (F6).
F5 shows or hides the bar. E, X and V switch the edge, face and vertex filters.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QToolBar, QWidget

from fdcad.ui import strings_extra as text
from fdcad.ui.input.selection_rules import FILTER_KINDS, TREE_KINDS, SelectionFilter

#: Icon of each filter button: the key commands' icons, else a filter icon.
ICONS = {
    "vertex": "select.filter_vertices",
    "edge": "select.filter_edges",
    "face": "select.filter_faces",
}


class FilterBar(QToolBar):
    """Buttons bound to one :class:`SelectionFilter`. ``changed`` follows every change."""

    changed = Signal()

    def __init__(self, model: SelectionFilter, parent: QWidget | None = None) -> None:
        super().__init__(text.FILTER_BAR, parent)
        from fdcad.ui.icons import icon

        self.setObjectName("selection_filter_bar")
        self.model = model
        self.buttons: dict[str, QAction] = {}
        self.enabled_action = self._action(
            "select.filters_toggle", text.FILTERS_ON, self._toggle_enabled, checkable=True
        )
        self.addSeparator()
        for kind in FILTER_KINDS:
            action = QAction(icon(ICONS.get(kind, f"filter.{kind}")), text.FILTER_NAMES[kind], self)
            action.setCheckable(True)
            action.setData(kind)
            action.triggered.connect(lambda _on=False, k=kind: self.toggle(k))
            if kind in TREE_KINDS:
                # The 3D view does not pick these; filtering them would pick nothing.
                action.setEnabled(False)
                action.setToolTip(text.FILTER_IN_TREE.format(name=text.FILTER_NAMES[kind]))
            self.addAction(action)
            self.buttons[kind] = action
        self.addSeparator()
        self.clear_action = self._action("", text.FILTER_CLEAR, self.clear)
        self.all_action = self._action("", text.FILTER_ALL, self.select_all)
        self.hide()
        self.sync()

    def _action(
        self, icon_name: str, label: str, slot: Callable[[], object], checkable: bool = False
    ) -> QAction:
        from fdcad.ui.icons import icon

        action = QAction(icon(icon_name), label, self) if icon_name else QAction(label, self)
        action.setCheckable(checkable)
        action.triggered.connect(lambda _on=False: slot())
        self.addAction(action)
        return action

    def toggle(self, kind: str) -> bool:
        """Switch one type's filter. Returns its new state."""
        on = self.model.toggle(kind)
        self.sync()
        self.changed.emit()
        return on

    def _toggle_enabled(self) -> None:
        self.model.toggle_enabled()
        self.sync()
        self.changed.emit()

    def toggle_enabled(self) -> bool:
        """F6: turn the chosen filters on or off at once. Returns the new state."""
        self._toggle_enabled()
        return self.model.enabled

    def clear(self) -> None:
        """Clear All."""
        self.model.clear()
        self.sync()
        self.changed.emit()

    def select_all(self) -> None:
        """Select All."""
        self.model.select_all()
        self.sync()
        self.changed.emit()

    def sync(self) -> None:
        """Show the model's state on the buttons."""
        for kind, action in self.buttons.items():
            action.setChecked(kind in self.model.active)
            action.setEnabled(self.model.enabled and kind not in TREE_KINDS)
        self.enabled_action.setChecked(self.model.enabled)
        tip = text.FILTERS_ON if self.model.enabled else text.FILTERS_OFF
        self.enabled_action.setToolTip(tip)

    def toggle_shown(self) -> bool:
        """F5: show or hide the bar. Returns True when it is shown now."""
        self.setVisible(not self.isVisible())
        return self.isVisible()
