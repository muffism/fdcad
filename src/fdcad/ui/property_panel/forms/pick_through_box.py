"""The Select Through Faces tick of the Fillet and Chamfer panels (TR64 item 4, D1800)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QCheckBox

from fdcad.ui import strings_finish as text
from fdcad.ui.viewport.through_edges import set_pick_through

if TYPE_CHECKING:
    from fdcad.ui.property_panel.forms.base import FeatureForm

#: The tick's state, kept for the session like other panel settings.
_STATE = {"on": False}


def pick_through_box(form_: FeatureForm, name: str) -> QCheckBox:
    """A tick that lets view clicks take hidden edges while the panel is open. It is
    view state only: nothing is written to the feature."""
    box = QCheckBox(text.FIELD_PICK_THROUGH)
    box.setObjectName(name)
    box.setToolTip(text.FIELD_PICK_THROUGH_TIP)
    box.setChecked(_STATE["on"])
    panel = form_.panel

    def toggled(on: bool) -> None:
        _STATE["on"] = on
        set_pick_through(panel, on)

    box.toggled.connect(toggled)
    set_pick_through(panel, _STATE["on"])
    form_.destroyed.connect(lambda *_a: set_pick_through(panel, False))
    return box
