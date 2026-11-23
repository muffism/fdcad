"""Change existing fillets and drafts without editing them (TR132, DECISIONS D1404).

1. Change Fillet Edge, from the view menu on a fillet face: its own radius, or
   Remove from Fillet.
2. Change Fillets, from the tree menu on a fillet: the part's constant fillets,
   filtered by a radius range, get a new radius together.
3. Change Drafts, from the tree menu on a draft: the part's drafts by pull
   direction and angle; a new angle for the selected ones, or Remove Selected.

Every change is one undoable step (several features in one macro).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.document.model import Feature, Param
from fdcad.core.fillet_edit import (
    EditError,
    draft_rows,
    fillet_rows,
    with_angle,
    with_edge_radius,
    with_radius,
    without_edge,
)
from fdcad.core.units import Kind
from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.property_panel.panel import ValueField
    from fdcad.ui.session import DocumentSession


def value_field(session: DocumentSession, kind: Kind, param: Param | None) -> ValueField:
    """A typed value field in the part's units, with its variables."""
    from fdcad.core.rebuild.engine import document_variables
    from fdcad.ui.property_panel.panel import ValueField

    doc = session.document
    return ValueField(kind, doc.units, document_variables(doc), param)


def _push(session: DocumentSession, edited: list[Feature], text: str) -> None:
    from fdcad.ui.commands.document import ReplaceFeature

    if not edited:
        return
    if len(edited) == 1:
        session.undo.push(ReplaceFeature(session, edited[0], text))
        return
    session.undo.beginMacro(text)
    for feature in edited:
        session.undo.push(ReplaceFeature(session, feature, text))
    session.undo.endMacro()


class EdgeDialog(QDialog):
    """Change Fillet Edge: a radius for one edge of a fillet, or remove it."""

    def __init__(
        self, session: DocumentSession, fid: str, edge: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("change_fillet_edge")
        self.session, self.fid, self.edge = session, fid, edge
        feature = session.document.feature(fid)
        self.setWindowTitle(strings.CHANGE_FILLET_EDGE)
        intro = QLabel(strings.CHANGE_FILLET_EDGE_INTRO.format(name=feature.name))
        intro.setWordWrap(True)
        radius = feature.params.get("radius")
        self.radius = value_field(
            session, Kind.LENGTH, radius if isinstance(radius, Param) else None
        )
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.remove = QPushButton(strings.CHANGE_FILLET_REMOVE)
        self.remove.setToolTip(strings.CHANGE_FILLET_REMOVE_TIP)
        self.remove.clicked.connect(self.remove_edge)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.set_radius)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        form = QFormLayout()
        form.addRow(strings.CHANGE_FILLET_RADIUS, self.radius)
        layout.addLayout(form)
        layout.addWidget(self.remove)
        layout.addWidget(self.message)
        layout.addWidget(buttons)

    def set_radius(self) -> None:
        """OK: give the edge the typed radius."""
        param = self.radius.param()
        if param is None:
            self.message.setText(strings.CHANGE_FILLET_BAD_VALUE)
            return
        self._apply(lambda f: with_edge_radius(f, self.edge, param))

    def remove_edge(self) -> None:
        """Remove from Fillet."""
        self._apply(lambda f: without_edge(f, self.edge))

    def _apply(self, change: object) -> None:
        feature = self.session.document.feature(self.fid)
        try:
            edited = change(feature)  # type: ignore[operator]
        except EditError as exc:
            self.message.setText(str(exc))
            return
        _push(self.session, [edited], strings.CHANGE_FILLET_EDGE)
        self.accept()


