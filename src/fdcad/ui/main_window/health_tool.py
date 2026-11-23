"""Model Health on the Evaluate tab (TR286, DECISIONS D775).

Check lists the advice from ``core.health`` for the part as last rebuilt.
Clicking a row selects its feature in the tree (Zoom to Item). For an early
fillet or chamfer, Move to End moves it to the end of the tree as one undo step;
nothing else changes the part.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QLabel, QListWidget, QPushButton, QWidget

from fdcad.ui import strings
from fdcad.ui.print_tools import jobs

if TYPE_CHECKING:
    from fdcad.core.health import HealthItem
    from fdcad.ui.main_window.window import DocumentTab, MainWindow


class HealthTool(QObject):
    """The window and its job."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window = window
        self.on = False
        self.generation = 0
        self.items: list[HealthItem] | None = None
        self.panel = QWidget(window, Qt.WindowType.Tool)
        self.panel.setObjectName("health_panel")
        self.panel.setWindowTitle(strings.HEALTH_TITLE)
        form = QFormLayout(self.panel)
        self.check_button = QPushButton(strings.HEALTH_CHECK)
        self.move_button = QPushButton(strings.HEALTH_MOVE)
        self.move_button.setToolTip(strings.HEALTH_MOVE_TIP)
        self.move_button.setEnabled(False)
        self.link_button = QPushButton(strings.HEALTH_LINK)  # TR351 (D905)
        self.link_button.setObjectName("health_link")
        self.link_button.setEnabled(False)
        self.link_button.clicked.connect(self.link_variable)
        row = QHBoxLayout()
        row.addWidget(self.check_button)
        row.addWidget(self.move_button)
        row.addWidget(self.link_button)
        self.found = QListWidget()
        self.found.setObjectName("health_found")
        self.found.setWordWrap(True)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        form.addRow(row)
        form.addRow(self.found)
        form.addRow(self.summary)
        self.check_button.clicked.connect(self.check)
        self.move_button.clicked.connect(self.move_to_end)
        self.found.currentRowChanged.connect(self.select_row)

    def set_on(self, on: bool) -> None:
        """Show or hide the window; showing it checks at once."""
        self.on = on
        self.panel.setVisible(on)
        if on:
            self.check()
        else:
            self.generation += 1

    def check(self) -> bool:
        """Work the advice out in the background. False when no part is open."""
        from fdcad.core.health import report

        tab = self.window.current
        built = tab.session.report if tab is not None else None
        if tab is None or built is None:
            self.summary.setText(strings.MASS_NO_BODY)
            return False
        doc, results = tab.session.document, dict(built.results)
        self.generation += 1
        generation = self.generation
        self.summary.setText(strings.HEALTH_RUNNING)
        jobs.start(
            lambda: report(doc, results),
            lambda items: self._done(tab, generation, items),
            lambda message: self._failed(generation, message),
        )
        return True

    def _failed(self, generation: int, message: str) -> None:
        if generation == self.generation:
            self.summary.setText(strings.HEALTH_FAILED.format(reason=message))

    def _done(self, tab: DocumentTab, generation: int, items: list[HealthItem]) -> None:
        if generation != self.generation or not self.on:
            return
        self.items = items
        self.found.clear()
        for item in items:
            self.found.addItem(item.message)
        self.summary.setText(
            strings.HEALTH_DONE.format(count=len(items)) if items else strings.HEALTH_NONE
        )
        self.move_button.setEnabled(False)
        self.link_button.setEnabled(False)

    def select_row(self, row: int) -> None:
        """Zoom to Item: select its feature; Move to End is offered for early rounds."""
        from fdcad.core.health import MOVE_TO_END

        if self.items is None or not 0 <= row < len(self.items):
            self.move_button.setEnabled(False)
            return
        item = self.items[row]
        if item.fid and self.window.tree is not None:
            self.window.tree.select(item.fid)
        self.move_button.setEnabled(item.fix == MOVE_TO_END)
        from fdcad.core.health import LINK_VARIABLE

        self.link_button.setEnabled(item.fix == LINK_VARIABLE)

    def link_variable(self) -> bool:
        """Type the variable's name in place of the matching number, as one undo step."""
        from fdcad.core.health import linked
        from fdcad.ui.commands.document import ReplaceFeature

        tab = self.window.current
        row = self.found.currentRow()
        if tab is None or self.items is None or not 0 <= row < len(self.items):
            return False
        item = self.items[row]
        fixed = linked(tab.session.document, item)
        if fixed is None:
            return False
        tab.session.undo.push(ReplaceFeature(tab.session, fixed))
        self.window.status.setText(
            strings.HEALTH_LINKED.format(name=fixed.name, variable=item.extra.get("variable"))
        )
        self.found.takeItem(row)
        self.items.pop(row)
        self.link_button.setEnabled(False)
        return True

    def move_to_end(self) -> bool:
        """Move the selected early fillet or chamfer to the end, as one undo step."""
        from fdcad.core.health import MOVE_TO_END
        from fdcad.ui.commands.document import MoveFeature

        tab = self.window.current
        row = self.found.currentRow()
        if tab is None or self.items is None or not 0 <= row < len(self.items):
            return False
        item = self.items[row]
        if item.fix != MOVE_TO_END or item.fid is None:
            return False
        doc = tab.session.document
        tab.session.undo.push(MoveFeature(tab.session, item.fid, len(doc.features) - 1))
        self.window.status.setText(strings.HEALTH_MOVED.format(name=doc.feature(item.fid).name))
        self.found.clear()
        self.items = None
        self.move_button.setEnabled(False)
        return True


def install(window: MainWindow) -> HealthTool:
    """Create the controller and its checkable command."""
    tool = HealthTool(window)
    action = window.commands.add(
        "evaluate.model_health", lambda: tool.set_on(action.isChecked()), checkable=True
    )
    return tool
