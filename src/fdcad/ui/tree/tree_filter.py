"""The filter box above the feature tree (TR95, DECISIONS D806).

Typing shows only the rows whose text holds what was typed (any case), with
the folders and parents above them, so a match is never shown on its own.
The state choice shows only features with an error or warning, suppressed
features, or features with a comment. Clearing both shows the whole tree. The
filter is applied again after each rebuild of the rows.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QLineEdit,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fdcad.ui import strings, strings_feedback
from fdcad.ui.empty_state import empty_label
from fdcad.ui.tree.feature_tree import COMMENT_ROLE, FID_ROLE, FeatureTree

STATES = ("all", "problems", "suppressed", "comments")


class TreeFilter(QWidget):
    """The box and the state choice, with the tree under them."""

    def __init__(self, tree: FeatureTree, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tree = tree
        self.text = QLineEdit()
        self.text.setObjectName("tree_filter")
        self.text.setPlaceholderText(strings.TREE_FILTER_HINT)
        self.text.setClearButtonEnabled(True)
        self.text.setToolTip(strings.TREE_FILTER_TIP)
        self.state = QComboBox()
        self.state.setObjectName("tree_filter_state")
        self.state.setToolTip(strings.TREE_FILTER_STATE_TIP)
        for key in STATES:
            self.state.addItem(strings.TREE_FILTER_STATES[key], key)
        # One above the other, so the tree panel can be narrow (IDEAS 19, D1033).
        from fdcad.ui.themes.style import unit

        u = unit(self.font())  # one 4 px step round and between the two (D2697)
        row = QVBoxLayout()
        row.setContentsMargins(u, u, u, 0)
        row.setSpacing(u)
        row.addWidget(self.text)
        row.addWidget(self.state)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(u)
        layout.addLayout(row)
        layout.addWidget(tree, 1)
        # With no part open the tree's place says so, in the dashed outline of the
        # start page beside it, and the two boxes are greyed: there is nothing to
        # filter (D2702). It was a filter box over a blank panel.
        self.empty = empty_label(strings_feedback.NO_PART_OPEN, boxed=True)
        hold = QVBoxLayout()
        hold.setContentsMargins(u, 0, u, u)
        hold.addWidget(self.empty)
        layout.addLayout(hold, 1)
        self.text.textChanged.connect(lambda _t: self.apply())
        self.state.currentIndexChanged.connect(lambda _i: self.apply())
        tree.refreshed.connect(self.apply)
        self.show_empty()

    def show_empty(self) -> None:
        """The empty state in the tree's place while no part is open."""
        none = self.tree.session is None
        self.empty.setVisible(none)
        self.tree.setVisible(not none)
        self.text.setEnabled(not none)
        self.state.setEnabled(not none)

    def apply(self) -> None:
        """Show the rows that match, with their parents; everything when nothing is set."""
        self.show_empty()
        typed = self.text.text().strip().lower()
        state = str(self.state.currentData() or "all")
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            if top is not None:
                self._show(top, typed, state)

    def _show(self, item: QTreeWidgetItem, typed: str, state: str) -> bool:
        child_hit = False
        for i in range(item.childCount()):
            child = item.child(i)
            if child is not None:
                child_hit = self._show(child, typed, state) or child_hit
        hit = self._matches(item, typed, state)
        visible = hit or child_hit
        item.setHidden(not visible)
        if child_hit and (typed or state != "all"):
            item.setExpanded(True)
        return visible

    def _matches(self, item: QTreeWidgetItem, typed: str, state: str) -> bool:
        if typed and typed not in item.text(0).lower():
            return False
        if state == "all":
            return True
        fid = item.data(0, FID_ROLE)
        session = self.tree.session
        if not isinstance(fid, str) or session is None:
            return False
        if state == "comments":
            return bool(item.data(0, COMMENT_ROLE))
        try:
            feature = session.document.feature(fid)
        except KeyError:
            return False
        if state == "suppressed":
            return feature.suppressed
        report = session.report
        result = report.results.get(fid) if report is not None else None
        return result is not None and bool(result.issues)
