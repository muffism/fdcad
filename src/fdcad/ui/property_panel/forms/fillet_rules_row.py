"""Fillet rules in the Fillet panel (TR320, DECISIONS D1408).

A rule kind list and Add Rule use the assistant's scope (a feature, or the whole
part for Parallel rules). Own radius gives the new rule its own radius. While Pick
Exclusions is pressed, edges clicked in the view are left out of the rule selected
in the items list.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QPushButton,
    QWidget,
)

from fdcad.core.document.model import Feature, Param
from fdcad.core.units import Kind
from fdcad.ui import strings
from fdcad.ui.themes.style import unit

if TYPE_CHECKING:
    from fdcad.core.naming.names import NamedShape
    from fdcad.ui.property_panel.forms.base import FeatureForm, PickList

#: The rule kinds in the list: (rule, axis).
CHOICES = (
    ("attach", None),
    ("free", None),
    ("feature", None),
    ("parallel", "x"),
    ("parallel", "y"),
    ("parallel", "z"),
)


class RulesRow(QWidget):
    """Rule kind, Add Rule, Own radius and Pick Exclusions."""

    def __init__(self, form_: FeatureForm, items: PickList, scope: QComboBox) -> None:
        super().__init__()
        self.form, self.items, self.scope = form_, items, scope
        self.kind = QComboBox()
        self.kind.setToolTip(strings.RULE_TIP)
        for rule, axis in CHOICES:
            label = strings.RULE_CHOICES[rule].format(axis=(axis or "").upper())
            self.kind.addItem(label, (rule, axis))
        self.add = QPushButton(strings.RULE_ADD)
        self.add.setToolTip(strings.RULE_TIP)
        self.add.clicked.connect(self.add_rule)
        self.own = QCheckBox(strings.RULE_OWN_RADIUS)
        self.own.setToolTip(strings.RULE_OWN_RADIUS_TIP)
        self.radius = form_.panel.make_field(Kind.LENGTH, Param("1", 1.0))
        self.radius.setToolTip(strings.RULE_OWN_RADIUS_TIP)
        self.exclude = QPushButton(strings.RULE_PICK_EXCLUDE)
        self.exclude.setCheckable(True)
        self.exclude.setToolTip(strings.RULE_PICK_EXCLUDE_TIP)
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setVerticalSpacing(unit(self.font()))  # as close as ``groups.stacked``
        # The kind and Add Rule each take a row: side by side they were wider than
        # the left panel's default width (D2790).
        layout.addWidget(self.kind, 0, 0, 1, 2)
        layout.addWidget(self.add, 1, 0, 1, 2)
        layout.addWidget(self.own, 2, 0)
        layout.addWidget(self.radius, 2, 1)
        layout.addWidget(self.exclude, 3, 0, 1, 2)
        #: The rule radii: param name to value, from the file and from Add Rule.
        self.radii: dict[str, Param] = {
            k: copy.deepcopy(v)
            for k, v in form_.feature.params.items()
            if k.startswith("rule_radius_") and isinstance(v, Param)
        }

    def add_rule(self) -> str | None:
        """Add the chosen rule for the scope's feature. A message when it needs one."""
        rule, axis = self.kind.currentData()
        fid = self.scope.currentData()
        ref: dict[str, Any] = {"rule": rule}
        if isinstance(fid, str):
            ref["feature"] = fid
        elif rule != "parallel":
            self.form.check.show_result(strings.RULE_NEEDS_FEATURE, [])
            return strings.RULE_NEEDS_FEATURE
        if axis:
            ref["axis"] = axis
        if self.own.isChecked():
            param = self.radius.param()
            if param is not None:
                used = [int(k.rsplit("_", 1)[1]) for k in self.radii]
                name = f"rule_radius_{max(used, default=0) + 1}"
                self.radii[name] = param
                ref["radius"] = name
        self.items.add(ref)
        return None

    def take(self, body: NamedShape, shapes: list[Any]) -> tuple[list[Any], str | None]:
        """While Pick Exclusions is pressed, picked edges are left out of the selected rule."""
        from OCP.TopAbs import TopAbs_EDGE

        if not self.exclude.isChecked():
            return shapes, None
        current = self.items.list.currentItem()
        data = current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        if not isinstance(data, dict) or "rule" not in data:
            return shapes, strings.RULE_SELECT_FIRST
        rest = []
        excluded = list(data.get("exclude", []))
        for shape in shapes:
            if shape.ShapeType() != TopAbs_EDGE:
                rest.append(shape)
                continue
            name = body.edge_name(shape)
            if name is not None and name not in excluded:
                excluded.append(name)
        data = dict(data, exclude=excluded)
        from fdcad.ui.property_panel.forms.base import ref_label

        current.setData(Qt.ItemDataRole.UserRole, data)
        current.setText(ref_label(self.form.doc, data))
        self.items.changed.emit()
        return rest, None

    def write(self, feature: Feature) -> None:
        """Store the radii the listed rules use, and drop the others."""
        for name in [n for n in feature.params if n.startswith("rule_radius_")]:
            del feature.params[name]
        for ref in feature.refs.get("auto_edges", []) or []:
            key = ref.get("radius") if isinstance(ref, dict) else None
            if isinstance(key, str) and key in self.radii:
                feature.params[key] = copy.deepcopy(self.radii[key])
