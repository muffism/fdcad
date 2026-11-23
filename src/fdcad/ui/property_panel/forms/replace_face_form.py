"""Replace Face panel (TR130, DECISIONS D1412): the faces to replace and the target."""

from __future__ import annotations

from typing import Any

from fdcad.core.document.model import Feature
from fdcad.core.naming.names import NamedShape
from fdcad.ui import strings
from fdcad.ui.property_panel.forms.base import form
from fdcad.ui.property_panel.forms.spec_form import F, G, SpecForm


@form("replace_face")
class ReplaceFaceForm(SpecForm):
    """Edits a Replace Face feature. Picks go to Faces to Replace until it has one,
    then to the target; clicking a list sends the next picks to it."""

    layout = (
        G(
            "replace",
            strings.REPLACE_FACE,
            strings.REPLACE_FACE_TIP,
            (
                F("faces", strings.REPLACE_FACE_FACES, "faces", strings.REPLACE_FACE_FACES_TIP),
                F(
                    "target",
                    strings.REPLACE_FACE_TARGET,
                    "faces",
                    strings.REPLACE_FACE_TARGET_TIP,
                    single=True,
                ),
            ),
        ),
    )

    _auto = True

    def _activate(self, name: str) -> None:
        self._auto = False  # a list was clicked: the next picks go to it
        super()._activate(name)

    def take_shapes(self, body: NamedShape, shapes: list[Any]) -> str | None:
        """The first picks replace; once a face is listed, the next pick is the target."""
        if self._auto:
            self.active_pick = "faces" if not self.picks["faces"].refs() else "target"
        return super().take_shapes(body, shapes)

    def extra_apply(self, feature: Feature) -> str | None:
        """Both lists are needed."""
        if not feature.refs.get("target"):
            return strings.REPLACE_FACE_NEEDS_TARGET
        return None


def start_replace(window: Any, tab: Any) -> None:
    """Open a new Replace Face; the selected faces become the faces to replace."""
    from fdcad.ui.main_window.new_feature import FeatureFlow

    if getattr(window, "feature_flow", None) is None:
        window.feature_flow = FeatureFlow(window)
    window.feature_flow.open_direct(tab, "replace_face", "boss")
