"""The Guide Curves group of Sweep and Loft (TR55, DECISIONS D804).

A list of guides: sketches or curve features chosen from a drop down and added
with Add, or model edges picked in the view while Pick Edges as Guides is ticked.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QPushButton, QWidget

from fdcad.ui import strings
from fdcad.ui.property_panel.forms.base import PickList

if TYPE_CHECKING:
    from fdcad.ui.property_panel.forms.base import FeatureForm
    from fdcad.ui.property_panel.groups import Group


class GuideBox:
    """The guide list, the sketch chooser and the pick tick of one form."""

    def __init__(self, form: FeatureForm, group: Group, stored: Any) -> None:
        from fdcad.ui.property_panel.forms.sweep_form import add_curves, sketch_box

        self.list = PickList(form.doc, strings.GUIDES_TIP)
        self.list.set_refs(stored if isinstance(stored, list) else [])
        self.chooser = sketch_box(form, None, strings.GUIDES_TIP)
        add_curves(form, self.chooser, None)
        self.chooser.setCurrentIndex(-1)
        add = QPushButton(strings.GUIDES_ADD)
        add.setToolTip(strings.GUIDES_ADD_TIP)
        add.clicked.connect(self.add_chosen)
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.chooser, 1)
        layout.addWidget(add)
        self.pick_edges = QCheckBox(strings.GUIDES_PICK)
        self.pick_edges.setToolTip(strings.GUIDES_PICK_TIP)
        group.form.addRow(self.list)
        group.form.addRow(row)
        group.form.addRow(self.pick_edges)
        self.list.changed.connect(form.changed.emit)

    def add_chosen(self) -> bool:
        """Add the chosen sketch or curve as a guide. False when none is chosen."""
        fid = self.chooser.currentData()
        if not isinstance(fid, str):
            return False
        return self.list.add({"feature": fid})

    def refs(self) -> list[dict[str, Any]]:
        """The guides in list order."""
        return self.list.refs()

    def take(self, ref: dict[str, Any]) -> bool:
        """Take a picked edge as a guide while the tick is on."""
        if not self.pick_edges.isChecked() or ref.get("kind") != "edge":
            return False
        self.list.add(ref)
        return True
