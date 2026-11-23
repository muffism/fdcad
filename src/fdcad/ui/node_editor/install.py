"""Puts the node editor in the main window: a dock beside the viewport, its
commands and the Graph command tab (PLAN section 8 items 1 and 18).

The editor and the node library load the first time the editor opens, so they
cost nothing at startup (PLAN 11.3 item 8).
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QTreeWidgetItem

from fdcad.ui.node_editor import strings

if TYPE_CHECKING:
    from PySide6.QtGui import QAction

    from fdcad.ui.command_tabs.ribbon import RibbonPanel
    from fdcad.ui.main_window.window import MainWindow
    from fdcad.ui.node_editor.panel import NodeEditorPanel

TAB_NAME = "graph"
#: The editor's width when it first opens: a share of the window, in percent, and
#: never less than this many pixels.
EDITOR_SHARE = 42
EDITOR_MIN_WIDTH = 520
#: Item data role holding a graph row's graph id (see ``tree_rows``).
GRAPH_ROLE = Qt.ItemDataRole.UserRole + 40
#: The Graph command tab: title, large tools, compact columns.
GRAPH_GROUPS: list[Any] = [
    (strings.GROUP_GRAPH, ["graph.editor"], [["graph.set_position"]]),
    (strings.GROUP_EDIT, ["graph.add_node"], [["graph.comment"], ["graph.group", "graph.ungroup"]]),
    (strings.GROUP_VIEW, [], [["graph.fit"]]),
]
#: Commands whose keys only work inside the editor, and the panel method each runs.
EDITOR_KEYS = {
    "graph.add_node": "open_search",
    "graph.delete": "delete_selected",
    "graph.copy": "copy_selected",
    "graph.paste": "paste",
    "graph.group": "group_selected",
    "graph.ungroup": "ungroup_selected",
}
#: Editor keys that also edit text, so they leave a focused text field alone (D741).
TEXT_KEYS = ("delete_selected", "copy_selected", "paste")


def typing_in_field() -> bool:
    """True when the keyboard focus is in a text field, spin box or text box."""
    from PySide6.QtWidgets import (
        QAbstractSpinBox,
        QApplication,
        QLineEdit,
        QPlainTextEdit,
        QTextEdit,
    )

    focus = QApplication.focusWidget()
    return isinstance(focus, (QLineEdit, QAbstractSpinBox, QTextEdit, QPlainTextEdit))


#: Toolbar commands, in order.
TOOLBAR = (
    "graph.add_node",
    "graph.comment",
    "graph.group",
    "graph.ungroup",
    "graph.set_position",
    "graph.fit",
)


def install(window: MainWindow, menu: Any = None) -> QDockWidget:
    """Create the (empty) dock and the commands. Returns the dock."""
    from fdcad.ui.node_editor.title_bar import DockTitleBar

    dock = QDockWidget(strings.PANEL_TITLE, window)
    dock.setObjectName("node_editor_dock")
    # FDCAD's own title bar (D2745): Qt's float and close buttons are 10 px wide.
    dock.setTitleBarWidget(DockTitleBar(dock))
    window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
    dock.hide()
    window.node_editor_dock = dock  # type: ignore[attr-defined]
    a = window.commands
    toggle = a.add("graph.editor", lambda: show(window, toggle.isChecked()), checkable=True)
    dock.visibilityChanged.connect(toggle.setChecked)

    def run(method: str) -> None:
        if method in TEXT_KEYS and typing_in_field():
            return  # Backspace in a settings field must not delete nodes (audit C item 15)
        getattr(panel_of(window), method)()

    def comment() -> None:
        show(window, True)
        panel_of(window).add_comment()

    def set_position() -> None:
        show(window, True)
        panel_of(window).set_position()

    for cid, method in EDITOR_KEYS.items():
        a.add(cid, partial(run, method), scope=dock)
    a.add("graph.comment", comment)
    a.add("graph.fit", lambda: panel_of(window).fit())
    a.add("graph.set_position", set_position)
    if menu is not None:
        menu.addAction(toggle)
    window.tabs.currentChanged.connect(lambda _i: _follow(window))
    tree = getattr(window, "tree", None)
    if tree is not None:
        tree.itemDoubleClicked.connect(lambda item, _c: _tree_row(window, item))
    return dock


def panel_of(window: MainWindow) -> NodeEditorPanel:
    """The editor panel, made the first time it is needed."""
    panel = getattr(window, "_node_editor_panel", None)
    if panel is not None:
        return panel  # type: ignore[no-any-return]
    from fdcad.ui.node_editor.panel import NodeEditorPanel

    panel = NodeEditorPanel(window)
    a = window.commands
    for cid in TOOLBAR:
        panel.toolbar.addAction(a.actions[cid])
    delete = a.actions.get("edit.delete")
    if delete is not None:
        panel.view.delete_keys = delete.shortcuts
    panel.view.on_delete = panel.delete_selected
    window.node_editor_dock.setWidget(panel)  # type: ignore[attr-defined]
    window._node_editor_panel = panel  # type: ignore[attr-defined]
    _follow(window)
    return panel


def show(window: MainWindow, on: bool = True) -> None:
    """Show or hide the node editor."""
    dock = window.node_editor_dock  # type: ignore[attr-defined]
    if on:
        panel = panel_of(window)
        first = not dock.property("sized")
        dock.setVisible(True)
        if first:
            # The first time, share the width with the 3D view: the editor took so
            # much that the part was a strip beside it (D1034).
            dock.setProperty("sized", True)
            width = max(EDITOR_MIN_WIDTH, window.width() * EDITOR_SHARE // 100)
            window.resizeDocks([dock], [width], Qt.Orientation.Horizontal)
        _follow(window)
        dock.raise_()
        panel.view.setFocus()
    else:
        dock.setVisible(False)


def _follow(window: MainWindow) -> None:
    panel = getattr(window, "_node_editor_panel", None)
    if panel is None:
        return
    tab = window.current
    panel.bind(tab.session if tab is not None else None)


def _tree_row(window: MainWindow, item: QTreeWidgetItem) -> None:
    if item.data(0, GRAPH_ROLE):
        show(window, True)


def shutdown(window: MainWindow) -> None:
    """Stop the editor's worker thread, if the editor was opened."""
    panel = getattr(window, "_node_editor_panel", None)
    if panel is not None:
        panel.shutdown()


def build_graph_panel(actions: dict[str, QAction]) -> RibbonPanel:
    """The Graph command tab."""
    from fdcad.ui.command_tabs.tabs import build_panel

    return build_panel(TAB_NAME, GRAPH_GROUPS, actions)
