"""Keyboard and mouse view navigation (WORKFLOW_SPEC item W7).

Pure functions map Qt key and modifier combinations to view actions, and mouse
drags to the angle or zoom factor the view applies. Keeping the mapping and the
step sizes here means they are tested without a GPU. Right and up are positive.
"""

from __future__ import annotations

import math

from PySide6.QtCore import Qt

#: Degrees an arrow key rotates the view.
ARROW_DEG = 15.0
#: Degrees Shift and an arrow key rotates the view.
SHIFT_ARROW_DEG = 90.0
#: Fraction of the view width or height that Ctrl and an arrow key pans.
PAN_FRACTION = 0.10
#: Degrees Alt and Left or Right rolls the view. Positive rolls left.
ROLL_DEG = 15.0
#: Pixels of vertical drag that double the zoom on a Shift middle drag.
ZOOM_PIXELS = 200.0
#: Pixels of horizontal drag that roll the view one degree on an Alt middle drag.
ROLL_PIXELS_PER_DEG = 3.0

#: A view action: rotate and pan carry two numbers, roll carries one.
Action = tuple[str, float] | tuple[str, float, float] | None


def _arrow(key: int) -> tuple[float, float]:
    """Unit direction of an arrow key, with right and up positive."""
    if key == Qt.Key.Key_Left:
        return (-1.0, 0.0)
    if key == Qt.Key.Key_Right:
        return (1.0, 0.0)
    if key == Qt.Key.Key_Down:
        return (0.0, -1.0)
    if key == Qt.Key.Key_Up:
        return (0.0, 1.0)
    return (0.0, 0.0)


def key_action(key: int, modifiers: Qt.KeyboardModifier, step: float = ARROW_DEG) -> Action:
    """Map an arrow key plus modifiers to a view action, or None.

    Rotate is in degrees (``step`` for a plain arrow, a preference: TR211), pan is a
    fraction of the view width or height, and roll is in degrees about the view normal.
    """
    dx, dy = _arrow(key)
    if not dx and not dy:
        return None
    alt = modifiers & Qt.KeyboardModifier.AltModifier
    ctrl = modifiers & Qt.KeyboardModifier.ControlModifier
    shift = modifiers & Qt.KeyboardModifier.ShiftModifier
    if alt:
        return ("roll", -ROLL_DEG * dx) if dx else None
    if ctrl:
        return ("pan", dx * PAN_FRACTION, dy * PAN_FRACTION)
    deg = SHIFT_ARROW_DEG if shift else step
    return ("rotate", dx * deg, dy * deg)


def roll_degrees(dx_pixels: float) -> float:
    """Degrees to roll for an Alt middle drag; dragging right rolls right."""
    return -dx_pixels / ROLL_PIXELS_PER_DEG


def zoom_factor(dy_pixels: float) -> float:
    """Zoom factor for a Shift middle drag; dragging up zooms in."""
    return math.pow(2.0, -dy_pixels / ZOOM_PIXELS)


#: Mouse presets (TR312, D1609): what a middle drag does with no key, Shift, Ctrl
#: and Alt. Named by behaviour. "turn" is FDCAD's default.
MOUSE_PRESETS: dict[str, dict[str, str]] = {
    "turn": {"": "rotate", "shift": "zoom", "ctrl": "pan", "alt": "roll"},
    "turn_shift_pan": {"": "rotate", "shift": "pan", "ctrl": "zoom", "alt": "roll"},
    "pan": {"": "pan", "shift": "rotate", "ctrl": "zoom", "alt": "roll"},
}


def middle_drag(preset: str, modifiers: Qt.KeyboardModifier) -> str:
    """What a middle drag does under a mouse preset: rotate, pan, zoom or roll."""
    table = MOUSE_PRESETS.get(preset, MOUSE_PRESETS["turn"])
    if modifiers & Qt.KeyboardModifier.ShiftModifier:
        return table["shift"]
    if modifiers & Qt.KeyboardModifier.AltModifier:
        return table["alt"]
    if modifiers & Qt.KeyboardModifier.ControlModifier:
        return table["ctrl"]
    return table[""]


def swipe_back(angle: float) -> bool:
    """True when a trackpad swipe at ``angle`` degrees (0 is right, 90 up) points left,
    which goes to the previous view; other swipes go to the next one (TR380)."""
    a = angle % 360.0
    return 90.0 < a < 270.0
