"""Split Line panel (TR60, DECISIONS D1414): method, faces, the sketch or the plane."""

from __future__ import annotations

from typing import Any

from fdcad.ui import strings
from fdcad.ui import strings_finish as finish
from fdcad.ui.property_panel.forms.base import form
from fdcad.ui.property_panel.forms.spec_form import F, G, SpecForm


def _projection(v: dict[str, Any]) -> bool:
    return v.get("method") in (None, "projection")


def _intersection(v: dict[str, Any]) -> bool:
    return v.get("method") == "intersection"


def _silhouette(v: dict[str, Any]) -> bool:
    return v.get("method") == "silhouette"  # TR60 (D1810)


@form("split_line")
class SplitLineForm(SpecForm):
    """Edits a Split Line feature."""

    layout = (
        G(
            "split_line",
            strings.SPLIT_LINE,
            strings.SPLIT_LINE_TIP,
            (
                F("method", strings.SPLIT_LINE_METHOD, "choice", strings.SPLIT_LINE_TIP,
                  "projection", tuple(strings.SPLIT_LINE_METHODS.items())),
                F("faces", strings.SPLIT_LINE_FACES, "faces", strings.SPLIT_LINE_FACES_TIP),
                F("sketch", strings.SPLIT_LINE_SKETCH, "sketch", strings.SPLIT_LINE_SKETCH_TIP,
                  when=_projection),
                F("reverse", strings.SPLIT_LINE_REVERSE, "bool", strings.SPLIT_LINE_SKETCH_TIP,
                  when=_projection),
                F("both", strings.SPLIT_LINE_BOTH, "bool", strings.SPLIT_LINE_SKETCH_TIP,
                  when=_projection),
                F("plane", strings.SPLIT_LINE_PLANE, "faces", strings.SPLIT_LINE_PLANE_TIP,
                  single=True, optional=True, when=_intersection),
                F("tool_body", finish.SPLIT_LINE_BODY, "faces", finish.SPLIT_LINE_BODY_TIP,
                  single=True, optional=True, when=_intersection),
                F("direction", finish.SPLIT_LINE_PULL, "any", finish.SPLIT_LINE_PULL_TIP,
                  single=True, when=_silhouette),
            ),
        ),
    )  # fmt: skip

    def take_shapes(self, body: Any, shapes: list[Any]) -> str | None:
        """Picks are faces to split unless the plane list was clicked."""
        if self.active_pick is None:
            self.active_pick = "faces"
        return super().take_shapes(body, shapes)


def start_split_line(window: Any, tab: Any) -> None:
    """Open a new Split Line; the selected faces become the faces to split."""
    from fdcad.ui.main_window.new_feature import FeatureFlow

    if getattr(window, "feature_flow", None) is None:
        window.feature_flow = FeatureFlow(window)
    window.feature_flow.open_direct(tab, "split_line", "boss")
