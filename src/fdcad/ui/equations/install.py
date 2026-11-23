"""Puts the equations manager, configurations and design tables into the main window.

The window calls ``install`` once while it builds its menus, so the window code
only needs one hook. The commands live in ``ui/input/commands.py`` so users can
rebind them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QMenu, QTreeWidgetItem

from fdcad.ui.equations.tree_rows import EQUATIONS_ROLE

if TYPE_CHECKING:
    from fdcad.ui.equations.dialog import EquationsDialog
    from fdcad.ui.main_window.window import MainWindow


class EquationsTool:
    """Opens the equations manager for the current part and routes dimension picks to it."""

    def __init__(self, window: MainWindow) -> None:
        self.window = window
        self.dialog: EquationsDialog | None = None

    def open(self) -> EquationsDialog | None:
        """Show the equations manager (non modal, so dimensions can be picked in the view)."""
        from fdcad.ui.equations.dialog import EquationsDialog

        tab = self.window.current
        if tab is None:
            return None
        if self.dialog is not None:
            self.dialog.close()  # _closed frees it
        dialog = EquationsDialog(tab.session, self.window)
        dialog.finished.connect(lambda _r: self._closed(dialog))
        self.dialog = dialog
        if self.window.isVisible():
            dialog.show()
        return dialog

    def _closed(self, dialog: EquationsDialog) -> None:
        if self.dialog is dialog:
            self.dialog = None
        dialog.deleteLater()  # closed managers stayed alive (D637)

    def pick(self, item: Any) -> bool:
        """A dimension double clicked in the view: its name goes into the open manager."""
        dialog = self.dialog
        if dialog is None or (not dialog.isVisible() and self.window.isVisible()):
            return False
        tab = self.window.current
        if tab is None or dialog.session is not tab.session:
            return False
        target = item.param or item.dim
        try:
            owner = tab.session.document.feature(item.feature).name
        except KeyError:
            return False
        return dialog.insert_name(f"{target}@{owner}")


def install(window: MainWindow, tools: QMenu) -> None:
    """Add the commands, menu items and the Configurations tab, and the tree folder's
    double click."""
    from fdcad.ui import strings_config as text
    from fdcad.ui.equations.config_panel import ConfigurationsPanel

    tool = EquationsTool(window)
    window.equations_tool = tool  # type: ignore[attr-defined]
    panel = ConfigurationsPanel()
    window.configurations = panel  # type: ignore[attr-defined]
    panel.table_opener = lambda: open_design_table(window)
    if window.left is not None:
        window.left.addTab(panel, text.TAB_CONFIGURATIONS)
    window.tabs.currentChanged.connect(
        lambda _i: panel.set_session(window.current.session if window.current else None)
    )
    tools.addSeparator()
    tools.addAction(window.commands.add("tools.equations", tool.open))
    tools.addAction(window.commands.add("tools.configurations", lambda: show_panel(window)))
    tools.addAction(window.commands.add("tools.design_table", lambda: open_design_table(window)))
    from fdcad.ui.main_window.expected_values import open_checks

    tools.addAction(window.commands.add("tools.expected_values", lambda: open_checks(window)))
    from fdcad.ui.main_window.bodies_by_size import open_dialog

    tools.addAction(window.commands.add("tools.bodies_by_size", lambda: open_dialog(window)))
    from fdcad.ui.main_window.slices import open_slices

    tools.addAction(window.commands.add("tools.slice", lambda: open_slices(window)))  # TR151
    from fdcad.ui.main_window.hole_table import open_table

    tools.addAction(window.commands.add("tools.hole_table", lambda: open_table(window)))  # TR316
    from fdcad.ui.main_window.named_items import open_list

    tools.addAction(window.commands.add("tools.named_items", lambda: open_list(window)))  # TR152
    tools.addAction(  # TR72 (D2115)
        window.commands.add(
            "tools.insert_library", lambda: window.feature_clipboard.insert_library()
        )
    )
    from fdcad.ui.main_window import bodies_to_files

    tools.addAction(  # TR280 (D2421)
        window.commands.add("tools.bodies_to_files", lambda: bodies_to_files.run(window))
    )
    if window.tree is not None:
        window.tree.library_requested.connect(window.feature_clipboard.save_library)
    from fdcad.ui.main_window.part_notes import open_notes

    tools.addAction(window.commands.add("tools.part_notes", lambda: open_notes(window)))  # TR392
    from fdcad.ui.main_window.goal_seek import open_dialog as open_goal_seek

    tools.addAction(window.commands.add("tools.goal_seek", lambda: open_goal_seek(window)))
    tree = window.tree
    if tree is not None:
        tree.itemDoubleClicked.connect(lambda item, _c: _tree_double_clicked(tool, item))


def show_panel(window: MainWindow) -> None:
    """Bring the Configurations tab to the front."""
    panel = getattr(window, "configurations", None)
    if panel is not None and window.left is not None:
        window.left.setCurrentWidget(panel)


def open_design_table(window: MainWindow) -> Any:
    """Open the design table editor for the current part."""
    from fdcad.ui.equations.table_dialog import DesignTableDialog

    tab = window.current
    if tab is None:
        return None
    old = getattr(window, "design_table_dialog", None)
    if old is not None:
        old.close()
        old.deleteLater()  # one table at a time; old ones stayed (D637)
    dialog = DesignTableDialog(tab.session, window)
    window.design_table_dialog = dialog  # type: ignore[attr-defined]
    if window.isVisible():
        dialog.show()
    return dialog


def _tree_double_clicked(tool: EquationsTool, item: QTreeWidgetItem) -> None:
    if item.data(0, EQUATIONS_ROLE) is not None:
        tool.open()