class FilletsDialog(QDialog):
    """Change Fillets: the part's constant fillets in a radius range, a new radius."""

    def __init__(self, session: DocumentSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("change_fillets")
        self.session = session
        self.setWindowTitle(strings.CHANGE_FILLETS)
        self.low = value_field(session, Kind.LENGTH, Param("0", 0.0))
        self.high = value_field(session, Kind.LENGTH, Param("1000", 1000.0))
        self.new = value_field(session, Kind.LENGTH, Param("1", 1.0))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(list(strings.CHANGE_FILLETS_COLUMNS))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.message = QLabel()
        self.message.setWordWrap(True)
        for fld in (self.low, self.high):
            fld.edit.textChanged.connect(lambda _t: self.fill())
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(strings.CHANGE_FILLETS_APPLY)
        buttons.accepted.connect(self.apply)
        buttons.rejected.connect(self.reject)
        form = QFormLayout()
        form.addRow(strings.CHANGE_FILLETS_FROM, self.low)
        form.addRow(strings.CHANGE_FILLETS_TO, self.high)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.table)
        new_form = QFormLayout()
        new_form.addRow(strings.CHANGE_FILLETS_NEW, self.new)
        layout.addLayout(new_form)
        # TR260 (D1410): rounds with no fillet feature (an imported body).
        self.rounds = QLabel()
        self.rounds.setWordWrap(True)
        self.add_remove = QPushButton(strings.REMOVE_FILLETS_ADD)
        self.add_remove.setToolTip(strings.REMOVE_FILLETS_TIP)
        self.add_remove.clicked.connect(self.add_remove_fillets)
        layout.addWidget(self.rounds)
        layout.addWidget(self.add_remove)
        layout.addWidget(self.message)
        layout.addWidget(buttons)
        self.fill()

    def listed(self) -> list[str]:
        """Ids of the fillets in the list."""
        ids = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None:
                ids.append(str(item.data(256)))
        return ids

    def fill(self) -> None:
        """List the fillets inside the radius range."""
        low, high = self.low.param(), self.high.param()
        rows = fillet_rows(
            self.session.document,
            low.value if low is not None else None,
            high.value if high is not None else None,
        )
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            name = QTableWidgetItem(row.name)
            name.setData(256, row.fid)
            self.table.setItem(r, 0, name)
            self.table.setItem(r, 1, QTableWidgetItem(row.text))
            self.table.setItem(r, 2, QTableWidgetItem(str(row.edges)))
        if hasattr(self, "rounds"):
            self.rounds.setText(strings.REMOVE_FILLETS_FOUND.format(count=self.count_rounds()))

    def count_rounds(self) -> int:
        """Round faces in the range on the built part, fillet features or not (TR260)."""
        from fdcad.core.features.remove_fillets import find_rounds

        report = self.session.report
        if report is None or report.body is None:
            return 0
        low, high = self.low.param(), self.high.param()
        return len(
            find_rounds(
                report.body,
                low.value if low is not None else None,
                high.value if high is not None else None,
            )
        )

    def add_remove_fillets(self) -> None:
        """Add a Remove Fillets feature for the range, with the new radius (TR260)."""
        from fdcad.core.features.names import default_name
        from fdcad.ui.commands.document import AddFeature

        low, high, new = self.low.param(), self.high.param(), self.new.param()
        if low is None or high is None or new is None:
            self.message.setText(strings.CHANGE_FILLET_BAD_VALUE)
            return
        doc = self.session.document
        feature = Feature(
            doc.new_feature_id(),
            "remove_fillets",
            default_name(doc, "remove_fillets"),
            params={
                "use_range": True,
                "min_radius": low,
                "max_radius": high,
                "resize": True,
                "new_radius": new,
            },
        )
        self.session.undo.push(AddFeature(self.session, feature))
        self.accept()

    def apply(self) -> None:
        """Give every listed fillet the new radius, in one undo step."""
        param = self.new.param()
        ids = self.listed()
        if param is None:
            self.message.setText(strings.CHANGE_FILLET_BAD_VALUE)
            return
        if not ids:
            self.message.setText(strings.CHANGE_FILLETS_NONE)
            return
        doc = self.session.document
        try:
            edited = [with_radius(doc.feature(fid), param) for fid in ids]
        except EditError as exc:
            self.message.setText(str(exc))
            return
        _push(self.session, edited, strings.CHANGE_FILLETS)
        self.accept()


