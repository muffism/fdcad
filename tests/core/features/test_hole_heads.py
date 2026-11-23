"""More screw heads, thread series and drill names (TR253, D786)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.features import hole_data, hole_heads
from fdcad.core.features.hole import defaults_for

INCH = 25.4


def test_series_and_sizes() -> None:
    iso, ansi = hole_data.size_names("iso"), hole_data.size_names("ansi")
    assert len(set(iso)) == len(iso) and len(set(ansi)) == len(ansi)
    for name in ("M10x1.25", "M10x1", "M12x1.5", "M30", "M48"):
        assert name in iso
    for name in ("#0-80", "#1-64", "#3-48", "#5-44", "5/16-24", "1/2-20", "1/4-32", "1-20"):
        assert name in ansi
    # Smallest first, coarsest thread first at each size.
    assert iso.index("M10") < iso.index("M10x1.25") < iso.index("M10x1") < iso.index("M12")
    fine = hole_data.find("iso", "M10x1.25")
    assert fine is not None and fine.pitch == 1.25 and fine.tap_drill == pytest.approx(8.75)
    assert fine.clearance == hole_data.find("iso", "M10").clearance  # type: ignore[union-attr]


def test_every_inch_tap_and_clearance_drill_has_a_name() -> None:
    for size in hole_data.ANSI:
        assert hole_heads.drill_names(size.tap_drill), size.name
        close, normal, _loose = size.clearance
        assert hole_heads.drill_names(close), size.name
        assert hole_heads.drill_names(normal), size.name


def test_drill_names() -> None:
    assert hole_heads.drill_names(0.136 * INCH) == ["#29"]
    assert hole_heads.drill_names(0.250 * INCH) == ["E", "1/4"]
    assert hole_heads.drill_names(0.332 * INCH) == ["Q"]
    assert hole_heads.drill_names(1.0 * INCH) == ["1"]
    assert hole_heads.drill_names(5.0) == []
    assert len(hole_heads.DRILLS) == 80 + 26 + 128
    assert hole_heads.drill_names(1.015625 * INCH) == ["1 1/64"]


def test_counterbore_heads() -> None:
    m5 = hole_data.find("iso", "M5")
    assert m5 is not None
    assert hole_data.counterbore(m5) == (9.5, 5.0)  # socket head, as before
    assert hole_data.counterbore(m5, "button") == (10.5, 2.75)
    assert hole_data.counterbore(m5, "low_head") == (9.5, 3.5)
    assert hole_data.counterbore(m5, "pan") == (10.5, 3.7)
    assert hole_data.counterbore(m5, "cheese") == (9.5, 3.3)
    assert hole_data.counterbore(m5, "washer") == (11.0, 6.0)  # 10 mm washer, 1 mm thick
    m48 = hole_data.find("iso", "M48")
    assert m48 is not None and hole_data.counterbore(m48, "pan") is None
    quarter = hole_data.find("ansi", "1/4-28")  # fine sizes share the coarse heads
    assert quarter is not None
    bore = hole_data.counterbore(quarter, "button")
    assert bore is not None and bore[0] == pytest.approx((0.437 + 1 / 16) * INCH, abs=1e-3)


def test_defaults_follow_the_head() -> None:
    socket = defaults_for("counterbore", "iso", "M6")
    pan = defaults_for("counterbore", "iso", "M6", head="pan")
    assert socket["cbore_diameter"] == 11.0 and pan["cbore_diameter"] == 13.0
    missing = defaults_for("counterbore", "iso", "M48", head="pan")
    assert "cbore_diameter" not in missing and "diameter" in missing
    flat = defaults_for("countersink", "iso", "M6")
    recessed = defaults_for("countersink", "iso", "M6", head="recessed")
    assert flat["csk_diameter"] == 13.44 and recessed["csk_diameter"] == 12.6
    assert recessed["csk_angle"] == pytest.approx(math.radians(90.0))
