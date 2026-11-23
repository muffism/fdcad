"""3D Sketch panel (TR7, DECISIONS D1719).

Plane sketch parts: pick a 2D sketch above and Add Part copies it, with its plane,
into the 3D sketch (edit the 2D sketch, then add it again to take the change).
3D lines: type points, one "x y z" a line in the part's units, choose Lines or
Spline, and Add 3D Line. 3D relations (D2206): Along X, Y or Z, Coincident, Fix and
3D Length between line points, or from a line point to a plane sketch part point.
"""

from __future__ import annotations

import copy
from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QWidget,
)

from fdcad.core.document.model import Feature
from fdcad.core.features.point_curve import read_points
from fdcad.ui import strings
from fdcad.ui.property_panel.forms.base import FeatureForm, form


def _scale(form_: FeatureForm) -> float:
    from fdcad.core.units import UnitSystem

    return 25.4 if form_.doc.units is UnitSystem.IN else 1.0


def _row(*widgets: QWidget) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    for w in widgets:
        layout.addWidget(w)
    return row


@form("sketch3d")
class Sketch3DForm(FeatureForm):
    """Edits a 3D sketch: its plane sketch parts and its free 3D lines."""

    def build(self) -> None:
        """Add the Parts and 3D Lines groups."""
        self.parts: list[dict[str, Any]] = copy.deepcopy(list(self.feature.data.get("parts") or []))
        self.lines: list[dict[str, Any]] = copy.deepcopy(list(self.feature.data.get("lines") or []))
        self.relations: list[dict[str, Any]] = copy.deepcopy(
            list(self.feature.data.get("relations") or [])
        )
        parts = self.group("parts", strings.S3D_PARTS, strings.S3D_PARTS_TIP)
        self.source = QComboBox()
        self.source.setObjectName("s3d_source")
        order = [f.id for f in self.doc.features]
        mine = order.index(self.feature.id) if self.feature.id in order else len(order)
        for other in self.doc.features[:mine]:
            if other.type == "sketch" and isinstance(other.refs.get("plane"), dict):
                self.source.addItem(other.name, other.id)
        add_part, remove_part = QPushButton(strings.S3D_ADD_PART), QPushButton(strings.S3D_REMOVE)
        add_part.clicked.connect(self.add_part)
        remove_part.clicked.connect(self.remove_part)
        self.part_list = QListWidget()
        parts.form.addRow(strings.S3D_SOURCE, self.source)
        parts.form.addRow(_row(add_part, remove_part))
        parts.form.addRow(self.part_list)
        lines = self.group("lines", strings.S3D_LINES, strings.S3D_LINES_TIP)
        self.points = QPlainTextEdit()
        self.points.setObjectName("s3d_points")
        self.points.setPlaceholderText("0 0 0\n10 0 0\n10 10 5")
        self.kind = QComboBox()
        self.kind.addItem(strings.S3D_KIND_LINES, "line")
        self.kind.addItem(strings.S3D_KIND_SPLINE, "spline")
        add_line, remove_line = QPushButton(strings.S3D_ADD_LINE), QPushButton(strings.S3D_REMOVE)
        add_line.clicked.connect(self.add_line)
        remove_line.clicked.connect(self.remove_line)
        self.line_list = QListWidget()
        lines.form.addRow(self.points)
        lines.form.addRow(strings.S3D_KIND, self.kind)
        lines.form.addRow(_row(add_line, remove_line))
        lines.form.addRow(self.line_list)
        self._build_relations()
        self.message = ""
        self._refill()

    def _build_relations(self) -> None:
        """The 3D Relations group (TR7, D2206)."""
        from fdcad.core.sketch.solve3d import TYPES

        group = self.group("relations", strings.S3D_RELATIONS, strings.S3D_RELATIONS_TIP)
        self.rel_type = QComboBox()
        self.rel_type.setObjectName("s3d_rel_type")
        for kind in TYPES:
            self.rel_type.addItem(strings.S3D_REL_TYPES[kind], kind)
        self.rel_first, self.rel_second = QComboBox(), QComboBox()
        self.rel_value = QDoubleSpinBox()
        self.rel_value.setRange(0.001, 1e6)
        self.rel_value.setDecimals(4)
        self.rel_value.setValue(10.0)
        add_rel, remove_rel = QPushButton(strings.S3D_ADD_RELATION), QPushButton(strings.S3D_REMOVE)
        add_rel.clicked.connect(self.add_relation)
        remove_rel.clicked.connect(self.remove_relation)
        self.relation_list = QListWidget()
        group.form.addRow(strings.S3D_REL_TYPE, self.rel_type)
        group.form.addRow(strings.S3D_REL_FIRST, self.rel_first)
        group.form.addRow(strings.S3D_REL_SECOND, self.rel_second)
        group.form.addRow(strings.S3D_REL_VALUE, self.rel_value)
        group.form.addRow(_row(add_rel, remove_rel))
        group.form.addRow(self.relation_list)
        self.rel_type.currentIndexChanged.connect(self._type_changed)
        self._type_changed()

    def _type_changed(self) -> None:
        kind = self.rel_type.currentData()
        self.rel_second.setEnabled(kind != "fixed")
        self.rel_value.setEnabled(kind == "length")

    def point_choices(self) -> list[tuple[str, str]]:
        """Every point a relation can name: (reference, label)."""
        from fdcad.core.sketch.model import Point, sketch_from_data

        out: list[tuple[str, str]] = []
        for k, line in enumerate(self.lines, start=1):
            for i in range(1, len(line.get("points") or []) + 1):
                out.append((f"{k}.{i}", strings.S3D_LINE_POINT.format(k=k, i=i)))
        for k, part in enumerate(self.parts, start=1):
            try:
                sketch = sketch_from_data(dict(part.get("sketch") or {}))
            except ValueError:
                continue
            for e in sketch.entities.values():
                if isinstance(e, Point) and not e.construction:
                    out.append((f"P{k}:{e.id}", strings.S3D_PART_POINT.format(k=k, eid=e.id)))
        return out

    def add_relation(self) -> bool:
        """Add the chosen relation between the chosen points."""
        kind = str(self.rel_type.currentData())
        first = self.rel_first.currentData()
        second = self.rel_second.currentData()
        if not isinstance(first, str) or (kind != "fixed" and not isinstance(second, str)):
            self.message = strings.S3D_REL_SAME
            return False
        rel: dict[str, Any] = {"type": kind, "points": [first]}
        if kind != "fixed":
            if second == first:
                self.message = strings.S3D_REL_SAME
                return False
            rel["points"].append(second)
        if kind == "fixed":
            at = self._place(first)
            if at is None:
                self.message = strings.S3D_REL_SAME
                return False
            rel["at"] = at
        if kind == "length":
            rel["value"] = self.rel_value.value() * _scale(self)
        self.relations.append(rel)
        self._refill()
        self.changed.emit()
        return True

    def _place(self, ref: str) -> list[float] | None:
        """Where line point ``ref`` is now, or None for a part point."""
        if "." not in ref or ref.startswith("P"):
            return None
        k, i = (int(v) for v in ref.split("."))
        return [float(v) for v in self.lines[k - 1]["points"][i - 1]]

    def remove_relation(self) -> None:
        """Remove the selected relation."""
        row = self.relation_list.currentRow()
        if 0 <= row < len(self.relations):
            del self.relations[row]
            self._refill()
            self.changed.emit()

    def _refill(self) -> None:
        self.part_list.clear()
        for k, part in enumerate(self.parts, start=1):
            self.part_list.addItem(strings.S3D_PART_ROW.format(k=k, name=part.get("name", "")))
        self.line_list.clear()
        for k, line in enumerate(self.lines, start=1):
            kind = (
                strings.S3D_KIND_SPLINE if line.get("kind") == "spline" else strings.S3D_KIND_LINES
            )
            count = len(line.get("points") or [])
            self.line_list.addItem(strings.S3D_LINE_ROW.format(k=k, kind=kind, count=count))
        from fdcad.core.sketch.solve3d import describe

        choices = self.point_choices()
        for box in (self.rel_first, self.rel_second):
            box.clear()
            for ref, label in choices:
                box.addItem(label, ref)
        if self.rel_second.count() > 1:
            self.rel_second.setCurrentIndex(1)
        self.relation_list.clear()
        for rel in self.relations:
            self.relation_list.addItem(describe(rel))

    def add_part(self) -> bool:
        """Copy the chosen 2D sketch, with its plane, in as a part."""
        fid = self.source.currentData()
        if fid is None:
            self.message = strings.S3D_NO_SKETCH
            return False
        sketch = self.doc.feature(str(fid))
        self.parts.append(
            {
                "name": sketch.name,
                "plane": copy.deepcopy(sketch.refs["plane"]),
                "sketch": copy.deepcopy(sketch.data),
            }
        )
        self._refill()
        self.changed.emit()
        return True

    def remove_part(self) -> None:
        """Remove the selected part."""
        row = self.part_list.currentRow()
        if 0 <= row < len(self.parts):
            del self.parts[row]
            self.relations = _without_part(self.relations, row + 1)
            self._refill()
            self.changed.emit()

    def add_line(self) -> bool:
        """Add the typed points as a 3D line or spline."""
        try:
            pts = read_points(self.points.toPlainText())
        except ValueError as exc:
            self.message = str(exc)
            return False
        if len(pts) < 2:
            self.message = strings.S3D_NEED_TWO
            return False
        scale = _scale(self)
        self.lines.append(
            {"kind": str(self.kind.currentData()), "points": [[v * scale for v in p] for p in pts]}
        )
        self.points.clear()
        self._refill()
        self.changed.emit()
        return True

    def remove_line(self) -> None:
        """Remove the selected 3D line."""
        row = self.line_list.currentRow()
        if 0 <= row < len(self.lines):
            del self.lines[row]
            self.relations = _without_line(self.relations, row + 1)
            self._refill()
            self.changed.emit()

    def apply(self, feature: Feature) -> str | None:
        """Write the parts and the 3D lines."""
        if not self.parts and not self.lines:
            return strings.S3D_EMPTY
        feature.data["parts"] = copy.deepcopy(self.parts)
        feature.data["lines"] = copy.deepcopy(self.lines)
        if not self.parts:
            feature.data.pop("parts")
        if not self.lines:
            feature.data.pop("lines")
        if self.relations and self.lines:  # TR7 (D2206)
            feature.data["relations"] = copy.deepcopy(self.relations)
        else:
            feature.data.pop("relations", None)
        return None


