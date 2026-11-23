"""The property panel body for Phase 3 features, built from ``forms.Form``.

``FeatureForm`` fills the panel's groups, keeps the fields in step with what
applies (hidden fields are not written), takes picks from the 3D view into
the active pick box and writes the edited copy of the feature. It edits a
copy only: the panel applies it with one undoable command on OK (CLAUDE.md
rule 3). Kernel work (region and piece lists) runs on the thread pool.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Sequence
from functools import partial
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QEvent, QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QKeyEvent, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.kernel import kernel_job
from fdcad.core.units import Kind
from fdcad.ui import strings_phase3 as text
from fdcad.ui.background import start_job
from fdcad.ui.body_tools.forms import (
    DATA_FIELDS,
    Field,
    Form,
    format_skip,
    parse_skip,
)
from fdcad.ui.property_panel.groups import Group

if TYPE_CHECKING:
    from fdcad.ui.property_panel.panel import PropertyPanel

#: Feature types a seed feature may be: boss or cut features with their own solid.
SEED_TYPES = ("extrude", "revolve")
#: Curve features a path box can take (as in the Sweep and Pipe panels).
CURVE_TYPES = ("helix", "projected_curve", "composite_curve", "contour")


def copyable(f: Feature) -> bool:
    """True when a pattern or mirror can copy ``f`` as a feature: a boss or cut, or a
    type whose copies are always one (a Hole Tool hole cuts; spec 2 section 20 item 1,
    D712). The list offers exactly what the core can copy."""
    from fdcad.core.features import REGISTRY

    if f.type == "sketch":
        return False
    from fdcad.core.features.patterns import NESTED_TYPES

    if f.type in NESTED_TYPES:  # TR141 (D1512): a pattern of features repeats whole
        return bool(f.refs.get("features"))
    ftype = REGISTRY.get(f.type)
    return (
        f.type in SEED_TYPES
        or "operation" in f.params
        or (ftype is not None and ftype.pattern_operation is not None)
    )


def ref_label(doc: Document, ref: dict[str, Any], body_index: int | None = None) -> str:
    """Short text for a stored pick."""
    if "sketch_entity" in ref:
        return f"{_feature_name(doc, ref.get('feature'))} {ref['sketch_entity']}"
    if isinstance(ref.get("axis"), str) and ref["axis"] in text.ORIGIN_AXES:
        return text.ORIGIN_AXES[ref["axis"]]
    if isinstance(ref.get("feature"), str) and "kind" not in ref:
        return _feature_name(doc, ref["feature"])
    if body_index is not None:
        return text.PICK_BODY.format(index=body_index + 1)
    return str(ref.get("name", "?"))


def _feature_name(doc: Document, fid: Any) -> str:
    try:
        return doc.feature(str(fid)).name
    except KeyError:
        return str(fid)


class PickBox(QWidget):
    """A list of picks from the view (faces, edges, vertices, bodies), with a plane or
    sketch list when the field takes planes or sketches."""

    changed = Signal()
    activated = Signal(str)  # field name
    hovered = Signal(list)  # names to highlight

    def __init__(self, spec: Field, doc: Document, before: list[Feature]) -> None:
        super().__init__()
        self.spec = spec
        self.doc = doc
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.combo: QComboBox | None = None
        takes = set(spec.accept)
        if takes & {"plane", "sketch", "axis", "curve"}:
            self.combo = QComboBox()
            self.combo.addItem(text.NO_PLANE, None)
            for f in before:
                if ("plane" in takes and f.type in ("plane", "ref_plane")) or (
                    "sketch" in takes and f.type == "sketch"
                ):
                    self.combo.addItem(f.name, {"feature": f.id})
                if "axis" in takes and f.type == "ref_axis":
                    self.combo.addItem(f.name, {"feature": f.id})
                if "curve" in takes and f.type in CURVE_TYPES:
                    # Curve features as a path (audit B item 17, D730).
                    self.combo.addItem(f.name, {"feature": f.id})
                if "axis" in takes and f.type == "origin":
                    # The origin's axes (spec 2 section 20 item 3, D712).
                    for key, label in text.ORIGIN_AXES.items():
                        self.combo.addItem(label, {"feature": f.id, "axis": key})
            self.combo.setToolTip(spec.tip)
            self.combo.activated.connect(self._combo_chosen)
            layout.addWidget(self.combo)
        self.list = QListWidget()
        self.list.setObjectName("pick_box")
        self.list.setToolTip(spec.tip)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        rows = 4 if spec.multiple else 1
        self.list.setFixedHeight(self.list.fontMetrics().height() * (rows + 1) + 8)
        self._rows = rows
        pick_menu(self.list, self.remove_selected, self.clear_all)  # TR206
        self.list.model().rowsInserted.connect(lambda *_a: self._grow())
        self.list.model().rowsRemoved.connect(lambda *_a: self._grow())
        self.list.installEventFilter(self)
        self.list.itemSelectionChanged.connect(self._selection)
        layout.addWidget(self.list)

    # Contents ------------------------------------------------------------------------

    def refs(self) -> list[dict[str, Any]]:
        """The stored picks, in order."""
        out = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            data = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
            if isinstance(data, dict):
                out.append(copy.deepcopy(data))
        return out

    def value(self) -> Any:
        """A list for multiple picks, else one pick or None."""
        refs = self.refs()
        if self.spec.multiple:
            return refs
        return refs[0] if refs else None

    def set_value(self, value: Any, labels: Callable[[dict[str, Any]], str]) -> None:
        """Fill from stored refs."""
        self.list.clear()
        items = value if isinstance(value, list) else ([value] if isinstance(value, dict) else [])
        for ref in items:
            self._append(ref, labels(ref))
        if self.combo is not None and not self.spec.multiple and isinstance(value, dict):
            index = self.combo.findData(value) if "kind" not in value else -1
            self.combo.setCurrentIndex(max(index, 0))

    def _append(self, ref: dict[str, Any], label: str) -> None:
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, copy.deepcopy(ref))
        self.list.addItem(item)

    def add(self, ref: dict[str, Any], label: str, by_label: bool = False) -> None:
        """Add a pick. A single box replaces its pick; a list toggles an existing one.

        ``by_label``: a row with the same label is the same pick (any face of
        "Body 2" picks that body), so clicking the body again removes it.
        """
        same = [
            i
            for i in range(self.list.count())
            if _same_ref(self.list.item(i).data(Qt.ItemDataRole.UserRole), ref)
            or (by_label and self.list.item(i).text() == label)
        ]
        if not self.spec.multiple:
            self.list.clear()
            self._append(ref, label)
        elif same:
            self.list.takeItem(same[0])
        else:
            self._append(ref, label)
        self.changed.emit()

    def _grow(self) -> None:
        if self.spec.multiple:
            grow(self.list, self._rows, 10)  # the box grows with its list (TR206)

    def clear_all(self) -> None:
        """Clear Selections: remove every pick."""
        if self.list.count():
            self.list.clear()
            self.changed.emit()

    def remove_selected(self) -> None:
        """Delete the selected rows."""
        for item in self.list.selectedItems():
            self.list.takeItem(self.list.row(item))
        self.changed.emit()

    def _combo_chosen(self, index: int) -> None:
        assert self.combo is not None
        data = self.combo.itemData(index)
        if isinstance(data, dict):
            self.add(data, self.combo.itemText(index))
        elif not self.spec.multiple:
            self.list.clear()
            self.changed.emit()

    def _selection(self) -> None:
        names = []
        for item in self.list.selectedItems():
            data = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, dict) and isinstance(data.get("name"), str):
                names.append(data["name"])
        self.hovered.emit(names)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Delete removes rows; focus makes this the box that takes view picks."""
        if watched is self.list:
            if event.type() == QEvent.Type.FocusIn:
                self.activated.emit(self.spec.name)
            elif (
                event.type() == QEvent.Type.KeyPress
                and isinstance(event, QKeyEvent)
                and event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace)
            ):
                self.remove_selected()
                return True
        return super().eventFilter(watched, event)

    def set_active(self, active: bool) -> None:
        """Mark the box that takes picks from the view."""
        if bool(self.list.property("active")) != active:
            self.list.setProperty("active", active)
            self.list.style().unpolish(self.list)
            self.list.style().polish(self.list)


