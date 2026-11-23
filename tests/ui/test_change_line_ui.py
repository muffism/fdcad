"""The status bar's result line (TR290, D878)."""

from __future__ import annotations

from types import SimpleNamespace

from fdcad.core.rebuild.change_line import Change
from fdcad.core.units import UnitSystem
from fdcad.ui.main_window.window import change_text


def _tab(units: UnitSystem) -> object:
    return SimpleNamespace(session=SimpleNamespace(document=SimpleNamespace(units=units)))


def test_line_in_part_units() -> None:
    report = SimpleNamespace(change=Change("Cut 2", 0.0, 2400.0, 3))
    assert change_text(report, _tab(UnitSystem.MM)) == "Cut 2 removed 2.4 cm3, 3 more faces."  # type: ignore[arg-type]
    report = SimpleNamespace(change=Change("Boss 1", 16387.064, 0.0, -2))
    assert change_text(report, _tab(UnitSystem.IN)) == "Boss 1 added 1 in3, 2 fewer faces."  # type: ignore[arg-type]
    report = SimpleNamespace(change=Change("Fillet 1", 0.0, 0.0, 0))
    assert "did not change" in change_text(report, _tab(UnitSystem.MM))  # type: ignore[arg-type]
    assert change_text(SimpleNamespace(change=None), _tab(UnitSystem.MM)) == ""  # type: ignore[arg-type]


def test_a_failed_feature_is_not_called_built() -> None:
    """D1041: the owner's Fillet 2 failed and the line read "built; the solid did not change"."""
    report = SimpleNamespace(change=Change("Fillet 2", 0.0, 0.0, 0, failed=True))
    line = change_text(report, _tab(UnitSystem.MM))  # type: ignore[arg-type]
    assert line.startswith("Fillet 2 failed: the part is unchanged.")
    assert "built" not in line and "Open the Errors tab" in line
