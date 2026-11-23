"""The zero thickness warning: curved contacts, and who gives it (D1057).

Found on a gearbox cover (2026-11-12): an inlay of the text "GB-200" warned that it
"makes bodies that touch only along an edge", and so did each of the twenty features
after it. An inlay's letters lie in their pockets face to face; the test for that
only knew flat and round faces, so every letter with a curve in it was called a touch.
"""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Circle, Sketch
from fdcad.core.sketch.text import SketchText
from tests.core.features.test_features import add_extrude, add_sketch, messages, plate, rect
from tests.core.features.test_hole import face_ref


@pytest.mark.parametrize("text", ["G", "B", "2", "0", "GB-200"])
def test_an_inlay_of_round_letters_is_not_a_touch(text: str) -> None:
    doc, ext = plate()
    s = Sketch()
    s.texts.append(SketchText("t1", text, x=3.0, y=20.0, height=8.0, bold=True))
    sk = add_sketch(doc, s, face_ref(doc, ext, "cap/end"))
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(fid, "inlay", "Inlay 1", params={"depth": Param("1", 1.0)},
                refs={"sketch": {"feature": sk}})
    )  # fmt: skip
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.OK, messages(res)
    assert res.body is not None and len(solids(res.body.shape)) >= 2


def test_only_the_feature_that_makes_the_touch_warns() -> None:
    doc, ext = plate()
    s = Sketch()
    rect(s, 50, 50, 60, 60)  # touches the plate only along one edge
    touch = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    hole = Sketch()
    c = hole.add_point(20, 20)
    eid = hole.new_id()
    hole.entities[eid] = Circle(eid, c, 3.0)
    cut = add_extrude(doc, add_sketch(doc, hole, face_ref(doc, ext, "cap/end")), 10.0,
                      operation="cut", reverse=True)  # fmt: skip
    results = rebuild(doc)
    assert "zero thickness" in messages(results[touch])
    assert results[cut].state is FeatureState.OK, messages(results[cut])  # it warned too


def test_the_check_looks_only_at_the_bodies_a_feature_changed(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """D1070: on a gearbox of 318 features, every feature after two blocks were locked
    with teeth took 6 s longer: the hundreds of edges the blocks share were checked
    again after each feature, though nothing had touched them. Here a stud is put on a
    plate far from two such blocks, and no shared edge of the blocks is looked at."""
    import fdcad.core.features.solids as module
    from fdcad.core.features.booleans import boolean_named
    from tests.core.features.test_boolean_named_bodies import (
        _named,
        _plate_and_locked_blocks,
        _stud,
    )

    before = _plate_and_locked_blocks()
    after = boolean_named("fuse", before, _named(_stud(25, 25, 9), "f99/stud"), "f99", "Studs")
    calls = []
    real = module._FaceContact.covers

    def counted(self, key, users):  # type: ignore[no-untyped-def]
        calls.append(key)
        return real(self, key, users)

    monkeypatch.setattr(module._FaceContact, "covers", counted)
    assert module.new_touches(before, after) == []
    assert calls == []
    # The whole part, as it was checked before: every shared edge and corner.
    assert module.zero_thickness(after.shape, 10**6) == []
    assert len(calls) > 50