def _built_default(ftype: str, name: str, fallback: Any) -> Any:
    """The value a feature type builds with when ``name`` is missing (a bool), or ``fallback``."""
    from fdcad.core.features import REGISTRY

    kind = REGISTRY.get(ftype)
    for param in kind.params if kind is not None else ():
        if param.name == name and isinstance(param.default, bool):
            return param.default
    return fallback


def _group_on(feature: Feature, toggle: str, fields: Sequence[Field]) -> bool:
    """True when a group with a tick box starts ticked.

    A tick that only the panel stores (the feature type does not read it, such as
    the sheet metal "own relief" groups) is also on when the feature has a value for
    one of the group's fields: the feature builds with those values, so they must
    not be dropped by the next OK.
    """
    if feature.params.get(toggle) is True:
        return True
    from fdcad.core.features import REGISTRY

    kind = REGISTRY.get(feature.type)
    if kind is None or any(p.name == toggle for p in kind.params) or toggle in feature.params:
        return False
    return any(f.name in feature.params or f.name in feature.refs for f in fields)


def _same_ref(a: Any, b: Any) -> bool:
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False
    keys = ("kind", "name", "feature", "sketch_entity")
    return all(a.get(k) == b.get(k) for k in keys)


class FeatureList(QListWidget):
    """Tick list of earlier boss and cut features (pattern and mirror seeds)."""

    changed = Signal()

    def __init__(self, before: list[Feature], chosen: Any) -> None:
        super().__init__()
        picked = {r.get("feature") for r in chosen or [] if isinstance(r, dict)}
        for f in before:
            if copyable(f):
                item = QListWidgetItem(f.name)
                item.setData(Qt.ItemDataRole.UserRole, f.id)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.CheckState.Checked if f.id in picked else Qt.CheckState.Unchecked
                )
                self.addItem(item)
        self.setFixedHeight(self.fontMetrics().height() * 5 + 8)
        self.itemChanged.connect(lambda _i: self.changed.emit())

    def value(self) -> list[dict[str, str]]:
        """The ticked features as references."""
        out = []
        for i in range(self.count()):
            item = self.item(i)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                out.append({"feature": str(item.data(Qt.ItemDataRole.UserRole))})
        return out

    def tick(self, fid: str) -> None:
        """Tick a feature (clicked in the tree)."""
        for i in range(self.count()):
            item = self.item(i)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == fid:
                item.setCheckState(Qt.CheckState.Checked)


