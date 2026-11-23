"""Sketch tool panels: tool options and the values of a shape (TOOL_SPEC T7.2, T7.3).

``ToolOptions`` holds the options of the active drawing tool: For construction,
and for Line the orientation (As drawn, Horizontal, Vertical, Angle, T2.1.4).
``ShapeValues`` shows the values of the shape drawn last, or of one selected
entity when no tool is active: point X and Y (T14.1.3), line length and angle
(T2.1.4), circle and arc centre and radius (T2.4.3), rectangle width and height.
Typed values go through the solver (``SketchEdit.set_*``); a value that the
relations or dimensions hold is refused and nothing moves.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.sketch.model import Arc, Circle, Line, Point
from fdcad.core.units import ExpressionError, Kind, UnitSystem, evaluate
from fdcad.ui import strings
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.tools import ORIENTATIONS, CornerRectangleTool, LineTool, Tool
from fdcad.ui.sketch_tools.typed_size import THREE_POINT

#: Tools that draw nothing but points or are always construction: no construction tick.
_NO_CONSTRUCTION = ("point", "centerline")


class ToolOptions(QGroupBox):
    """Options of the active drawing tool. They stay set while the sketch is open."""

    def __init__(self, canvas: SketchCanvas, parent: QWidget | None = None) -> None:
        super().__init__(strings.TOOL_OPTIONS, parent)
        self.setObjectName("tool_options")
        self.canvas = canvas
        layout = QVBoxLayout(self)
        self.construction = QCheckBox(strings.FOR_CONSTRUCTION)
        self.construction.toggled.connect(lambda _on: self.apply())
        self.orientation = QComboBox()
        for key in ORIENTATIONS:
            self.orientation.addItem(strings.LINE_ORIENTATIONS[key], key)
        self.orientation.currentIndexChanged.connect(lambda _i: self.apply())
        self.angle = QLineEdit("0deg")
        self.angle.setToolTip(strings.LINE_ANGLE_TIP)
        self.angle.editingFinished.connect(self.apply)
        self.orientation_form = QWidget()
        form = QFormLayout(self.orientation_form)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow(strings.LINE_ORIENTATION, self.orientation)
        form.addRow(strings.LINE_ANGLE, self.angle)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        layout.addWidget(self.orientation_form)
        layout.addWidget(self.construction)
        layout.addWidget(self.hint)
        canvas.tool_changed.connect(lambda _name: self.refresh())
        self.refresh()

    def refresh(self) -> None:
        """Show the options that fit the active tool and hand them to it."""
        tool = self.canvas.tool
        self.setVisible(tool is not None)
        if tool is None:
            return
        self.setTitle(f"{tool.label}: {strings.TOOL_OPTIONS}")
        is_line = isinstance(tool, LineTool) and not tool.centerline
        self.orientation_form.setVisible(is_line)
        self.construction.setVisible(
            tool.name not in _NO_CONSTRUCTION and getattr(tool, "construction_option", True)
        )
        hint = strings.TOOL_HINTS.get(tool.name, "")
        self.hint.setText(hint)
        self.hint.setVisible(bool(hint))
        if not getattr(tool, "construction_option", True) and not hint and not is_line:
            self.setVisible(False)  # a Phase 2 tool shows its own panel (P2.8)
        self.apply()

    def apply(self) -> None:
        """Hand the options to the active tool."""
        tool = self.canvas.tool
        if tool is None:
            return
        if tool.name not in _NO_CONSTRUCTION and getattr(tool, "construction_option", True):
            tool.construction = self.construction.isChecked()
        if isinstance(tool, LineTool) and not tool.centerline:
            tool.orientation = str(self.orientation.currentData())
            self.angle.setEnabled(tool.orientation == "angle")
            try:
                tool.angle = evaluate(self.angle.text(), Kind.ANGLE, self.canvas.units)
            except ExpressionError:
                self.angle.setText(f"{math.degrees(tool.angle):.6g}deg")


class ShapeValues(QGroupBox):
    """Values of the shape drawn last, or of the selected entity, that can be typed."""

    def __init__(self, canvas: SketchCanvas, parent: QWidget | None = None) -> None:
        super().__init__(strings.SHAPE_VALUES, parent)
        self.setObjectName("shape_values")
        self.canvas = canvas
        self.form = QFormLayout(self)
        #: The value fields by key (x, y, length, angle, cx, cy, radius, width, height).
        self.fields: dict[str, QLineEdit] = {}
        #: What the fields show: ("point" | "line" | "round" | "rectangle", ids).
        self.target: tuple[str, list[str]] | None = None
        canvas.edited.connect(self.refresh)
        canvas.selection_changed.connect(self.refresh)
        canvas.tool_changed.connect(lambda _name: self.refresh())
        self.refresh()

    def _target(self) -> tuple[str, list[str]] | None:
        canvas = self.canvas
        sk = canvas.edit.sketch
        ids: list[str] = []
        tool: Tool | None = canvas.tool
        if tool is not None:
            ids = [i for i in tool.drawn if i in sk.entities]
            quad = isinstance(tool, CornerRectangleTool) or tool.name in THREE_POINT
            if quad and len(ids) == 4:
                return "rectangle", ids
            ids = ids[-1:]
        elif not canvas.dimension_mode:
            ids = [i for i in canvas.selection if i in sk.entities]
        if len(ids) != 1:
            return None
        ent = sk.entities[ids[0]]
        if isinstance(ent, Point):
            return "point", ids
        if isinstance(ent, Line):
            return "line", ids
        if isinstance(ent, Circle | Arc):
            return "round", ids
        return None

    def refresh(self) -> None:
        """Rebuild the fields for the current target and fill in its values."""
        target = self._target()
        if target != self.target:
            self.target = target
            self._build()
        self.setVisible(target is not None)
        if target is None:
            return
        for key, value in self._values().items():
            field = self.fields[key]
            if not field.hasFocus():
                field.setText(value)
                field.setProperty("error", False)

    def _build(self) -> None:
        while self.form.rowCount():
            row = self.form.takeRow(0)
            for item in (row.labelItem, row.fieldItem):
                widget = item.widget() if item is not None else None
                if widget is not None:
                    widget.hide()
                    widget.deleteLater()
        self.fields = {}
        if self.target is None:
            return
        for key in _KEYS[self.target[0]]:
            field = QLineEdit()
            field.setObjectName(f"shape_{key}")
            field.setToolTip(strings.SHAPE_VALUE_TIP)
            field.returnPressed.connect(lambda k=key: self.apply(k))
            self.form.addRow(strings.SHAPE_FIELDS[key], field)
            self.fields[key] = field

    def _values(self) -> dict[str, str]:
        assert self.target is not None
        kind, ids = self.target
        sk = self.canvas.edit.sketch
        length = self._length
        if kind == "point":
            x, y = sk.xy(ids[0])
            return {"x": length(x), "y": length(y)}
        if kind == "line":
            line = sk.entities[ids[0]]
            assert isinstance(line, Line)
            (x1, y1), (x2, y2) = sk.xy(line.p1), sk.xy(line.p2)
            angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
            return {"length": length(math.hypot(x2 - x1, y2 - y1)), "angle": f"{angle:.4g}deg"}
        if kind == "round":
            ent = sk.entities[ids[0]]
            assert isinstance(ent, Circle | Arc)
            cx, cy = sk.xy(ent.center)
            return {"cx": length(cx), "cy": length(cy), "radius": length(sk.radius(ent.id))}
        width, height = (self._line_length(i) for i in ids[:2])
        return {"width": length(width), "height": length(height)}

    def _line_length(self, lid: str) -> float:
        sk = self.canvas.edit.sketch
        line = sk.entities[lid]
        assert isinstance(line, Line)
        (x1, y1), (x2, y2) = sk.xy(line.p1), sk.xy(line.p2)
        return math.hypot(x2 - x1, y2 - y1)

    def _length(self, mm: float) -> str:
        if self.canvas.units is UnitSystem.IN:
            return f"{mm / 25.4:.6g}in"
        return f"{mm:.6g}mm"

    def apply(self, key: str) -> bool:
        """Apply the typed value of field ``key`` through the solver."""
        if self.target is None or key not in self.fields:
            return False
        field = self.fields[key]
        kind = Kind.ANGLE if key == "angle" else Kind.LENGTH
        canvas = self.canvas
        try:
            value = evaluate(field.text(), kind, canvas.units, canvas.variables)
        except ExpressionError as exc:
            self._error(field, str(exc))
            return False
        change = self._change(key, value)
        if change is None:
            self._error(field, strings.SHAPE_VALUE_POSITIVE)
            return False
        if not canvas.apply_shape_value(change):
            self._error(field, strings.SHAPE_VALUE_HELD)
            return False
        field.setToolTip(strings.SHAPE_VALUE_TIP)
        field.setProperty("error", False)
        field.style().unpolish(field)  # drop the red look of an earlier wrong value
        field.style().polish(field)
        self.refresh()
        return True

    def _change(self, key: str, value: float) -> Callable[[], bool] | None:
        assert self.target is not None
        kind, ids = self.target
        edit = self.canvas.edit
        sk = edit.sketch
        if key in ("length", "radius", "width", "height") and value <= 0:
            return None
        if kind == "point":
            x, y = sk.xy(ids[0])
            x, y = (value, y) if key == "x" else (x, value)
            return lambda: edit.set_point(ids[0], x, y)
        if kind == "line":
            if key == "length":
                return lambda: edit.set_length(ids[0], value)
            return lambda: edit.set_angle(ids[0], value)
        if kind == "round":
            if key == "radius":
                return lambda: edit.set_radius(ids[0], value)
            ent = sk.entities[ids[0]]
            assert isinstance(ent, Circle | Arc)
            cx, cy = sk.xy(ent.center)
            cx, cy = (value, cy) if key == "cx" else (cx, value)
            return lambda: edit.set_point(ent.center, cx, cy)
        lid = ids[0] if key == "width" else ids[1]
        return lambda: edit.set_length(lid, value)

    def _error(self, field: QLineEdit, message: str) -> None:
        field.setToolTip(message)
        field.setProperty("error", True)
        field.style().unpolish(field)
        field.style().polish(field)
        self.canvas.status_message.emit(message)


#: Value fields by target kind, in panel order.
_KEYS = {
    "point": ("x", "y"),
    "line": ("length", "angle"),
    "round": ("cx", "cy", "radius"),
    "rectangle": ("width", "height"),
}
