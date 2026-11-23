"""Panel forms for the Phase 2 features that do not start from one sketch profile:
fillet, chamfer, shell, draft, sweep and loft (PHASE2_SPEC common rules, TOOL_SPEC T5).

The property panel keeps the header, OK and Cancel and the message line; a form
adds its groups, writes its values into the edited copy and takes picks from
the view. Every pick is stored as a reference by topological name (FDEF_SPEC 7).
A form also shows what the preview's pre check found (PLAN 5A items 4 and 5).
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QResizeEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.document.dependencies import referenced_ids
from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.units import Kind
from fdcad.ui import strings
from fdcad.ui.property_panel.groups import Group, with_icon
from fdcad.ui.themes.theme import chrome

if TYPE_CHECKING:
    from fdcad.core.features.base import Fix
    from fdcad.core.features.preview import PreviewGeometry
    from fdcad.core.naming.names import NamedShape
    from fdcad.ui.property_panel.panel import PropertyPanel, ValueField

#: Settings each form remembers within a session (P2.4 item 1), by feature type.
REMEMBERED: dict[str, dict[str, Any]] = {}


def remember(feature: Feature, keys: tuple[str, ...]) -> None:
    """Keep ``keys`` of an accepted feature for the next new feature of its type."""
    REMEMBERED[feature.type] = {k: copy.deepcopy(v) for k, v in feature.params.items() if k in keys}


def remembered(ftype: str) -> dict[str, Any]:
    """The settings kept from the last accepted feature of ``ftype`` in this session."""
    return copy.deepcopy(REMEMBERED.get(ftype, {}))


def ref_label(doc: Document, ref: dict[str, Any]) -> str:
    """Short text for a picked item: its kind and the feature that made it."""
    owners = [f.name for f in doc.features if f.id in referenced_ids(ref)]
    owner = ", ".join(owners) or strings.THE_PART
    if "rule" in ref:  # TR320 (D1408)
        label = strings.RULE_LABELS.get(str(ref["rule"]), "{feature}").format(
            feature=owner, axis=str(ref.get("axis", "z")).upper()
        )
        excluded = len(ref.get("exclude", []) or [])
        return label + (strings.RULE_EXCLUDED.format(count=excluded) if excluded else "")
    if "convexity" in ref:
        labels = strings.AUTO_EDGE_LABELS
        return labels.get(str(ref["convexity"]), labels["convex"]).format(feature=owner)
    if "feature" in ref and "kind" not in ref and "sketch_entity" not in ref:
        return owner
    kind = str(ref.get("kind", "item"))
    return strings.PICK_LABELS.get(kind, "{feature}").format(feature=owner)


class PickList(QWidget):
    """A list of picked items with Remove and, optionally, Move Up and Move Down.

    Lost items (TR125) show first in the error colour. Selecting one draws where it
    was and makes the next pick replace it (Pick Again); Clear All Missing removes
    every lost item at once.
    """

    changed = Signal()
    #: The reference of the selected lost item, or None (draw where it was, TR125).
    lost_selected = Signal(object)

    def __init__(self, doc: Document, tooltip: str, ordered: bool = False) -> None:
        super().__init__()
        self.doc = doc
        self.list = QListWidget()
        self.list.setToolTip(tooltip)
        self.list.setObjectName("pick_list")
        lines = max(4, self.fontMetrics().height())
        self.list.setMinimumHeight(5 * lines)
        self.list.setMaximumHeight(9 * lines)
        self.remove = QPushButton(strings.PICK_REMOVE)
        self.remove.setToolTip(strings.PICK_REMOVE_TIP)
        self.remove.clicked.connect(self.remove_selected)
        # Remove on one row, Move Up and Move Down on the next: in one row the three
        # were wider than the left panel's default width (D2790).
        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.addWidget(self.remove)
        moves = QHBoxLayout()
        moves.setContentsMargins(0, 0, 0, 0)
        self.up: QPushButton | None = None
        self.down: QPushButton | None = None
        if ordered:
            self.up = QPushButton(strings.PICK_UP)
            self.down = QPushButton(strings.PICK_DOWN)
            self.up.setToolTip(strings.PICK_UP_TIP)
            self.down.setToolTip(strings.PICK_DOWN_TIP)
            self.up.clicked.connect(lambda: self.move_item(-1))
            self.down.clicked.connect(lambda: self.move_item(1))
            moves.addWidget(self.up)
            moves.addWidget(self.down)
            moves.addStretch(1)
        self.lost: set[str] = set()
        self.clear_missing = QPushButton(strings.PICK_CLEAR_GONE)
        self.clear_missing.setToolTip(strings.PICK_CLEAR_GONE_TIP)
        self.clear_missing.clicked.connect(self.remove_lost)
        self.clear_missing.hide()
        buttons.addWidget(self.clear_missing)
        self.list.currentItemChanged.connect(self._current_changed)
        from fdcad.ui.body_tools.form_widget import pick_menu

        pick_menu(self.list, self.remove_selected, self.clear_all)  # TR206
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.list)
        layout.addLayout(buttons)
        if ordered:
            layout.addLayout(moves)

    # Contents ---------------------------------------------------------------------

    def refs(self) -> list[dict[str, Any]]:
        """The picked references, in list order."""
        out = []
        for i in range(self.list.count()):
            data = self.list.item(i).data(Qt.ItemDataRole.UserRole)
            if isinstance(data, dict):
                out.append(copy.deepcopy(data))
        return out

    def names(self) -> list[str]:
        """Names (or feature ids) of the picked items."""
        return [_key(r) for r in self.refs()]

    def add(self, ref: dict[str, Any], label: str | None = None) -> bool:
        """Add ``ref`` unless it is listed. Returns True when it was added.

        While a lost item is selected, ``ref`` takes its place instead (Pick Again).
        """
        if any(_same_pick(ref, listed) for listed in self.refs()):
            return False
        item = QListWidgetItem(label or ref_label(self.doc, ref))
        item.setData(Qt.ItemDataRole.UserRole, copy.deepcopy(ref))
        item.setToolTip(_key(ref))
        current = self.list.currentItem()
        if current is not None and _item_key(current) in self.lost:
            row = self.list.row(current)
            self.lost.discard(_item_key(current))
            self.list.takeItem(row)
            self.list.insertItem(row, item)
            self._lost_changed()
            self.lost_selected.emit(None)
        else:
            self.list.addItem(item)
        self.changed.emit()
        return True

    def remove_lost(self) -> None:
        """Clear All Missing: remove every lost item (TR125)."""
        names = [n for n in self.names() if n in self.lost]
        self.lost.clear()
        self._lost_changed()
        self.lost_selected.emit(None)
        if names:
            self.remove_names(names)

    def _lost_changed(self) -> None:
        self.clear_missing.setVisible(bool(self.lost & set(self.names())))

    def _current_changed(self, item: QListWidgetItem | None, _old: object) -> None:
        data = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        lost = isinstance(data, dict) and _key(data) in self.lost
        self.lost_selected.emit(copy.deepcopy(data) if lost else None)

    def set_refs(self, refs: list[dict[str, Any]]) -> None:
        """Replace the contents without sending ``changed``."""
        self.list.blockSignals(True)
        self.list.clear()
        self.blockSignals(True)
        for ref in refs:
            if isinstance(ref, dict):
                self.add(ref)
        self.blockSignals(False)
        self.list.blockSignals(False)

    def clear_all(self) -> None:
        """Clear Selections: remove every pick (TR206)."""
        if self.list.count():
            self.list.clear()
            self.lost = set()
            self.clear_missing.hide()
            self.changed.emit()

    def remove_selected(self) -> None:
        """Remove the selected items."""
        rows = sorted({self.list.row(i) for i in self.list.selectedItems()}, reverse=True)
        for row in rows:
            self.list.takeItem(row)
        if rows:
            self.changed.emit()

    def remove_edges_at(self, places: list[int]) -> None:
        """Remove the picked edges at these places, counted from 1 among the edges in
        the list (D1051). Two edges can share a name, so a name cannot say which."""
        wanted = {int(p) for p in places}
        rows = []
        count = 0
        for row in range(self.list.count()):
            data = self.list.item(row).data(Qt.ItemDataRole.UserRole)
            if isinstance(data, dict) and data.get("kind") == "edge":
                count += 1
                if count in wanted:
                    rows.append(row)
        for row in reversed(rows):
            self.list.takeItem(row)
        if rows:
            self.changed.emit()

    def remove_names(self, names: list[str]) -> None:
        """Remove the items called ``names``."""
        drop = set(names)
        for row in range(self.list.count() - 1, -1, -1):
            data = self.list.item(row).data(Qt.ItemDataRole.UserRole)
            if isinstance(data, dict) and _key(data) in drop:
                self.list.takeItem(row)
        self.changed.emit()

    def move_item(self, step: int) -> None:
        """Move the current item up (-1) or down (1)."""
        row = self.list.currentRow()
        target = row + step
        if row < 0 or not 0 <= target < self.list.count():
            return
        item = self.list.takeItem(row)
        self.list.insertItem(target, item)
        self.list.setCurrentRow(target)
        self.changed.emit()

    def mark_lost(self, names: list[str]) -> None:
        """Show lost items first, in the error colour (P2.5 item 4, CLAUDE.md 5.12)."""
        lost = set(names)
        self.lost = lost & set(self.names())
        items = [self.list.takeItem(0) for _ in range(self.list.count())]
        first = [i for i in items if i is not None and _item_key(i) in lost]
        rest = [i for i in items if i is not None and _item_key(i) not in lost]
        for item in first + rest:
            data = item.data(Qt.ItemDataRole.UserRole)
            label = ref_label(self.doc, data) if isinstance(data, dict) else item.text()
            if item in first:
                item.setText(strings.PICK_LOST.format(item=label))
                item.setForeground(QBrush(QColor(chrome().danger)))
            else:
                item.setText(label)
                item.setData(Qt.ItemDataRole.ForegroundRole, None)
            self.list.addItem(item)
        self._lost_changed()


def _key(ref: dict[str, Any]) -> str:
    if "rule" in ref:  # TR320 (D1408)
        return f"rule:{ref['rule']}:{ref.get('feature', '')}:{ref.get('axis', '')}"
    if "convexity" in ref:
        return f"{ref['convexity']}:{ref.get('feature', '')}"
    if "name" in ref:
        return str(ref["name"])
    if "sketch_entity" in ref:
        return f"{ref.get('feature', '')}:{ref['sketch_entity']}"
    return str(ref.get("feature", ""))


def _place(ref: dict[str, Any]) -> list[float] | None:
    """Where a picked edge or face is: the point its snapshot keeps, or None."""
    snapshot = ref.get("snapshot")
    if not isinstance(snapshot, dict):
        return None
    point = snapshot.get("midpoint", snapshot.get("point"))
    if isinstance(point, list | tuple) and len(point) == 3:
        return [float(v) for v in point]
    return None


def _same_pick(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """True when two references are the same pick: the same name and, when both say
    where they are, the same place (D1051). An edge is named by the two faces it lies
    between, and two faces can meet in more than one edge: a tube through a plate, a
    joint cut in two. The second of two such edges was refused as already listed, with
    nothing said, so it could not be picked at all."""
    if _key(a) != _key(b):
        return False
    one, two = _place(a), _place(b)
    if one is None or two is None:
        return True
    return sum((x - y) ** 2 for x, y in zip(one, two, strict=True)) < 1e-10


def _item_key(item: QListWidgetItem) -> str:
    data = item.data(Qt.ItemDataRole.UserRole)
    return _key(data) if isinstance(data, dict) else ""


def _soft_breaks(text: str) -> str:
    """Let long names such as ``edge(f6/cap/end|f8/side/e4)`` wrap inside a narrow panel."""
    for mark in ("/", "|", "(", ","):
        text = text.replace(mark, mark + "​")
    return text


class _FixButton(QPushButton):
    """A fix button that shortens its text to the panel width; the tooltip keeps the full text."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self._full = text
        self.setToolTip(text)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self._elide()

    def _elide(self) -> None:
        room = max(self.width() - 16, 40)
        self.setText(self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideMiddle, room))

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802  (Qt override)
        """Re-fit the text when the panel width changes."""
        super().resizeEvent(event)
        self._elide()


