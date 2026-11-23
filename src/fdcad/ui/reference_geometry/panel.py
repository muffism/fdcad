"""Panel for reference planes, axes, points and coordinate systems (PHASE2_SPEC P2.10).

Up to three reference boxes: click one, then pick a face, edge or vertex in the
3D view, or choose a plane, axis or point from its menu. The method is guessed
from the picks until the user chooses one. The message line says what is still
missing; OK only works when the feature is fully defined and its preview built
(P2.10 item 1). Values accept units and formulas (T14.6).
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.datum import REFERENCE_TYPES, Vec3, pick_kind
from fdcad.core.features.ref_plane import SCREEN_KEYS, screen_normal
from fdcad.core.units import Kind, UnitSystem
from fdcad.ui import strings
from fdcad.ui.property_panel.header import PanelHeader
from fdcad.ui.property_panel.panel import ValueField, feature_icon_name
from fdcad.ui.reference_geometry.specs import GUESS, METHODS, PICK_KEYS, SPECS, MethodSpec
from fdcad.ui.themes.style import unit

#: Default text for new value fields.
_DEFAULTS = {"distance": "10", "angle": "45", "percent": "50", "crossing": "1"}


def describe(ref: dict[str, Any], names: dict[str, str]) -> str:
    """Short text for a picked reference."""
    if "feature" in ref:
        name = names.get(str(ref["feature"]), str(ref["feature"]))
        if "sketch_entity" in ref:
            return f"{name}: {ref['sketch_entity']}"
        return name
    kind = str(ref.get("kind", "")).capitalize()
    return f"{kind} {ref.get('name', '')}".strip()


class ReferencePanel(QWidget):
    """Edits a copy of a reference feature. ``changed`` sends the copy after each change."""

    changed = Signal(object)
    accepted = Signal()
    rejected = Signal()

    def __init__(
        self,
        feature: Feature,
        units: UnitSystem,
        variables: dict[str, tuple[Kind, float]],
        features: list[Feature],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("reference_panel")
        self.feature = copy.deepcopy(feature)
        self.units, self.variables = units, variables
        #: Earlier reference features that can be chosen from the box menus.
        self.choices = [f for f in features if f.type in (*REFERENCE_TYPES, "origin")]
        #: Earlier sketches, whose points, lines, arcs and circles can be picked (D718).
        before = (
            features[: [f.id for f in features].index(feature.id)]
            if any(f.id == feature.id for f in features)
            else features
        )
        self.sketches = [f for f in before if f.type == "sketch"]
        self.types = {f.id: f.type for f in features}
        self.names = {f.id: f.name for f in features}
        #: Picks by box index; the method is guessed from them until the user chooses.
        self.picks: list[dict[str, Any] | None] = [
            copy.deepcopy(self.feature.refs.get(k)) for k in PICK_KEYS
        ]
        self.method_chosen = any(p is not None for p in self.picks)
        self.active = 0
        self.preview_ok = False
        self.preview_message = ""
        self.fields: dict[str, ValueField] = {}
        self.checks: dict[str, QCheckBox] = {}
        #: The view direction of a Parallel to screen plane (D526), and where to read it.
        self.screen_normal: Vec3 | None = (
            screen_normal(self.feature) if self.feature.type == "ref_plane" else None
        )
        self.view_direction: Callable[[], Vec3 | None] = lambda: None
        # The header of the property panel (D2743): icon and name, then OK and Cancel
        # at equal width, words only. They were two small buttons with icons beside
        # the name, and OK's tick could not be seen once OK was the main button.
        u = unit(self.font())
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.header = PanelHeader(self.feature.name, feature_icon_name(self.feature))
        self.ok_button, self.cancel_button = self.header.ok_button, self.header.cancel_button
        self.ok_button.setToolTip(strings.PANEL_TIPS["ok"])
        self.cancel_button.setToolTip(strings.PANEL_TIPS["cancel"])
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.rejected.emit)
        outer.addWidget(self.header)
        layout = QVBoxLayout()
        layout.setContentsMargins(3 * u, 3 * u, 3 * u, 3 * u)  # 12 px, as the header
        layout.setSpacing(2 * u)
        outer.addLayout(layout, 1)
        layout.addWidget(QLabel(strings.REF_METHOD))
        self.method = QComboBox()
        for m in METHODS[self.feature.type]:
            self.method.addItem(strings.REF_METHODS.get(m, m), m)
        current = str(self.feature.params.get("method", self.method.itemData(0)))
        self.method.setCurrentIndex(max(0, self.method.findData(current)))
        self.method.activated.connect(self._method_chosen)
        layout.addWidget(self.method)
        self.boxes: list[QPushButton] = []
        self.rows: list[QWidget] = []
        for i in range(3):
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            box = QPushButton()
            box.setCheckable(True)
            box.setObjectName(f"reference_box_{i + 1}")
            box.clicked.connect(lambda _c=False, i=i: self.set_active(i))
            menu_button = QToolButton()
            menu_button.setText("...")
            menu_button.setToolTip(strings.REF_PICK_FEATURES)
            menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            menu_button.setMenu(self._feature_menu(i))
            clear = QToolButton()
            clear.setText("x")
            clear.setToolTip(strings.REF_PICK_CLEAR)
            clear.clicked.connect(lambda _c=False, i=i: self.clear_pick(i))
            h.addWidget(box, 1)
            h.addWidget(menu_button)
            h.addWidget(clear)
            layout.addWidget(row)
            self.boxes.append(box)
            self.rows.append(row)
        self.values_box = QVBoxLayout()
        layout.addLayout(self.values_box)
        self.use_view = QPushButton(strings.REF_USE_VIEW)
        self.use_view.setObjectName("reference_use_view")
        self.use_view.setToolTip(strings.REF_USE_VIEW_TIP)
        self.use_view.clicked.connect(self.capture_view)
        layout.addWidget(self.use_view)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setObjectName("reference_message")
        layout.addWidget(self.message)
        layout.addStretch(1)
        self._build_values()
        self._refresh()

    # Picks ---------------------------------------------------------------------------

    def _feature_menu(self, index: int) -> QMenu:
        menu = QMenu(self)
        for f in self.choices:
            if f.id == self.feature.id:
                continue
            name = strings.REF_PART_ORIGIN if f.type == "origin" else f.name
            action = menu.addAction(name)
            action.triggered.connect(
                lambda _c=False, fid=f.id, i=index: self.set_pick(i, {"feature": fid})
            )
        for f in self.sketches:
            self._sketch_menu(menu.addMenu(f.name), f, index)
        return menu

    def _sketch_menu(self, menu: QMenu, sketch: Feature, index: int) -> None:
        """A sketch's points, lines, arcs and circles as picks (audit B item 3, D718)."""
        from fdcad.core.sketch.model import Arc, Circle, Line, Point, sketch_from_data

        try:
            model = sketch_from_data(sketch.data)
        except (ValueError, KeyError, TypeError):
            return
        labels = {Point: strings.REF_SKETCH_POINT, Line: strings.REF_SKETCH_LINE}
        labels.update({Arc: strings.REF_SKETCH_ROUND, Circle: strings.REF_SKETCH_ROUND})
        for eid, ent in model.entities.items():
            label = labels.get(type(ent))
            if label is None:
                continue
            action = menu.addAction(label.format(id=eid))
            ref = {"feature": sketch.id, "sketch_entity": eid}
            action.triggered.connect(lambda _c=False, r=ref, i=index: self.set_pick(i, r))
        menu.setEnabled(not menu.isEmpty())

    @property
    def spec(self) -> MethodSpec:
        """What the current method asks for."""
        return SPECS[self.feature.type][self.method_name]

    @property
    def method_name(self) -> str:
        """The current method."""
        return str(self.method.currentData())

    def set_active(self, index: int) -> None:
        """Make box ``index`` take the next pick in the view."""
        self.active = index
        self._refresh()

    def take_pick(self, ref: dict[str, Any]) -> None:
        """A pick from the 3D view goes into the active box; the next empty box gets active."""
        self.set_pick(self.active, ref)

    def set_pick(self, index: int, ref: dict[str, Any]) -> None:
        """Put ``ref`` in box ``index`` and guess the method when it was not chosen."""
        self.picks[index] = copy.deepcopy(ref)
        if not self.method_chosen:
            self._guess()
        count = self._box_count()
        empty = [i for i in range(count) if self.picks[i] is None]
        self.active = empty[0] if empty else min(index + 1, max(count - 1, 0))
        self._changed()

    def _box_count(self) -> int:
        """Boxes on show: the method's, plus one more while the method is still guessed."""
        count = len(self.spec.picks)
        if not self.method_chosen and GUESS.get(self.feature.type) is not None:
            filled = sum(1 for p in self.picks if p is not None)
            count = max(count, min(filled + 1, 3))
        return count

    def clear_pick(self, index: int) -> None:
        """Empty box ``index``."""
        self.picks[index] = None
        self.active = index
        self._changed()

    def _guess(self) -> None:
        guess = GUESS.get(self.feature.type)
        if guess is None:
            return
        kinds = [pick_kind(p, self.types) for p in self.picks if p is not None]
        method = guess(kinds)
        if method is not None and method != self.method_name:
            self.method.setCurrentIndex(self.method.findData(method))
            self._build_values()

    def _method_chosen(self) -> None:
        self.method_chosen = True
        self._build_values()
        self._take_view_once()
        self._changed()

    def _take_view_once(self) -> None:
        """A Parallel to screen plane takes the view direction when first chosen (D526)."""
        if self.method_name == "screen" and self.screen_normal is None:
            self.screen_normal = self.view_direction()

    def capture_view(self) -> None:
        """Use Current View: take the view direction again as the plane normal (D526)."""
        direction = self.view_direction()
        if direction is not None:
            self.screen_normal = direction
        self._changed()

    # Values --------------------------------------------------------------------------

    def _build_values(self) -> None:
        while self.values_box.count():
            item = self.values_box.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        self.fields, self.checks = {}, {}
        for name, kind in self.spec.values:
            current = self.feature.params.get(name)
            param = current if isinstance(current, Param) else None
            if param is None:
                param = Param(_DEFAULTS.get(name, "0"), 0.0)
            label = QLabel(strings.REF_VALUES.get(name, name))
            field = ValueField(kind, self.units, self.variables, param)
            field.setObjectName(f"reference_value_{name}")
            field.edit.textChanged.connect(self._changed)
            self.values_box.addWidget(label)
            self.values_box.addWidget(field)
            self.fields[name] = field
        for name in self.spec.checks:
            box = QCheckBox(strings.REF_CHECKS.get(name, name))
            box.setChecked(bool(self.feature.params.get(name, False)))
            box.toggled.connect(self._changed)
            self.values_box.addWidget(box)
            self.checks[name] = box
        self.count_box: QSpinBox | None = None  # TR148 (D1925): several at once
        self.spacing_box: QComboBox | None = None
        if self.repeats():
            from fdcad.core.features.datum_series import MAX_COUNT

            label = QLabel(strings.REF_HOW_MANY)
            self.count_box = QSpinBox()
            self.count_box.setObjectName("reference_count")
            self.count_box.setRange(1, MAX_COUNT)
            self.count_box.setToolTip(strings.REF_HOW_MANY_TIP)
            self.values_box.addWidget(label)
            self.values_box.addWidget(self.count_box)
            if self.feature.type == "ref_point":
                self.spacing_box = QComboBox()
                self.spacing_box.setObjectName("reference_spacing")
                for key, text in strings.REF_POINT_SPACINGS.items():
                    self.spacing_box.addItem(text, key)
                self.values_box.addWidget(self.spacing_box)

    #: Set by the tool: a new feature may come with more like it (TR148, D1925).
    new_feature = False

    def repeats(self) -> bool:
        """True when this new feature can be made several times at once (TR148)."""
        kinds = {"ref_plane": ("offset", "angle"), "ref_point": ("along_curve",)}
        return self.new_feature and self.method_name in kinds.get(self.feature.type, ())

    def count(self) -> tuple[int, str]:
        """How many to make, and how points are spaced (TR148, D1925)."""
        count = self.count_box.value() if self.count_box is not None else 1
        spacing = self.spacing_box.currentData() if self.spacing_box is not None else None
        return count, str(spacing or "distance")

    # State ---------------------------------------------------------------------------

    def missing(self) -> str | None:
        """What is still needed before the feature is fully defined, or None."""
        spec = self.spec
        for i, what in enumerate(spec.picks):
            if self.picks[i] is None and i not in spec.optional:
                return strings.REF_NEEDS_PICK.format(what=what, index=i + 1)
        for field in self.fields.values():
            if field.param() is None:
                return field.info.text()
        if self.method_name == "screen" and self.screen_normal is None:
            return strings.REF_NEEDS_VIEW
        return None

    def current_feature(self) -> Feature:
        """The edited copy as it stands."""
        f = copy.deepcopy(self.feature)
        f.params = {"method": self.method_name}
        for name, field in self.fields.items():
            param = field.param()
            if param is not None and name.startswith("extra_") and abs(param.value) < 1e-12:
                continue  # TR149: an extra offset of 0 is not stored
            if param is not None:
                f.params[name] = param
        for name, box in self.checks.items():
            if box.isChecked():
                f.params[name] = True
        if self.method_name == "screen" and self.screen_normal is not None:
            for key, value in zip(SCREEN_KEYS, self.screen_normal, strict=True):
                f.params[key] = round(value, 12)
        f.refs = {}
        for i, key in enumerate(PICK_KEYS[: len(self.spec.picks)]):
            if self.picks[i] is not None:
                f.refs[key] = copy.deepcopy(self.picks[i])
        return f

    def set_preview(self, ok: bool, message: str) -> None:
        """The background preview finished: ``message`` is its error, if any."""
        self.preview_ok, self.preview_message = ok, message
        self._refresh()

    @property
    def fully_defined(self) -> bool:
        """True when nothing is missing and the preview built."""
        return self.missing() is None and self.preview_ok

    def _changed(self) -> None:
        self.preview_ok, self.preview_message = False, ""
        self._refresh()
        self.changed.emit(self.current_feature())

    def _refresh(self) -> None:
        self.use_view.setVisible(self.method_name == "screen")
        count = self._box_count()
        for i, (box, row) in enumerate(zip(self.boxes, self.rows, strict=True)):
            row.setVisible(i < count)
            pick = self.picks[i]
            box.setText(describe(pick, self.names) if pick else strings.REF_PICK_NONE)
            box.setChecked(i == self.active)
        missing = self.missing()
        if missing is not None:
            text = missing
        elif self.preview_message:
            text = self.preview_message
        elif not self.preview_ok:
            text = strings.REF_WORKING
        else:
            text = strings.REF_FULLY_DEFINED
        self.message.setText(text)
        self.ok_button.setEnabled(self.fully_defined)

    def accept(self) -> None:
        """OK: only when fully defined (P2.10 item 1)."""
        if self.fully_defined:
            self.accepted.emit()
