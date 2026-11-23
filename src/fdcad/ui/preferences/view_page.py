"""Preferences > View: edge display, display quality and mouse settings (round 12)."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QWidget

from fdcad.ui.preferences.view_options import ViewOptions

TAB_VIEW = "View"
SMOOTH_EDGES = "Smooth edges"
SMOOTH_EDGES_TIP = "How edges between faces that meet smoothly are drawn in Shaded with Edges."
SMOOTH_LABELS = {"shown": "Shown", "dashed": "Dashed", "removed": "Removed"}
HIDDEN_EDGES = "Hidden edges"
HIDDEN_EDGES_TIP = "How hidden edges are drawn in Hidden Lines Visible."
HIDDEN_LABELS = {"dashed": "Dashed", "solid": "Solid"}
FEATURE_EDGES = "Highlight all edges of the feature selected in the tree"
FEATURE_EDGES_TIP = "Draws every edge of the selected feature in the selection colour."
WHEEL_REVERSE = "Reverse the mouse wheel zoom"
ZOOM_CENTRE = "Zoom about"
ZOOM_CENTRE_LABELS = {"cursor": "The pointer", "centre": "The view centre"}
ARROW_STEP = "Arrow key turn"
TURN_SPEED = "Mouse turn speed"
FIT_ON_VIEW = "Zoom to fit when a standard view is chosen"
MOUSE_PRESET = "Middle button"
MOUSE_PRESET_TIP = "What a middle button drag does, alone and with Shift, Ctrl or Alt."
MOUSE_PRESET_LABELS = {
    "turn": "Drag turns; Shift zooms, Ctrl pans",
    "turn_shift_pan": "Drag turns; Shift pans, Ctrl zooms",
    "pan": "Drag pans; Shift turns, Ctrl zooms",
}


def _combo(name: str, tip: str, labels: dict[str, str], value: str) -> QComboBox:
    box = QComboBox()
    box.setObjectName(name)
    box.setToolTip(tip)
    for key, label in labels.items():
        box.addItem(label, key)
    box.setCurrentIndex(max(box.findData(value), 0))
    return box


class ViewPage(QWidget):
    """The View page of Preferences."""

    def __init__(self, store: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        options = ViewOptions(store)
        form = QFormLayout(self)
        self.smooth_box = _combo(
            "pref_smooth_edges", SMOOTH_EDGES_TIP, SMOOTH_LABELS, options.smooth_edges
        )
        form.addRow(SMOOTH_EDGES, self.smooth_box)
        self.hidden_box = _combo(
            "pref_hidden_edges", HIDDEN_EDGES_TIP, HIDDEN_LABELS, options.hidden_edges
        )
        form.addRow(HIDDEN_EDGES, self.hidden_box)
        self.feature_edges_box = QCheckBox(FEATURE_EDGES)
        self.feature_edges_box.setObjectName("pref_feature_edges")
        self.feature_edges_box.setToolTip(FEATURE_EDGES_TIP)
        self.feature_edges_box.setChecked(options.feature_edges)
        form.addRow("", self.feature_edges_box)
        from PySide6.QtWidgets import QDoubleSpinBox

        self.wheel_box = QCheckBox(WHEEL_REVERSE)  # TR211
        self.wheel_box.setObjectName("pref_wheel_reverse")
        self.wheel_box.setChecked(options.wheel_reverse)
        form.addRow("", self.wheel_box)
        self.zoom_box = _combo(
            "pref_zoom_about",
            ZOOM_CENTRE,
            ZOOM_CENTRE_LABELS,
            "cursor" if options.zoom_about_cursor else "centre",
        )
        form.addRow(ZOOM_CENTRE, self.zoom_box)
        self.arrow_box = QDoubleSpinBox()
        self.arrow_box.setObjectName("pref_arrow_step")
        self.arrow_box.setRange(1.0, 90.0)
        self.arrow_box.setSuffix(" deg")
        self.arrow_box.setValue(options.arrow_step)
        form.addRow(ARROW_STEP, self.arrow_box)
        self.speed_box = QDoubleSpinBox()
        self.speed_box.setObjectName("pref_turn_speed")
        self.speed_box.setRange(0.25, 4.0)
        self.speed_box.setSingleStep(0.25)
        self.speed_box.setSuffix(" x")
        self.speed_box.setValue(options.turn_speed)
        form.addRow(TURN_SPEED, self.speed_box)
        self.fit_box = QCheckBox(FIT_ON_VIEW)
        self.fit_box.setObjectName("pref_fit_on_view")
        self.fit_box.setChecked(options.fit_on_view)
        form.addRow("", self.fit_box)
        self.preset_box = _combo(  # TR312
            "pref_mouse_preset", MOUSE_PRESET_TIP, MOUSE_PRESET_LABELS, options.mouse_preset
        )
        form.addRow(MOUSE_PRESET, self.preset_box)
        self.form = form

    def apply(self, store: Any) -> None:
        """Write the page's values back."""
        options = ViewOptions(store)
        options.smooth_edges = str(self.smooth_box.currentData())
        options.hidden_edges = str(self.hidden_box.currentData())
        options.feature_edges = self.feature_edges_box.isChecked()
        options.wheel_reverse = self.wheel_box.isChecked()
        options.zoom_about_cursor = self.zoom_box.currentData() == "cursor"
        options.arrow_step = self.arrow_box.value()
        options.turn_speed = self.speed_box.value()
        options.fit_on_view = self.fit_box.isChecked()
        options.mouse_preset = str(self.preset_box.currentData())
