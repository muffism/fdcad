"""Skip one face as a fix (TR278, D1406)."""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.document.model import Feature
from fdcad.core.features.fixes import fixed_feature
from fdcad.core.features.shell import SKIPPED, skip_help
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, plate, volume
from tests.core.features.test_shell import _face_ref, add_shell


def test_skipped_face_is_left_open_like_a_removed_face() -> None:
    doc, ext = plate()
    top = _face_ref(doc, ext, "cap/end")
    opened = add_shell(doc, 1.0, faces=[top])
    expected = volume(body(rebuild(doc), opened).shape)
    doc, ext = plate()
    fid = add_shell(doc, 1.0, **{SKIPPED: [_face_ref(doc, ext, "cap/end")]})
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(expected, rel=1e-9)


def test_help_finds_the_face_and_offers_the_fix() -> None:
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    bad = b.face(f"{ext}/side/e6")
    assert bad is not None
    feature = Feature("f9", "shell", "Shell 1")

    def attempt(extra: tuple[Any, ...]) -> object | None:
        return object() if any(f.IsSame(bad) for f in extra) else None

    error = skip_help(feature, b, b.shape, [], False, attempt)
    assert f"face {ext}/side/e6" in str(error)
    assert error.highlight == [f"{ext}/side/e6"]
    (fix,) = error.fixes
    assert fix.action == "add_refs" and fix.data["key"] == SKIPPED
    doc.features.append(Feature("f9", "shell", "Shell 1"))
    edited = fixed_feature(doc, "f9", fix)
    assert edited is not None
    assert [r["name"] for r in edited.refs[SKIPPED]] == [fix.data["refs"][0]["name"]]
    again = fixed_feature(doc, "f9", fix)  # the same face is not listed twice
    assert again is not None and len(again.refs[SKIPPED]) == 1


def test_no_face_helps_gives_the_plain_message() -> None:
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    error = skip_help(Feature("f9", "shell", "Shell 1"), b, b.shape, [], False, lambda _e: None)
    assert "could not offset the faces" in str(error) and not error.fixes


def _attractor_plate():  # type: ignore[no-untyped-def]
    from pathlib import Path

    from fdcad.core.io import fdef
    from fdcad.core.rebuild.engine import RebuildEngine

    doc = fdef.load(Path(__file__).parents[3] / "samples" / "graphs" / "attractor_plate.fdprt")
    doc.solid = {}
    return RebuildEngine().rebuild(doc).body


def test_the_search_tries_fewer_faces_on_a_large_body() -> None:
    # D2606: a 1 mm shell of the attractor plate (83 faces) fails, and the 25 tries of
    # the search took 33 s, so the app sweep counted the step as a hang.
    b = _attractor_plate()
    tried: list[object] = []

    def attempt(extra: tuple[Any, ...]) -> None:
        tried.append(extra)

    skip_help(Feature("f9", "shell", "Shell 1"), b, b.shape, [], False, attempt)
    assert len(tried) == 12  # 1000 faces of work over 83 faces, not 25 tries


def test_the_search_stops_when_the_build_is_cancelled() -> None:
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    tried: list[object] = []

    def attempt(extra: tuple[Any, ...]) -> None:
        tried.append(extra)

    error = skip_help(
        Feature("f9", "shell", "Shell 1"), b, b.shape, [], False, attempt, lambda: len(tried) >= 2
    )
    assert len(tried) == 2 and not error.fixes