class ResultList(QWidget):
    """Numbered results to tick (split bodies) or untick (intersect regions)."""

    changed = Signal()
    refresh_requested = Signal()
    save_requested = Signal()

    def __init__(self, spec: Field, stored: Any) -> None:
        super().__init__()
        self.spec = spec
        self.stored = list(stored) if isinstance(stored, list) else None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        buttons = QHBoxLayout()
        self.button = QPushButton(text.CUT_BUTTON if spec.kind == "pieces" else text.SELECT_ALL)
        buttons.addWidget(self.button)
        self.invert = QPushButton(text.INVERT)
        buttons.addWidget(self.invert)
        self.invert.setVisible(spec.kind == "regions")
        layout.addLayout(buttons)
        self.hint = QLabel(text.CUT_HINT if spec.kind == "pieces" else "")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        self.list = QListWidget()
        self.list.setFixedHeight(self.list.fontMetrics().height() * 5 + 8)
        layout.addWidget(self.list)
        self.list.itemChanged.connect(self._item_changed)
        self._ticks: dict[int, bool] = {}
        # Split: save the ticked bodies to files (PHASE3_SPEC P3.4 item 3, D528).
        save_row = QHBoxLayout()
        self.format = QComboBox()
        for key, label in text.SAVE_FORMATS.items():
            self.format.addItem(label, key)
        self.format.setToolTip(text.SAVE_FORMAT_TIP)
        save_row.addWidget(self.format)
        self.save = QPushButton(text.SAVE_BODIES)
        self.save.setToolTip(text.SAVE_BODIES_TIP)
        self.save.setEnabled(False)
        save_row.addWidget(self.save)
        layout.addLayout(save_row)
        self.format.setVisible(spec.kind == "pieces")
        self.save.setVisible(spec.kind == "pieces")
        if spec.kind == "pieces":
            self.button.clicked.connect(self.refresh_requested.emit)
            self.save.clicked.connect(self.save_requested.emit)
        else:
            self.button.clicked.connect(lambda: self._set_all(True))
            self.invert.clicked.connect(self._invert)

    def show_items(
        self, count: int, labels: list[str] | None = None, numbers: list[int] | None = None
    ) -> None:
        """List ``count`` numbered results, ticked as stored.

        ``numbers`` lists only some result numbers (Intersect shows the regions
        of the chosen kind). Regions keep the ticks the user already changed.
        """
        if self.spec.kind == "regions" and self.list.count():
            self.stored = self.value()
        self.list.blockSignals(True)
        self.list.clear()
        self._ticks = {}
        word = text.PIECE if self.spec.kind == "pieces" else text.REGION
        for k in numbers if numbers is not None else range(1, count + 1):
            label = labels[k - 1] if labels and k <= len(labels) else word.format(index=k)
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, k)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            if self.spec.kind == "pieces":
                on = self.stored is None or k in self.stored
                # Double click to name the body's file (D528).
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                item.setToolTip(text.PIECE_NAME_TIP)
            else:
                on = self.stored is None or k not in self.stored
            item.setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
            self._ticks[k] = on
            self.list.addItem(item)
        self.list.blockSignals(False)
        self.hint.setText("" if count or self.spec.kind == "pieces" else text.NO_REGIONS)
        self.save.setEnabled(count > 0)

    def clear_cut(self) -> None:
        """Split: forget the listed bodies and their ticks; every body is kept until Cut."""
        self.list.blockSignals(True)
        self.list.clear()
        self.list.blockSignals(False)
        self._ticks = {}
        self.stored = None
        self.hint.setText(text.CUT_HINT)
        self.save.setEnabled(False)

    def _item_changed(self, item: QListWidgetItem) -> None:
        """A tick changes the result; a new file name changes nothing in the part."""
        k = int(item.data(Qt.ItemDataRole.UserRole))
        on = item.checkState() == Qt.CheckState.Checked
        if self._ticks.get(k) != on:
            self._ticks[k] = on
            self.changed.emit()

    def file_names(self) -> dict[int, str]:
        """Split: the ticked body numbers and the names typed for their files."""
        out: dict[int, str] = {}
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                out[int(item.data(Qt.ItemDataRole.UserRole))] = item.text().strip()
        return out

    def show_message(self, message: str) -> None:
        """Show what saving did, under the buttons."""
        self.hint.setText(message)

    def value(self) -> list[int] | None:
        """Split: the kept numbers. Intersect: the excluded numbers. None before Cut."""
        if self.list.count() == 0:
            return self.stored
        ticked: list[int] = []
        unticked: list[int] = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item is None:
                continue
            k = int(item.data(Qt.ItemDataRole.UserRole))
            (ticked if item.checkState() == Qt.CheckState.Checked else unticked).append(k)
        if self.spec.kind == "pieces":
            return None if not unticked else ticked
        return sorted(unticked) or None

    def _set_all(self, on: bool) -> None:
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item is not None:
                item.setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)

    def _invert(self) -> None:
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item is not None:
                checked = item.checkState() == Qt.CheckState.Checked
                item.setCheckState(Qt.CheckState.Unchecked if checked else Qt.CheckState.Checked)


def _file_name(typed: str, part: str, k: int) -> str:
    """The typed name, or "<part> body <k>" when the row keeps its own label (D528)."""
    if not typed or typed == text.PIECE.format(index=k):
        return text.SAVE_DEFAULT_NAME.format(part=part, index=k)
    return typed


class _CountSignals(QObject):
    done = Signal(int, object)
    round = 0  # which count this is, so a late result of an older count is dropped