def _without_line(relations: list[dict[str, Any]], k: int) -> list[dict[str, Any]]:
    """``relations`` after 3D line ``k`` is removed: its relations go, later lines move
    up one number."""
    out = []
    for rel in relations:
        refs = [str(r) for r in rel.get("points") or []]
        if any(r.split(".")[0] == str(k) for r in refs if not r.startswith("P")):
            continue
        moved = dict(rel)
        moved["points"] = [_renumber(r, "", k) for r in refs]
        out.append(moved)
    return out


def _without_part(relations: list[dict[str, Any]], k: int) -> list[dict[str, Any]]:
    """``relations`` after part ``k`` is removed, as :func:`_without_line` for parts."""
    out = []
    for rel in relations:
        refs = [str(r) for r in rel.get("points") or []]
        if any(r.startswith(f"P{k}:") for r in refs):
            continue
        moved = dict(rel)
        moved["points"] = [_renumber(r, "P", k) for r in refs]
        out.append(moved)
    return out


def _renumber(ref: str, prefix: str, k: int) -> str:
    """``ref`` with its line (or part, for prefix P) number lowered past ``k``."""
    if prefix == "P":
        if not ref.startswith("P"):
            return ref
        head, rest = ref[1:].split(":", 1)
        n = int(head)
        return f"P{n - 1 if n > k else n}:{rest}"
    if ref.startswith("P"):
        return ref
    head, rest = ref.split(".", 1)
    n = int(head)
    return f"{n - 1 if n > k else n}.{rest}"
