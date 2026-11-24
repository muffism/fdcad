"""Property panel content while a sketch is open: status, relations, OK and Cancel."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.sketch.model import Spline
from fdcad.core.sketch.solver import SketchStatus
from fdcad.ui import icons, strings
from fdcad.ui.empty_state import EmptyOverlay, empty_label
from fdcad.ui.sketch_tools import tool_text
from fdcad.ui.sketch_tools.canvas import SketchCanvas, relation_index
from fdcad.ui.sketch_tools.dimension_panel import DimensionPanel
from fdcad.ui.sketch_tools.edit import ordered_for, relations_for
from fdcad.ui.sketch_tools.pick_panel import PickToolPanel
from fdcad.ui.sketch_tools.shape_panel import ShapeValues, ToolOptions
from fdcad.ui.themes.style import unit
from fdcad.ui.themes.typography import Role, type_font


class SketchPanel(QWidget):
    """Shows the sketch status and offers relations for the selection."""

    accepted = Signal()
    rejected = Signal()

    def __init__(self, canvas: SketchCanvas, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.canvas = canvas
        self.title = QLabel(f"<b>{canvas.edit.feature.name}</b>")
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.issues = QLabel()
        self.issues.setWordWrap(True)
        self.selected = QLabel()
        self.selection_state = QLabel()
        self.relation_box = QGroupBox(strings.SKETCH_RELATIONS)
        # An empty card says what will show in it (D2702): one muted line above the
        # grid of buttons, hidden as soon as a relation fits the selection.
        relation_rows = QVBoxLayout(self.relation_box)
        self.relation_empty = empty_label(strings.RELATIONS_NONE_PICKED, compact=True)
        relation_rows.addWidget(self.relation_empty)
        self.relation_grid = QGridLayout()
        relation_rows.addLayout(self.relation_grid)
        self.existing = QListWidget()
        self.existing.setMaximumHeight(160)
        #: The same for the list of relations, in its middle (D2702).
        self.existing_empty = EmptyOverlay(self.existing, strings.EXISTING_NONE_PICKED)
        # Hovering a row highlights its tag in the sketch (T14.1.3).
        self.existing.setMouseTracking(True)
        self.existing.itemEntered.connect(self._hover_relation)
        self.existing.viewport().installEventFilter(self)
        #: Options of the active drawing tool, and the values of a shape (T7.2, T7.3).
        self.tool_options = ToolOptions(canvas)
        self.shape_values = ShapeValues(canvas)
        #: The panel of a Phase 2 sketch tool (P2.8).
        self.pick_panel = PickToolPanel(canvas)
        #: Show curvature combs on splines (P2.8 item 10, D514): shown for the Spline
        #: tool or a selected spline.
        self.curvature = QCheckBox(tool_text.SHOW_CURVATURE)
        self.curvature.setObjectName("show_curvature")
        self.curvature.setToolTip(tool_text.SHOW_CURVATURE_TIP)
        self.curvature.setChecked(canvas.show_curvature)
        self.curvature.toggled.connect(canvas.set_show_curvature)
        #: One delete button per listed relation, keyed by relation index (T3.2.4).
        self.delete_buttons: dict[int, QToolButton] = {}
        #: Value, driving or reference and Measure To of a dimension (T4.2.5, T7.4).
        self.dimension_panel = DimensionPanel(canvas)
        self.construction = QPushButton(icons.icon("sketch.construction"), strings.CONSTRUCTION)
        self.construction.clicked.connect(self._toggle_construction)
        # OK and Cancel at equal width across the panel, as in the property panel
        # (D2692): a button box put them at the right at their smallest size.
        self.ok_button = QPushButton(strings.OK)
        self.ok_button.setObjectName("panel_ok")
        self.cancel_button = QPushButton(strings.CANCEL)
        self.ok_button.clicked.connect(self.accepted.emit)
        self.cancel_button.clicked.connect(self.rejected.emit)
        existing_box = QGroupBox(strings.SKETCH_EXISTING)
        self.existing_box = existing_box
        existing_layout = QVBoxLayout(existing_box)
        existing_layout.addWidget(self.existing)
        self.setObjectName("property_panel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        u = unit(self.font())
        self.title.setObjectName("panel_title")
        self.title.setFont(type_font(Role.TITLE))
        header_box = QWidget()
        header_box.setObjectName("panel_header")
        header_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        # Two rows, like the property panel (D1034): OK and Cancel never get cut off.
        rows = QVBoxLayout(header_box)
        rows.setContentsMargins(3 * u, 3 * u, 3 * u, 3 * u)  # 12 px panel padding (U2.2)
        rows.setSpacing(2 * u)
        header = QHBoxLayout()
        header.setSpacing(2 * u)
        rows.addLayout(header)
        sketch_icon = QLabel()
        size = self.style().pixelMetric(QStyle.PixelMetric.PM_LargeIconSize)
        sketch_icon.setPixmap(
            icons.icon("tree.sketch").pixmap(QSize(size, size), self.devicePixelRatioF())
        )
        header.addWidget(sketch_icon)
        header.addWidget(self.title, 1)
        actions = QHBoxLayout()
        actions.setSpacing(2 * u)
        actions.addWidget(self.ok_button, 1)
        actions.addWidget(self.cancel_button, 1)
        rows.addLayout(actions)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(header_box)
        layout = QVBoxLayout()
        layout.setContentsMargins(3 * u, 3 * u, 3 * u, 3 * u)  # 12 px, as the header
        layout.setSpacing(2 * u)
        outer.addLayout(layout, 1)
        layout.addWidget(self.status)
        layout.addWidget(self.issues)
        layout.addWidget(self.tool_options)
        layout.addWidget(self.pick_panel)
        layout.addWidget(self.shape_values)
        layout.addWidget(self.curvature)
        layout.addWidget(self.dimension_panel)
        layout.addWidget(self.selected)
        layout.addWidget(self.selection_state)
        layout.addWidget(self.relation_box)
        layout.addWidget(existing_box)
        layout.addWidget(self.construction)
        layout.addStretch(1)
        self.relation_buttons: dict[str, QPushButton] = {}
        canvas.edited.connect(self.refresh)
        canvas.selection_changed.connect(self.refresh)
        canvas.tool_changed.connect(lambda _name: self.refresh())
        canvas.dimension_focus.connect(self._show_dimension_panel)
        canvas.curvature_toggled.connect(self._update_curvature)
        for signal in (canvas.edited, canvas.selection_changed):
            signal.connect(self._update_curvature)
        canvas.tool_changed.connect(lambda _name: self._update_curvature())
        self.refresh()
        self._update_curvature()

    def _update_curvature(self) -> None:
        """Show the curvature tick box for the Spline tool or a selected spline."""
        canvas = self.canvas
        sk = canvas.edit.sketch
        spline = any(isinstance(sk.entities.get(i), Spline) for i in canvas.selection)
        self.curvature.setVisible(canvas.tool_name == "spline" or spline)
        if self.curvature.isChecked() != canvas.show_curvature:
            self.curvature.blockSignals(True)
            self.curvature.setChecked(canvas.show_curvature)
            self.curvature.blockSignals(False)

    @property
    def measure_combos(self) -> dict[str, QComboBox]:
        """Measure To lists of the Dimension panel (T4.3.2), by circle or arc id."""
        return self.dimension_panel.measure_combos

    @property
    def measure_box(self) -> QGroupBox:
        """The Measure To group of the Dimension panel."""
        return self.dimension_panel.measure_box

    def _show_dimension_panel(self) -> None:
        self.dimension_panel.setVisible(self.dimension_panel.wanted)

    def _show_sections(self) -> None:
        """While a tool or Smart Dimension is active the panel is that tool's panel
        (T1.1.4); the relation sections return when the tool ends."""
        selecting = self.canvas.tool is None and not self.canvas.dimension_mode
        for widget in (
            self.selected,
            self.relation_box,
            self.existing_box,
            self.construction,
        ):
            widget.setVisible(selecting)
        if not selecting:
            self.selection_state.setVisible(False)

    def _hover_relation(self, item: QListWidgetItem) -> None:
        index = item.data(256)
        self.canvas.set_hot_relation(index if isinstance(index, int) else None)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """The cursor left the relation list: no tag stays highlighted."""
        if watched is self.existing.viewport() and event.type() == QEvent.Type.Leave:
            self.canvas.set_hot_relation(None)
        return super().eventFilter(watched, event)

    def refresh(self) -> None:
        """Update every part of the panel from the canvas."""
        edit = self.canvas.edit
        status = edit.status()
        pal = self.canvas.palette_colors
        color = {
            SketchStatus.UNDER.value: pal.sketch_under,
            SketchStatus.FULL.value: pal.sketch_full,
            "dangling": pal.state_warning,  # TR38 (D1301)
        }.get(status.display or status.state.value, pal.sketch_over)
        text = strings.SKETCH_STATUS[status.display or status.state.value].format(
            dof=status.dof, message=status.message
        )
        self.status.setText(f'<span style="color:{color}">{text}</span>')
        self.issues.setText("\n".join(i.message for i in status.issues))
        self.issues.setVisible(bool(status.issues))
        self._fill_relations()
        self._fill_existing()
        self._fill_state(status.conflicting)
        self._show_dimension_panel()
        self._show_sections()

    def _fill_relations(self) -> None:
        while self.relation_grid.count():
            item = self.relation_grid.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        self.relation_buttons = {}
        sk = self.canvas.edit.sketch
        ids = [s for s in self.canvas.selection if s in sk.entities]
        self.selected.setText(
            strings.SELECTED_COUNT.format(count=len(self.canvas.selection))
            if self.canvas.selection
            else strings.NOTHING_SELECTED
        )
        for i, rtype in enumerate(relations_for(sk, ids)):
            button = QPushButton(icons.icon(f"relation.{rtype}"), strings.RELATION_NAMES[rtype])
            button.clicked.connect(lambda _c=False, r=rtype: self.add_relation(r))
            self.relation_grid.addWidget(button, i // 2, i % 2)
            self.relation_buttons[rtype] = button
        self.relation_empty.setText(
            strings.RELATIONS_NONE_FIT if self.canvas.selection else strings.RELATIONS_NONE_PICKED
        )
        self.relation_empty.setVisible(not self.relation_buttons)
        self.construction.setEnabled(any(not i.startswith("d") for i in ids))

    def _fill_existing(self) -> None:
        self.existing.clear()
        self.delete_buttons = {}
        sk = self.canvas.edit.sketch
        chosen = set(self.canvas.selection)
        picked = set(self.canvas.selected_relations())
        bad, _ = self.canvas.edit.conflicting_items()
        for index, rel in enumerate(sk.relations):
            if index not in picked and not chosen & set(rel.entities):
                continue
            label = strings.RELATION_NAMES.get(rel.type, rel.type)
            # The list makes the row itself. An item made in Python gets PySide's own
            # destructor, which crashed in clear() on the Mac runner (IDEAS 85).
            self.existing.addItem("")
            item = self.existing.item(self.existing.count() - 1)
            item.setData(256, index)
            row = QWidget()
            line = QHBoxLayout(row)
            line.setContentsMargins(2, 0, 2, 0)
            icon = QLabel()
            icon.setPixmap(
                icons.icon(f"relation.{rel.type}").pixmap(QSize(16, 16), self.devicePixelRatioF())
            )
            text = QLabel(f"{label} ({', '.join(rel.entities)})")
            if index in bad:
                text.setStyleSheet(f"color: {self.canvas.palette_colors.sketch_over}")
            delete = QToolButton()
            delete.setIcon(icons.icon("edit.delete"))
            delete.setToolTip(strings.DELETE_RELATION)
            delete.setAutoRaise(True)
            delete.clicked.connect(lambda _c=False, i=index: self.delete_relation(i))
            line.addWidget(icon)
            line.addWidget(text, 1)
            line.addWidget(delete)
            item.setSizeHint(row.sizeHint())
            self.existing.setItemWidget(item, row)
            self.delete_buttons[index] = delete
        self.existing_empty.setText(
            strings.EXISTING_NONE if chosen or picked else strings.EXISTING_NONE_PICKED
        )

    def selection_state_of(self, conflicting: set[str]) -> str:
        """State of the selected entities: ``under``, ``full``, ``over`` or "" (T3.2.4)."""
        edit = self.canvas.edit
        ids = [s for s in self.canvas.selection if s in edit.sketch.entities]
        if not ids:
            return ""
        if conflicting & set(ids):
            return "over"
        if all(i in edit.defined for i in ids):
            return "full"
        return "under"

    def _fill_state(self, conflicting: set[str]) -> None:
        state = self.selection_state_of(conflicting)
        self.selection_state.setText(strings.SELECTION_STATE.get(state, ""))
        self.selection_state.setVisible(bool(state))

    def set_measure(self, did: str, rid: str, side: str) -> None:
        """Measure dimension ``did`` to the centre, nearest or farthest side of ``rid``."""
        self.dimension_panel.set_measure(did, rid, side)

    def add_relation(self, rtype: str) -> None:
        """Add a relation between the selected entities."""
        sk = self.canvas.edit.sketch
        ids = ordered_for(sk, rtype, [s for s in self.canvas.selection if s in sk.entities])
        self.canvas.run(lambda: self.canvas.edit.relate(rtype, ids))

    def delete_relation(self, index: int) -> None:
        """Delete one relation (undoable inside the sketch)."""
        self.canvas.selection = [s for s in self.canvas.selection if relation_index(s) is None]
        self.canvas.run(lambda: self.canvas.edit.delete({f"r{index}"}))
        self.canvas.selection_changed.emit()

    def _toggle_construction(self) -> None:
        ids = {s for s in self.canvas.selection if s in self.canvas.edit.sketch.entities}
        self.canvas.run(lambda: self.canvas.edit.toggle_construction(ids))
