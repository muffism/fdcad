"""Snap options at the cursor (F3, TOOL_SPEC T12.4 and T1.2.8).

A small popup with the three Phase 1 snap settings: snapping, snap to model
geometry and automatic relations. Each change is saved in the preferences at
once and reaches an open sketch through ``changed``.
"""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QCheckBox, QFrame, QLabel, QVBoxLayout, QWidget

from fdcad.ui import strings
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.sketch_tools.options import SketchOptions

#: The settings in the popup (the first three of T1.2.8).
SNAP_KEYS = ("snapping", "model_snaps", "auto_relations")


def with_snap(options: SketchOptions, key: str, on: bool) -> SketchOptions:
    """``options`` with one of the :data:`SNAP_KEYS` switches set to ``on``.

    Only the three boolean switches can be set, so no other preference (such as
    the over define choice) can ever be given a bool (D483).
    """
    if key == "snapping":
        return replace(options, snapping=on)
    if key == "model_snaps":
        return replace(options, model_snaps=on)
    if key == "auto_relations":
        return replace(options, auto_relations=on)
    raise ValueError(f"not a snap setting: {key}")


class SnapOptions(QFrame):
    """Three tick boxes bound to the sketch preferences."""

    changed = Signal()

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("snap_options")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.settings = settings
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        title = QLabel(strings.SNAP_OPTIONS_TITLE)
        title.setObjectName("snap_options_title")
        layout.addWidget(title)
        options = settings.sketch_options
        self.boxes: dict[str, QCheckBox] = {}
        for key in SNAP_KEYS:
            label, tip = strings.PREF_SKETCH[key]
            box = QCheckBox(label)
            box.setObjectName(f"snap_{key}")
            box.setToolTip(tip)
            box.setChecked(getattr(options, key))
            box.toggled.connect(lambda on, k=key: self._set(k, on))
            layout.addWidget(box)
            self.boxes[key] = box

    def _set(self, key: str, on: bool) -> None:
        self.settings.sketch_options = with_snap(self.settings.sketch_options, key, on)
        self.changed.emit()

    def open_at(self, pos: QPoint) -> None:
        """Show with its top left at a screen point."""
        self.adjustSize()
        self.move(pos)
        self.show()
