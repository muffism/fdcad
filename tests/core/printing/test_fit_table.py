"""Fit values by size and direction (TR412, D1919)."""

from __future__ import annotations

import pytest

from fdcad.core.printing.fit_table import fit_for, parse_fit_table

TABLE = """# hole fits
hole upright 6 0.25
hole upright 20 0.2
hole flat 20 0.15
hole any 100 0.1
hole upright 6 0.3 0.6
outside any 100 0.05
"""


@pytest.mark.parametrize(
    ("diameter", "kind", "upright", "nozzle", "gap"),
    [
        (5.0, "hole", True, 0.4, 0.25),
        (5.0, "hole", True, 0.6, 0.3),  # the nozzle's own row first
        (10.0, "hole", True, 0.4, 0.2),
        (10.0, "hole", False, 0.4, 0.15),
        (50.0, "hole", False, 0.4, 0.1),
        (50.0, "outside", True, 0.4, 0.05),
        (500.0, "hole", True, 0.4, 0.2),  # past every band: the printer's value
    ],
)
def test_the_gap_follows_size_direction_and_nozzle(
    diameter: float, kind: str, upright: bool, nozzle: float, gap: float
) -> None:
    rows = parse_fit_table(TABLE)
    assert fit_for(rows, diameter, kind, upright, nozzle, 0.2)[0] == pytest.approx(gap)


def test_a_bad_line_is_named() -> None:
    with pytest.raises(ValueError, match="Line 2"):
        parse_fit_table("hole flat 5 0.1\nhole sideways 5 0.1")
    with pytest.raises(ValueError, match="not a number"):
        parse_fit_table("hole flat five 0.1")
