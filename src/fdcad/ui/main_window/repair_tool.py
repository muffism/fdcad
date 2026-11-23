"""Repair Lost References (TR125, DECISIONS D795).

Check lists every lost face, edge, vertex or feature pick of the part (or of one
feature, from the tree), with the replacement ``core.naming.repair`` offers when
there is one clear match. Each row has a tick. Use Offered puts the offered
replacement in for the ticked rows, Remove takes the ticked picks out, both as
one undo step; nothing changes until the user clicks (CLAUDE.md 5.12). Clicking
a row selects the feature and draws where the lost item was beside its offer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QWidget,
)

from fdcad.ui import strings
from fdcad.ui.print_tools import jobs

if TYPE_CHECKING:
    from fdcad.core.naming.repair import LostRef
    from fdcad.ui.main_window.window import DocumentTab, MainWindow


#: One found item: the lost reference, where it was drawn, and its offered match.
Row = tuple["LostRef", Any, Any]


def _work(doc: Any, results: dict[str, Any], only: list[str] | None) -> list[Row]:
    """Find the lost picks and the shapes to draw, on a worker thread."""
    from fdcad.core.features.preview import body_before
    from fdcad.core.naming.repair import find_lost, ghost
    from fdcad.core.naming.select import shapes_for_names

    out: list[Row] = []
    for lost in find_lost(doc, results, only):
        match = None
        if lost.suggestion is not None:
            body = body_before(doc, doc.feature(lost.fid), results)
            if body is not None:
                found = shapes_for_names(body, [str(lost.suggestion.get("name", ""))])
                match = found[0] if found else None
        out.append((lost, ghost(lost.ref), match))
    return out


class RepairTool(QObject):
    """The window and its job."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window = window
        self.on = False
        self.generation = 0
        self.only: list[str] | None = None
        self.rows: list[Row] | None = None
        self.panel = QWidget(window, Qt.WindowType.Tool)
        self.panel.setObjectName("repair_panel")
        self.panel.setWindowTitle(strings.REPAIR_TITLE)
        form = QFormLayout(self.panel)
        self.check_button = QPushButton(strings.REPAIR_CHECK)
        self.use_button = QPushButton(strings.REPAIR_USE)
        self.use_button.setToolTip(strings.REPAIR_USE_TIP)
        self.remove_button = QPushButton(strings.REPAIR_REMOVE)
        self.remove_button.setToolTip(strings.REPAIR_REMOVE_TIP)
        self.all_button = QPushButton(strings.REPAIR_TICK_ALL)
        row = QHBoxLayout()
        for button in (self.check_button, self.all_button, self.use_button, self.remove_button):
            row.addWidget(button)
        self.found = QListWidget()
        self.found.setObjectName("repair_found")
        self.found.setWordWrap(True)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        form.addRow(row)
        form.addRow(self.found)
        form.addRow(self.summary)
        self.check_button.clicked.connect(self.check)
        self.use_button.clicked.connect(self.use_offered)
        self.remove_button.clicked.connect(self.remove)
        self.all_button.clicked.connect(self.tick_all)
        self.found.currentRowChanged.connect(self.select_row)
        self._buttons()

    # Showing ------------------------------------------------------------------------

    def set_on(self, on: bool, only: list[str] | None = None) -> None:
        """Show or hide the window; showing it checks at once. ``only`` limits the
        check to those features (Repair from the tree)."""
        self.on = on
        self.only = only
        self.panel.setVisible(on)
        if on:
            self.check()
        else:
            self.generation += 1
            self._highlight([])

    def open_for(self, fid: str) -> None:
        """Repair one feature (tree menu)."""
        action = self.window.commands.actions.get("evaluate.repair_references")
        if action is not None:
            action.setChecked(True)
        self.set_on(True, [fid])

    def check(self) -> bool:
        """Look for lost picks in the background. False when no part is open."""
        tab = self.window.current
        built = tab.session.report if tab is not None else None
        if tab is None or built is None:
            self.summary.setText(strings.MASS_NO_BODY)
            return False
        doc, results, only = tab.session.document, dict(built.results), self.only
        self.generation += 1
        generation = self.generation
        self.summary.setText(strings.REPAIR_RUNNING)
        jobs.start(
            lambda: _work(doc, results, only),
            lambda rows: self._done(tab, generation, rows),
            lambda message: self._failed(generation, message),
        )
        return True

    def _failed(self, generation: int, message: str) -> None:
        if generation == self.generation:
            self.summary.setText(strings.REPAIR_FAILED.format(reason=message))

    def _done(self, tab: DocumentTab, generation: int, rows: list[Row]) -> None:
        from fdcad.core.naming.repair import describe, total_distance

        if generation != self.generation or not self.on:
            return
        self.rows = rows
        self.found.clear()
        doc = tab.session.document
        for lost, _ghost, _match in rows:
            text = describe(lost, doc)
            if lost.suggestion is not None:
                away = total_distance(lost.ref, lost.suggestion)
                text += " " + strings.REPAIR_OFFER.format(
                    kind=lost.kind, distance=f"{away:.3g}" if away == away else "?"
                )
            else:
                text += " " + strings.REPAIR_NO_OFFER
            item = QListWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.found.addItem(item)
        offers = sum(1 for lost, _g, _m in rows if lost.suggestion is not None)
        self.summary.setText(
            strings.REPAIR_DONE.format(count=len(rows), offers=offers)
            if rows
            else strings.REPAIR_NONE
        )
        self._buttons()

    def _buttons(self) -> None:
        has = bool(self.rows)
        for button in (self.use_button, self.remove_button, self.all_button):
            button.setEnabled(has)

    def tick_all(self) -> None:
        """Tick every row (Repair All: the user still clicks Use Offered)."""
        for i in range(self.found.count()):
            self.found.item(i).setCheckState(Qt.CheckState.Checked)

    def select_row(self, row: int) -> None:
        """Select the feature and draw the lost item beside its offered match."""
        if self.rows is None or not 0 <= row < len(self.rows):
            self._highlight([])
            return
        lost, ghost, match = self.rows[row]
        if self.window.tree is not None:
            self.window.tree.select(lost.fid)
        self._highlight([s for s in (ghost, match) if s is not None])

    def _highlight(self, shapes: list[Any]) -> None:
        tab = self.window.current
        highlight = getattr(tab.viewport, "highlight", None) if tab is not None else None
        if highlight is not None:
            highlight(shapes)

    # Changing -----------------------------------------------------------------------

    def ticked(self) -> list[LostRef]:
        """The lost picks whose rows are ticked."""
        if self.rows is None:
            return []
        return [
            self.rows[i][0]
            for i in range(self.found.count())
            if self.found.item(i).checkState() == Qt.CheckState.Checked
        ]

    def use_offered(self) -> bool:
        """Put the offered replacement in for every ticked row that has one."""
        chosen = [lost for lost in self.ticked() if lost.suggestion is not None]
        return self._apply([(lost, lost.suggestion) for lost in chosen], strings.REPAIR_UNDO)

    def remove(self) -> bool:
        """Take every ticked pick out of its feature (Clear All Missing, when all ticked)."""
        return self._apply([(lost, None) for lost in self.ticked()], strings.REPAIR_UNDO_REMOVE)

    def _apply(self, changes: list[tuple[LostRef, dict[str, Any] | None]], text: str) -> bool:
        from fdcad.core.naming.repair import replaced
        from fdcad.ui.commands.document import ReplaceFeature

        tab = self.window.current
        if tab is None or not changes:
            self.summary.setText(strings.REPAIR_NOTHING_TICKED)
            return False
        doc = tab.session.document
        by_feature: dict[str, list[tuple[Any, dict[str, Any] | None]]] = {}
        for lost, new in changes:
            by_feature.setdefault(lost.fid, []).append((lost.path, new))
        session = tab.session
        session.undo.beginMacro(text)
        for fid, steps in by_feature.items():
            try:
                feature = doc.feature(fid)
            except KeyError:
                continue
            session.undo.push(ReplaceFeature(session, replaced(feature, steps), text))
        session.undo.endMacro()
        self.window.status.setText(strings.REPAIR_APPLIED.format(count=len(changes)))
        self.found.clear()
        self.rows = None
        self._buttons()
        self._highlight([])
        return True


def install(window: MainWindow) -> RepairTool:
    """Create the controller, its checkable command and the tree's Repair item."""
    tool = RepairTool(window)
    action = window.commands.add(
        "evaluate.repair_references", lambda: tool.set_on(action.isChecked()), checkable=True
    )
    tree = getattr(window, "tree", None)
    if tree is not None:
        tree.repair_requested.connect(tool.open_for)
    return tool
