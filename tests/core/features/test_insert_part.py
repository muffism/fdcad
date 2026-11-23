"""Insert Part (TR71, D2420)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.insert_part import break_link
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine
from tests.core.features.test_features import messages, plate, volume
from tests.core.features.test_stone_sprue import _box


def _insert(path: Path, **params: object) -> tuple[object, str]:
    doc = new_document()
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "insert_part",
            "Insert Part 1",
            params={"part_file": str(path), "dx": Param("100", 100.0), **params},  # type: ignore[dict-item]
            refs={},
        )
    )
    return doc, fid


def test_the_inserted_bodies_follow_the_source_file(tmp_path: Path) -> None:
    source, ext = plate()
    path = tmp_path / "plate.fdprt"
    fdef.save(source, path)
    doc, fid = _insert(path)
    engine = RebuildEngine()
    res = engine.rebuild(doc).results[fid]  # type: ignore[arg-type]
    assert res.state is FeatureState.OK, messages(res)
    assert volume(res.body.shape) == pytest.approx(25000, rel=1e-9)  # type: ignore[union-attr]
    assert _box(res.body.shape)[0] == pytest.approx(100.0, abs=1e-6)  # type: ignore[union-attr]
    source.feature(ext).params["depth"] = Param("20", 20.0)  # the source part changes
    fdef.save(source, path)
    res = engine.rebuild(doc).results[fid]  # type: ignore[arg-type]
    assert volume(res.body.shape) == pytest.approx(50000, rel=1e-9)  # type: ignore[union-attr]


def test_break_link_keeps_the_bodies_and_a_missing_file_says_where(tmp_path: Path) -> None:
    source, _ext = plate()
    path = tmp_path / "plate.fdprt"
    fdef.save(source, path)
    doc, fid = _insert(path)
    made, block_id, block = break_link(doc, fid)  # type: ignore[arg-type]
    doc.embedded[block_id] = block  # type: ignore[attr-defined]
    doc.features[-1] = made  # type: ignore[attr-defined]
    path.unlink()
    res = RebuildEngine().rebuild(doc).results[fid]  # type: ignore[arg-type]
    assert res.state is FeatureState.OK, messages(res)
    assert volume(res.body.shape) == pytest.approx(25000, rel=1e-6)  # type: ignore[union-attr]
    doc2, fid2 = _insert(path)
    res = RebuildEngine().rebuild(doc2).results[fid2]  # type: ignore[arg-type]
    assert res.state is FeatureState.ERROR and str(path) in messages(res)


def test_a_part_cannot_insert_itself(tmp_path: Path) -> None:
    path = tmp_path / "self.fdprt"
    doc, fid = _insert(path)
    fdef.save(doc, path)  # type: ignore[arg-type]
    res = RebuildEngine().rebuild(doc).results[fid]  # type: ignore[arg-type]
    assert res.state is FeatureState.ERROR and "inserts itself" in messages(res)
