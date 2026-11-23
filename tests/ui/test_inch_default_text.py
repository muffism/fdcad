"""Table values filled into inch parts keep their length (D2643, bug hunt round 10b O10)."""

from __future__ import annotations

import pytest

from fdcad.core.units import Kind, UnitSystem
from fdcad.core.units.expressions import evaluate
from fdcad.ui.property_panel.forms.spec_form import number_text


@pytest.mark.parametrize("mm", [4.2, 5.1054, 6.35, 25.4, 0.3, 12.7, 3.0, 2.5])
def test_inch_text_reads_back_as_the_same_length(mm: float) -> None:
    # An M5 tap drill (4.2 mm) was written 0.1654 and read back as 4.2012 mm.
    text = number_text(mm, Kind.LENGTH, UnitSystem.IN)
    assert evaluate(text, Kind.LENGTH, UnitSystem.IN) == pytest.approx(mm, abs=1e-9)


def test_inch_values_stay_in_inches_and_metric_ones_say_mm() -> None:
    assert number_text(6.35, Kind.LENGTH, UnitSystem.IN) == "0.25"
    assert number_text(5.1054, Kind.LENGTH, UnitSystem.IN) == "0.201"
    assert number_text(4.2, Kind.LENGTH, UnitSystem.IN) == "4.2 mm"
    assert number_text(4.2, Kind.LENGTH, UnitSystem.MM) == "4.2"
