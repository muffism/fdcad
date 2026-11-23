"""Thread tolerance classes on tapped holes and modelled threads (TR393, D1507)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureError
from fdcad.core.features.modeled_thread import clearance_of
from fdcad.core.features.thread_class import allowance, choices, is_internal
from fdcad.core.hole_table import rows
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_hole import add_hole, on_top


def test_metric_allowances_follow_the_formulas() -> None:
    assert allowance("6H", 0.8, 5.0) == 0.0
    assert allowance("6h", 0.8, 5.0) == 0.0
    assert allowance("6g", 0.8, 5.0) == pytest.approx(0.0238)
    assert allowance("6G", 1.0, 6.0) == pytest.approx(0.026)
    assert allowance("6e", 1.0, 6.0) == pytest.approx(0.061)
    with pytest.raises(ValueError):
        allowance("9z", 1.0, 6.0)


def test_inch_allowances() -> None:
    # 1/4-20 class 2A: about 0.0012 inch; 3A and B classes have none.
    assert allowance("2A", 25.4 / 20, 6.35) / 25.4 == pytest.approx(0.0012, abs=1e-4)
    assert allowance("1A", 25.4 / 20, 6.35) == allowance("2A", 25.4 / 20, 6.35)
    assert allowance("3A", 25.4 / 20, 6.35) == 0.0 and allowance("2B", 25.4 / 20, 6.35) == 0.0
    assert choices(inch=True, internal=True) == ("2B", "1B", "3B")
    assert is_internal("6H") and not is_internal("6g")


def _thread(**params: object) -> Feature:
    base: dict[str, object] = {"diameter": Param("5", 5.0), "pitch": Param("0.8", 0.8)}
    base.update(params)
    return Feature("f9", "modeled_thread", "Thread", params=base)  # type: ignore[arg-type]


def test_the_class_adds_half_its_allowance_to_the_clearance() -> None:
    assert clearance_of(_thread(thread_class="6g"), internal=False) == pytest.approx(0.0119)
    assert clearance_of(_thread(), internal=False) == 0.0
    typed = _thread(thread_class="6g", clearance=Param("0.1", 0.1))
    assert clearance_of(typed, internal=False) == pytest.approx(0.1)
    with pytest.raises(FeatureError, match="Choose a class for internal threads"):
        clearance_of(_thread(thread_class="6g"), internal=True)


def test_hole_list_shows_the_class() -> None:
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(
        doc,
        sk,
        "tapped",
        face=top,
        diameter=4.2,
        depth=8.0,
        thread_depth=6.0,
        pitch=0.8,
        size="M5",
        thread_class="6H",
    )
    found = rows(doc, rebuild(doc))
    assert found[0].thread == "M5 6H"
    doc.feature(fid).params["thread_class"] = "none"
    assert rows(doc, rebuild(doc))[0].thread == "M5"
