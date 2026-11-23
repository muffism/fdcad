"""Partial edge ends by picks for Fillet and Chamfer (TR64 item 5, DECISIONS D1401).

With Partial Edges set to Reference, a list holds two picks: the start and the end.
Vertices clicked in the view always go to it. While Pick Ends is pressed, flat
faces go to it too, so a face can set an end without being rounded.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from fdcad.ui import strings
from fdcad.ui.property_panel.forms.base import PickList

if TYPE_CHECKING:
    from fdcad.core.document.model import Feature
    from fdcad.core.naming.names import NamedShape
    from fdcad.ui.property_panel.forms.base import FeatureForm

REFS = "partial_ends"


class PartialEnds(QWidget):
    """The start and end picks of a partial range."""

    changed = Signal()

    def __init__(self, form_: FeatureForm) -> None:
        super().__init__()
        self.form = form_
        self.picks = PickList(form_.doc, strings.PARTIAL_ENDS_TIP, ordered=True)
        self.picks.setObjectName("partial_ends")
        stored = form_.feature.refs.get(REFS)
        self.picks.set_refs(stored if isinstance(stored, list) else [])
        self.picks.changed.connect(self.changed.emit)
        self.faces = QPushButton(strings.PARTIAL_ENDS_FACES)
        self.faces.setCheckable(True)
        self.faces.setToolTip(strings.PARTIAL_ENDS_FACES_TIP)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(strings.PARTIAL_ENDS_LABEL)
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addWidget(self.picks)
        layout.addWidget(self.faces)

    def take(self, body: NamedShape, shapes: list[Any]) -> tuple[list[Any], str | None]:
        """Take the vertices (and faces while Pick Ends is pressed); return the rest."""
        from OCP.TopAbs import TopAbs_FACE, TopAbs_VERTEX

        from fdcad.core.naming.select import reference_for

        rest: list[Any] = []
        problem = None
        for shape in shapes:
            kind = shape.ShapeType()
            wanted = kind == TopAbs_VERTEX or (kind == TopAbs_FACE and self.faces.isChecked())
            if not wanted:
                rest.append(shape)
                continue
            if len(self.picks.refs()) >= 2:
                problem = strings.PARTIAL_ENDS_FULL
                continue
            ref = reference_for(body, shape)
            if ref is None:
                continue
            refused = self.form.own_ref(ref)
            if refused:
                problem = refused
                continue
            self.picks.add(ref)
        return rest, problem

    def write(self, feature: Feature, used: bool) -> str | None:
        """Store the two picks when ``used``; a message when they are not two."""
        feature.refs.pop(REFS, None)
        if not used:
            return None
        refs = self.picks.refs()
        if len(refs) != 2:
            return strings.PARTIAL_ENDS_NEEDED
        feature.refs[REFS] = refs
        return None
