"""The sketch problem list (TUTORIAL_REVIEW_SPEC_2 TR38, D1301).

Opened by clicking the sketch status in the status bar. Each row names one
problem (``core.sketch.problems``): a dangling relation or dimension, invalid
geometry, a conflict set, a redundant item, or no solution. Clicking a row
selects its items. Buttons: Zoom to Item, Pick New Item (a dangling row takes
the item selected in the sketch), Delete, Repair All Dangling (offers the one
clear replacement of each dangling item, one question each), Diagnose (steps
through the ways out of a conflict set) with Apply Way Out, and Select Under
Defined. The dialog does not block the sketch, so items can be picked in it.
Every change is one sketch undo step.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.sketch.model import Point, entity_points
from fdcad.core.sketch.problems import (
    Problem,
    WayOut,
    apply_way_out,
    delete_item,
    diagnose,
    item_name,
    problems,
    replacement,
    set_item_entity,
)
from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.sketch_tools.canvas import SketchCanvas


def ask(parent: QWidget, text: str) -> bool:
    """Ask a yes or no question; tests replace this."""
    answer = QMessageBox.question(parent, strings.PROBLEMS_TITLE, text)
    return answer == QMessageBox.StandardButton.Yes


class ProblemListDialog(QDialog):
    """The list of sketch problems with the buttons that act on them."""

    def __init__(self, canvas: SketchCanvas, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(strings.PROBLEMS_TITLE)
        self.setObjectName("sketch_problems")
        self.canvas = canvas
        self.rows: list[Problem] = []
        self.ways: list[WayOut] = []
        self.way_index = -1
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._row_changed)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.buttons: dict[str, QPushButton] = {}
        grid = QGridLayout()
        for i, (key, label, slot) in enumerate(
            (
                ("zoom", strings.PROBLEMS_ZOOM, self.zoom),
                ("pick", strings.PROBLEMS_PICK, self.pick_new),
                ("delete", strings.PROBLEMS_DELETE, self.delete),
                ("repair", strings.PROBLEMS_REPAIR, self.repair_all),
                ("diagnose", strings.PROBLEMS_DIAGNOSE, self.diagnose),
                ("apply", strings.PROBLEMS_APPLY, self.apply_way),
                ("under", strings.PROBLEMS_UNDER, self.select_under),
            )
        ):
            button = QPushButton(label)
            button.clicked.connect(slot)
            grid.addWidget(button, i // 2, i % 2)
            self.buttons[key] = button
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.list)
        layout.addLayout(grid)
        layout.addWidget(self.message)
        layout.addWidget(close)
        canvas.edited.connect(self.refill)
        self.refill()

    # Filling -------------------------------------------------------------------------

    def refill(self) -> None:
        """List the problems of the sketch as it stands."""
        edit = self.canvas.edit
        row = self.list.currentRow()
        self.rows = problems(edit.sketch, edit.result, edit.dangling)
        self.list.blockSignals(True)
        self.list.clear()
        for p in self.rows:
            kind = strings.PROBLEMS_KINDS.get(p.kind, p.kind)
            QListWidgetItem(f"{kind}: {p.message}", self.list)
        if not self.rows:
            QListWidgetItem(strings.PROBLEMS_NONE, self.list)
        self.list.blockSignals(False)
        if self.rows:
            self.list.setCurrentRow(min(max(row, 0), len(self.rows) - 1))
        self.buttons["repair"].setEnabled(any(p.kind == "dangling" for p in self.rows))
        self._update_buttons()

    def _current(self) -> Problem | None:
        row = self.list.currentRow()
        return self.rows[row] if 0 <= row < len(self.rows) else None

    def _update_buttons(self) -> None:
        p = self._current()
        kind = p.kind if p is not None else ""
        self.buttons["zoom"].setEnabled(p is not None and bool(p.entities))
        self.buttons["pick"].setEnabled(kind == "dangling")
        self.buttons["delete"].setEnabled(p is not None and bool(p.keys or p.entities))
        self.buttons["diagnose"].setEnabled(kind == "conflicting")
        self.buttons["apply"].setEnabled(bool(self.ways) and self.way_index >= 0)

    def _row_changed(self, _row: int) -> None:
        """Select the items of the row."""
        self.ways, self.way_index = [], -1
        p = self._current()
        if p is not None:
            sk = self.canvas.edit.sketch
            dims = [k for k in p.keys if any(d.id == k for d in sk.dimensions)]
            self.canvas.selection = [e for e in p.entities if e in sk.entities] + dims
            self.canvas.selection_changed.emit()
            self.canvas.update()
        self._update_buttons()

    # Actions ---------------------------------------------------------------------------

    def zoom(self) -> None:
        """Centre the sketch on the row's items."""
        p = self._current()
        if p is None:
            return
        sk = self.canvas.edit.sketch
        pts = [
            sk.xy(pid)
            for eid in p.entities
            if eid in sk.entities
            for pid in entity_points(sk.entities[eid])
            if pid in sk.entities
        ]
        if pts:
            self.canvas.center = (
                sum(x for x, _ in pts) / len(pts),
                sum(y for _, y in pts) / len(pts),
            )
            self.canvas.scale = max(self.canvas.scale, 8.0)
            self.canvas.update()

    def pick_new(self) -> None:
        """A dangling item names the one item selected in the sketch instead."""
        p = self._current()
        if p is None or p.kind != "dangling" or not p.missing:
            self.message.setText(strings.PROBLEMS_NOT_DANGLING)
            return
        sk = self.canvas.edit.sketch
        picked = [s for s in self.canvas.selection if s in sk.entities and s not in p.entities]
        if len(picked) != 1:
            self.message.setText(strings.PROBLEMS_PICK_FIRST)
            return
        key, old, new = p.keys[0], p.missing[0], picked[0]
        self.canvas.run(lambda: set_item_entity(self.canvas.edit.sketch, key, old, new))

    def delete(self) -> None:
        """Delete the row's relations and dimensions, or its invalid curve."""
        p = self._current()
        if p is None:
            return
        keys = list(p.keys)
        ents = set(p.entities) if not keys else set()

        def change() -> None:
            sk = self.canvas.edit.sketch
            # Relations by index: the highest first so the others keep their place.
            for key in sorted(keys, key=_order, reverse=True):
                delete_item(sk, key)
            if ents:
                self.canvas.edit.delete(ents)

        self.canvas.run(change)

    def repair_all(self) -> None:
        """Offer the clear replacement of each dangling item; apply the accepted ones
        as one undo step."""
        sk = self.canvas.edit.sketch
        chosen: list[tuple[str, str, str]] = []
        left = 0
        for p in [r for r in self.rows if r.kind == "dangling"]:
            match = replacement(sk, p.keys[0])
            if match is None:
                left += 1
                continue
            ((old, new),) = match.items()
            text = strings.PROBLEMS_REPAIR_ASK.format(
                new=new, old=old, item=item_name(sk, p.keys[0])
            )
            if ask(self, text):
                chosen.append((p.keys[0], old, new))
            else:
                left += 1
        if chosen:

            def change() -> None:
                for key, old, new in chosen:
                    set_item_entity(self.canvas.edit.sketch, key, old, new)

            self.canvas.run(change)
        self.message.setText(strings.PROBLEMS_REPAIRED.format(n=len(chosen), left=left))

    def diagnose(self) -> None:
        """Show the next way out of the conflict set, with how far it moves points."""
        p = self._current()
        if p is None or p.kind != "conflicting":
            self.message.setText(strings.PROBLEMS_NOT_CONFLICT)
            return
        if not self.ways:
            self.ways = diagnose(self.canvas.edit.sketch, p.keys)
            self.way_index = -1
        if not self.ways:
            self.message.setText(strings.PROBLEMS_NO_WAY)
            self._update_buttons()
            return
        self.way_index = (self.way_index + 1) % len(self.ways)
        way = self.ways[self.way_index]
        self.message.setText(
            strings.PROBLEMS_WAY.format(n=self.way_index + 1, count=len(self.ways), label=way.label)
        )
        sk = self.canvas.edit.sketch
        dims = [way.key] if any(d.id == way.key for d in sk.dimensions) else []
        ents = [e for e in p.entities if e in sk.entities] if not dims else []
        self.canvas.selection = dims or ents
        self.canvas.selection_changed.emit()
        self.canvas.update()
        self._update_buttons()

    def apply_way(self) -> None:
        """Apply the way out shown last."""
        if not self.ways or self.way_index < 0:
            return
        way = self.ways[self.way_index]
        self.ways, self.way_index = [], -1
        self.canvas.run(lambda: apply_way_out(self.canvas.edit.sketch, way))

    def select_under(self) -> None:
        """Select every curve and point that is not fully defined."""
        edit = self.canvas.edit
        edit.refresh(full=True)
        sk = edit.sketch
        under = [
            eid
            for eid, e in sk.entities.items()
            if eid not in edit.defined and not (isinstance(e, Point) and e.construction)
        ]
        self.canvas.selection = under
        self.canvas.selection_changed.emit()
        self.canvas.update()
        if not under:
            self.message.setText(strings.PROBLEMS_UNDER_NONE)


def _order(key: str) -> tuple[int, int]:
    """Relations by index after dimensions, so deleting from the end is safe."""
    if key.startswith("r") and key[1:].isdigit():
        return (1, int(key[1:]))
    return (0, 0)