class _CountJob(QRunnable):
    """Counts split pieces or intersect regions on a worker thread (CLAUDE.md rule 2)."""

    def __init__(self, work: Callable[[], tuple[int, list[str]]]) -> None:
        super().__init__()
        self.work = work
        self.signals = _CountSignals()

    @kernel_job
    def run(self) -> None:
        try:
            count, labels = self.work()
        except Exception:  # a failed count just leaves the list empty
            count, labels = -1, []
        self.signals.done.emit(count, labels)


#: Optional choices that are not written while set to "none", so files stay as before.
OMIT_NONE = {"print_fit", "bend_notches"}


class FeatureForm(QObject):
    """Builds and reads the panel for one Phase 3 feature."""

    changed = Signal()
    face_added = Signal(object)  # the picked face (TopoDS_Face), for the helper bar
    highlight = Signal(list)  # names to show in the view

    def __init__(
        self,
        panel: PropertyPanel,
        form: Form,
        add_group: Callable[[str, Group], Group],
        variables: dict[str, tuple[Kind, float]],
    ) -> None:
        super().__init__(panel)
        assert panel.session is not None and panel.feature is not None
        self.panel = panel
        self.form = form
        self.feature: Feature = panel.feature
        self.doc = panel.session.document
        index = next(
            (i for i, f in enumerate(self.doc.features) if f.id == self.feature.id),
            len(self.doc.features),
        )
        self.before = self.doc.features[:index]
        self.widgets: dict[str, Any] = {}
        self.rows: dict[str, QWidget] = {}
        self.groups: list[tuple[Group, list[Field]]] = []
        self.active_pick: str | None = None
        self._jobs: set[_CountJob] = set()
        self._count_round = 0
        self._region_key: str | None = None
        for g_index, spec in enumerate(form.groups):
            group = add_group(f"p3_{g_index}", Group(spec.title, spec.title, bool(spec.toggle)))
            if spec.toggle:
                group.set_checked(_group_on(self.feature, spec.toggle, spec.fields))
                group.toggled.connect(lambda _on: self._changed())
                self.widgets[spec.toggle] = group
            self.groups.append((group, list(spec.fields)))
            for f in spec.fields:
                self._add_field(group, f, variables)
        #: The number of copies a Fill Pattern keeps, from the live preview (TR57).
        self.count_label: QLabel | None = None
        if self.feature.type == "fill_pattern" and self.groups:
            self.count_label = QLabel(text.FILL_COUNT_PENDING)
            self.count_label.setToolTip(text.FILL_COUNT_TIP.format(name=self.feature.name))
            self.groups[0][0].form.addRow(text.FILL_COUNT, self.count_label)
        if self.feature.type == "move_face" and "follow" in self.widgets:
            self._add_solution_steps()  # TR264 item 2
        self._update()
        self._list_regions()

    def _show_rule_effects(self, info: dict[str, float]) -> None:
        """Each ticked rule's tick box says how many faces it adds or holds (TR263 item 2)."""
        from fdcad.core.features.face_rules import HOLDING, RULES

        for rule in RULES:
            box = self.widgets.get(f"rule_{rule}")
            if box is None or not hasattr(box, "setText"):
                continue
            label = text.LABELS.get(f"rule_{rule}", rule)
            count = info.get(f"rule:{rule}")
            if count is None:
                box.setText(label)
            elif count == 0:
                box.setText(text.RULE_IDLE.format(label=label))
            else:
                how = text.RULE_HOLDS if rule in HOLDING else text.RULE_ADDS
                box.setText(how.format(label=label, count=int(count)))

    def _add_solution_steps(self) -> None:
        """Previous and Next Solution step the Neighbours choice round (TR264, D797)."""
        from PySide6.QtWidgets import QHBoxLayout, QPushButton

        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        for label, step in ((text.FOLLOW_PREVIOUS, -1), (text.FOLLOW_NEXT, 1)):
            button = QPushButton(label)
            button.setToolTip(text.FOLLOW_STEP_TIP)
            button.setObjectName(f"follow_step_{'next' if step > 0 else 'previous'}")
            button.clicked.connect(lambda _c=False, s=step: self.step_solution(s))
            layout.addWidget(button)
        group = next(g for g, fields in self.groups if any(f.name == "follow" for f in fields))
        group.form.addRow(row)
        self.rows["follow_steps"] = row

    def step_solution(self, step: int) -> None:
        """Choose the previous (-1) or next (1) way of following, wrapping round."""
        box = self.widgets.get("follow")
        if box is None or box.count() == 0:
            return
        box.setCurrentIndex((box.currentIndex() + step) % box.count())

    def preview_checked(self, geometry: Any) -> None:
        """A preview finished: show the values it measured (TR57 copy count, TR263 rule
        effects)."""
        self._show_rule_effects(getattr(geometry, "info", {}) or {})
        if self.count_label is None:
            return
        count = getattr(geometry, "info", {}).get("count")
        if getattr(geometry, "error", None) or count is None:
            self.count_label.setText(text.FILL_COUNT_PENDING)
        else:
            self.count_label.setText(str(int(count)))

    # Building ------------------------------------------------------------------------

    def _add_field(
        self, group: Group, spec: Field, variables: dict[str, tuple[Kind, float]]
    ) -> None:
        feature = self.feature
        if spec.kind == "value":
            from fdcad.ui.property_panel.panel import ValueField

            assert spec.value_kind is not None
            current = feature.params.get(spec.name)
            if not isinstance(current, Param):
                default = self.form.defaults.get(spec.name)
                current = Param(*default) if isinstance(default, tuple) else None
            row = ValueField(spec.value_kind, self.doc.units, variables, current)
            row.setToolTip(spec.tip)
            row.edit.textChanged.connect(self._changed)
            row.edit.returnPressed.connect(self.panel.accept)
            row.edit.installEventFilter(self.panel)
            row.edit.setProperty("param_name", spec.name)
            self.panel.values[spec.name] = row
            self.widgets[spec.name] = row
            group.form.addRow(spec.label, row)
            self.rows[spec.name] = row
            return
        widget: QWidget
        if spec.kind == "choice":
            box = QComboBox()
            for choice in spec.choices:
                box.addItem(text.CHOICES.get(choice, choice), choice)
            for choice in spec.disabled:
                index = box.findData(choice)
                model = box.model()
                item = model.item(index) if isinstance(model, QStandardItemModel) else None
                if item is not None:
                    item.setEnabled(False)
                    item.setToolTip(text.DELETE_GREYED)
            stored = feature.params.get(spec.name, spec.default)
            box.setCurrentIndex(max(box.findData(stored), 0))
            box.currentIndexChanged.connect(self._changed)
            widget = box
        elif spec.kind == "flag":
            check = QCheckBox(spec.label)
            default = (
                spec.default
                if spec.default is not None
                else self.form.defaults.get(spec.name, False)
            )
            if not self.panel.is_new and spec.name not in feature.params:
                # A saved feature without the flag builds with the type's own default.
                default = _built_default(feature.type, spec.name, default)
            check.setChecked(bool(feature.params.get(spec.name, default)))
            check.toggled.connect(self._changed)
            widget = check
        elif spec.kind == "picks":
            box_ = PickBox(spec, self.doc, self.before)
            label = partial(self._label, takes_body="body" in spec.accept)
            box_.set_value(feature.refs.get(spec.name), label)
            box_.changed.connect(self._changed)
            box_.activated.connect(self._activate)
            box_.hovered.connect(self.highlight.emit)
            widget = box_
        elif spec.kind == "features":
            widget = FeatureList(self.before, feature.refs.get("features"))
            widget.changed.connect(self._changed)
        elif spec.kind == "sketch":
            sk = QComboBox()
            sk.addItem(text.NO_PLANE, None)
            for f in self.before:
                if f.type == "sketch":
                    sk.addItem(f.name, f.id)
            current = (feature.refs.get(spec.name) or {}).get("feature")
            sk.setCurrentIndex(max(sk.findData(current), 0))
            sk.currentIndexChanged.connect(self._changed)
            widget = sk
        elif spec.kind == "table":  # TR58
            from fdcad.ui.body_tools.xy_table import XYTable

            widget = XYTable(feature.data.get(spec.name))
            widget.changed.connect(self._changed)
        elif spec.kind == "text":  # TR366 (D1018): a plain line kept in params
            line = QLineEdit(str(feature.params.get(spec.name, "") or ""))
            hint = spec.default if isinstance(spec.default, str) else None
            line.setPlaceholderText(
                hint
                or {
                    "angles": "30, 75, 160",
                    "vary": "depth 2",  # TR59 (D1513)
                    "instance_values": "3: depth 8",  # TR59 (D1900)
                }.get(spec.name.rstrip("12"), "0.1, 0.3, 1")
            )
            line.textChanged.connect(self._changed)
            widget = line
        elif spec.kind == "skip":
            edit = QLineEdit(format_skip(feature.data.get("skip")))
            edit.setPlaceholderText("3, 5, 2.2")
            edit.textChanged.connect(self._changed)
            widget = edit
        else:  # pieces, regions
            results = ResultList(spec, feature.data.get(spec.name))
            results.changed.connect(self._changed)
            results.refresh_requested.connect(self.count_results)
            results.save_requested.connect(lambda r=results: self.save_bodies(r))
            widget = results
        widget.setToolTip(spec.tip)
        self.widgets[spec.name] = widget
        if spec.kind == "flag":
            group.form.addRow(widget)
        else:
            group.form.addRow(spec.label, widget)
        self.rows[spec.name] = widget

    def _label(self, ref: dict[str, Any], takes_body: bool = False) -> str:
        """The text of a stored pick: "Body 2" in a box that takes bodies."""
        index = None
        report = self.panel.session.report if self.panel.session is not None else None
        has_body = report is not None and report.body is not None
        if ref.get("kind") == "face" and has_body and (takes_body or self._accepts_body(ref)):
            index = self._body_index(ref)
        return ref_label(self.doc, ref, index)

    def _accepts_body(self, ref: dict[str, Any]) -> bool:
        return any(
            isinstance(w, PickBox) and "body" in w.spec.accept and ref in w.refs()
            for w in self.widgets.values()
        )

    def _body_index(self, ref: dict[str, Any]) -> int | None:
        from fdcad.core.features.bodies import solid_of_face

        report = self.panel.session.report if self.panel.session is not None else None
        if report is None or report.body is None:
            return None
        face = report.body.face(str(ref.get("name", "")))
        if face is None:
            return None
        found = solid_of_face(report.body.shape, face)
        return found if found >= 0 else None

    # State ---------------------------------------------------------------------------

    def values(self) -> dict[str, Any]:
        """Every field's current value, for ``when`` tests."""
        out: dict[str, Any] = {}
        for name, widget in self.widgets.items():
            if isinstance(widget, Group):
                out[name] = widget.is_checked()
            elif isinstance(widget, QComboBox):
                out[name] = widget.currentData()
            elif isinstance(widget, QCheckBox):
                out[name] = widget.isChecked()
            elif isinstance(widget, (PickBox, FeatureList, ResultList)) or hasattr(
                widget, "set_rows"
            ):
                out[name] = widget.value()
            elif isinstance(widget, QLineEdit):
                out[name] = widget.text()
            else:
                out[name] = widget.edit.text()
        return out

    def shown_fields(self) -> list[Field]:
        """Fields that apply now, in order."""
        values = self.values()
        out = []
        for group, fields in self.groups:
            group_on = group.is_checked()
            for f in fields:
                if group_on and f.shown(values):
                    out.append(f)
        return out

    def _update(self) -> None:
        in_order = [f.name for f in self.shown_fields()]
        shown = set(in_order)
        values = self.values()
        for group, fields in self.groups:
            visible = False
            for f in fields:
                row = self.rows.get(f.name)
                on = f.name in shown or (not group.is_checked() and f.shown(values))
                if row is not None:
                    group.form.setRowVisible(row, f.name in shown)
                visible = visible or on
            group.setVisible(visible or group.check is not None)
        steps = self.rows.get("follow_steps")
        if steps is not None:  # TR264: the solution steps go with the Neighbours choice
            for group, fields in self.groups:
                if any(f.name == "follow" for f in fields):
                    group.form.setRowVisible(steps, "follow" in shown)
        if self.active_pick not in shown:
            # In panel order: a set's order would send clicks to a random pick box.
            picks = [n for n in in_order if isinstance(self.widgets.get(n), PickBox)]
            empty = [n for n in picks if not self.widgets[n].refs()]
            self._activate(next(iter(empty or picks), None))

    def next_pick(self) -> str | None:
        """Right click in the view (TR207, D831): make the next shown pick box active.
        Returns its label, or None when the active box is the last one."""
        order = [
            f.name for f in self.shown_fields() if isinstance(self.widgets.get(f.name), PickBox)
        ]
        if self.active_pick not in order:
            return None
        index = order.index(self.active_pick)
        if index + 1 >= len(order):
            return None
        name = order[index + 1]
        self._activate(name)
        spec = next((f for f in self.form.fields() if f.name == name), None)
        return spec.label if spec is not None else name

    def _activate(self, name: str | None) -> None:
        self.active_pick = name
        for key, widget in self.widgets.items():
            if isinstance(widget, PickBox):
                widget.set_active(key == name)

    def _changed(self) -> None:
        self._update()
        self._list_regions()
        self.changed.emit()

    def _list_regions(self) -> None:
        """Intersect: list the regions again when the picks or the region kind change.

        The region list appears by itself (PHASE3_SPEC P3.4 item 2), so regions can
        be excluded. Ticking a region does not count them again.
        """
        lists = [w for w in self.widgets.values() if isinstance(w, ResultList)]
        pieces = [w for w in lists if w.spec.kind == "pieces"]
        if pieces:
            # Split: other tools or bodies number the bodies anew, so the listed
            # bodies and their ticks no longer apply. Press Cut again.
            values = self.values()
            key = repr([values.get(k) for k in ("tools", "bodies")])
            if self._region_key is not None and key != self._region_key:
                self._count_round += 1  # a Cut still running counts the old tools
                for widget in pieces:
                    widget.clear_cut()
            self._region_key = key
            return
        if not any(w.spec.kind == "regions" for w in lists):
            return
        values = self.values()
        key = repr([values.get(k) for k in ("bodies", "planes", "regions")])
        if key == self._region_key:
            return
        self._region_key = key
        if values.get("bodies"):
            self.count_results()
        else:
            for widget in lists:
                widget.show_items(0)

    # Writing -------------------------------------------------------------------------

    def apply(self, feature: Feature) -> tuple[Feature | None, str]:
        """Write the fields into ``feature`` (a copy). Returns it, or None and what is wrong."""
        shown = self.shown_fields()
        shown_names = {f.name for f in shown}
        values = self.values()
        for name, widget in self.widgets.items():
            if isinstance(widget, Group):
                if widget.is_checked():
                    feature.params[name] = True
                else:
                    feature.params.pop(name, None)
        for spec in self.form.fields():
            name = spec.name
            if name not in shown_names:
                if spec.kind in ("picks", "features", "sketch"):
                    feature.refs.pop(name, None)
                elif spec.name in DATA_FIELDS:
                    feature.data.pop(name, None)
                elif spec.kind != "flag" or name not in self.form.defaults:
                    feature.params.pop(name, None)
                continue
            widget = self.widgets[name]
            if spec.kind == "value":
                param = widget.param()
                if param is None:
                    return None, f"{spec.label}: {widget.info.text()}"
                feature.params[name] = param
            elif spec.kind == "choice":
                if name in OMIT_NONE and values[name] == "none":
                    feature.params.pop(name, None)  # optional choices are left out (D413)
                else:
                    feature.params[name] = values[name]
            elif spec.kind == "flag":
                if values[name]:
                    feature.params[name] = True
                elif spec.default is True or self.form.defaults.get(name) is True:
                    # A flag that starts ticked keeps an explicit False, or reopening
                    # the panel would show it ticked again.
                    feature.params[name] = False
                else:
                    feature.params.pop(name, None)
            elif spec.kind == "picks":
                value = values[name]
                if value:
                    feature.refs[name] = value
                else:
                    feature.refs.pop(name, None)
            elif spec.kind == "features":
                if values[name]:
                    feature.refs[name] = values[name]
                else:
                    feature.refs.pop(name, None)
            elif spec.kind == "sketch":
                if isinstance(values[name], str):
                    feature.refs[name] = {"feature": values[name]}
                else:
                    feature.refs.pop(name, None)
            elif spec.kind == "table":
                if values[name] is None:
                    return None, text.TABLE_NOT_NUMBERS
                if values[name]:
                    feature.data[name] = values[name]
                else:
                    feature.data.pop(name, None)
            elif spec.kind == "text":
                line_text = str(values[name]).strip()
                if line_text:
                    feature.params[name] = line_text
                else:
                    feature.params.pop(name, None)
            elif spec.kind == "skip":
                parsed = parse_skip(str(values[name]))
                if parsed is None:
                    return None, text.SKIP_INVALID
                if parsed:
                    feature.data["skip"] = parsed
                else:
                    feature.data.pop("skip", None)
            else:
                result = values[name]
                if result:
                    feature.data[name] = result
                else:
                    feature.data.pop(name, None)
        return feature, ""

    # View picks ----------------------------------------------------------------------

    def take_pick(self, shapes: list[Any]) -> str | None:
        """Put shapes clicked in the view into the active pick box. Returns why not, or None."""
        from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX

        from fdcad.core.naming.select import is_planar_face, reference_for

        session = self.panel.session
        report = session.report if session is not None else None
        if not shapes or self.active_pick is None or report is None or report.body is None:
            return None
        box = self.widgets.get(self.active_pick)
        if not isinstance(box, PickBox):
            return None
        accept = set(box.spec.accept)
        problem = None
        for shape in shapes:
            kind = shape.ShapeType()
            fits = (
                (kind == TopAbs_FACE and bool(accept & {"face", "body"}))
                or (kind == TopAbs_FACE and "plane" in accept and is_planar_face(shape))
                or (kind == TopAbs_EDGE and "edge" in accept)
                or (kind == TopAbs_VERTEX and "vertex" in accept)
            )
            if not fits:
                problem = f"{box.spec.label}: pick {', '.join(sorted(accept))}."
                continue
            ref = reference_for(report.body, shape)
            if ref is None:
                continue
            label = ref_label(self.doc, ref)
            index = None
            if "body" in accept and kind == TopAbs_FACE:
                index = self._body_index(ref)
                label = ref_label(self.doc, ref, index)
            box.add(ref, label, by_label=index is not None)
            if kind == TopAbs_FACE and box.spec.name == "faces":
                self.face_added.emit(shape)
        if not box.spec.multiple:
            self._advance()
        return problem

    def add_faces(self, faces: list[Any]) -> None:
        """Add faces found by a helper button to the Faces box (no toggling off)."""
        from fdcad.core.naming.select import reference_for

        session = self.panel.session
        report = session.report if session is not None else None
        box = self.widgets.get("faces")
        if report is None or report.body is None or not isinstance(box, PickBox):
            return
        have = box.refs()
        for face in faces:
            ref = reference_for(report.body, face)
            if ref is not None and not any(_same_ref(ref, h) for h in have):
                box.add(ref, ref_label(self.doc, ref))
                have.append(ref)

    def _advance(self) -> None:
        """After a single pick, the next empty pick box takes the next click."""
        shown = [f.name for f in self.shown_fields()]
        picks = [n for n in shown if isinstance(self.widgets.get(n), PickBox)]
        empty = [n for n in picks if not self.widgets[n].refs()]
        if empty:
            self._activate(empty[0])

    # Handles -------------------------------------------------------------------------

    def set_value(self, name: str, value: float) -> bool:
        """A dragged handle set ``name`` (always a positive amount). Keeps the field's sign."""
        from fdcad.ui.property_panel.panel import typed_angle, typed_length

        widget = self.widgets.get(name)
        if widget is None or not hasattr(widget, "edit") or self.panel.session is None:
            return False
        if name in self.form.handle_modes and name not in {f.name for f in self.shown_fields()}:
            self._switch_mode(self.form.handle_modes[name])
        current = widget.param()
        negative = current is not None and current.value < 0
        if widget.kind is Kind.ANGLE:
            typed = typed_angle(abs(value))
        elif widget.kind is Kind.NUMBER:  # a scale factor (D411)
            typed = f"{round(abs(value), 4):g}"
        else:
            typed = typed_length(abs(value), self.panel.session.document.units)
        typed = f"-{typed}" if negative and abs(value) > 0 else typed
        if widget.edit.text() != typed:
            widget.edit.setText(typed)
        return True

    def _switch_mode(self, choices: dict[str, str]) -> None:
        """Set the choice fields a dragged handle needs, for example Rotate (D411)."""
        for key, choice in choices.items():
            box = self.widgets.get(key)
            if isinstance(box, QComboBox):
                index = box.findData(choice)
                if index >= 0 and box.currentIndex() != index:
                    box.setCurrentIndex(index)

    def flip(self, name: str) -> bool:
        """A handle was dragged past its start: flip Reverse, or the sign of a delta."""
        reverse = self.widgets.get("reverse")
        if name in ("distance", "angle") and isinstance(reverse, QCheckBox):
            reverse.setChecked(not reverse.isChecked())
            return True
        widget = self.widgets.get(name)
        if widget is None or not hasattr(widget, "edit"):
            return False
        typed = widget.edit.text().strip()
        if typed.startswith("="):
            return False  # never replace a formula
        widget.edit.setText(typed[1:] if typed.startswith("-") else f"-{typed}")
        return True

    # Result lists ----------------------------------------------------------------------

    def count_results(self) -> None:
        """List the split pieces or intersect regions (kernel work on the pool)."""
        session = self.panel.session
        if session is None or session.report is None:
            return
        feature, _problem = self.apply(copy.deepcopy(self.feature))
        if feature is None:
            return
        doc = copy.deepcopy(session.document)
        results = dict(session.report.results)
        ftype = feature.type

        def work() -> tuple[int, list[str]]:
            from fdcad.core.features.base import BuildContext
            from fdcad.core.features.preview import body_before
            from fdcad.core.features.solids import solids

            ctx = BuildContext(doc, body_before(doc, feature, results), results)
            if ftype == "split":
                from fdcad.core.features.split import Split

                named, _indices, _issues = Split().pieces(feature, ctx)
                return len(solids(named.shape)), []
            from fdcad.core.features.intersect import regions_of, wanted

            regions, depth, indices, _issues = regions_of(feature, ctx)
            keep = wanted(feature, depth, len(indices) == 1)
            return len(regions), [str(k + 1) for k in keep]

        self._count_round += 1
        round_ = self._count_round
        job = _CountJob(work)
        job.signals.round = round_
        job.signals.done.connect(self._counted)
        self._jobs.add(job)
        start_job(QThreadPool.globalInstance(), job)

    def save_bodies(self, results: ResultList) -> None:
        """Write each ticked split body to its own file (D528). The part is not changed."""
        session = self.panel.session
        if session is None or session.report is None:
            return
        names = results.file_names()
        if not names:
            results.show_message(text.SAVE_NONE)
            return
        from PySide6.QtWidgets import QFileDialog

        folder = QFileDialog.getExistingDirectory(results, text.SAVE_FOLDER_TITLE)
        if not folder:
            return
        feature, _problem = self.apply(copy.deepcopy(self.feature))
        if feature is None:
            return
        feature.data["keep"] = sorted(names)
        doc = copy.deepcopy(session.document)
        results_by_id = dict(session.report.results)
        fmt = str(results.format.currentData())
        part = session.path.stem if session.path else (session.name or text.SAVE_PART)
        from fdcad.core.appearance import part_color as color_of

        part_color = color_of(doc.appearance)

        def work() -> tuple[int, list[str]]:
            from fdcad.core.features.base import BuildContext
            from fdcad.core.features.preview import body_before
            from fdcad.core.features.split import Split
            from fdcad.core.io.export import ExportError
            from fdcad.core.io.save_bodies import save_bodies

            ctx = BuildContext(doc, body_before(doc, feature, results_by_id), results_by_id)
            kept = Split().kept_bodies(feature, ctx)
            bodies = [(_file_name(names.get(k, ""), part, k), shape) for k, shape in kept]
            try:
                # The part's colour, not the default grey (spec 2 section 20 item 12).
                written = save_bodies(bodies, folder, fmt, doc.units, color=part_color)
            except ExportError as exc:
                return -1, [str(exc)]
            return len(written), [folder]

        job = _CountJob(work)
        job.signals.done.connect(lambda count, info: self._saved(results, count, info))
        self._jobs.add(job)
        results.save.setEnabled(False)
        start_job(QThreadPool.globalInstance(), job)

    def _saved(self, results: ResultList, count: int, info: object) -> None:
        results.save.setEnabled(True)
        lines = list(info) if isinstance(info, list) else []
        if count >= 0:
            folder = lines[0] if lines else ""
            results.show_message(text.SAVED_BODIES.format(count=count, folder=folder))
        else:
            results.show_message(lines[0] if lines else text.SAVE_FAILED)

    def _counted(self, count: int, labels: object) -> None:
        """Show the counted results. A count that a newer one replaced is dropped."""
        self._jobs = {j for j in self._jobs if not j.signals.signalsBlocked()}
        if getattr(self.sender(), "round", self._count_round) != self._count_round:
            return
        import shiboken6

        for widget in self.widgets.values():
            # A count can arrive after the panel closed: skip deleted lists.
            if not isinstance(widget, ResultList) or not shiboken6.isValid(widget.list):
                continue
            if widget.spec.kind == "regions":
                numbers = [int(n) for n in labels] if isinstance(labels, list) else []
                widget.show_items(len(numbers) if count >= 0 else 0, numbers=numbers)
            elif count >= 0:
                widget.show_items(count)


