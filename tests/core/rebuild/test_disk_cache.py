"""Disk cache of finished parts (FDEF_SPEC 13)."""

from pathlib import Path

import pytest
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

from fdcad.core.cache import disk
from fdcad.core.document.model import Param
from fdcad.core.rebuild.engine import RebuildEngine
from tests.core.features.test_features import _hole, plate


@pytest.fixture(autouse=True)
def _cache_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _volume(shape: object) -> float:
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return float(props.Mass())


def test_store_and_load_round_trip() -> None:
    doc, ext = plate()
    cut = _hole(doc, f"{ext}/cap/end")
    report = RebuildEngine().rebuild(doc)
    key = disk.document_key(doc)
    disk.store(key, report.body, {cut: {"state": "ok", "messages": []}})
    cached = disk.load(key)
    assert cached is not None and cached.body is not None
    assert report.body is not None
    assert _volume(cached.body.shape) == pytest.approx(_volume(report.body.shape))
    assert sorted(n for n, _ in cached.body.faces) == sorted(n for n, _ in report.body.faces)
    top = cached.body.face(f"{ext}/cap/end")
    assert top is not None
    assert cached.states[cut]["state"] == "ok"


def test_key_ignores_appearance_but_not_geometry() -> None:
    doc, ext = plate()
    key = disk.document_key(doc)
    doc.appearance["part_color"] = "#FF0000"
    assert disk.document_key(doc) == key
    doc.feature(ext).params["depth"] = Param("11", 11.0)
    assert disk.document_key(doc) != key


def test_missing_or_damaged_entries_are_not_errors(_cache_folder: Path) -> None:
    assert disk.load("0" * 64) is None
    _cache_folder.mkdir(parents=True)
    (_cache_folder / ("1" * 64 + ".json")).write_text("{not json", encoding="utf-8")
    assert disk.load("1" * 64) is None
    (_cache_folder / ("2" * 64 + ".json")).write_text(
        '{"format": 1, "has_body": true, "names": [], "states": {}}', encoding="utf-8"
    )
    assert disk.load("2" * 64) is None  # its .brep file is missing


def test_prune_and_clear(_cache_folder: Path) -> None:
    doc, _ = plate()
    report = RebuildEngine().rebuild(doc)
    disk.store("a" * 64, report.body, {})
    disk.store("b" * 64, report.body, {})
    disk.prune(_cache_folder, limit=1)
    assert len(list(_cache_folder.glob("*.json"))) <= 1
    disk.clear()
    assert list(_cache_folder.glob("*.json")) == []
