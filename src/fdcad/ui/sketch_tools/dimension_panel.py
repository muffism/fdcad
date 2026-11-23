"""The Dimension panel (TOOL_SPEC T4.2.5, T7.4, owner note 3).

Shown in the left panel while Smart Dimension is active and when one dimension
is selected. It holds the value (the same as the value box), whether the
dimension is driving or a reference, and Measure To for distances to circles
and arcs (T4.3.2). Before a dimension is placed it shows the value it would
get (T4.2.1). Every change is a step on the sketch's undo list.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.sketch.model import Arc, Dimension
from fdcad.ui import strings
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.edit import measure_options
from fdcad.ui.themes.style import unit


class DimensionPanel(QGroupBox):
    """Value, driving or reference, and Measure To of one sketch dimension."""

    def __init__(self, canvas: SketchCanvas, parent: QWidget | None = None) -> None:
        super().__init__(strings.DIMENSION_PANEL, parent)
        self.setObjectName("dimension_panel")
        self.canvas = canvas
        #: The dimension shown, or None (the hint shows instead).
        self.dimension: Dimension | None = None
        u = unit(self.font())
        layout = QVBoxLayout(self)
        layout.setSpacing(u)
        self.kind = QLabel()
        self.hint = QLabel(strings.DIMENSION_PANEL_HINT)
        self.hint.setWordWrap(True)
        self.value = QLineEdit()
        self.value.setObjectName("dimension_value")
        self.value.setToolTip(strings.DIMENSION_VALUE_TIP)
        # Enter or leaving the field applies the value, so Tab never drops it (D593).
        self.value.returnPressed.connect(self.apply_value)
        self.value.editingFinished.connect(self.apply_value)
        self.name = QLineEdit()  # TR32: the dimension's name in formulas
        self.name.setObjectName("dimension_name")
        self.name.setToolTip(strings.DIMENSION_NAME_TIP)
        self.name.setPlaceholderText(strings.DIMENSION_NAME_EMPTY)
        self.name.returnPressed.connect(self.apply_name)
        self.name.editingFinished.connect(self.apply_name)
        form = QFormLayout()
        form.addRow(strings.DIMENSION_VALUE, self.value)
        form.addRow(strings.DIMENSION_NAME, self.name)
        self.driving = QRadioButton(strings.DIMENSION_DRIVING)
        self.driving.setToolTip(strings.DIMENSION_DRIVING_TIP)
        self.reference = QRadioButton(strings.DIMENSION_REFERENCE)
        self.reference.setToolTip(strings.DIMENSION_REFERENCE_TIP)
        self._modes = QButtonGroup(self)
        self._modes.addButton(self.driving)
        self._modes.addButton(self.reference)
        self.driving.clicked.connect(lambda: self.set_driving(True))
        self.reference.clicked.connect(lambda: self.set_driving(False))
        modes = QHBoxLayout()
        modes.addWidget(self.driving)
        modes.addWidget(self.reference)
        modes.addStretch(1)
        self.measure_box = QGroupBox(strings.MEASURE_TO)
        self.measure_form = QFormLayout(self.measure_box)
        self.measure_combos: dict[str, QComboBox] = {}
        self.reset_label = QPushButton(strings.DIMENSION_RESET_LABEL)
        self.reset_label.setToolTip(strings.DIMENSION_RESET_LABEL_TIP)
        self.reset_label.clicked.connect(self._reset_label)
        layout.addWidget(self.hint)
        layout.addWidget(self.kind)
        layout.addLayout(form)
        layout.addLayout(modes)
        layout.addWidget(self.measure_box)
        layout.addWidget(self.reset_label)
        canvas.dimension_focus.connect(self.refresh)
        canvas.edited.connect(self.refresh)
        canvas.selection_changed.connect(self.refresh)
        self.refresh()

    @property
    def wanted(self) -> bool:
        """True when the panel has something to show: Smart Dimension or a dimension."""
        return self.canvas.dimension_mode or self.canvas.panel_dimension() is not None

    def refresh(self) -> None:
        """Show the canvas's current dimension."""
        dim = self.canvas.panel_dimension()
        changed = dim is not self.dimension
        self.dimension = dim
        has = dim is not None
        for widget in (self.kind, self.value, self.name, self.driving, self.reference):
            widget.setVisible(has)
        self.hint.setVisible(not has)
        if dim is None:
            self._fill_measure(None)
            self.reset_label.setVisible(False)
            return
        preview = dim.id == "preview"
        self.kind.setText(strings.DIMENSION_TYPES.get(dim.type, dim.type))
        editable = dim.driving and not preview
        self.value.setReadOnly(not editable)
        if changed or not self.value.hasFocus() or not editable:
            self.value.setText(self._text(dim))
        self.name.setEnabled(not preview)
        if changed or not self.name.hasFocus():
            self.name.setText(dim.name or "")
        for button in (self.driving, self.reference):
            button.setEnabled(not preview)
        (self.driving if dim.driving else self.reference).setChecked(True)
        self._fill_measure(None if preview else dim)
        self.reset_label.setVisible(not preview and dim.label is not None)

    def _text(self, dim: Dimension) -> str:
        """The value as typed, or the measured size of a reference or preview."""
        if dim.driving and dim.id != "preview":
            return dim.param.expr
        return self.canvas.dimension_value_text(dim)

    def apply_value(self) -> None:
        """Enter in the value field, or leaving it: change the dimension, as the value
        box does. Text that is already the dimension's value changes nothing."""
        dim = self.dimension
        if dim is None or dim.id == "preview" or not dim.driving:
            return
        text = self.value.text().strip()
        if text == dim.param.expr and not self.value.property("error"):
            return
        error = self.canvas.apply_dimension_text(dim.id, text)
        self.value.setToolTip(error or strings.DIMENSION_VALUE_TIP)
        self.value.setProperty("error", bool(error))
        self.value.style().unpolish(self.value)
        self.value.style().polish(self.value)

    def apply_name(self) -> None:
        """Enter in the Name field, or leaving it: name the dimension (TR32)."""
        dim = self.dimension
        if dim is None or dim.id == "preview":
            return
        text = self.name.text().strip()
        if text == (dim.name or ""):
            return
        error = self.canvas.set_dimension_name(dim.id, text)
        self.name.setToolTip(error or strings.DIMENSION_NAME_TIP)
        self.name.setProperty("error", bool(error))
        self.name.style().unpolish(self.name)
        self.name.style().polish(self.name)

    def set_driving(self, driving: bool) -> None:
        """Make the dimension driving or a reference (T1.4.4, T4.2.5)."""
        dim = self.dimension
        if dim is None or dim.id == "preview" or dim.driving == driving:
            return
        self.canvas.set_dimension_driving(dim.id, driving)
        self.refresh()

    def _reset_label(self) -> None:
        dim = self.dimension
        if dim is not None and dim.id != "preview":
            did = dim.id
            self.canvas.run(lambda: self.canvas.edit.set_label(did, None))

    def _fill_measure(self, dim: Dimension | None) -> None:
        # A combo's own change rebuilds this form, so its widgets must outlive the
        # signal: take the rows out and delete the widgets later, never at once.
        while self.measure_form.rowCount():
            row = self.measure_form.takeRow(0)
            for item in (row.labelItem, row.fieldItem):
                widget = item.widget() if item is not None else None
                if widget is not None:
                    widget.hide()
                    widget.deleteLater()
        self.measure_combos = {}
        sk = self.canvas.edit.sketch
        options = measure_options(sk, dim) if dim is not None else {}
        self.measure_box.setVisible(bool(options))
        for rid, side in options.items():
            combo = QComboBox()
            for key in ("center", "nearest", "farthest"):
                combo.addItem(strings.MEASURE_SIDES[key], key)
            combo.setCurrentIndex(combo.findData(side))
            assert dim is not None
            did = dim.id
            combo.currentIndexChanged.connect(
                lambda _i, c=combo, r=rid, d=did: self.set_measure(d, r, str(c.currentData()))
            )
            kind = strings.MEASURE_KINDS["arc" if isinstance(sk.entities[rid], Arc) else "circle"]
            self.measure_form.addRow(f"{kind} {rid}", combo)
            self.measure_combos[rid] = combo

    def set_measure(self, did: str, rid: str, side: str) -> None:
        """Measure dimension ``did`` to the centre, nearest or farthest side of ``rid``."""
        self.canvas.run(lambda: self.canvas.edit.set_measure(did, rid, side))
