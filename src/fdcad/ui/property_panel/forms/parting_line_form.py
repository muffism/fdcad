"""Parting Line panel (TR84, DECISIONS D1415): the pull direction and Reverse."""

from __future__ import annotations

from typing import Any

from fdcad.core.document.model import Feature
from fdcad.ui import strings
from fdcad.ui import strings_finish as finish
from fdcad.ui.property_panel.forms.base import form
from fdcad.ui.property_panel.forms.spec_form import F, G, SpecForm


@form("parting_line")
class PartingLineForm(SpecForm):
    """Edits a Parting Line feature."""

    layout = (
        G(
            "parting_line",
            strings.PARTING_LINE,
            strings.PARTING_LINE_TIP,
            (
                F("direction", strings.PARTING_LINE_DIRECTION, "any", strings.PARTING_LINE_TIP,
                  single=True),
                F("reverse", strings.PARTING_LINE_REVERSE, "bool", strings.PARTING_LINE_TIP),
                F("split_faces", finish.PARTING_SPLIT, "bool", finish.PARTING_SPLIT_TIP),
            ),
        ),
    )  # fmt: skip

    def extra_apply(self, feature: Feature) -> str | None:
        """The direction is one reference."""
        ref = feature.refs.get("direction")
        if isinstance(ref, list):
            feature.refs["direction"] = ref[0]
        return None

    def build(self) -> None:
        """Show a stored direction (one reference) in its list."""
        stored = self.feature.refs.get("direction")
        if isinstance(stored, dict):
            self.feature.refs["direction"] = [stored]
        super().build()
        if isinstance(stored, dict):
            self.feature.refs["direction"] = stored


def start_parting_line(window: Any, tab: Any) -> None:
    """Open a new Parting Line; a selected flat face or edge becomes the pull."""
    from fdcad.ui.main_window.new_feature import FeatureFlow

    if getattr(window, "feature_flow", None) is None:
        window.feature_flow = FeatureFlow(window)
    window.feature_flow.open_direct(tab, "parting_line", "boss")
