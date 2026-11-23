"""Dimensions of a selected feature, shown on the model and editable (W5.4, W4.2).

Selecting an extrude or revolve shows its depth or angle and the dimensions of
its sketch; selecting a sketch shows its dimensions. Double clicking one opens
the value box, and the change is one undoable command, so the part rebuilds.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import (
    Arc,
    Circle,
    Line,
    Point,
    Sketch,
    sketch_from_data,
    sketch_to_data,
)
from fdcad.core.units import ExpressionError, Kind, UnitSystem, evaluate
from fdcad.ui import strings
from fdcad.ui.main_window.visibility import sketch_of

if TYPE_CHECKING:
    from fdcad.core.sketch.profiles import SketchPlane
    from fdcad.ui.main_window.window import MainWindow
    from fdcad.ui.session import DocumentSession
    from fdcad.ui.sketch_tools.value_box import ValueBox

Vec3 = tuple[float, float, float]
_VALUE_PARAMS = ("depth", "depth2", "angle", "angle2")


@dataclass
class ModelDimension:
    """One value shown on the model. ``param`` names a feature value; ``dim`` a sketch one."""

    key: str
    feature: str
    text: str
    expr: str
    anchor: Vec3
    kind: Kind
    param: str | None = None
    dim: str | None = None


def _named(name: str | None, text: str) -> str:
    """A label with the value's own name in front, when it has one (TR32)."""
    return f"{name} = {text}" if name else text


def _given_name(feature: object, target: str) -> str | None:
    from fdcad.core.equations.value_names import value_name

    name = value_name(feature, target)  # type: ignore[arg-type]
    return None if name == target else name


def _text(value: float, kind: Kind, units: UnitSystem) -> str:
    if kind is Kind.ANGLE:
        return f"{math.degrees(value):.2f}°"
    if units is UnitSystem.IN:
        return f"{value / 25.4:.3f}"
    return f"{value:.2f}"


def _entity_xy(sk: Sketch, eid: str) -> tuple[float, float]:
    e = sk.entities[eid]
    if isinstance(e, Point):
        return e.x, e.y
    if isinstance(e, Line):
        (x1, y1), (x2, y2) = sk.xy(e.p1), sk.xy(e.p2)
        return (x1 + x2) / 2, (y1 + y2) / 2
    assert isinstance(e, Circle | Arc)
    cx, cy = sk.xy(e.center)
    r = sk.radius(e.id)
    return cx + r * math.cos(math.pi / 4), cy + r * math.sin(math.pi / 4)


def _sketch_dims(session: DocumentSession, sid: str, offset: Vec3) -> list[ModelDimension]:
    report = session.report
    result = report.results.get(sid) if report is not None else None
    if result is None or result.sketch is None:
        return []
    out = result.sketch
    sk, plane = out.model, out.plane
    units = session.document.units
    dims = []
    for dim in sk.dimensions:
        try:
            pts = [_entity_xy(sk, e) for e in dim.entities]
        except (KeyError, AssertionError):
            continue
        u = sum(p[0] for p in pts) / len(pts)
        v = sum(p[1] for p in pts) / len(pts)
        p = plane.to_3d(u, v)
        kind = Kind.ANGLE if dim.type == "angle" else Kind.LENGTH
        prefix = {"diameter": "⌀", "radius": "R"}.get(dim.type, "")
        dims.append(
            ModelDimension(
                key=f"{sid}:{dim.id}",
                feature=sid,
                text=_named(dim.name, prefix + _text(dim.param.value, kind, units)),
                expr=dim.param.expr,
                anchor=(p.X() + offset[0], p.Y() + offset[1], p.Z() + offset[2]),
                kind=kind,
                dim=dim.id,
            )
        )
    return dims


def _centre(sk: Sketch, plane: SketchPlane) -> Vec3:
    pts = [(e.x, e.y) for e in sk.entities.values() if isinstance(e, Point)] or [(0.0, 0.0)]
    p = plane.to_3d(sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts))
    return p.X(), p.Y(), p.Z()


def all_dimensions(session: DocumentSession) -> list[ModelDimension]:
    """Every sketch dimension and feature value of the part that is built (TR32),
    each once, in tree order."""
    from fdcad.core.document.rollback import rolled_back

    doc = session.document
    skip = set(rolled_back(doc))
    out: dict[str, ModelDimension] = {}
    for feature in doc.features:
        if feature.suppressed or feature.id in skip:
            continue
        for item in model_dimensions(session, feature.id):
            out.setdefault(item.key, item)
    return list(out.values())


def model_dimensions(session: DocumentSession, fid: str) -> list[ModelDimension]:
    """Values to show on the model for feature ``fid`` (empty for other kinds)."""
    doc = session.document
    try:
        feature = doc.feature(fid)
    except KeyError:
        return []
    if feature.type == "sketch":
        return _sketch_dims(session, fid, (0.0, 0.0, 0.0))
    sid = sketch_of(feature)
    if sid is None:
        return []
    out = _sketch_dims(session, sid, (0.0, 0.0, 0.0))
    report = session.report
    result = report.results.get(sid) if report is not None else None
    if result is None or result.sketch is None:
        return out
    plane = result.sketch.plane
    centre = _centre(result.sketch.model, plane)
    n = plane.normal
    for name in _VALUE_PARAMS:
        param = feature.params.get(name)
        if not isinstance(param, Param):
            continue
        kind = Kind.ANGLE if name.startswith("angle") else Kind.LENGTH
        reach = param.value if kind is Kind.LENGTH else 0.0
        if name == "depth2" or bool(feature.params.get("reverse")):
            reach = -reach
        anchor = (centre[0] + n[0] * reach, centre[1] + n[1] * reach, centre[2] + n[2] * reach)
        out.append(
            ModelDimension(
                key=f"{fid}:{name}",
                feature=fid,
                text=_named(_given_name(feature, name), _text(param.value, kind, doc.units)),
                expr=param.expr,
                anchor=anchor,
                kind=kind,
                param=name,
            )
        )
    return out


