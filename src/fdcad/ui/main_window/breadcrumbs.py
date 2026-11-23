"""Selection breadcrumbs at the top left of the view (TR20, DECISIONS D756).

When a face, edge or vertex is picked, a short row in the strip above the view
shows its chain: the part, its body, the feature that made it and that
feature's sketch (``core.breadcrumbs``). Clicking a crumb selects that item in
the feature tree; right clicking shows the tree's menu for it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QToolButton, QWidget

from fdcad.core.breadcrumbs import Crumb, crumbs

if TYPE_CHECKING:
    from PySide6.QtWidgets import QTreeWidgetItem

    from fdcad.ui.main_window.window import DocumentTab, MainWindow
    from fdcad.ui.tree.feature_tree import FeatureTree

SEPARATOR = chr(0x203A)  # a small right pointing angle


class Breadcrumbs(QWidget):
    """The row of crumbs. Hidden while nothing is picked."""

    clicked = Signal(object)  # Crumb
    menu_requested = Signal(object, QPoint)  # Crumb, global position

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("breadcrumbs")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(4, 0, 4, 0)
        self._layout.setSpacing(2)
        self._layout.addStretch(1)
        self.chain: list[Crumb] = []
        self.buttons: list[QToolButton] = []
        self.hide()

    def set_chain(self, chain: list[Crumb]) -> None:
        """Show ``chain``, or hide the row when it is empty."""
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        self.chain, self.buttons = list(chain), []
        for i, crumb in enumerate(chain):
            if i:
                self._layout.insertWidget(self._layout.count() - 1, QLabel(SEPARATOR))
            button = QToolButton()
            button.setObjectName(f"crumb_{crumb.kind}")
            button.setText(crumb.label)
            button.setAutoRaise(True)
            button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            button.clicked.connect(lambda _c=False, c=crumb: self.clicked.emit(c))
            button.customContextMenuRequested.connect(
                lambda pos, c=crumb, b=button: self.menu_requested.emit(c, b.mapToGlobal(pos))
            )
            self._layout.insertWidget(self._layout.count() - 1, button)
            self.buttons.append(button)
        self.setVisible(bool(chain))


def chain_for(tab: DocumentTab, shapes: list[Any]) -> list[Crumb]:
    """The chain of the last picked item, or [] with nothing picked or nothing named."""
    report = tab.session.report
    if not shapes or report is None or report.body is None:
        return []
    try:
        session = tab.session
        name = session.path.stem if session.path else session.display_name
        return crumbs(session.document, name, report.body, shapes[-1])
    except Exception:  # display only: a pick the naming does not know shows no crumbs
        return []


def tree_item(tree: FeatureTree, crumb: Crumb) -> QTreeWidgetItem | None:
    """The tree row a crumb stands for."""
    from fdcad.ui.tree.feature_tree import BODY_ROLE, FID_ROLE, PART_MARK

    for item in tree.all_items():
        if crumb.kind == "part" and item.data(0, FID_ROLE) == PART_MARK:
            return item
        if crumb.kind == "body" and item.data(0, BODY_ROLE) == crumb.target:
            return item
        if crumb.kind in ("feature", "sketch") and item.data(0, FID_ROLE) == crumb.target:
            return item
    return None


def show_menu(menu: QMenu, at: QPoint) -> None:
    """Show a crumb's menu (a seam for tests, which cannot click a real menu)."""
    menu.exec(at)


def install(window: MainWindow, tab: DocumentTab, holder: QWidget) -> Breadcrumbs:
    """Put the crumbs in ``holder`` (the left end of the view strip) and wire them."""
    bar = Breadcrumbs(holder)
    layout = QHBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(bar)

    def pick(crumb: Crumb) -> None:
        tree = window.tree
        item = tree_item(tree, crumb) if tree is not None else None
        if tree is not None and item is not None:
            tree.setCurrentItem(item)
            tree.scrollToItem(item)

    def menu(crumb: Crumb, at: QPoint) -> None:
        tree = window.tree
        item = tree_item(tree, crumb) if tree is not None else None
        if tree is None or item is None:
            return
        built = tree._context_menu(tab.session, item)
        if built is not None:
            show_menu(built, at)

    bar.clicked.connect(pick)
    bar.menu_requested.connect(menu)
    return bar
