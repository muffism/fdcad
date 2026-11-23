"""The Relations panel: every relation of the open sketch, with a filter (TOOL_SPEC T3.3).

Selecting rows selects those relations in the canvas, which highlights their
items. Delete and Delete All remove relations as one step on the sketch's undo
list. The origin's own fixed relation is internal and never listed.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.sketch.model import Line, Point, Sketch
from fdcad.ui import icons, strings
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.edit import SketchEdit
from fdcad.ui.themes.style import unit

#: Filter choices, in the order of the filter list.
FILTERS = ("all", "problems", "model")


def _fixed_ids(sketch: Sketch) -> set[str]:
    return {e for r in sketch.relations if r.type == "fixed" for e in r.entities}


def is_origin_fix(sketch: Sketch, index: int) -> bool:
    """True for the fixed relation that holds the sketch origin point."""
    rel = sketch.relations[index]
    if rel.type != "fixed" or len(rel.entities) != 1:
        return False
    p = sketch.entities.get(rel.entities[0])
    return isinstance(p, Point) and p.construction and abs(p.x) < 1e-12 and abs(p.y) < 1e-12


def model_copies(sketch: Sketch) -> set[str]:
    """Fixed construction copies of part geometry (D113, D116 item 3).

    These are fixed construction lines and fixed construction points other than
    the origin. The points and lines that belong to such a line count too.
    """
    fixed = _fixed_ids(sketch)
    out: set[str] = set()
    for eid in fixed:
        ent = sketch.entities.get(eid)
        if isinstance(ent, Line) and ent.construction:
            out |= {eid, ent.p1, ent.p2}
        elif (
            isinstance(ent, Point)
            and ent.construction
            and not (abs(ent.x) < 1e-12 and abs(ent.y) < 1e-12)
        ):
            out.add(eid)
    return out


def listed_relations(edit: SketchEdit, which: str) -> list[int]:
    """Indexes of the relations the panel lists for filter ``which``."""
    sk = edit.sketch
    indexes = [i for i in range(len(sk.relations)) if not is_origin_fix(sk, i)]
    if which == "problems":
        if edit.result is None or not edit.result.solved:
            return indexes
        bad, _dims = edit.conflicting_items()
        return [i for i in indexes if i in bad]
    if which == "model":
        copies = model_copies(sk)
        return [i for i in indexes if copies & set(sk.relations[i].entities)]
    return indexes


class RelationsPanel(QWidget):
    """Lists, highlights and deletes the relations of the open sketch."""

    closed = Signal()

    def __init__(self, canvas: SketchCanvas, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.canvas = canvas
        self.setObjectName("property_panel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        u = unit(self.font())
        title = QLabel(f"<b>{strings.RELATIONS_PANEL}</b>")
        title.setObjectName("panel_title")
        self.back = QPushButton(strings.RELATIONS_BACK)
        self.back.clicked.connect(self.closed.emit)
        header_box = QWidget()
        header_box.setObjectName("panel_header")
        header_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        header = QHBoxLayout(header_box)
        header.setContentsMargins(2 * u, 2 * u, 2 * u, 2 * u)
        mark = QLabel()
        mark.setPixmap(
            icons.icon("sketch.relations").pixmap(QSize(24, 24), self.devicePixelRatioF())
        )
        header.addWidget(mark)
        header.addWidget(title, 1)
        header.addWidget(self.back)
        self.filter = QComboBox()
        for key in FILTERS:
            self.filter.addItem(strings.RELATION_FILTERS[key], key)
        self.filter.currentIndexChanged.connect(self.refresh)
        self.rows = QListWidget()
        self.rows.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.rows.itemSelectionChanged.connect(self._rows_selected)
        self.delete = QPushButton(icons.icon("edit.delete"), strings.DELETE)
        self.delete.clicked.connect(self.delete_selected)
        self.delete_all = QPushButton(strings.DELETE_ALL)
        self.delete_all.clicked.connect(self.delete_listed)
        buttons = QHBoxLayout()
        buttons.addWidget(self.delete)
        buttons.addWidget(self.delete_all)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(header_box)
        body = QVBoxLayout()
        body.setContentsMargins(2 * u, 2 * u, 2 * u, 2 * u)
        body.setSpacing(2 * u)
        body.addWidget(QLabel(strings.RELATION_FILTER))
        body.addWidget(self.filter)
        body.addWidget(self.rows, 1)
        body.addLayout(buttons)
        outer.addLayout(body, 1)
        self._filling = False
        canvas.edited.connect(self.refresh)
        self.refresh()

    @property
    def which(self) -> str:
        """The current filter key."""
        return str(self.filter.currentData())

    def set_filter(self, which: str) -> None:
        """Choose a filter by key (``all``, ``problems`` or ``model``)."""
        self.filter.setCurrentIndex(FILTERS.index(which))

    def listed(self) -> list[int]:
        """Relation indexes shown in the list, in order."""
        return [int(self.rows.item(r).data(256)) for r in range(self.rows.count())]

    def refresh(self) -> None:
        """Fill the list from the sketch."""
        edit = self.canvas.edit
        sk = edit.sketch
        bad, _dims = edit.conflicting_items()
        keep = set(self.canvas.selected_relations())
        self._filling = True
        self.rows.clear()
        for index in listed_relations(edit, self.which):
            rel = sk.relations[index]
            name = strings.RELATION_NAMES.get(rel.type, rel.type)
            item = QListWidgetItem(
                icons.icon(f"relation.{rel.type}"), f"{name} ({', '.join(rel.entities)})"
            )
            item.setData(256, index)
            if index in bad:
                item.setForeground(self.palette().brightText())
            self.rows.addItem(item)
            item.setSelected(index in keep)
        self._filling = False
        self.delete.setEnabled(bool(self.rows.selectedItems()))
        self.delete_all.setEnabled(self.rows.count() > 0)

    def select_rows(self, indexes: list[int]) -> None:
        """Select the rows of these relation indexes."""
        for r in range(self.rows.count()):
            item = self.rows.item(r)
            item.setSelected(int(item.data(256)) in indexes)

    def _rows_selected(self) -> None:
        if self._filling:
            return
        chosen = [int(i.data(256)) for i in self.rows.selectedItems()]
        self.canvas.select_relations(chosen)
        self.delete.setEnabled(bool(chosen))

    def _remove(self, indexes: list[int]) -> None:
        if not indexes:
            return
        ids = {f"r{i}" for i in indexes}
        self.canvas.selection = []
        self.canvas.run(lambda: self.canvas.edit.delete(ids))
        self.canvas.selection_changed.emit()

    def delete_selected(self) -> None:
        """Delete the selected rows' relations."""
        self._remove([int(i.data(256)) for i in self.rows.selectedItems()])

    def delete_listed(self) -> None:
        """Delete All: every relation the current filter lists."""
        self._remove(self.listed())
