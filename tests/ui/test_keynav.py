"""Keyboard and mouse navigation mapping (WORKFLOW_SPEC W7)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from fdcad.ui.viewport.keynav import (
    ARROW_DEG,
    PAN_FRACTION,
    ROLL_DEG,
    SHIFT_ARROW_DEG,
    key_action,
    roll_degrees,
    zoom_factor,
)


def test_arrows_rotate_by_fifteen_degrees() -> None:
    assert key_action(Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier) == (
        "rotate",
        ARROW_DEG,
        0.0,
    )
    assert key_action(Qt.Key.Key_Left, Qt.KeyboardModifier.NoModifier) == (
        "rotate",
        -ARROW_DEG,
        0.0,
    )
    assert key_action(Qt.Key.Key_Up, Qt.KeyboardModifier.NoModifier) == (
        "rotate",
        0.0,
        ARROW_DEG,
    )
    assert key_action(Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier) == (
        "rotate",
        0.0,
        -ARROW_DEG,
    )


def test_shift_arrows_rotate_ninety_degrees() -> None:
    assert key_action(Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier) == (
        "rotate",
        SHIFT_ARROW_DEG,
        0.0,
    )
    assert key_action(Qt.Key.Key_Up, Qt.KeyboardModifier.ShiftModifier) == (
        "rotate",
        0.0,
        SHIFT_ARROW_DEG,
    )


def test_ctrl_arrows_pan_by_a_tenth_of_the_view() -> None:
    assert key_action(Qt.Key.Key_Right, Qt.KeyboardModifier.ControlModifier) == (
        "pan",
        PAN_FRACTION,
        0.0,
    )
    assert key_action(Qt.Key.Key_Up, Qt.KeyboardModifier.ControlModifier) == (
        "pan",
        0.0,
        PAN_FRACTION,
    )
    assert key_action(Qt.Key.Key_Left, Qt.KeyboardModifier.ControlModifier) == (
        "pan",
        -PAN_FRACTION,
        0.0,
    )
    assert key_action(Qt.Key.Key_Down, Qt.KeyboardModifier.ControlModifier) == (
        "pan",
        0.0,
        -PAN_FRACTION,
    )


def test_alt_left_and_right_roll() -> None:
    assert key_action(Qt.Key.Key_Left, Qt.KeyboardModifier.AltModifier) == ("roll", ROLL_DEG)
    assert key_action(Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier) == ("roll", -ROLL_DEG)
    assert key_action(Qt.Key.Key_Up, Qt.KeyboardModifier.AltModifier) is None
    assert key_action(Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier) is None


def test_other_keys_are_ignored() -> None:
    assert key_action(Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier) is None
    assert key_action(Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier) is None


def test_shift_middle_drag_zoom_factor() -> None:
    assert zoom_factor(0.0) == pytest.approx(1.0)
    assert zoom_factor(-100.0) > 1.0  # drag up zooms in
    assert zoom_factor(100.0) < 1.0  # drag down zooms out


def test_alt_middle_drag_roll_degrees() -> None:
    assert roll_degrees(0.0) == pytest.approx(0.0)
    assert roll_degrees(30.0) < 0.0  # drag right rolls right
    assert roll_degrees(-30.0) > 0.0  # drag left rolls left
