"""Hidden and isolated bodies (PHASE3_SPEC P3.4 item 6, DECISIONS D410, FDEF_SPEC 10.1)."""

from __future__ import annotations

from pathlib import Path

from fdcad.core.body_visibility import (
    HIDDEN_BODIES,
    bodies_of,
    body_names,
    first_hit,
    hidden_indices,
    hidden_names,
    marks_for,
    set_hidden_names,
    shown_shape,
    visible_indices,
    without_bodies,
)
from fdcad.core.document.display import set_display
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.io import fdef
from fdcad.core.naming.names import faces_of
from tests.core.features.phase3_parts import ok_body, rebuild
from tests.core.features.test_multibody import BLOCK, two_blocks


def test_marks_hide_bodies_and_keep_them_hidden_after_renumbering() -> None:
    doc, first, second, body = two_blocks(gap=10.0)
    names = body_names(body)
    assert len(names) == 2
    assert any(n.startswith(f"{second}/") for n in names[1])
    marks = marks_for(body, [1])
    assert len(marks) == 1 and marks <= names[1]
    assert hidden_indices(body, marks) == [1]
    assert visible_indices(body, marks) == [0]
    # Suppressing the first block makes the second one body 1: it stays hidden.
    doc.feature(first).suppressed = True
    alone = ok_body(rebuild(doc), second)
    assert len(solids(alone.shape)) == 1
    assert hidden_indices(alone, marks) == [0]
    assert visible_indices(alone, marks) == []
    assert shown_shape(alone, []) is None


def test_isolate_and_shown_shape() -> None:
    _doc, _first, _second, body = two_blocks(gap=10.0)
    isolated = marks_for(body, [0])
    assert visible_indices(body, set(), isolated) == [0]
    shape = shown_shape(body, [0])
    assert shape is not None and abs(volume_of(shape) - BLOCK) < 1e-6
    assert shown_shape(body, [0, 1]) is body.shape  # nothing filtered: the part itself
    hidden = marks_for(body, [0, 1])
    assert without_bodies(hidden, body, [0]) == marks_for(body, [1])


def test_picks_find_their_body() -> None:
    _doc, _first, _second, body = two_blocks(gap=10.0)
    parts = solids(body.shape)
    face_b = faces_of(parts[1])[0]
    face_a = faces_of(parts[0])[2]
    assert bodies_of(body.shape, [face_b, face_a, face_b]) == [1, 0]
    assert bodies_of(None, [face_a]) == []


def test_first_hit_takes_the_nearest_body_on_the_ray() -> None:
    _doc, _first, _second, body = two_blocks(gap=10.0)
    # Block A spans x 0..20, block B x 30..50, both y 0..20, z 0..10.
    down = ((10.0, 10.0, 100.0), (0.0, 0.0, -1.0))
    assert first_hit(body, [0, 1], *down) == 0
    assert first_hit(body, [1], *down) is None
    along_x = ((-100.0, 10.0, 5.0), (1.0, 0.0, 0.0))
    assert first_hit(body, [0, 1], *along_x) == 0
    assert first_hit(body, [1], *along_x) == 1
    back = ((100.0, 10.0, 5.0), (-1.0, 0.0, 0.0))
    assert first_hit(body, [0, 1], *back) == 1


def test_saved_in_the_file_last_and_left_out_while_empty(tmp_path: Path) -> None:
    doc, _first, _second, body = two_blocks(gap=10.0)
    set_hidden_names(doc, set())
    assert HIDDEN_BODIES not in doc.appearance
    set_hidden_names(doc, {"zz/long/name", "f9/a"})
    set_display(doc, {"f2"} - {"f2"}, {"f2"})  # shown: a plane, written before hidden_bodies
    assert list(doc.appearance)[-1] == HIDDEN_BODIES
    assert doc.appearance[HIDDEN_BODIES] == ["f9/a", "zz/long/name"]
    path = tmp_path / "bodies.fdef"
    fdef.save(doc, path)
    loaded = fdef.load(path)
    assert hidden_names(loaded) == {"f9/a", "zz/long/name"}
    assert list(loaded.appearance)[-1] == HIDDEN_BODIES
    set_hidden_names(loaded, set())
    assert HIDDEN_BODIES not in loaded.appearance
    assert body is not None