class DraftsDialog(QDialog):
    """Change Drafts: the part's drafts, a new angle, Remove Selected."""

    def __init__(self, session: DocumentSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("change_drafts")
        self.session = session
        self.setWindowTitle(strings.CHANGE_DRAFTS)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(list(strings.CHANGE_DRAFTS_COLUMNS))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.angle = value_field(session, Kind.ANGLE, Param("3", math.radians(3)))
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.set_angle = QPushButton(strings.CHANGE_DRAFTS_SET)
        self.set_angle.clicked.connect(self.apply_angle)
        self.remove = QPushButton(strings.CHANGE_DRAFTS_REMOVE)
        self.remove.clicked.connect(self.remove_selected)
        row = QHBoxLayout()
        row.addWidget(self.set_angle)
        row.addWidget(self.remove)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        form = QFormLayout()
        form.addRow(strings.CHANGE_DRAFTS_ANGLE, self.angle)
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addLayout(form)
        layout.addLayout(row)
        layout.addWidget(self.message)
        layout.addWidget(buttons)
        self.fill()

    def fill(self) -> None:
        """List the drafts by pull direction, then angle."""
        rows = draft_rows(self.session.document)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            name = QTableWidgetItem(row.name)
            name.setData(256, row.fid)
            self.table.setItem(r, 0, name)
            self.table.setItem(r, 1, QTableWidgetItem(f"{math.degrees(row.angle):g} deg"))
            self.table.setItem(r, 2, QTableWidgetItem(row.pull))

    def selected(self) -> list[str]:
        """Ids of the selected drafts."""
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        out = []
        for r in rows:
            item = self.table.item(r, 0)
            if item is not None:
                out.append(str(item.data(256)))
        return out

    def apply_angle(self) -> None:
        """Set Angle: the typed angle on every selected draft."""
        ids, param = self.selected(), self.angle.param()
        if not ids:
            self.message.setText(strings.CHANGE_DRAFTS_PICK)
            return
        if param is None:
            self.message.setText(strings.CHANGE_FILLET_BAD_VALUE)
            return
        doc = self.session.document
        try:
            edited = [with_angle(doc.feature(fid), param) for fid in ids]
        except EditError as exc:
            self.message.setText(str(exc))
            return
        _push(self.session, edited, strings.CHANGE_DRAFTS)
        self.message.setText("")
        self.fill()

    def remove_selected(self) -> None:
        """Remove Selected: delete the selected drafts, in one undo step."""
        from fdcad.ui.commands.document import DeleteFeature

        ids = self.selected()
        if not ids:
            self.message.setText(strings.CHANGE_DRAFTS_PICK)
            return
        session = self.session
        session.undo.beginMacro(strings.CHANGE_DRAFTS_REMOVE)
        for fid in ids:
            session.undo.push(DeleteFeature(session, fid))
        session.undo.endMacro()
        self.fill()


def split_fillet_command(session: DocumentSession, fid: str, fix: object) -> None:
    """Split a failing fillet into several (TR346, D1405), as one undo step."""
    from fdcad.core.features.fillet_help import split_fillet
    from fdcad.ui.commands.document import AddFeature, ReplaceFeature

    data = getattr(fix, "data", {})
    target = str(data.get("feature", fid))
    groups = [[str(n) for n in g] for g in data.get("groups", [])]
    doc = session.document
    made = split_fillet(doc, target, groups)
    index = next(i for i, f in enumerate(doc.features) if f.id == target)
    session.undo.beginMacro(strings.SPLIT_FILLET_UNDO.format(name=made[0].name))
    session.undo.push(ReplaceFeature(session, made[0]))
    for n, feature in enumerate(made[1:], start=1):
        session.undo.push(AddFeature(session, feature, index + n))
    session.undo.endMacro()


def limit_failing_command(session: DocumentSession, fid: str, fix: object) -> None:
    """Limit Failing Areas (TR271, D1802): the failing edges become Partial Edges
    fillets after the fillet, as one undo step."""
    from fdcad.core.features.fillet_limit_areas import limit_failing
    from fdcad.ui.commands.document import AddFeature, ReplaceFeature
    from fdcad.ui.strings_finish import LIMIT_FAILING_UNDO

    data = getattr(fix, "data", {})
    target = str(data.get("feature", fid))
    parts = [list(p) for p in data.get("parts", [])]
    doc = session.document
    made = limit_failing(doc, target, parts)
    index = next(i for i, f in enumerate(doc.features) if f.id == target)
    session.undo.beginMacro(LIMIT_FAILING_UNDO.format(name=made[0].name))
    session.undo.push(ReplaceFeature(session, made[0]))
    for n, feature in enumerate(made[1:], start=1):
        session.undo.push(AddFeature(session, feature, index + n))
    session.undo.endMacro()
