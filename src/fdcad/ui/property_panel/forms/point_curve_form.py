"""Curve Through Points panel (TR61, DECISIONS D817).

Points typed in a table (X, Y, Z in the part's units) or read from a text file
with Load File and Reload, placed in a picked frame; or points picked in the
view in order (vertices, sketch points, reference points), which then win.
Closed joins the ends smoothly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from fdcad.core.document.model import Feature
from fdcad.core.features.point_curve import read_points
from fdcad.core.naming.names import NamedShape
from fdcad.ui import strings
from fdcad.ui.property_panel.forms.base import FeatureForm, PickList, form


def _units(form_: FeatureForm) -> float:
    """Millimetres in one unit of the part (inch parts type inches)."""
    from fdcad.core.units import UnitSystem

    return 25.4 if form_.doc.units is UnitSystem.IN else 1.0


@form("point_curve")
class PointCurveForm(FeatureForm):
    """Edits a curve through points."""

    def build(self) -> None:
        """Add the points group."""
        group = self.group("points", strings.GROUP_POINTS, strings.POINTS_TIP)
        self.table = QTableWidget(0, 3)
        self.table.setObjectName("point_table")
        self.table.setHorizontalHeaderLabels(["X", "Y", "Z"])
        # X, Y and Z share the width of the table: at 100 px each it scrolled sideways
        # at the left panel's default width (D2804).
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        scale = _units(self)
        for point in self.feature.data.get("points", []) or []:
            if isinstance(point, list) and len(point) == 3:
                self._add_row([float(v) / scale for v in point])
        add, remove = QPushButton(strings.POINTS_ADD), QPushButton(strings.POINTS_REMOVE)
        load, reload = QPushButton(strings.POINTS_LOAD), QPushButton(strings.POINTS_RELOAD)
        add.clicked.connect(lambda: self._add_row([0.0, 0.0, 0.0]))
        remove.clicked.connect(self._remove_row)
        load.clicked.connect(self.load_file)
        reload.clicked.connect(self.reload)
        reload.setToolTip(strings.POINTS_RELOAD_TIP)
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        for button in (add, remove, load, reload):
            layout.addWidget(button)
        self.file = str(self.feature.data.get("file", ""))
        self.frame = QComboBox()
        self.frame.addItem(strings.POINTS_PART_AXES, None)
        order = [f.id for f in self.doc.features]
        mine = order.index(self.feature.id) if self.feature.id in order else len(order)
        for other in self.doc.features[:mine]:
            if other.type in ("plane", "ref_plane", "coord_system"):
                self.frame.addItem(other.name, {"feature": other.id})
        stored = self.feature.refs.get("frame")
        if isinstance(stored, dict):
            self.frame.setCurrentIndex(max(self.frame.findData(stored), 0))
        self.picks = PickList(self.doc, strings.POINTS_PICK_TIP, ordered=True)
        self.picks.set_refs(self.feature.refs.get("points", []))
        self.closed = QCheckBox(strings.POINTS_CLOSED)
        self.closed.setChecked(self.feature.params.get("closed") is True)
        group.form.addRow(self.table)
        group.form.addRow(row)
        group.form.addRow(strings.POINTS_FRAME, self.frame)
        group.form.addRow(self.picks)
        group.form.addRow(self.closed)
        self._expression_rows(group.form)
        self.table.itemChanged.connect(lambda _i: self.changed.emit())
        for signal in (self.frame.currentIndexChanged, self.closed.toggled):
            signal.connect(lambda *_a: self.changed.emit())
        self.picks.changed.connect(self.changed.emit)

    def _expression_rows(self, rows: QFormLayout) -> None:
        """X(t), Y(t), Z(t), the range of t and Fill Points (TR374, D1011)."""
        kept = self.feature.data.get("equation")
        kept = kept if isinstance(kept, dict) else {}
        self.exprs = []
        for axis, default in zip("xyz", ("10*cos(t)", "10*sin(t)", "2*t"), strict=True):
            edit = QLineEdit(str(kept.get(axis, default)))
            edit.setObjectName(f"point_expr_{axis}")
            edit.setToolTip(strings.POINTS_EXPR_TIP)
            self.exprs.append(edit)
            rows.addRow(strings.POINTS_EXPR.format(axis=axis.upper()), edit)
        self.t_from = QLineEdit(str(kept.get("t0", "0")))
        self.t_to = QLineEdit(str(kept.get("t1", "6.2832")))
        self.t_count = QSpinBox()
        self.t_count.setRange(2, 5000)
        self.t_count.setValue(
            int(kept.get("count", 50)) if str(kept.get("count", "")).isdigit() else 50
        )
        span = QWidget()
        line = QHBoxLayout(span)
        line.setContentsMargins(0, 0, 0, 0)
        for widget in (self.t_from, self.t_to, self.t_count):
            line.addWidget(widget)
        rows.addRow(strings.POINTS_T_RANGE, span)
        fill = QPushButton(strings.POINTS_FILL)
        fill.setObjectName("point_fill")
        fill.setToolTip(strings.POINTS_FILL_TIP)
        fill.clicked.connect(self.fill_from_expressions)
        rows.addRow(fill)
        self.equation: dict[str, Any] | None = dict(kept) if kept else None

    def fill_from_expressions(self) -> bool:
        """Fill the table from x(t), y(t), z(t). False with a message when it cannot."""
        from fdcad.core.features.point_curve import expression_points

        texts = tuple(e.text() for e in self.exprs)
        try:
            t0, t1 = float(self.t_from.text()), float(self.t_to.text())
        except ValueError:
            self.check.show_result(strings.POINTS_T_NOT_NUMBERS, [])
            return False
        count = self.t_count.value()
        try:
            found = expression_points(texts, t0, t1, count, self.doc.units)  # type: ignore[arg-type]
        except ValueError as exc:
            self.check.show_result(strings.POINTS_EXPR_FAILED.format(reason=exc), [])
            return False
        self.equation = {"x": texts[0], "y": texts[1], "z": texts[2], "t0": t0, "t1": t1}
        self.equation["count"] = count
        self.set_points(found)
        self.check.show_result("", [])
        return True

    def _add_row(self, point: list[float]) -> None:
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c, value in enumerate(point):
            self.table.setItem(r, c, QTableWidgetItem(f"{value:g}"))
        self.changed.emit()

    def _remove_row(self) -> None:
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)
            self.changed.emit()

    def set_points(self, points: list[list[float]]) -> None:
        """Replace the table with ``points`` (mm)."""
        scale = _units(self)
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        self.table.blockSignals(False)
        for point in points:
            self._add_row([v / scale for v in point])

    def load_file(self) -> bool:
        """Read points from a text file (three columns, in the part's units)."""
        path, _ = QFileDialog.getOpenFileName(
            self.panel, strings.POINTS_LOAD, "", strings.POINTS_FILTER
        )
        if not path:
            return False
        self.file = path
        return self.reload()

    def reload(self) -> bool:
        """Read the chosen file again. False when there is none or it cannot be read."""
        if not self.file:
            self.check.show_result(strings.POINTS_NO_FILE, [])
            return False
        try:
            found = read_points(Path(self.file).read_text(encoding="utf-8", errors="replace"))
        except (OSError, ValueError) as exc:
            self.check.show_result(strings.POINTS_FILE_FAILED.format(reason=exc), [])
            return False
        scale = _units(self)
        self.set_points([[v * scale for v in p] for p in found])
        self.check.show_result("", [])
        return True

    def points(self) -> list[list[float]] | None:
        """The table's points in mm, or None when a cell is not a number."""
        scale = _units(self)
        out = []
        for r in range(self.table.rowCount()):
            row = []
            for c in range(3):
                item = self.table.item(r, c)
                try:
                    row.append(float(item.text()) * scale if item is not None else 0.0)
                except ValueError:
                    return None
            out.append(row)
        return out

    def apply(self, feature: Feature) -> str | None:
        """Write the points, the frame, the picks and Closed."""
        found = self.points()
        if found is None:
            return strings.POINTS_NOT_NUMBERS
        picks = self.picks.refs()
        for key in ("points", "frame"):
            feature.refs.pop(key, None)
        feature.data.pop("points", None)
        feature.data.pop("file", None)
        feature.data.pop("equation", None)
        if picks:
            feature.refs["points"] = picks
        else:
            if len(found) < 2:
                return strings.POINTS_NEED_TWO
            feature.data["points"] = found
            if self.file:
                feature.data["file"] = self.file
            if self.equation:
                feature.data["equation"] = dict(self.equation)
            frame = self.frame.currentData()
            if isinstance(frame, dict):
                feature.refs["frame"] = dict(frame)
        if self.closed.isChecked():
            feature.params["closed"] = True
        else:
            feature.params.pop("closed", None)
        return None

    def take_shapes(self, body: NamedShape, shapes: list[Any]) -> str | None:
        """Vertices clicked in the view are added in order."""
        from OCP.TopAbs import TopAbs_VERTEX

        from fdcad.core.naming.select import reference_for

        problem = None
        for shape in shapes:
            if shape.ShapeType() != TopAbs_VERTEX:
                problem = strings.POINTS_PICK_VERTICES
                continue
            ref = reference_for(body, shape)
            if ref is not None and not self.own_ref(ref):
                self.picks.add(ref)
        return problem
