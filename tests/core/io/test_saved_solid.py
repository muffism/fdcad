"""The finished solid saved inside the part file (FDEF_SPEC 13A, D1102)."""

from __future__ import annotations

import pytest
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

from fdcad.core.cache.disk import document_key
from fdcad.core.cache.saved_solid import decode, encode
from fdcad.core.document.model import Param
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine
from tests.core.features.test_features import _hole, plate


def _volume(shape: object) -> float:
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props, 1e-6)
    return float(props.Mass())


def _saved():  # type: ignore[no-untyped-def]
    doc, ext = plate()
    cut = _hole(doc, f"{ext}/cap/end")
    report = RebuildEngine().rebuild(doc)
    doc.solid = encode(document_key(doc), report.body, report.results)
    return doc, ext, cut, report


def test_a_part_file_carries_its_solid_and_shows_it_on_open() -> None:
    # The first open of a part anywhere built every feature first (40 s for a bike
    # frame); the solid saved in the file shows it at once.
    doc, ext, cut, report = _saved()
    opened = fdef.loads(fdef.dumps(doc))
    part = decode(opened, document_key(opened))
    assert part is not None and part.body is not None and report.body is not None
    assert _volume(part.body.shape) == pytest.approx(_volume(report.body.shape), rel=1e-9)
    assert sorted(n for n, _ in part.body.faces) == sorted(n for n, _ in report.body.faces)
    assert part.body.face(f"{ext}/cap/end") is not None
    assert part.states[cut]["state"] == "ok"


def test_the_solid_is_not_used_once_the_features_change() -> None:
    doc, _ext, cut, _report = _saved()
    opened = fdef.loads(fdef.dumps(doc))
    feature = opened.feature(cut)
    key = next(k for k, v in feature.params.items() if isinstance(v, Param))
    value = feature.params[key]
    assert isinstance(value, Param)
    feature.params[key] = Param(str(value.value + 1), value.value + 1)
    assert decode(opened, document_key(opened)) is None


def test_a_damaged_solid_is_ignored() -> None:
    doc, _ext, _cut, _report = _saved()
    doc.solid = {**doc.solid, "brep": "not base64 at all!"}
    assert decode(doc, document_key(doc)) is None
    doc.solid = {**doc.solid, "format": 99}
    assert decode(doc, document_key(doc)) is None


def test_the_solid_changes_neither_the_cache_key_nor_parts_saved_without_it() -> None:
    doc, _ext, _cut, _report = _saved()
    with_solid = fdef.dumps(doc)
    key = document_key(doc)
    solid, doc.solid = doc.solid, {}
    without = fdef.dumps(doc)
    assert '"solid"' not in without  # a part with no solid saves as before
    assert document_key(doc) == key
    assert fdef.loads(with_solid) == fdef.loads(without)  # not part of the document's sameness
    doc.solid = solid
    assert list(fdef.to_json_data(doc))[-1] == "solid"  # after every key of the spec


def test_build_seconds_adds_up_the_saved_times() -> None:
    """D1106: the times decide whether a part opens without a rebuild."""
    from fdcad.core.cache.saved_solid import build_seconds

    assert build_seconds({"a": {"seconds": 1.5}, "b": {"seconds": 2}, "c": {}}) == 3.5
    assert build_seconds({"a": {"state": "ok"}}) == 0.0  # written before times were kept
    assert build_seconds({"a": {"seconds": "x"}, "b": None, "c": {"seconds": -4}}) == 0.0
    assert build_seconds(None) == 0.0
