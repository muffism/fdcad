"""The Bodies box of cuts, bosses and holes in a multibody part (TR33, D697).

All bodies (the default, the behaviour before) or Selected bodies, picked in the
view: a click on any face of a body adds that body. Stored as ``bodies_scope``
and one face reference per body in ``refs.bodies`` (D233 item 1).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QVBoxLayout, QWidget

from fdcad.core.document.model import Document, Feature
from fdcad.ui import strings_extra as text
from fdcad.ui.property_panel.forms.base import PickList

#: Feature types that have the box (cuts and bosses alike; holes only cut).
TYPES = ("extrude", "revolve", "sweep", "loft", "hole")


class BodiesBox(QWidget):
    """All bodies or Selected bodies, with the picked bodies listed."""

    changed = Signal()

    def __init__(self, doc: Document, feature: Feature) -> None:
        super().__init__()
        self.scope = QComboBox()
        self.scope.setObjectName("bodies_scope")
        self.scope.addItem(text.BODIES_ALL, "all")
        self.scope.addItem(text.BODIES_SELECTED, "selected")
        self.scope.setToolTip(text.BODIES_TIP)
        self.picks = PickList(doc, text.BODIES_PICK_TIP)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scope)
        layout.addWidget(self.picks)
        selected = feature.params.get("bodies_scope") == "selected"
        self.scope.setCurrentIndex(1 if selected else 0)
        refs = feature.refs.get("bodies")
        self.picks.set_refs(list(refs) if isinstance(refs, list) else [])
        self._show()
        self.scope.currentIndexChanged.connect(self._scope_changed)
        self.picks.changed.connect(self.changed.emit)

    def _show(self) -> None:
        self.picks.setVisible(self.selected())

    def _scope_changed(self) -> None:
        self._show()
        self.changed.emit()

    def selected(self) -> bool:
        """True with Selected bodies."""
        return bool(self.scope.currentData() == "selected")

    def wants_pick(self) -> bool:
        """True while view picks go to this box."""
        return self.selected()

    def take(self, body: Any, shapes: list[Any]) -> str | None:
        """Add the bodies of the picked faces (one face reference per body)."""
        from OCP.TopAbs import TopAbs_FACE

        from fdcad.core.features.bodies import solid_of_face
        from fdcad.core.naming.select import reference_for

        added = False
        have = set()
        for ref in self.picks.refs():
            from fdcad.core.features.lookup import resolve_face

            try:
                face, _issues = resolve_face(body, ref, "")
            except Exception:  # a lost pick: leave it listed, the rebuild names it
                continue
            have.add(solid_of_face(body.shape, face))
        for shape in shapes:
            if shape.ShapeType() != TopAbs_FACE:
                continue
            index = solid_of_face(body.shape, shape)
            if index < 0 or index in have:
                continue
            found = reference_for(body, shape)
            if found is None:
                continue
            ref = found
            have.add(index)
            added = self.picks.add(ref, text.BODY_PICK.format(index=index + 1)) or added
        return None if added else text.BODIES_PICK_FACE

    def apply(self, feature: Feature) -> str | None:
        """Write the scope and the picks. Returns a message when Selected has none."""
        if not self.selected():
            feature.params.pop("bodies_scope", None)
            feature.refs.pop("bodies", None)
            return None
        refs = self.picks.refs()
        if not refs:
            return text.BODIES_NONE
        feature.params["bodies_scope"] = "selected"
        feature.refs["bodies"] = refs
        return None


def wanted(doc: Document, feature: Feature, results: Any) -> bool:
    """True when the feature takes the box: its type has one and the part has two or
    more bodies before it."""
    from fdcad.core.features.preview import body_before
    from fdcad.core.features.solids import solids

    if feature.type not in TYPES:
        return False
    if feature.params.get("bodies_scope") == "selected":
        return True
    body = body_before(doc, feature, results) if results is not None else None
    return body is not None and len(solids(body.shape)) > 1
