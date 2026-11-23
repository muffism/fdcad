"""The machine bed: one solid body of more than 500 features (``machine_builder.py``).

The quick test builds the bed and one station; the slow test builds the whole part.
After every feature, points are checked to be inside or outside the material, and the
part must stay a single body throughout.
"""

from __future__ import annotations

import pytest

from fdcad.core.features.base import FeatureState
from tests.core.features.machine_builder import Bed


def _built(*parts: int) -> Bed:
    bed = Bed()
    bed.b.quiet = True
    bed.watch_valid = False
    bed.build(*parts)
    return bed


def _failed(bed: Bed) -> list[str]:
    return [f"{r['name']}: {r['issues']}" for r in bed.b.rows if r.get("suppressed")]


def test_one_station_is_one_body_with_material_where_it_should_be() -> None:
    bed = _built(1)
    report = bed.b.rebuild()
    assert _failed(bed) == []
    assert all(r.state is FeatureState.OK for r in report.results.values())
    assert report.body_count == 1
    assert bed.wrong == [] and bed.checks > 60
    assert len(bed.b.doc.features) > 45


@pytest.mark.parametrize("parts", [(0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)],
                         ids=["shaft", "pattern plate", "yard"])  # fmt: skip
def test_each_other_kind_of_station_is_one_body(parts: tuple[int, int, int, int]) -> None:
    bed = _built(*parts)
    report = bed.b.rebuild()
    assert _failed(bed) == []
    assert all(r.state is FeatureState.OK for r in report.results.values())
    assert report.body_count == 1
    assert bed.wrong == [] and bed.checks > 30


@pytest.mark.slow
def test_the_whole_machine_bed() -> None:
    """More than 500 features, every one OK, one valid body, every place check right."""
    bed = _built(12, 3, 3, 1)  # pod stations, shafts, pattern plates, the yard
    report = bed.b.rebuild()
    assert _failed(bed) == []
    assert all(r.state is FeatureState.OK for r in report.results.values())
    assert report.body_count == 1 and bed.b.valid()
    assert len(bed.b.doc.features) >= 500
    assert bed.wrong == [] and bed.checks > 800
