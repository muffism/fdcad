"""Sheet metal parameters and bend allowance (PHASE5_SPEC P5.1)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureError, FeatureState
from fdcad.core.features.sheetmetal.params import (
    DEFAULT_K,
    BendRule,
    bend_allowance,
    defaults_of,
    new_sheet_metal,
    outside_setback,
    parse_bend_table,
    table_allowance,
)
from tests.core.features.sheetmetal.parts import build, sheet_doc

RIGHT = math.pi / 2


def test_k_factor_default_is_0_44() -> None:
    doc = sheet_doc()
    folder = next(f for f in doc.features if f.type == "sheet_metal")
    assert defaults_of(folder).rule.k_factor == pytest.approx(DEFAULT_K) == pytest.approx(0.44)


@pytest.mark.parametrize(
    ("r", "t", "k", "deg"), [(1.0, 2.0, 0.44, 90.0), (3.0, 1.5, 0.3, 45.0), (0.0, 1.0, 0.5, 120.0)]
)
def test_k_factor_formula(r: float, t: float, k: float, deg: float) -> None:
    rule = BendRule(r, "k_factor", k)
    want = math.pi * (r + k * t) * deg / 180
    assert bend_allowance(rule, t, math.radians(deg), "x") == pytest.approx(want)


def test_bend_allowance_and_deduction_methods() -> None:
    assert bend_allowance(BendRule(1.0, "bend_allowance", allowance=3.3), 2.0, RIGHT, "x") == 3.3
    rule = BendRule(1.0, "bend_deduction", allowance=4.0)
    want = 2 * outside_setback(1.0, 2.0, RIGHT) - 4.0
    assert bend_allowance(rule, 2.0, RIGHT, "x") == pytest.approx(want) == pytest.approx(2.0)


def test_bend_table_interpolates_angle() -> None:
    table = parse_bend_table("thickness,radius,angle,allowance\n2,1,45,1.5\n2,1,90,3.0\n", "t")
    assert table_allowance(table, 2.0, 1.0, math.radians(60), "t") == pytest.approx(2.0)
    assert table_allowance(table, 2.0, 1.0, RIGHT, "t") == pytest.approx(3.0)
    with pytest.raises(FeatureError, match="no row for thickness"):
        table_allowance(table, 3.0, 1.0, RIGHT, "t")
    with pytest.raises(FeatureError, match="no angle"):
        table_allowance(table, 2.0, 1.0, math.radians(120), "t")


@pytest.mark.parametrize(
    ("text", "match"),
    [("", "empty"), ("2,1,90\n", "needs thickness"), ("a,b,c,d\n2,x,90,3\n", "row 2")],
)
def test_bad_bend_tables(text: str, match: str) -> None:
    with pytest.raises(FeatureError, match=match):
        parse_bend_table(text, "t")


def test_folder_rejects_bad_values() -> None:
    for values, match in (
        ({"thickness": Param("0", 0.0)}, "thickness"),
        ({"k_factor": Param("1.5", 1.5)}, "K-factor"),
        ({"relief_ratio": Param("3", 3.0)}, "relief ratio"),
    ):
        doc = sheet_doc()
        folder = doc.features[-1]
        folder.params.update(values)
        result = build(doc).results[folder.id]
        assert result.state is FeatureState.ERROR
        assert match in result.issues[0].message


def test_folder_uses_bend_table_from_data() -> None:
    doc = sheet_doc(method="bend_table")
    folder = doc.features[-1]
    folder.data["bend_table"] = "2,1,90,3.5\n"
    assert defaults_of(folder).rule.table == ((2.0, 1.0, 90.0, 3.5),)


def test_new_folder_has_defaults() -> None:
    doc = sheet_doc()
    folder = new_sheet_metal(doc)
    defaults = defaults_of(folder)
    assert (defaults.thickness, defaults.rule.radius, defaults.relief.kind) == (
        1.0,
        1.0,
        "rectangular",
    )


def test_a_flange_can_use_the_folders_table_when_the_folder_uses_k_factor() -> None:
    """Audit A item 1 (D727): the flange got an empty table and failed with "no row for
    thickness" although a table was loaded."""
    from fdcad.core.document.model import Feature
    from fdcad.core.features.sheetmetal.params import rule_from

    doc = sheet_doc()  # K-factor
    folder = doc.features[-1]
    folder.data["bend_table"] = "2,1,90,3.5\n"
    base = defaults_of(folder).rule
    assert base.method == "k_factor" and base.table == ((2.0, 1.0, 90.0, 3.5),)
    flange = Feature("f99", "edge_flange", "Edge Flange 1", params={"method": "bend_table"})
    assert rule_from(flange, base).table == base.table


def test_a_bad_table_does_not_block_a_k_factor_folder() -> None:
    doc = sheet_doc()
    folder = doc.features[-1]
    folder.data["bend_table"] = "not,a,table\n"
    assert defaults_of(folder).rule.table == ()


def test_blank_cells_and_repeated_gauges_are_errors() -> None:
    """Audit A item 31 (D738): a blank cell shifted values into the wrong columns, and a
    repeated gauge name replaced the first."""
    from fdcad.core.features.sheetmetal.params import parse_gauge_table

    with pytest.raises(FeatureError):
        parse_bend_table("2,,90,3.5\n", "t")  # was read as 2, 90, 3.5 and refused oddly
    assert parse_bend_table("2,1,90,3.5,,\n", "t") == ((2.0, 1.0, 90.0, 3.5),)
    with pytest.raises(FeatureError, match="repeats the name"):
        parse_gauge_table("16 gauge,1.5,1\n16 gauge,1.6,1\n", "t")