class CheckBox(QWidget):
    """The pre check result: what fails, and fix buttons the user may click."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("check_box")
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.label.setObjectName("panel_message")
        self.buttons = QVBoxLayout()
        self.buttons.setContentsMargins(0, 0, 0, 0)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)
        layout.addLayout(self.buttons)
        self.hide()

    def show_result(self, text: str, fixes: list[tuple[str, Callable[[], None]]]) -> None:
        """Show ``text`` and one button per fix; an empty text hides the box."""
        while self.buttons.count():
            child = self.buttons.takeAt(0)
            widget = child.widget() if child is not None else None
            if widget is not None:
                widget.deleteLater()
        self.label.setText(_soft_breaks(text))
        for label, action in fixes:
            button = _FixButton(label)
            button.setObjectName("fix_button")
            button.clicked.connect(action)
            self.buttons.addWidget(button)
        self.setVisible(bool(text))


class FeatureForm(QObject):
    """Base class: builds groups into the panel, writes values and takes picks."""

    changed = Signal()
    #: Parameters kept for the next new feature of this type (P2.4 item 1).
    remembered_keys: ClassVar[tuple[str, ...]] = ()
    #: The value field that takes focus and the drag handle first.
    first_param: ClassVar[str] = ""

    def __init__(self, panel: PropertyPanel, feature: Feature) -> None:
        super().__init__(panel)
        self.panel = panel
        assert panel.session is not None
        self.session = panel.session
        self.doc = panel.session.document
        self.feature = feature
        self.fields: dict[str, ValueField] = {}
        self.check = CheckBox()

    # Helpers ----------------------------------------------------------------------

    def group(self, key: str, title: str, tooltip: str, checkable: bool = False) -> Group:
        """Add a group to the panel."""
        return self.panel.add_form_group(key, Group(title, tooltip, checkable=checkable))

    def field(
        self,
        group: Group,
        name: str,
        kind: Kind,
        tooltip: str,
        default: tuple[str, float],
        icon_name: str = "",
    ) -> ValueField:
        """A typed value field for parameter ``name``, filled from the feature or ``default``."""
        current = self.feature.params.get(name)
        if not isinstance(current, Param):
            text, value = default
            current = Param(text, value)
        field = self.panel.make_field(kind, current)
        field.setToolTip(tooltip)
        field.edit.textChanged.connect(lambda _t: self.changed.emit())
        field.edit.returnPressed.connect(self.panel.accept)
        field.edit.setProperty("param_name", name)
        field.edit.installEventFilter(self.panel)
        self.fields[name] = field
        icon = icon_name or ("field.angle" if kind is Kind.ANGLE else "field.depth")
        group.form.addRow(with_icon(icon, tooltip, field))
        return field

    def write_fields(self, feature: Feature, names: list[str] | None = None) -> str | None:
        """Write the named fields (all by default). Returns a message when one is wrong."""
        for name in names if names is not None else list(self.fields):
            field = self.fields.get(name)
            if field is None:
                continue
            param = field.param()
            if param is None:
                return strings.FIX_ERRORS
            feature.params[name] = param
        return None

    def own_ref(self, ref: dict[str, Any]) -> str | None:
        """Why ``ref`` cannot be used (made by this feature or a later one), or None."""
        order = [f.id for f in self.doc.features]
        mine = order.index(self.feature.id) if self.feature.id in order else len(order)
        if any(fid not in order or order.index(fid) >= mine for fid in referenced_ids(ref)):
            return strings.PICK_TOO_LATE.format(feature=self.feature.name)
        return None

    def body_before(self) -> NamedShape | None:
        """The part just before the edited feature, from the last rebuild."""
        from fdcad.core.features.preview import body_before

        report = self.session.report
        if report is None:
            return None
        return body_before(self.doc, self.feature, report.results)

    # Hooks ------------------------------------------------------------------------

    def build(self) -> None:
        """Add the form's groups."""

    def apply(self, feature: Feature) -> str | None:
        """Write the form into ``feature``. Returns a message when something is missing."""
        return None

    def for_preview(self, feature: Feature) -> Feature | None:
        """The copy to preview (None for no preview). Usually ``feature`` itself."""
        return feature

    def take_shapes(self, body: NamedShape, shapes: list[Any]) -> str | None:
        """Picks from the view. Returns a message for the status bar, or None."""
        return None

    def pick_lists(self) -> list[PickList]:
        """Every pick list of the form."""
        return [v for v in vars(self).values() if isinstance(v, PickList)]

    def mark_lost_picks(self, geometry: PreviewGeometry) -> None:
        """Show lost picks in every pick list, or clear the marks (TR125 item 1)."""
        error = geometry.error or ""
        lost = list(geometry.failed) if ("lost" in error or "missing reference" in error) else []
        for picks in self.pick_lists():
            if lost or picks.lost:
                picks.mark_lost(lost)
            if not picks.property("ghost_wired"):
                show = getattr(self.panel.window(), "show_lost_ghost", None)
                if show is not None:
                    picks.lost_selected.connect(show)
                    picks.setProperty("ghost_wired", True)

    def preview_checked(self, geometry: PreviewGeometry) -> None:
        """The preview finished: show what failed and offer the fixes."""
        self.mark_lost_picks(geometry)
        if geometry.error and geometry.failed:
            self.show_failed(geometry.error, geometry.failed, geometry.fixes)
        elif geometry.error:
            self.check.show_result(geometry.error, [])
        else:
            self.check.show_result("", [])

    def show_failed(self, message: str, failed: list[str], fixes: list[Fix]) -> None:
        """Show the failing items and the fixes as buttons (never applied by themselves)."""
        self.check.show_result(message, [(f.label, self._fix_action(f)) for f in fixes])

    def _fix_action(self, fix: Fix) -> Callable[[], None]:
        def run() -> None:
            self.apply_fix(fix)

        return run

    def apply_fix(self, fix: Fix) -> None:
        """Do what a clicked fix button asks, in the panel (OK still applies it)."""

    def accepted(self, feature: Feature) -> None:
        """OK was pressed: remember the settings for the next new feature."""
        if self.remembered_keys:
            remember(feature, self.remembered_keys)


#: Form class for each feature type, filled by the form modules.
FORMS: dict[str, type[FeatureForm]] = {}


def form(ftype: str) -> Callable[[type[FeatureForm]], type[FeatureForm]]:
    """Class decorator: use the class as the panel form of ``ftype``."""

    def register(cls: type[FeatureForm]) -> type[FeatureForm]:
        FORMS[ftype] = cls
        return cls

    return register
