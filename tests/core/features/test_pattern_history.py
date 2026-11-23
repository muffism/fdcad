"""A Geometry pattern of features falls back on the part's history (D1045).

Found on a bike frame (2026-11-12): a Mounting Boss on a lofted tube could not be
patterned at all. As a feature it "cannot be copied as a feature ... turn on Geometry
pattern"; with Geometry pattern on, its faces could not be patched away from the tube,
and the message said to "pick the feature instead", which was what was picked.
"""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.features import patterns
from fdcad.core.features.base import FeatureError, FeatureState
from fdcad.core.features.solids import solids
from tests.core.features.phase3_parts import length, messages, ok_body, volume_of
from tests.core.features.test_patterns import BOSS, PLATE, X, Y, centred, count, pattern


def _no_patch(*_args: Any, **_kwargs: Any) -> Any:
    raise FeatureError("the faces could not be patched away")


def test_geometry_pattern_of_a_feature_whose_faces_cannot_be_patched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(patterns, "feature_volumes", _no_patch)
    doc, _plate, boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(3), "geometry": True},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    body = ok_body(results, fid)
    # What the boss added when it was built, copied twice more.
    assert volume_of(body.shape) == pytest.approx(PLATE + 3 * BOSS, rel=1e-9)
    assert len(solids(body.shape)) == 1
    assert any("/instance3.1/" in n for n, _f in body.faces)


def test_a_history_copy_of_a_pattern_copies_the_pattern_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D1081: on the gearbox, a Geometry mirror of a foot and the pattern of it copied
    the foot only. The history copy skipped the pattern, as the face copy must (its
    faces are only its copies, D604), but what a pattern added is just its copies."""
    monkeypatch.setattr(patterns, "feature_volumes", _no_patch)
    doc, _plate, boss = centred()
    inner, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(2)},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    assert volume_of(ok_body(results, inner).shape) == pytest.approx(PLATE + 2 * BOSS, rel=1e-9)
    fid, results = pattern(
        doc,
        "mirror",
        {"geometry": True},
        {"plane": Y, "features": [{"feature": boss}, {"feature": inner}]},
    )
    body = ok_body(results, fid)
    assert volume_of(body.shape) == pytest.approx(PLATE + 4 * BOSS, rel=1e-9)
    assert len(solids(body.shape)) == 1


def test_picked_faces_that_cannot_be_patched_are_still_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Faces have no history to fall back on: the message is the one from before."""
    monkeypatch.setattr(patterns, "feature_volumes", _no_patch)
    doc, _plate, boss = centred()
    from tests.core.features.phase3_parts import face_ref, rebuild

    top = face_ref(ok_body(rebuild(doc), boss), f"{boss}/cap/end")
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(2)},
        {"direction1": X, "faces": [top]},
    )
    assert results[fid].state is FeatureState.ERROR
    assert "do not form a whole feature" in messages(results[fid])


def test_a_history_copy_that_leaves_the_part_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(patterns, "feature_volumes", _no_patch)
    doc, _plate, boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(40), "count1": count(2), "geometry": True},  # off the plate
        {"direction1": X, "features": [{"feature": boss}]},
    )
    assert results[fid].state is FeatureState.ERROR
    assert "fall off" in messages(results[fid])


def test_a_geometry_pattern_of_features_gives_no_pick_notes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D1048: the faces of the seed features are listed from the part, not picked. On
    the frame two of them had one name, so each was "found by its position" and the
    mirror warned the user to "check it and reselect it", with nothing to reselect."""
    from fdcad.core.features.base import Issue

    real = patterns._pattern_faces

    def noted(*args: Any, **kwargs: Any) -> Any:
        body, issues = real(*args, **kwargs)
        return body, [*issues, Issue(FeatureState.WARNING, "found by its position")]

    monkeypatch.setattr(patterns, "_pattern_faces", noted)
    doc, _plate, boss = centred()
    values = {"spacing1": length(12), "count1": count(2), "geometry": True}
    fid, results = pattern(
        doc, "linear_pattern", dict(values), {"direction1": X, "features": [{"feature": boss}]}
    )
    assert results[fid].state is FeatureState.OK
    # Faces the user picked keep their notes.
    from tests.core.features.phase3_parts import face_ref, rebuild

    doc, _plate, boss = centred()
    b = ok_body(rebuild(doc), boss)
    picked = [face_ref(b, n) for n, _f in b.faces if n.startswith(f"{boss}/")]
    fid, results = pattern(doc, "linear_pattern", dict(values), {"direction1": X, "faces": picked})
    assert "found by its position" in messages(results[fid])
