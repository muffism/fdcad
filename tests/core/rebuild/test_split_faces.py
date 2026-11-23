"""A picked face that split because two features no longer line up (IDEAS 70, D2628)."""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.document.model import Document, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.fixes import tied_values
from fdcad.core.naming.names import centroid
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.rebuild.split_faces import SPLIT_FACE, TIE_VALUES
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, rect
from tests.core.features.test_hole import add_hole, points_sketch


def _two_plates(cut_b: bool = False) -> tuple[Document, str, str, str]:
    """Plate A (x 0 to 20) and plate B (x 20 to 30), both 10 mm thick, so their tops are
    one face; a hole is put on that face over B. With ``cut_b`` B is a pocket cut 4 mm
    into a 14 mm block, so its floor is level with A's top."""
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 20, 10)
    a = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    s = Sketch()
    rect(s, 20, 0, 30, 10)
    if cut_b:
        block = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 14.0)
        built = rebuild(doc)[block].body
        assert built is not None
        lid = built.face(f"{block}/cap/end")
        assert lid is not None
        plane = reference_for(built, lid)
        assert plane is not None
        top = Sketch()
        rect(top, 20, 0, 30, 10)
        b = add_extrude(doc, add_sketch(doc, top, plane), 4.0, operation="cut", reverse=True)
    else:
        b = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    results = rebuild(doc)
    body = results[b].body
    assert body is not None
    face = next(f for _n, f in body.faces if abs(centroid(f)[2] - 10) < 1e-6)
    assert len({n.split("/")[0] for n in body.names_of(face)}) == 2  # one face of both
    ref = reference_for(body, face)
    assert ref is not None
    hole = add_hole(doc, points_sketch(doc, ref, [(25, 5)]), face=ref, diameter=3.0, depth=4.0)
    assert rebuild(doc)[hole].state is FeatureState.OK
    return doc, a, b, hole


def _depth(doc: Document, fid: str) -> Param:
    value = doc.feature(fid).params["depth"]
    assert isinstance(value, Param)
    return value


def _apply(doc: Document, fix: Any) -> None:
    tied = tied_values(doc, fix)
    assert tied is not None
    features, variables = tied
    doc.variables = variables
    doc.features = [features.get(f.id, f) for f in doc.features]


@pytest.mark.parametrize("moved", ["a", "b"])
def test_the_error_says_the_picked_face_was_two_features_that_split(moved: str) -> None:
    doc, a, b, hole = _two_plates()
    doc.feature(a if moved == "a" else b).params["depth"] = Param("12", 12.0)
    result = rebuild(doc)[hole]
    assert result.state is FeatureState.ERROR
    (error,) = [i for i in result.issues if i.state is FeatureState.ERROR]
    assert "is not over the picked face" in error.message  # the hole's own error stays
    assert f"was one face of Extrude {a} and Extrude {b}, which no longer line up" in (
        error.message
    )
    assert "now 2 mm apart" in error.message
    assert error.code != "" and {f.action for f in error.fixes} == {TIE_VALUES}
    assert sorted(f.label for f in error.fixes) == [
        f"Use Extrude {a}'s Depth for Both",
        f"Use Extrude {b}'s Depth for Both",
    ]


def test_each_fix_ties_both_depths_to_one_variable() -> None:
    for lead in ("a", "b"):
        doc, a, b, hole = _two_plates()
        doc.feature(b).params["depth"] = Param("12", 12.0)
        error = next(i for i in rebuild(doc)[hole].issues if i.state is FeatureState.ERROR)
        leader = a if lead == "a" else b
        fix = next(f for f in error.fixes if f"Extrude {leader}'s" in f.label)
        assert doc.variables == []  # nothing changes until the fix is clicked
        _apply(doc, fix)
        (variable,) = doc.variables
        assert variable.name == f"Extrude_{leader}_depth"
        assert variable.value == pytest.approx(10.0 if lead == "a" else 12.0)
        for fid in (a, b):
            assert _depth(doc, fid).expr == f"={variable.name}"
        results = rebuild(doc)
        assert results[hole].state is FeatureState.OK
        assert _depth(doc, b).value == pytest.approx(variable.value)
        # The two now move together.
        variable.expr, variable.value = "15", 15.0
        results = rebuild(doc)
        assert results[hole].state is FeatureState.OK
        assert _depth(doc, a).value == pytest.approx(15.0) == _depth(doc, b).value


def test_a_cut_floor_and_a_boss_top_are_tied_by_their_sum() -> None:
    doc, a, b, hole = _two_plates(cut_b=True)
    doc.feature(b).params["depth"] = Param("5", 5.0)  # the pocket's floor drops 1 mm
    error = next(i for i in rebuild(doc)[hole].issues if i.state is FeatureState.ERROR)
    assert "now 1 mm apart" in error.message
    fix = next(f for f in error.fixes if f"Extrude {a}'s" in f.label)
    _apply(doc, fix)
    # 14 - 10 = a 4 mm pocket, and a thicker plate makes a shallower pocket (D2656).
    assert _depth(doc, b).expr == f"=14mm - {doc.variables[0].name}"
    assert rebuild(doc)[hole].state is FeatureState.OK
    assert _depth(doc, b).value == pytest.approx(4.0)


@pytest.mark.parametrize("lead", ["a", "b"])
def test_a_cut_floor_and_a_boss_top_tied_keep_moving_together(lead: str) -> None:
    """D2656: a boss end rises with its depth and a cut floor sinks with its own, so the
    tie must take the cut's depth away from a fixed sum, not add an offset to it."""
    doc, a, b, hole = _two_plates(cut_b=True)
    doc.feature(b).params["depth"] = Param("5", 5.0)
    error = next(i for i in rebuild(doc)[hole].issues if i.state is FeatureState.ERROR)
    leader = a if lead == "a" else b
    fix = next(f for f in error.fixes if f"Extrude {leader}'s" in f.label)
    _apply(doc, fix)
    assert rebuild(doc)[hole].state is FeatureState.OK
    (variable,) = doc.variables
    variable.expr, variable.value = "3", 3.0  # a 3 mm plate, or a 3 mm pocket
    results = rebuild(doc)
    assert results[hole].state is FeatureState.OK, [i.message for i in results[hole].issues]
    plate, pocket = _depth(doc, a).value, _depth(doc, b).value
    assert plate == pytest.approx(14.0 - pocket)  # the plate's top is the pocket's floor


def test_a_face_that_did_not_split_gets_no_explanation() -> None:
    doc, _a, _b, hole = _two_plates()
    ref = doc.feature(hole).refs["face"][0]
    # A second hole on the same whole face, with its point off the part: an error,
    # but the face it picked is still one face.
    off = add_hole(doc, points_sketch(doc, ref, [(50, 5)]), face=ref, diameter=3.0, depth=4.0)
    result = rebuild(doc)[off]
    assert result.state is FeatureState.ERROR
    assert all("no longer line up" not in i.message for i in result.issues)
    assert all(i.code != SPLIT_FACE for i in result.issues)
