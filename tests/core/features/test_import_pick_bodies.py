"""Pick which bodies of a STEP file come in (TR302 item 2, D1203)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fdcad.core.features.base import FeatureState
from fdcad.core.features.import_step import keep_list, part_from_step
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.io.export import export_step
from fdcad.core.rebuild.runner import rebuild
from tests.core.io.test_3mf_conformance import _two_boxes


def _two_box_step(tmp_path: Path) -> bytes:
    out = tmp_path / "two.step"
    export_step(_two_boxes(), out)
    return out.read_bytes()


def test_keep_list() -> None:
    assert keep_list("3, 1 1;2", 3) == [0, 1, 2]
    assert keep_list("", 3) == []
    assert keep_list("5", 3) == []
    with pytest.raises(ValueError):
        keep_list("1, x", 3)
    with pytest.raises(ValueError):
        keep_list("0", 3)


def test_only_the_picked_body_comes_in_with_its_names(tmp_path: Path) -> None:
    doc = part_from_step("two.step", _two_box_step(tmp_path))
    feature = doc.features[-1]
    whole = rebuild(doc)[feature.id]
    assert whole.body is not None and len(solids(whole.body.shape)) == 2
    parts = solids(whole.body.shape)
    index = min(range(len(parts)), key=lambda i: volume_of(parts[i])) + 1
    all_names = {n for n, _f in whole.body.faces}
    feature.params["keep_bodies"] = str(index)
    res = rebuild(doc)[feature.id]
    assert res.state is FeatureState.OK
    assert res.body is not None
    assert volume_of(res.body.shape) == pytest.approx(125.0, rel=1e-9)
    kept = {n for n, _f in res.body.faces}
    assert len(kept) == 6 and kept <= all_names  # names as in the whole file


@pytest.mark.parametrize("pick", ["x", "9"])
def test_a_wrong_pick_is_a_feature_error(tmp_path: Path, pick: str) -> None:
    doc = part_from_step("two.step", _two_box_step(tmp_path))
    feature = doc.features[-1]
    feature.params["keep_bodies"] = pick
    res = rebuild(doc)[feature.id]
    assert res.state is FeatureState.ERROR
    assert "Pick Bodies" in res.issues[0].message
