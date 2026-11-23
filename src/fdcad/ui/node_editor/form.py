"""Settings of the selected node: values of unwired inputs and the node's own settings.

Typed values accept the full expression syntax (PLAN section 7) and keep the
typed text. Every change is sent to the panel, which makes it one undoable edit.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QWidget,
)

from fdcad.core.document.model import Document, Param
from fdcad.core.graph.model import Graph, Node
from fdcad.core.graph.nodes import NODE_TYPES
from fdcad.core.graph.nodes.base import Port, Setting
from fdcad.core.graph.nodes.inputs import snap
from fdcad.core.graph.types import PortType
from fdcad.core.units import ExpressionError, Kind, evaluate
from fdcad.ui.node_editor import strings

if TYPE_CHECKING:
    from fdcad.core.graph.engine import NodeResult

#: Called with (node id, parameter name, new value, merge key or None).
Change = Callable[[str, str, Any, str | None], None]
SLIDER_TICKS = 1000

_PORT_KIND = {PortType.LENGTH: Kind.LENGTH, PortType.ANGLE: Kind.ANGLE}
_SETTING_KIND = {"number": Kind.NUMBER, "length": Kind.LENGTH, "angle": Kind.ANGLE}


def parse(text: str, kind: Kind, doc: Document, variables: dict[str, tuple[Kind, float]]) -> Param:
    """A typed value as a parameter object. Raises ExpressionError."""
    return Param(text.strip(), evaluate(text, kind, doc.units, variables))


class ValueField(QLineEdit):
    """A text field for one typed value. Shows the typed text."""

    def __init__(
        self, text: str, apply: Callable[[str], str | None], parent: QWidget | None = None
    ) -> None:
        super().__init__(text, parent)
        self._apply = apply
        self.editingFinished.connect(self._done)

    def _done(self) -> None:
        problem = self._apply(self.text())
        self.setToolTip(problem or "")
        self.setProperty("invalid", problem is not None)
        self.style().unpolish(self)
        self.style().polish(self)


class NodeForm(QWidget):
    """Shows and edits the selected node."""

    def __init__(self, change: Change, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("node_form")
        self.change = change
        self.layout_ = QFormLayout(self)
        self.layout_.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.node: Node | None = None
        self.fields: dict[str, QWidget] = {}
        self.run_anyway: QPushButton | None = None
        self.message = QLabel(strings.NOTHING_SELECTED)
        self.message.setWordWrap(True)
        self.layout_.addRow(self.message)
        self.reference_picker: Callable[[], dict[str, Any] | None] | None = None

    def _clear(self) -> None:
        while self.layout_.rowCount():
            self.layout_.removeRow(0)
        self.fields = {}
        self.run_anyway = None

    def show_node(
        self,
        graph: Graph | None,
        nid: str | None,
        doc: Document | None,
        variables: dict[str, tuple[Kind, float]],
        result: NodeResult | None = None,
    ) -> None:
        """Fill the form for node ``nid`` of ``graph``."""
        self._clear()
        node = graph.find(nid) if graph is not None and nid is not None else None
        self.node = node
        ntype = NODE_TYPES.get(node.type) if node is not None else None
        if node is None or ntype is None or graph is None or doc is None:
            self.message = QLabel(strings.NOTHING_SELECTED)
            self.message.setWordWrap(True)
            self.layout_.addRow(self.message)
            return
        title = QLabel(f"<b>{ntype.title}</b>  ({node.id})")
        self.layout_.addRow(title)
        wired = {w.input for w in graph.wires_into(node.id)}
        for port in ntype.inputs:
            if port.name in wired or port.type in (PortType.CURVE, PortType.BODY, PortType.PLANE):
                continue
            widget = self._port_field(node, port, doc, variables)
            if widget is not None:
                self.fields[port.name] = widget
                self.layout_.addRow(port.title, widget)
        for setting in ntype.settings:
            widget = self._setting_field(node, setting, doc, variables)
            self.fields[setting.name] = widget
            self.layout_.addRow(setting.title, widget)
        if node.type == "slider":
            self._slider_row(node)
        if result is not None and (result.error or result.warning):
            text = QLabel(result.error or result.warning or "")
            text.setWordWrap(True)
            text.setObjectName("node_message")
            self.layout_.addRow(text)
            if result.needs_confirmation:
                self.run_anyway = QPushButton(strings.RUN_ANYWAY)
                self.run_anyway.setObjectName("run_anyway")
                self.run_anyway.clicked.connect(
                    lambda: self.change(node.id, "allow_many", True, None)
                )
                self.layout_.addRow(self.run_anyway)

    # Fields --------------------------------------------------------------------------

    def _typed(
        self,
        nid: str,
        name: str,
        kind: Kind,
        doc: Document,
        variables: dict[str, tuple[Kind, float]],
    ) -> Callable[[str], str | None]:
        def apply(text: str) -> str | None:
            try:
                value = parse(text, kind, doc, variables)
            except ExpressionError as exc:
                return str(exc)
            self.change(nid, name, value, None)
            return None

        return apply

    def _port_field(
        self, node: Node, port: Port, doc: Document, variables: dict[str, tuple[Kind, float]]
    ) -> QWidget | None:
        stored = node.params.get(port.name, port.default)
        if port.type in (PortType.POINT, PortType.VECTOR) and not port.whole_list:
            return self._point_field(node, port, stored)
        if port.type in (PortType.NUMBER, PortType.LENGTH, PortType.ANGLE) and not port.whole_list:
            kind = _PORT_KIND.get(port.type, Kind.NUMBER)
            text = (
                stored.expr
                if isinstance(stored, Param)
                else (f"{stored:g}" if isinstance(stored, int | float) else "")
            )
            return ValueField(text, self._typed(node.id, port.name, kind, doc, variables))
        if port.type is PortType.BOOLEAN:
            box = QCheckBox()
            box.setChecked(bool(stored))
            box.toggled.connect(
                lambda on, n=node.id, k=port.name: self.change(n, k, bool(on), None)
            )
            return box
        return None

    def _point_field(self, node: Node, port: Port, stored: Any) -> QWidget:
        values = (
            list(stored)
            if isinstance(stored, list | tuple) and len(stored) == 3
            else [0.0, 0.0, 0.0]
        )
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        edits: list[QLineEdit] = []

        def apply(_text: str) -> str | None:
            try:
                point = [float(e.text()) for e in edits]
            except ValueError:
                return "Enter three numbers in millimetres."
            self.change(node.id, port.name, point, None)
            return None

        for v in values:
            edit = ValueField(f"{float(v):g}", apply)
            edits.append(edit)
            row.addWidget(edit)
        return holder

    def _setting_field(
        self, node: Node, setting: Setting, doc: Document, variables: dict[str, tuple[Kind, float]]
    ) -> QWidget:
        stored = node.params.get(setting.name, setting.default)
        nid, name = node.id, setting.name
        if setting.kind == "bool":
            box = QCheckBox()
            box.setChecked(bool(stored))
            box.toggled.connect(lambda on: self.change(nid, name, bool(on), None))
            return box
        if setting.kind == "choice":
            combo = QComboBox()
            combo.addItems(list(setting.choices))
            if stored in setting.choices:
                combo.setCurrentText(str(stored))
            combo.currentTextChanged.connect(lambda text: self.change(nid, name, text, None))
            return combo
        if setting.kind == "int":
            spin = QSpinBox()
            spin.setRange(0, 1_000_000)
            spin.setValue(int(stored or 0))
            spin.valueChanged.connect(lambda v: self.change(nid, name, int(v), None))
            return spin
        if setting.kind == "float":
            text = f"{float(stored):g}" if isinstance(stored, int | float) else "0"

            def apply_float(t: str) -> str | None:
                try:
                    value = evaluate(t, Kind.NUMBER, doc.units, variables)
                except ExpressionError as exc:
                    return str(exc)
                self.change(nid, name, value, None)
                return None

            return ValueField(text, apply_float)
        if setting.kind in _SETTING_KIND:
            chosen = str(node.params.get("kind", "number")) if name == "value" else setting.kind
            kind = _SETTING_KIND.get(chosen, Kind.NUMBER)
            text = stored.expr if isinstance(stored, Param) else ""
            return ValueField(text, self._typed(nid, name, kind, doc, variables))
        if setting.kind == "variable":
            combo = QComboBox()
            combo.addItem("")
            combo.addItems([v.name for v in doc.variables])
            combo.setCurrentText(str(stored or ""))
            combo.currentTextChanged.connect(lambda text: self.change(nid, name, text, None))
            return combo
        if setting.kind == "feature":
            combo = QComboBox()
            combo.addItem("", "")
            for f in doc.features[4:]:
                combo.addItem(f"{f.name} ({f.id})", f.id)
            index = combo.findData(str(stored or ""))
            combo.setCurrentIndex(max(index, 0))
            combo.currentIndexChanged.connect(
                lambda _i: self.change(nid, name, str(combo.currentData()), None)
            )
            return combo
        if setting.kind == "param":
            combo = QComboBox()
            combo.addItem("")
            fid = str(node.params.get("feature", ""))
            feature = next((f for f in doc.features if f.id == fid), None)
            if feature is not None:
                combo.addItems(sorted(k for k, v in feature.params.items() if isinstance(v, Param)))
            combo.setCurrentText(str(stored or ""))
            combo.currentTextChanged.connect(lambda text: self.change(nid, name, text, None))
            return combo
        if setting.kind == "ref":
            button = QPushButton(_ref_text(stored))
            button.setObjectName("use_selection")

            def pick() -> None:
                if self.reference_picker is None:
                    return
                ref = self.reference_picker()
                if ref is not None:
                    self.change(nid, name, ref, None)

            button.clicked.connect(pick)
            return button
        edit = QLineEdit(str(stored or ""))
        edit.editingFinished.connect(lambda: self.change(nid, name, edit.text(), None))
        return edit

    def _slider_row(self, node: Node) -> None:
        low = float(node.params.get("min", 0.0) or 0.0)
        high = float(node.params.get("max", 10.0) or 10.0)
        step = float(node.params.get("step", 1.0) or 0.0)
        value = node.params.get("value")
        current = value.value if isinstance(value, Param) else low
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setObjectName("node_slider")
        slider.setRange(0, SLIDER_TICKS)
        span = high - low
        slider.setValue(round((current - low) / span * SLIDER_TICKS) if span > 0 else 0)

        def moved(tick: int) -> None:
            v = snap(low + span * tick / SLIDER_TICKS, low, high, step)
            self.change(node.id, "value", Param(f"{v:g}", v), f"slider:{node.id}")

        slider.valueChanged.connect(moved)
        self.fields["slider"] = slider
        self.layout_.addRow("", slider)


def _ref_text(stored: Any) -> str:
    if isinstance(stored, dict):
        name = stored.get("name") or stored.get("feature")
        if name:
            return f"{name} (use selection to change)"
    return "Use Selection"
