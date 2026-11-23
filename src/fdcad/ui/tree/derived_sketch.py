"""Derived Sketch, Edit Placement and Break Link from the tree (TR49, D845)."""

from __future__ import annotations

import copy
import math
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QInputDialog,
    QLineEdit,
    QWidget,
)

from fdcad.core.units import ExpressionError, Kind, UnitSystem, evaluate
from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.session import DocumentSession

_PLANES = ("plane", "ref_plane")


def ask_plane(parent: QWidget | None, names: list[str]) -> str | None:
    """The chosen plane name, or None (a seam for tests)."""
    chosen, ok = QInputDialog.getItem(
        parent, strings.DERIVED_TITLE, strings.DERIVED_ASK, names, 0, False
    )
    return chosen if ok and chosen else None


def make_derived(
    session: DocumentSession, source: str, parent: QWidget | None = None
) -> str | None:
    """Add a linked copy of sketch ``source`` on a chosen plane. Returns its id."""
    from fdcad.core.document.model import Feature
    from fdcad.core.sketch.model import Sketch, sketch_to_data
    from fdcad.ui.body_tools.flow import default_name
    from fdcad.ui.commands.document import AddFeature

    doc = session.document
    planes = [(f.id, f.name) for f in doc.features if f.type in _PLANES]
    chosen = ask_plane(parent, [name for _fid, name in planes])
    if chosen is None:
        return None
    plane = next(fid for fid, name in planes if name == chosen)
    fid = doc.new_feature_id()
    data: dict[str, Any] = {
        **sketch_to_data(Sketch()),
        "derived_place": {"dx": 0.0, "dy": 0.0, "angle": 0.0},
    }
    feature = Feature(
        fid,
        "sketch",
        default_name(doc, "derived_sketch"),
        refs={"plane": {"feature": plane}, "derived_from": {"feature": source}},
        data=data,
    )
    session.undo.push(AddFeature(session, feature))
    return fid


class PlacementDialog(QDialog):
    """Move and turn a derived sketch by typed values."""

    def __init__(
        self, place: tuple[float, float, float], units: UnitSystem, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(strings.DERIVED_PLACE)
        self.units = units
        scale = 25.4 if units is UnitSystem.IN else 1.0
        self.dx = QLineEdit(f"{place[0] / scale:g}")
        self.dy = QLineEdit(f"{place[1] / scale:g}")
        self.angle = QLineEdit(f"{math.degrees(place[2]):g}")
        form = QFormLayout(self)
        form.addRow("X", self.dx)
        form.addRow("Y", self.dy)
        form.addRow(strings.DERIVED_ANGLE, self.angle)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> tuple[float, float, float] | None:
        """(dx, dy) in mm and the angle in radians, or None for text that is not a value."""
        try:
            return (
                evaluate(self.dx.text(), Kind.LENGTH, self.units),
                evaluate(self.dy.text(), Kind.LENGTH, self.units),
                evaluate(self.angle.text(), Kind.ANGLE, self.units),
            )
        except ExpressionError:
            return None


def run(dialog: QDialog) -> bool:
    """Show the dialog; tests replace this."""
    return dialog.exec() == QDialog.DialogCode.Accepted


def edit_placement(session: DocumentSession, fid: str, parent: QWidget | None = None) -> bool:
    """Move or turn a derived sketch as one undo step."""
    from fdcad.core.sketch.derived import placement
    from fdcad.ui.commands.document import ReplaceFeature

    feature = session.document.feature(fid)
    dialog = PlacementDialog(placement(feature.data), session.document.units, parent)
    accepted = run(dialog)
    values = dialog.values()
    dialog.deleteLater()
    if not accepted or values is None:
        return False
    edited = copy.deepcopy(feature)
    edited.data["derived_place"] = {"dx": values[0], "dy": values[1], "angle": values[2]}
    session.undo.push(ReplaceFeature(session, edited, strings.DERIVED_PLACE))
    return True


def break_link(session: DocumentSession, fid: str) -> bool:
    """Turn a derived sketch into an ordinary sketch holding its current geometry."""
    from fdcad.core.sketch.model import sketch_to_data
    from fdcad.ui.commands.document import ReplaceFeature

    report = session.report
    result = report.results.get(fid) if report is not None else None
    if result is None or result.sketch is None:
        return False
    model = copy.deepcopy(result.sketch.model)
    model.relations = [r for r in model.relations if r.type != "fixed"]
    edited = copy.deepcopy(session.document.feature(fid))
    edited.refs.pop("derived_from", None)
    edited.data.pop("derived_place", None)
    edited.data.update(sketch_to_data(model))
    session.undo.push(ReplaceFeature(session, edited, strings.DERIVED_BREAK))
    return True
