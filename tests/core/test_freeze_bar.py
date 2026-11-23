"""The freeze bar (TR98, D2507)."""

from __future__ import annotations

from fdcad.core.document.freeze import frozen, is_frozen, place, set_place
from fdcad.core.document.model import Param, new_document
from fdcad.core.features.solids import bounding_size
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, rect


def _part():  # type: ignore[no-untyped-def]
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 10, 10)
    sk = add_sketch(doc, s, {"feature": "f2"})
    ext = add_extrude(doc, sk, 5.0)
    return doc, sk, ext


def test_place_and_frozen_ids(tmp_path) -> None:  # type: ignore[no-untyped-def]
    doc, sk, ext = _part()
    assert place(doc) is None and frozen(doc) == []
    set_place(doc, "f2")  # a default plane: nothing frozen
    assert place(doc) is None
    set_place(doc, sk)
    assert frozen(doc) == [sk] and is_frozen(doc, sk) and not is_frozen(doc, ext)
    path = tmp_path / "p.fdprt"
    fdef.save(doc, path)
    assert place(fdef.load(path)) == sk
    set_place(doc, None)
    assert "freeze_bar" not in doc.extra
    set_place(doc, "f99")
    assert place(doc) is None


def test_frozen_feature_keeps_its_result() -> None:
    doc, _sk, ext = _part()
    engine = RebuildEngine()
    first = engine.rebuild(doc).results[ext].body
    assert first is not None
    size = bounding_size(first.shape)
    set_place(doc, ext)
    engine.rebuild(doc)  # the frozen result is taken now
    doc.feature(ext).params["depth"] = Param("40", 40.0)
    report = engine.rebuild(doc)
    assert ext in report.reused
    body = report.results[ext].body
    assert body is not None and abs(bounding_size(body.shape) - size) < 1e-6
    set_place(doc, None)  # unfrozen: the change builds
    report = engine.rebuild(doc)
    body = report.results[ext].body
    assert body is not None and bounding_size(body.shape) > size + 10
