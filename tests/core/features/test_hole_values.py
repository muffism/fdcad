"""Hole values for formulas: the table values and the number of holes (TR397 item 2, D1508)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature, Param
from fdcad.core.equations.engine import solve
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_hole import add_hole, on_top


def test_count_and_sizes_of_a_hole_feature_feed_formulas() -> None:
    doc, ext, sk, top = on_top([(10, 10), (40, 40), (10, 40)])
    hole = add_hole(doc, sk, "counterbore", face=top, diameter=5.0, depth=6.0)
    doc.feature(hole).params.update(
        {"cbore_diameter": Param("9", 9.0), "cbore_depth": Param("3", 3.0)}
    )
    name = doc.feature(hole).name
    results = rebuild(doc)
    assert results[hole].state is not FeatureState.ERROR
    assert results[hole].extras["count"] == 3
    space = solve(doc).namespace
    assert space[f"count@{name}"][1] == 3
    assert space[f"count@{hole}"][1] == 3
    assert space[f"cbore_diameter@{name}"][1] == pytest.approx(9.0)
    # A feature below reads them in the same rebuild.
    later = doc.new_feature_id()
    doc.features.append(
        Feature(
            later,
            "hole",
            "Hole 2",
            params={
                "hole_type": "simple",
                "end_condition": "blind",
                "diameter": Param(f'="cbore_diameter@{name}" / "count@{name}"', 0.0),
                "depth": Param("2", 2.0),
            },
            refs={"sketch": {"feature": sk}, "face": [top]},
        )
    )
    rebuild(doc)
    assert doc.feature(later).params["diameter"].value == pytest.approx(3.0)
    _ = ext
