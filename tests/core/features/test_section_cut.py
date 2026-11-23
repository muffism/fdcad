"""Section Cut: a section view kept as a cut body feature (TR151 item 2, D2205)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature
from fdcad.core.features.base import FeatureState
from fdcad.core.features.section_cut import zones_data
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.phase3_parts import ok_body, volume_of
from tests.core.test_goal_seek import block

X = ((10.0, 0.0, 0.0), (1.0, 0.0, 0.0))
Y = ((0.0, 10.0, 0.0), (0.0, 1.0, 0.0))
BACK_X = ((10.0, 0.0, 0.0), (-1.0, 0.0, 0.0))
BACK_Y = ((0.0, 10.0, 0.0), (0.0, -1.0, 0.0))


def _cut(zones: list[list[tuple[tuple[float, float, float], tuple[float, float, float]]]]):  # type: ignore[no-untyped-def]
    doc = block(10.0)  # 20 x 20 x 10 from the origin: 4000 mm3
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, "section_cut", "Section Cut 1", data=zones_data(zones)))
    return fid, rebuild(doc)


def test_one_plane_keeps_the_half_behind_it() -> None:
    fid, results = _cut([[X]])
    body = ok_body(results, fid)
    assert volume_of(body.shape) == pytest.approx(2000.0, rel=1e-9)
    assert any(n == f"{fid}/zone1.plane1" for n, _f in body.faces)


def test_two_planes_cut_a_corner_and_zones_add_up() -> None:
    fid, results = _cut([[X, Y]])
    assert volume_of(ok_body(results, fid).shape) == pytest.approx(3000.0, rel=1e-9)
    fid, results = _cut([[X, Y], [BACK_X, BACK_Y]])
    assert volume_of(ok_body(results, fid).shape) == pytest.approx(2000.0, rel=1e-9)


def test_damaged_planes_or_cutting_everything_say_what_to_do() -> None:
    doc = block(10.0)
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, "section_cut", "Section Cut 1", data={"zones": []}))
    results = rebuild(doc)
    assert results[fid].state is FeatureState.ERROR
    assert "make it again" in results[fid].issues[0].message
    far = ((-5.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    fid, results = _cut([[far]])
    assert results[fid].state is FeatureState.ERROR


def test_a_feature_after_the_cut_builds_on_the_cut_part() -> None:
    """D1063: found on a gearbox. Section Cut was marked as not changing the part, so
    the feature after it was given the part from before the cut: the cut was gone."""
    from fdcad.core.document.model import Param
    from fdcad.core.rebuild.engine import RebuildEngine

    doc = block(10.0)  # 20 x 20 x 10 from the origin
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, "section_cut", "Section Cut 1", data=zones_data([[X]])))
    ball = doc.new_feature_id()
    doc.features.append(
        Feature(ball, "primitive", "Ball",
                params={"kind": "sphere", "operation": "cut", "diameter": Param("4", 4.0),
                        "centred": True})
    )  # fmt: skip
    engine = RebuildEngine()
    report = engine.rebuild(doc)
    assert report.results[ball].state is FeatureState.OK
    # Half the block (2000) less the eighth of a 4 mm ball at the origin corner.
    eighth = 4 / 3 * 3.141592653589793 * 8 / 8
    assert volume_of(report.body.shape) == pytest.approx(2000.0 - eighth, rel=1e-6)
    # A change before the cut reaches the cut: the block is made 20 mm tall.
    first = next(f for f in doc.features if f.type == "extrude")
    first.params["depth"] = Param("20", 20.0)
    report = engine.rebuild(doc)
    assert volume_of(report.results[fid].body.shape) == pytest.approx(4000.0, rel=1e-6)
