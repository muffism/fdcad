"""Drain holes at the lowest point of each void (TR189 item 3, D1006)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.cavities import enclosed_voids
from fdcad.core.document.model import Feature, Param
from fdcad.core.features import drain_holes
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import volume_of
from tests.core.test_cavities import _box, _hollow_cube


def _hollow_doc(tmp_path):  # type: ignore[no-untyped-def]
    from fdcad.core.features.import_step import part_from_step
    from fdcad.core.io.export import export_step

    step = tmp_path / "hollow.step"
    export_step(_hollow_cube(), step)
    return part_from_step("hollow.step", step.read_bytes())


def _drain(doc, toward="bottom"):  # type: ignore[no-untyped-def]
    fid = doc.new_feature_id()
    params = {"hole_diameter": Param("3", 3.0), "toward": toward}
    doc.features.append(Feature(fid, "drain_holes", "Drain Holes 1", params=params))
    return fid


def test_lowest_point_of_a_void() -> None:
    (void,) = enclosed_voids(_hollow_cube())
    assert drain_holes.extreme_point(void.shell, False, 30.0)[2] == pytest.approx(5.0)
    assert drain_holes.extreme_point(void.shell, True, 30.0)[2] == pytest.approx(15.0)


@pytest.mark.parametrize("toward", ["bottom", "top"])
def test_the_void_drains_out_of_the_part(tmp_path, toward) -> None:  # type: ignore[no-untyped-def]
    from fdcad.core.rebuild.engine import RebuildEngine

    doc = _hollow_doc(tmp_path)
    fid = _drain(doc, toward)
    after = RebuildEngine().rebuild(doc)
    assert after.results[fid].state is not FeatureState.ERROR, after.results[fid].issues
    assert after.body is not None and enclosed_voids(after.body.shape) == []
    # 20 cube less the 10 cube void less a 3 mm hole through the 5 mm wall.
    hole = math.pi * 1.5**2 * 5.0
    assert volume_of(after.body.shape) == pytest.approx(8000 - 1000 - hole, rel=1e-3)


def test_a_solid_part_says_what_to_do(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from fdcad.core.features.import_step import part_from_step
    from fdcad.core.io.export import export_step
    from fdcad.core.rebuild.engine import RebuildEngine

    step = tmp_path / "solid.step"
    export_step(_box(0, 0, 0, 10, 10, 10), step)
    doc = part_from_step("solid.step", step.read_bytes())
    fid = _drain(doc)
    result = RebuildEngine().rebuild(doc).results[fid]
    assert result.state is FeatureState.ERROR
    assert "Use Shell with no face removed" in result.issues[0].message
