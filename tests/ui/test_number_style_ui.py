"""Number display preferences reach the shown values (TR350, D949)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from fdcad.core.measure import Value
from fdcad.core.units import Kind, UnitSystem
from fdcad.core.units import number_display as nd
from fdcad.ui.measure.box import format_value as measure_text
from fdcad.ui.preferences.dialog import PreferencesDialog
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.property_panel.panel import format_value as panel_text
from fdcad.ui.sketch_tools.canvas import format_length, plain_length


def _settings(tmp_path: Path) -> Settings:
    return Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))


def test_preferences_store_and_apply(qtbot: QtBot, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = PreferencesDialog(settings, parent)
    qtbot.addWidget(dialog)
    dialog.rounding_box.setCurrentIndex(dialog.rounding_box.findData("truncate"))
    dialog.separator_box.setCurrentIndex(dialog.separator_box.findData(","))
    dialog.fraction_box.setCurrentIndex(dialog.fraction_box.findData(16))
    dialog.accept()
    assert settings.number_rounding == "truncate"
    assert settings.number_separator == ","
    assert settings.inch_fraction == 16
    settings.apply_number_style()
    assert nd.style() == nd.NumberStyle("truncate", ",", 16)


def test_shown_values_follow_the_style(tmp_path: Path) -> None:
    nd.set_style(nd.NumberStyle("truncate", ",", 8))
    assert panel_text(12.349, Kind.LENGTH, UnitSystem.MM) == "12,34 mm"
    assert panel_text(25.4 * 1.5, Kind.LENGTH, UnitSystem.IN) == "1 1/2 in"
    assert format_length(25.4 * 0.25, UnitSystem.IN) == "1/4"
    assert plain_length(12.349, UnitSystem.MM) == "12.35"  # a field reads it back
    assert measure_text(Value("d", "length", 3.456), UnitSystem.MM, 2) == "3,45 mm"
    point = measure_text(Value("p", "point", (1.0, 2.0, 3.0)), UnitSystem.MM, 1)
    assert point == "1,0; 2,0; 3,0 mm"


def test_system_separator_is_a_point_or_comma(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    assert settings.number_separator == "system"
    assert settings.number_style().separator in (".", ",")
