"""Mouse presets (TR312, D1609)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

from fdcad.ui.preferences.view_options import ViewOptions
from fdcad.ui.preferences.view_page import ViewPage
from fdcad.ui.viewport.keynav import MOUSE_PRESETS, middle_drag

NONE = Qt.KeyboardModifier.NoModifier
SHIFT = Qt.KeyboardModifier.ShiftModifier
CTRL = Qt.KeyboardModifier.ControlModifier
ALT = Qt.KeyboardModifier.AltModifier


def test_default_preset_is_the_old_behaviour() -> None:
    assert [middle_drag("turn", m) for m in (NONE, SHIFT, CTRL, ALT)] == [
        "rotate",
        "zoom",
        "pan",
        "roll",
    ]
    assert middle_drag("unknown", NONE) == "rotate"


def test_other_presets() -> None:
    assert [middle_drag("pan", m) for m in (NONE, SHIFT, CTRL, ALT)] == [
        "pan",
        "rotate",
        "zoom",
        "roll",
    ]
    assert middle_drag("turn_shift_pan", SHIFT) == "pan"
    for table in MOUSE_PRESETS.values():
        assert sorted(table.values()) == ["pan", "roll", "rotate", "zoom"]


def test_preset_preference(tmp_path: Path, qapp: QApplication) -> None:
    store = QSettings(str(tmp_path / "p.ini"), QSettings.Format.IniFormat)
    assert ViewOptions(store).mouse_preset == "turn"
    page = ViewPage(store)
    page.preset_box.setCurrentIndex(page.preset_box.findData("pan"))
    page.apply(store)
    assert ViewOptions(store).mouse_preset == "pan"
