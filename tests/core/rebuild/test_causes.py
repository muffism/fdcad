"""Show the cause of an error (TR288, D773)."""

from __future__ import annotations

from fdcad.core.document.model import Feature
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.causes import SHOW_CAUSE, cause_in
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_sketch, rect


def _deleted_body_under_a_sketch():  # type: ignore[no-untyped-def]
    """Two blocks; Delete Body takes the second away, then a sketch sits on its top."""
    from tests.core.features.test_multibody import two_blocks

    doc, _first, second, _body = two_blocks(gap=10.0)
    ext = second  # the second block's extrude
    top = {"kind": "face", "name": f"{ext}/cap/end"}
    delete = doc.new_feature_id()
    doc.features.append(
        Feature(
            delete, "delete_body", "Delete Top", params={"option": "delete"}, refs={"bodies": [top]}
        )
    )
    on_top = Sketch()
    rect(on_top, 5, 5, 10, 10)
    user = add_sketch(doc, on_top, top)  # a sketch placed on the deleted body's top
    return doc, ext, delete, user


def test_a_lost_face_names_the_feature_that_took_it() -> None:
    doc, _ext, delete, user = _deleted_body_under_a_sketch()
    report = RebuildEngine().rebuild(doc)
    result = report.results[user]
    assert result.state is FeatureState.ERROR
    issue = result.issues[0]
    assert "missing reference" in issue.message and "It was lost at Delete Top." in issue.message
    (fix,) = [f for f in issue.fixes if f.action == SHOW_CAUSE]
    assert fix.data == {"feature": delete} and fix.label == "Show Cause: Delete Top"
    assert cause_in(issue) == delete


def _piece_under_a_sketch():  # type: ignore[no-untyped-def]
    """A plate whose top a slot cuts in two, and a sketch on the narrow piece."""
    from fdcad.core.naming.names import centroid
    from fdcad.core.naming.select import reference_for
    from fdcad.core.sketch.model import sketch_to_data
    from tests.core.features.test_features import add_extrude, plate

    doc, ext = plate()
    top = {"kind": "face", "name": f"{ext}/cap/end"}
    across = Sketch()
    rect(across, 5, -1, 7, 51)
    slot_sketch = add_sketch(doc, across, top)
    add_extrude(doc, slot_sketch, 2.0, operation="cut", reverse=True)
    built = RebuildEngine().rebuild(doc).body
    assert built is not None
    narrow = next(
        f for n, f in built.faces if n.startswith(f"{ext}/cap/end#") and centroid(f)[0] < 5
    )
    piece = reference_for(built, narrow)
    assert piece is not None and piece["name"].startswith(f"{ext}/cap/end#")
    on_piece = Sketch()
    rect(on_piece, 1, 20, 4, 30)
    user = add_sketch(doc, on_piece, piece)
    inside = Sketch()
    rect(inside, 5, 10, 7, 40)  # the slot no longer reaches the edges: the top is one face
    return doc, ext, slot_sketch, user, sketch_to_data(inside)


def test_a_piece_no_longer_split_off_blames_no_feature() -> None:
    """D2637, found by the edit storm on the gearbox: a sketch on a piece of a face that
    an edit no longer splits failed with "It was lost at Input Bearing Boss", the
    feature that makes the whole face and was not changed; the face is still there."""
    doc, ext, slot_sketch, user, inside = _piece_under_a_sketch()
    assert RebuildEngine().rebuild(doc).results[user].state is not FeatureState.ERROR
    doc.feature(slot_sketch).data = inside
    report = RebuildEngine().rebuild(doc)
    issue = report.results[user].issues[0]
    assert issue.state is FeatureState.ERROR and "missing reference" in issue.message
    assert "It was lost at" not in issue.message
    assert cause_in(issue) is None
    assert doc.feature(ext).name not in issue.message


def test_a_piece_whose_whole_face_is_cut_away_names_the_cut() -> None:
    from tests.core.features.test_features import add_extrude

    doc, ext, slot_sketch, user, inside = _piece_under_a_sketch()
    doc.feature(slot_sketch).data = inside
    whole = Sketch()
    rect(whole, -1, -1, 51, 51)
    skim_sketch = add_sketch(doc, whole, {"kind": "face", "name": f"{ext}/cap/end"})
    skim = add_extrude(doc, skim_sketch, 1.0, operation="cut", reverse=True)
    doc.features.append(
        doc.features.pop(next(i for i, f in enumerate(doc.features) if f.id == user))
    )
    report = RebuildEngine().rebuild(doc)
    issue = report.results[user].issues[0]
    assert issue.state is FeatureState.ERROR
    assert cause_in(issue) == skim


def test_a_face_its_feature_no_longer_makes_names_that_feature() -> None:
    doc, ext, _delete, user = _deleted_body_under_a_sketch()
    doc.feature(user).refs["plane"] = {"kind": "face", "name": f"{ext}/side/nowhere"}
    report = RebuildEngine().rebuild(doc)
    issue = report.results[user].issues[0]
    assert cause_in(issue) == ext
    assert f"It was lost at {doc.feature(ext).name}." in issue.message
