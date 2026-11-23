"""The Bend Table window (TR282, DECISIONS D1110).

Lists every bend of the sheet metal part: number, feature, direction, angle, radius,
bend allowance and its step in the bending order. Picking a row highlights the bend
in the model. Radius, allowance and step can be typed; OK turns each changed bend
into an Edit Bends feature and the steps into the Flat Pattern's bend order, all in
one undo step (``flow.bend_table``). A second table lists the Rip features with
their gap, which can be typed too (TR282, D2310).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.features.sheetmetal.bend_list import BendRow, RipRow
from fdcad.ui import strings_sheetmetal as text

#: Columns: label, editable.
COLUMNS = (
    ("number", False),
    ("feature", False),
    ("direction", False),
    ("angle", False),
    ("radius", True),
    ("allowance", True),
    ("step", True),
)


def _number(value: str) -> float | None:
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return None


class BendTableDialog(QDialog):
    """A table of the part's bends with editable radius, allowance and step."""

    picked = Signal(str)  # bend id of the row picked

    def __init__(
        self,
        rows: list[BendRow],
        names: dict[str, str],
        order: dict[str, int],
        parent: QWidget | None = None,
        rips: list[RipRow] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("bend_table_dialog")
        self.setWindowTitle(text.BEND_LIST_TITLE)
        self.rows = rows
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(text.BEND_LIST_HINT))
        self.table = QTableWidget(len(rows), len(COLUMNS))
        self.table.setObjectName("bend_table")
        self.table.setHorizontalHeaderLabels([text.BEND_LIST_COLUMNS[c] for c, _e in COLUMNS])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        for r, row in enumerate(rows):
            values = (
                str(row.number),
                names.get(row.owner, row.owner),
                text.BEND_LIST_DIRECTIONS[row.direction],
                f"{row.angle:g}",
                f"{row.radius:g}",
                f"{row.allowance:.4g}",
                str(order.get(row.bid, row.number)),
            )
            for c, ((_name, editable), value) in enumerate(zip(COLUMNS, values, strict=True)):
                item = QTableWidgetItem(value)
                if not editable:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(r, c, item)
        self.table.resizeColumnsToContents()
        self.table.currentCellChanged.connect(self._row_picked)
        layout.addWidget(self.table)
        # TR282 (D2310): the rips, with their gap.
        self.rips = rips or []
        self.rip_table = QTableWidget(len(self.rips), 4)
        self.rip_table.setObjectName("rip_table")
        self.rip_table.setHorizontalHeaderLabels(list(text.RIP_LIST_COLUMNS.values()))
        self.rip_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        for r, rip in enumerate(self.rips):
            cells = (
                f"R{rip.number}",
                names.get(rip.fid, rip.fid),
                text.RIP_LIST_KINDS[rip.kind],
                f"{rip.gap:g}",
            )
            for c, value in enumerate(cells):
                item = QTableWidgetItem(value)
                if c != 3:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.rip_table.setItem(r, c, item)
        self.rip_table.resizeColumnsToContents()
        self.rip_table.currentCellChanged.connect(self._rip_picked)
        if self.rips:
            layout.addWidget(QLabel(text.RIP_LIST_HINT))
            layout.addWidget(self.rip_table)
        else:
            self.rip_table.hide()
        self.error = QLabel("")
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _row_picked(self, row: int, *_rest: int) -> None:
        if 0 <= row < len(self.rows):
            self.picked.emit(self.rows[row].bid)

    rip_picked = Signal(str)  # feature id of the rip row picked (D2310)

    def _rip_picked(self, row: int, *_rest: int) -> None:
        if 0 <= row < len(self.rips):
            self.rip_picked.emit(self.rips[row].fid)

    def _rip_gap(self, row: int) -> float | None:
        item = self.rip_table.item(row, 3)
        return _number(item.text().strip()) if item is not None else None

    def rip_changes(self) -> dict[str, float]:
        """Rip feature id to its new gap, for the rips whose gap was changed (D2310)."""
        out = {}
        for r, rip in enumerate(self.rips):
            gap = self._rip_gap(r)
            if gap is not None and abs(gap - rip.gap) > 1e-9:
                out[rip.fid] = gap
        return out

    def _cell(self, row: int, column: str) -> str:
        index = [c for c, _e in COLUMNS].index(column)
        item = self.table.item(row, index)
        return item.text().strip() if item is not None else ""

    def changes(self) -> dict[str, tuple[float | None, float | None]]:
        """Bend id to its new (radius, allowance), None where it is unchanged."""
        out: dict[str, tuple[float | None, float | None]] = {}
        for r, row in enumerate(self.rows):
            radius = _number(self._cell(r, "radius"))
            allowance = _number(self._cell(r, "allowance"))
            new_r = radius if radius is not None and abs(radius - row.radius) > 1e-9 else None
            new_a = None
            if allowance is not None and abs(allowance - float(f"{row.allowance:.4g}")) > 1e-9:
                new_a = allowance
            if new_r is not None or new_a is not None:
                out[row.bid] = (new_r, new_a)
        return out

    def order_text(self) -> str:
        """The bend numbers sorted by their typed step, as the bend order text."""
        steps = []
        for r, row in enumerate(self.rows):
            step = _number(self._cell(r, "step"))
            steps.append((step if step is not None else float(row.number), row.number))
        return ", ".join(str(n) for _s, n in sorted(steps))

    def problem(self) -> str:
        """What is wrong with the typed values, or an empty string."""
        for r in range(len(self.rows)):
            for column in ("radius", "allowance", "step"):
                value = _number(self._cell(r, column))
                if value is None or value < 0 or (column == "allowance" and value == 0):
                    return text.BEND_LIST_BAD.format(row=r + 1)
        for r in range(len(self.rips)):
            gap = self._rip_gap(r)
            if gap is None or gap <= 0:
                return text.RIP_LIST_BAD.format(row=r + 1)
        return ""

    def _accept(self) -> None:
        problem = self.problem()
        if problem:
            self.error.setText(problem)
            return
        self.accept()
