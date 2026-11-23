"""Face set pick lists for the face fillet, full round fillet and face to face chamfer
(DECISIONS D518 and D520).

Each set is a pick list with a title. A "Pick into" list chooses which set takes
the faces clicked in the view; after a pick it moves on to the next set, so the
common case (one face per set) needs no extra clicks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QLabel, QListView, QVBoxLayout, QWidget

from fdcad.ui import strings
from fdcad.ui.property_panel.forms.base import PickList
from fdcad.ui.property_panel.groups import with_icon

if TYPE_CHECKING:
    from fdcad.core.document.model import Feature
    from fdcad.core.naming.names import NamedShape
    from fdcad.ui.property_panel.forms.base import FeatureForm


class FaceSets(QWidget):
    """Named face pick lists, keyed by their ``refs`` key, with a target chooser."""

    changed = Signal()

    def __init__(self, form_: FeatureForm, sets: list[tuple[str, str]], tooltip: str) -> None:
        super().__init__()
        self.form = form_
        self.target = QComboBox()
        self.target.setToolTip(strings.PANEL_TIPS["face_set_target"])
        self.lists: dict[str, PickList] = {}
        self.labels: dict[str, QLabel] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(with_icon("view.shaded", self.target.toolTip(), self.target))
        stored = form_.feature.refs
        for key, title in sets:
            label = QLabel(title)
            picks = PickList(form_.doc, tooltip)
            refs = stored.get(key, [])
            picks.set_refs(refs if isinstance(refs, list) else [])
            picks.changed.connect(self.changed.emit)
            picks.list.itemPressed.connect(lambda _i, k=key: self.set_target(k))
            layout.addWidget(label)
            layout.addWidget(picks)
            self.lists[key] = picks
            self.labels[key] = label
            self.target.addItem(title, key)
        first_empty = next((k for k, p in self.lists.items() if not p.refs()), None)
        self.set_target(first_empty or sets[0][0])

    def set_target(self, key: str) -> None:
        """Send the next picks to set ``key``."""
        self.target.setCurrentIndex(max(self.target.findData(key), 0))

    def show_set(self, key: str, shown: bool) -> None:
        """Show or hide one set (the centre set is for the full round only)."""
        self.labels[key].setVisible(shown)
        self.lists[key].setVisible(shown)
        view = self.target.view()
        if isinstance(view, QListView):
            view.setRowHidden(self.target.findData(key), not shown)
        if not shown and self.target.currentData() == key:
            self.set_target(self.shown_keys()[0])

    def shown_keys(self) -> list[str]:
        """Keys of the visible sets, in order."""
        return [k for k in self.lists if not self.lists[k].isHidden()]

    def take(self, body: NamedShape, shapes: list[Any]) -> str | None:
        """Picked faces go to the chosen set; then the next set is chosen."""
        from fdcad.ui.property_panel.forms.shell_form import face_refs

        refs, problem = face_refs(self.form, body, shapes)
        key = str(self.target.currentData())
        added = False
        for ref in refs:
            added = self.lists[key].add(ref) or added
        keys = self.shown_keys()
        if added and key in keys:
            self.set_target(keys[(keys.index(key) + 1) % len(keys)])
        return problem

    def write(self, feature: Feature, keys: list[str]) -> bool:
        """Write the sets in ``keys`` into ``feature.refs``. False when one is empty."""
        complete = True
        for key, picks in self.lists.items():
            feature.refs.pop(key, None)
            if key not in keys:
                continue
            refs = picks.refs()
            if refs:
                feature.refs[key] = refs
            else:
                complete = False
        return complete

    def mark_lost(self, names: list[str]) -> None:
        """Show lost faces first in each set."""
        for picks in self.lists.values():
            picks.mark_lost(names)
