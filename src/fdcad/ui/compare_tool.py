"""Before and After: the volume change per feature after a change (TR289, D2019).

The window lists the features whose part volume changed in the last rebuild,
with the volume before, after and the change. Clicking a row draws that
feature's part from before the change faintly over the part as it is now.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from fdcad.ui import strings_extra as text
from fdcad.ui.themes.theme import DATA

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow

LAYER = "before_after"
#: Colour of the faint shape from before the change.
COLOUR = DATA["before_after"]


def _number(value: float | None) -> str:
    return "" if value is None else f"{value:.6g}"


class CompareDialog(QDialog):
    """The volume changes of the last rebuild."""

    def __init__(self, window: MainWindow, rows: list[Any], before: Any) -> None:
        super().__init__(window)
        self.setObjectName("before_after")
        self.setWindowTitle(text.COMPARE_TITLE)
        self.window_, self.rows, self.before = window, rows, before
        layout = QVBoxLayout(self)
        note = QLabel(text.COMPARE_NOTE if rows else text.COMPARE_NONE)
        note.setWordWrap(True)
        layout.addWidget(note)
        self.table = QTableWidget(len(rows), 4)
        self.table.setObjectName("before_after_table")
        self.table.setHorizontalHeaderLabels(list(text.COMPARE_COLUMNS))
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        for r, row in enumerate(rows):
            cells = (row.name, _number(row.before), _number(row.after), f"{row.delta:+.6g}")
            for c, value in enumerate(cells):
                self.table.setItem(r, c, QTableWidgetItem(value))
        self.table.itemSelectionChanged.connect(self._picked)
        layout.addWidget(self.table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _picked(self) -> None:
        index = self.table.currentRow()
        shapes = []
        if 0 <= index < len(self.rows):
            old = self.before.results.get(self.rows[index].feature_id)
            body = getattr(old, "body", None)
            if body is not None:
                shapes = [body.shape]
        self.show_before(shapes)

    def show_before(self, shapes: list[Any]) -> None:
        """Draw ``shapes`` faintly in the view (an empty list clears it)."""
        from fdcad.ui.print_tools.overlay import show_layer

        tab = self.window_.current
        if tab is not None:
            show_layer(tab.viewport, LAYER, shapes, COLOUR, shaded=True)

    def done(self, result: int) -> None:
        self.show_before([])  # the faint shape goes with the window
        super().done(result)


def show_changes(window: MainWindow) -> CompareDialog | None:
    """Before and After: open the list for the current part."""
    from fdcad.core.rebuild_compare import volume_changes

    tab = window.current
    if tab is None:
        window.status.setText(text.COMPARE_NO_PART)
        return None
    session = tab.session
    rows = volume_changes(session.document, session.previous_report, session.report)
    dialog = CompareDialog(window, rows, session.previous_report)
    dialog.setModal(False)
    dialog.show()
    return dialog
