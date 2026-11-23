"""The tree follows the view and the view follows the tree (TR200, DECISIONS D808).

- Picking a face, edge or vertex in the view opens the tree to the feature that
  made it and scrolls it into sight (preference, on by default). Clearing the
  pick scrolls the tree back to where it was.
- Go To Feature on a face or edge's right click menu selects that feature.
- Hovering a feature row draws that feature's faces in the view (preference, on
  by default).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QEvent, QObject, QTimer

if TYPE_CHECKING:
    from PySide6.QtWidgets import QTreeWidgetItem

    from fdcad.ui.main_window.window import DocumentTab, MainWindow


class TreeFollow(QObject):
    """Keeps the tree and the view pointing at the same feature."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window = window
        self.saved_scroll: int | None = None
        self.hovered: str | None = None
        tree = window.tree
        assert tree is not None
        tree.setMouseTracking(True)
        tree.itemEntered.connect(self._entered)
        tree.viewport().installEventFilter(self)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self._show_hovered)

    # The view picks -> the tree -------------------------------------------------------

    def picked(self, tab: DocumentTab, shapes: list[Any]) -> str | None:
        """Scroll the tree to the feature of the last pick; returns its id, or None."""
        tree = self.window.tree
        if tree is None or not self.window.settings.tree_follows_selection:
            return None
        bar = tree.verticalScrollBar()
        if not shapes:
            if self.saved_scroll is not None:
                bar.setValue(self.saved_scroll)
                self.saved_scroll = None
            return None
        fid = self.window.context_menus.feature_of(tab, shapes[-1])
        item = tree.item_for(fid) if fid is not None else None
        if item is None:
            return None
        if self.saved_scroll is None:
            self.saved_scroll = bar.value()
        parent = item.parent()
        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()
        tree.scrollToItem(item)
        return fid

    def go_to(self, tab: DocumentTab, shape: Any) -> bool:
        """Go To Feature: select the feature that made ``shape`` in the tree."""
        tree = self.window.tree
        fid = self.window.context_menus.feature_of(tab, shape)
        if tree is None or fid is None:
            return False
        self.window._left_tab(0)
        tree.select(fid)
        item = tree.item_for(fid)
        if item is not None:
            tree.scrollToItem(item)
        return True

    # Hovering the tree -> the view ----------------------------------------------------

    def _entered(self, item: QTreeWidgetItem, _column: int) -> None:
        from fdcad.ui.tree.feature_tree import FID_ROLE

        if not self.window.settings.tree_hover_highlight:
            return
        fid = item.data(0, FID_ROLE)
        self.hovered = fid if isinstance(fid, str) else None
        self._timer.start()

    def _show_hovered(self) -> None:
        self.window.highlight_names(self.names_of(self.hovered) if self.hovered else [])

    def names_of(self, fid: str) -> list[str]:
        """The names of the faces of the part that ``fid`` made."""
        tab = self.window.current
        report = tab.session.report if tab is not None else None
        if report is None or report.body is None:
            return []
        prefix = f"{fid}/"
        return [name for name, _face in report.body.faces if name.startswith(prefix)]

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 (Qt)
        """Leaving the tree clears the hover highlight."""
        if event.type() == QEvent.Type.Leave and self.hovered is not None:
            self.hovered = None
            self._timer.start()
        return False
