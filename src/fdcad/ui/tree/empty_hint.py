"""The feature tree's empty state: what to do first in a new part (U8.3, D673).

While a part has only its built in planes and origin, a short muted line under
the rows says to start a sketch on a plane. It sits in the tree's viewport,
lets clicks through and hides as soon as the part has a feature.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QLabel, QTreeWidget

from fdcad.ui import strings_feedback as text
from fdcad.ui.themes import theme

GAP = 12


class EmptyTreeHint(QLabel):
    """A hint under the tree rows of a part that has no features yet."""

    def __init__(self, tree: QTreeWidget) -> None:
        super().__init__(text.EMPTY_TREE, tree.viewport())
        self.setObjectName("empty_tree_hint")
        self.tree = tree
        self.setWordWrap(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.restyle()
        model = tree.model()
        for signal in (model.rowsInserted, model.rowsRemoved, model.modelReset):
            signal.connect(self._later)
        tree.viewport().installEventFilter(self)
        self._later()

    def restyle(self) -> None:
        """The muted caption colour of the theme."""
        self.setStyleSheet(f"QLabel#empty_tree_hint {{ color: {theme.chrome().muted}; }}")

    def _later(self, *_args: object) -> None:
        QTimer.singleShot(0, self.update_hint)

    def is_empty(self) -> bool:
        """True when the tree shows a part with no features of its own."""
        from fdcad.ui.tree.feature_tree import _BUILT_IN

        session = getattr(self.tree, "session", None)
        if session is None:
            return False
        return all(f.id in _BUILT_IN for f in session.document.features)

    def update_hint(self) -> None:
        """Show the hint under the last row when the part is empty."""
        empty = self.is_empty()
        self.setVisible(empty)
        if not empty:
            return
        port = self.tree.viewport()
        last = self.tree.topLevelItem(self.tree.topLevelItemCount() - 1)
        bottom = self.tree.visualItemRect(last).bottom() if last is not None else 0
        width = max(port.width() - 2 * GAP, 80)
        self.setFixedWidth(width)
        self.adjustSize()
        self.move(GAP, bottom + GAP)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Follow the tree's width."""
        if event.type() == QEvent.Type.Resize:
            self._later()
        return False
