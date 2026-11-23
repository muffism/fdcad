"""View preferences of round 12 (TR211, TR212, TR214, TR312): stored under ``view/``.

Kept beside ``Settings`` so the shared settings module stays small. Each value is
read from and written to the same QSettings store.
"""

from __future__ import annotations

from typing import Any

from fdcad.ui.viewport.edge_look import HIDDEN_CHOICES, SMOOTH_CHOICES


def _true(value: Any) -> bool:
    return str(value).lower() in ("true", "1", "yes")


class ViewOptions:
    """Edge display, display quality and mouse preferences."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def _choice(self, key: str, choices: tuple[str, ...], default: str) -> str:
        value = str(self.store.value(key, default))
        return value if value in choices else default

    # TR212 edge display (D1602) -------------------------------------------------------

    @property
    def smooth_edges(self) -> str:
        """Smooth edges between tangent faces: "shown", "dashed" or "removed"."""
        return self._choice("view/smooth_edges", SMOOTH_CHOICES, "shown")

    @smooth_edges.setter
    def smooth_edges(self, value: str) -> None:
        self.store.setValue("view/smooth_edges", value)

    @property
    def hidden_edges(self) -> str:
        """Hidden edges in Hidden Lines Visible: "dashed" or "solid"."""
        return self._choice("view/hidden_edges", HIDDEN_CHOICES, "dashed")

    @hidden_edges.setter
    def hidden_edges(self, value: str) -> None:
        self.store.setValue("view/hidden_edges", value)

    @property
    def feature_edges(self) -> bool:
        """Draw every edge of the feature selected in the tree. Default off."""
        return _true(self.store.value("view/feature_edges", "false"))

    @feature_edges.setter
    def feature_edges(self, value: bool) -> None:
        self.store.setValue("view/feature_edges", "true" if value else "false")

    # TR211 mouse and keys (D1607) ------------------------------------------------------

    def _flag(self, key: str, default: bool) -> bool:
        return _true(self.store.value(key, "true" if default else "false"))

    def _set_flag(self, key: str, value: bool) -> None:
        self.store.setValue(key, "true" if value else "false")

    def _number(self, key: str, default: float, low: float, high: float) -> float:
        try:
            value = float(self.store.value(key, default))
        except (TypeError, ValueError):
            return default
        return max(low, min(high, value))

    @property
    def wheel_reverse(self) -> bool:
        """Reverse the wheel: away from you zooms out. Default off."""
        return self._flag("view/wheel_reverse", False)

    @wheel_reverse.setter
    def wheel_reverse(self, value: bool) -> None:
        self._set_flag("view/wheel_reverse", value)

    @property
    def zoom_about_cursor(self) -> bool:
        """The wheel zooms about the pointer (True) or the view centre."""
        return self._flag("view/zoom_about_cursor", True)

    @zoom_about_cursor.setter
    def zoom_about_cursor(self, value: bool) -> None:
        self._set_flag("view/zoom_about_cursor", value)

    @property
    def arrow_step(self) -> float:
        """Degrees an arrow key turns the view, 1 to 90 (15 by default)."""
        return self._number("view/arrow_step", 15.0, 1.0, 90.0)

    @arrow_step.setter
    def arrow_step(self, value: float) -> None:
        self.store.setValue("view/arrow_step", float(value))

    @property
    def turn_speed(self) -> float:
        """How fast a mouse drag turns the view, 0.25 to 4 times (1 by default)."""
        return self._number("view/turn_speed", 1.0, 0.25, 4.0)

    @turn_speed.setter
    def turn_speed(self, value: float) -> None:
        self.store.setValue("view/turn_speed", float(value))

    @property
    def fit_on_view(self) -> bool:
        """Zoom to Fit when a standard view is chosen. Default on."""
        return self._flag("view/fit_on_view", True)

    @fit_on_view.setter
    def fit_on_view(self, value: bool) -> None:
        self._set_flag("view/fit_on_view", value)

    # TR312 mouse presets (D1609) -------------------------------------------------------

    @property
    def mouse_preset(self) -> str:
        """What the middle button does: "turn" (default), "turn_shift_pan" or "pan"."""
        from fdcad.ui.viewport.keynav import MOUSE_PRESETS

        return self._choice("view/mouse_preset", tuple(MOUSE_PRESETS), "turn")

    @mouse_preset.setter
    def mouse_preset(self, value: str) -> None:
        self.store.setValue("view/mouse_preset", value)
