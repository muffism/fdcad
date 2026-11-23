"""Paste a sketch onto a plane, and a feature onto a face (TR3.2, TR9, D685)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Document
from fdcad.core.document.paste import (
    PasteError,
    link_count,
    paste_feature,
    paste_sketch,
    sketch_of,
)
from fdcad.core.features.base import FeatureState
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import sketch_from_data
from fdcad.samples.make import SAMPLE_DIR, measure


def _bracket() -> Document:
    return fdef.loads((SAMPLE_DIR / "bracket.fdprt").read_text(encoding="utf-8"))


def _volume(doc: Document) -> float:
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None
    return float(measure(report.body.shape)["volume"])


def test_paste_a_sketch_on_another_plane() -> None:
    doc = _bracket()
    source = doc.feature("f5")
    pasted = paste_sketch(doc, source, {"feature": "f3"})
    (sketch,) = pasted.features
    assert sketch.type == "sketch" and sketch.refs == {"plane": {"feature": "f3"}}
    assert sketch.id not in {f.id for f in doc.features}
    a, b = sketch_from_data(source.data), sketch_from_data(sketch.data)
    assert set(a.entities) == set(b.entities)
    assert len(a.dimensions) == len(b.dimensions)
    doc.features.append(sketch)
    report = RebuildEngine().rebuild(doc)
    assert report.results[sketch.id].state is not FeatureState.ERROR


def test_paste_a_cut_on_another_plane_cuts_there_too() -> None:
    # The base holes' sketch lands on the Front Plane where one hole crosses the part.
    doc = _bracket()
    before = _volume(doc)
    cut = doc.feature("f8")
    sketch = sketch_of(doc, cut)
    assert sketch is not None and sketch.id == "f7"
    pasted = paste_feature(doc, cut, sketch, {"feature": "f2"})
    new_sketch, new_cut = pasted.features
    assert new_cut.refs["sketch"] == {"feature": new_sketch.id}
    assert new_cut.params == cut.params
    assert new_cut.name.startswith("Cut") and new_cut.name != cut.name
    doc.features += pasted.features
    after = _volume(doc)
    assert after == pytest.approx(before - 44.53, abs=0.05)


def test_features_without_a_sketch_and_links() -> None:
    doc = _bracket()
    assert sketch_of(doc, doc.feature("f2")) is None
    assert link_count(doc.feature("f7")) >= 0
    with pytest.raises(PasteError):
        paste_sketch(doc, doc.feature("f6"), {"feature": "f3"})


def test_a_cut_pasted_on_a_face_is_centred_on_it() -> None:
    from fdcad.core.document.paste import face_centre
    from fdcad.core.sketch.profiles import SketchPlane

    doc = _bracket()
    before = _volume(doc)
    cut = doc.feature("f8")  # two holes on the base
    face = doc.feature("f9").refs["plane"]  # the leg's outer face
    middle = face_centre(face)
    assert middle is not None
    # The leg face faces -X: sketch X along model -Z (D74), origin at the model origin.
    plane = SketchPlane((0.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, -1.0))
    u, v, _w = plane.to_2d(*middle)
    pasted = paste_feature(doc, cut, doc.feature("f7"), face, centre=(u, v))
    doc.features += pasted.features
    assert _volume(doc) < before - 50


def _cut_with_refs(doc: Document) -> tuple[object, object]:
    from fdcad.core.document.model import Param

    cut = doc.feature("f8")
    sketch = sketch_of(doc, cut)
    assert sketch is not None
    cut.refs["end_face"] = {"kind": "face", "name": "f6/cap/end"}
    cut.refs["axis"] = {"feature": sketch.id, "entity": "e1"}
    cut.params["depth"] = Param('="d1@Sketch 1" / 2', 7.5)
    return cut, sketch


def test_paste_into_another_part_clears_foreign_picks_and_formulas() -> None:
    """Audit D3 item 3, E item 7.8 (D708): the face reference named an unrelated
    feature of the target part, and the cut went into it with no message."""
    source = _bracket()
    cut, sketch = _cut_with_refs(source)
    target = _bracket()
    pasted = paste_feature(target, cut, sketch, {"feature": "f2"}, other_part=True)  # type: ignore[arg-type]
    new_sketch, new_cut = pasted.features
    assert "end_face" not in new_cut.refs and pasted.cleared == ["end_face"]
    assert new_cut.refs["axis"] == {"feature": new_sketch.id, "entity": "e1"}
    assert new_cut.params["depth"].expr == "7.5mm" and pasted.frozen >= 1


def test_paste_in_the_same_part_keeps_picks_and_follows_its_sketch() -> None:
    doc = _bracket()
    cut, sketch = _cut_with_refs(doc)
    pasted = paste_feature(doc, cut, sketch, {"feature": "f2"})  # type: ignore[arg-type]
    new_sketch, new_cut = pasted.features
    assert new_cut.refs["end_face"] == {"kind": "face", "name": "f6/cap/end"}
    assert new_cut.refs["axis"]["feature"] == new_sketch.id
    assert new_cut.params["depth"].expr.startswith("=") and not pasted.cleared