def apply_value(session: DocumentSession, item: ModelDimension, text: str) -> str | None:
    """Change a model dimension to ``text`` with one undoable command.

    Returns an error message, or None when the change was made.
    """
    from fdcad.core.rebuild.engine import document_variables
    from fdcad.ui.commands.document import ReplaceFeature, SetParam

    doc = session.document
    try:
        variables = document_variables(doc)
    except ExpressionError:
        variables = {}
    try:
        value = evaluate(text, item.kind, doc.units, variables)
    except ExpressionError as exc:
        return str(exc)
    if item.kind is Kind.LENGTH and value <= 0:
        return strings.DIMENSION_POSITIVE
    param = Param(text.strip(), value)
    if item.param is not None:
        session.undo.push(SetParam(session, item.feature, item.param, param))
        return None
    sketch_feature = copy.deepcopy(doc.feature(item.feature))
    sk = sketch_from_data(sketch_feature.data)
    for dim in sk.dimensions:
        if dim.id == item.dim:
            dim.param = param
    sketch_feature.data.update(sketch_to_data(sk))
    session.undo.push(
        ReplaceFeature(session, sketch_feature, f"{strings.EDIT_SKETCH} {sketch_feature.name}")
    )
    return None


class ModelDimensions:
    """Shows the selected feature's dimensions in the 3D view and edits them.

    Only a feature the user clicked in the tree shows them: a finished feature
    that is selected for the user keeps the part clean (owner note 2026-10-30).
    The Measure tool reads sizes off the part.
    """

    def __init__(self, window: MainWindow) -> None:
        self.window = window
        self.items: dict[str, ModelDimension] = {}
        self.box: ValueBox | None = None
        #: The feature the user clicked in the tree; only its dimensions show.
        self.clicked: str | None = None
        #: Show All Dimensions (TR32): every feature's values show, not only the clicked one.
        self.show_all = False

    def set_show_all(self, on: bool) -> None:
        """Show every sketch and feature value of the part at once, or go back to the
        selected feature's values (TR32)."""
        self.show_all = on
        self.refresh()

    def clicked_in_tree(self, *_args: object) -> None:
        """The user clicked a tree row: show that feature's dimensions."""
        w = self.window
        self.clicked = w.tree.selected_id() if w.tree is not None else None
        self.refresh()

    def refresh(self, *_args: object) -> None:
        """Show the dimensions of the feature the user clicked, while it stays selected."""
        w = self.window
        tab = w.current
        fid = w.tree.selected_id() if w.tree is not None else None
        if getattr(w.tree, "_filling", False):
            return  # the tree is refilling after a rebuild; it selects the row again
        if fid != self.clicked:
            fid = self.clicked = None
        if tab is None:
            self.items = {}
            return
        if self.show_all:
            dims = all_dimensions(tab.session)
        else:
            dims = model_dimensions(tab.session, fid) if fid is not None else []
        self.items = {d.key: d for d in dims}
        show = getattr(tab.viewport, "show_labels", None)
        if show is not None:
            show([(d.key, d.text, d.anchor) for d in dims] + measurement_labels(tab.session))

    def edit(self, key: str) -> ValueBox | None:
        """Open the value box for dimension ``key`` at the cursor (double click)."""
        from PySide6.QtGui import QCursor

        from fdcad.ui.sketch_tools.value_box import ValueBox

        item = self.items.get(key)
        tab = self.window.current
        if item is None or tab is None:
            return None
        picker = getattr(self.window, "equations_tool", None)
        if picker is not None and picker.pick(item):
            return None  # the equations manager is open: the name goes there (P4.10)
        self.close()
        from fdcad.core.rebuild.engine import document_variables

        session = tab.session
        try:
            variables = document_variables(session.document)
        except ExpressionError:
            variables = {}
        box = ValueBox(item.expr, self.window, item.kind, session.document.units, variables)

        def accept() -> None:
            error = apply_value(session, item, box.text())
            if error is not None:
                box.show_error(error)
                self.window.status.setText(error)
                return
            self.close()

        box.accepted.connect(accept)
        box.rejected.connect(self.close)
        box.applied.connect(lambda: apply_value(session, item, box.text()))
        pos = self.window.mapFromGlobal(QCursor.pos())
        box.open_at(max(0, pos.x()), max(0, pos.y()))
        self.box = box
        return box

    def close(self) -> None:
        """Close the value box."""
        if self.box is not None:
            self.box.hide()
            self.box.deleteLater()
        self.box = None


def measurement_labels(session: DocumentSession) -> list[tuple[str, str, Vec3]]:
    """The labels of saved measurements, always shown (TR191, D818)."""
    report = session.report
    if report is None:
        return []
    out = []
    for feature in session.document.features:
        result = report.results.get(feature.id)
        label = result.extras.get("label") if result is not None else None
        if feature.type == "measurement" and not feature.suppressed and label is not None:
            out.append((f"measure:{feature.id}", str(label[0]), tuple(label[1])))
    return out
