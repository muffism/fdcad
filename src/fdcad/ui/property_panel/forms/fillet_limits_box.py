"""Fillet Limits group: Edges to Keep and a limiting plane (TR271, DECISIONS D1407).

While Pick Kept Edges is pressed, edges clicked in the view go to Edges to Keep
instead of the items to round. While Pick Limit is pressed, a flat face clicked
sets the limiting plane. Flip keeps the rounds in front of the plane instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.ui import strings
from fdcad.ui.property_panel.forms.base import PickList

if TYPE_CHECKING:
    from fdcad.core.document.model import Feature
    from fdcad.core.naming.names import NamedShape
    from fdcad.ui.property_panel.forms.base import FeatureForm


class FilletLimits(QWidget):
    """Edges to Keep, the limiting plane and its flip."""

    changed = Signal()

    def __init__(self, form_: FeatureForm) -> None:
        super().__init__()
        self.form = form_
        f = form_.feature
        self.keep = PickList(form_.doc, strings.LIMIT_KEEP_TIP)
        self.keep.setObjectName("fillet_keep_edges")
        stored = f.refs.get("keep_edges")
        self.keep.set_refs(stored if isinstance(stored, list) else [])
        self.keep.changed.connect(self.changed.emit)
        self.pick_keep = QPushButton(strings.LIMIT_PICK_KEEP)
        self.pick_keep.setCheckable(True)
        self.pick_keep.setToolTip(strings.LIMIT_KEEP_TIP)
        self.plane = PickList(form_.doc, strings.LIMIT_PLANE_TIP)
        self.plane.setObjectName("fillet_limit_plane")
        limit = f.refs.get("limit_plane")
        self.plane.set_refs([limit] if isinstance(limit, dict) else [])
        self.plane.changed.connect(self.changed.emit)
        self.pick_plane = QPushButton(strings.LIMIT_PICK_PLANE)
        self.pick_plane.setCheckable(True)
        self.pick_plane.setToolTip(strings.LIMIT_PLANE_TIP)
        self.flip = QCheckBox(strings.LIMIT_FLIP)
        self.flip.setToolTip(strings.LIMIT_FLIP_TIP)
        self.flip.setChecked(f.params.get("limit_flip") is True)
        self.flip.toggled.connect(lambda _on: self.changed.emit())
        self.pick_keep.toggled.connect(lambda on: self._one_pick(on, self.pick_plane))
        self.pick_plane.toggled.connect(lambda on: self._one_pick(on, self.pick_keep))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(strings.LIMIT_KEEP_LABEL))
        layout.addWidget(self.keep)
        layout.addWidget(self.pick_keep)
        layout.addWidget(QLabel(strings.LIMIT_PLANE_LABEL))
        layout.addWidget(self.plane)
        layout.addWidget(self.pick_plane)  # one under the other: narrow panel (D2790)
        layout.addWidget(self.flip)

    @staticmethod
    def _one_pick(on: bool, other: QAbstractButton) -> None:
        """Only one of the two pick buttons is down at a time."""
        if on:
            other.setChecked(False)

    def take(self, body: NamedShape, shapes: list[Any]) -> tuple[list[Any], str | None]:
        """Take picks while a pick button is pressed; return the rest."""
        from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE

        from fdcad.core.naming.select import is_planar_face, reference_for

        if not (self.pick_keep.isChecked() or self.pick_plane.isChecked()):
            return shapes, None
        rest: list[Any] = []
        problem = None
        for shape in shapes:
            kind = shape.ShapeType()
            if self.pick_keep.isChecked() and kind == TopAbs_EDGE:
                ref = reference_for(body, shape)
                if ref is not None:
                    self.keep.add(ref)
                continue
            if self.pick_plane.isChecked() and kind == TopAbs_FACE:
                if not is_planar_face(shape):
                    problem = strings.LIMIT_NOT_FLAT
                    continue
                ref = reference_for(body, shape)
                if ref is not None:
                    self.plane.clear_all()
                    self.plane.add(ref)
                continue
            rest.append(shape)
        return rest, problem

    def write(self, feature: Feature) -> None:
        """Store Edges to Keep, the limiting plane and the flip (only when set)."""
        feature.refs.pop("keep_edges", None)
        feature.refs.pop("limit_plane", None)
        feature.params.pop("limit_flip", None)
        keep = self.keep.refs()
        if keep:
            feature.refs["keep_edges"] = keep
        plane = self.plane.refs()
        if plane:
            feature.refs["limit_plane"] = plane[0]
            if self.flip.isChecked():
                feature.params["limit_flip"] = True