__all__ = ["FeatureForm", "Param", "PickBox", "ref_label"]


def pick_menu(list_widget: Any, remove: Any, clear: Any) -> None:
    """Right click on a pick box: Delete and Clear Selections (TR206, D861)."""
    from PySide6.QtCore import Qt as _Qt
    from PySide6.QtWidgets import QMenu

    from fdcad.ui import strings as _s

    def show(pos: Any) -> None:
        menu = QMenu(list_widget)
        delete = menu.addAction(_s.PICK_DELETE)
        delete.setEnabled(bool(list_widget.selectedItems()))
        delete.triggered.connect(lambda _c=False: remove())
        wipe = menu.addAction(_s.PICK_CLEAR)
        wipe.setEnabled(list_widget.count() > 0)
        wipe.triggered.connect(lambda _c=False: clear())
        menu.popup(list_widget.mapToGlobal(pos))

    list_widget.setContextMenuPolicy(_Qt.ContextMenuPolicy.CustomContextMenu)
    list_widget.customContextMenuRequested.connect(show)


def grow(list_widget: Any, fewest: int, most: int) -> None:
    """Make a pick box tall enough for its rows, between ``fewest`` and ``most``."""
    rows = min(max(list_widget.count(), fewest), most)
    list_widget.setFixedHeight(list_widget.fontMetrics().height() * (rows + 1) + 8)
