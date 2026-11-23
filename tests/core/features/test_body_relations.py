"""Move Body by relations, solved together (TR268 item 1, D2415)."""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.document.model import Feature
from fdcad.core.features.base import FeatureState
from fdcad.core.features.body_relations import parse
from fdcad.core.features.sketch import face_plane
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, plate, volume
from tests.core.features.test_stone_sprue import _box


def _face(b: Any, normal: tuple[float, float, float], at: float) -> dict[str, str]:
    for name, face in b.faces:
        plane = face_plane(face)
        if plane is None:
            continue
        n = plane.normal
        lift = sum(o * c for o, c in zip(plane.origin, normal, strict=True))
        if sum(a * c for a, c in zip(n, normal, strict=True)) > 0.999 and abs(lift - at) < 1e-6:
            return {"kind": "face", "name": name}
    raise AssertionError("no such face")


def _move(text: str, pairs: list[tuple[dict[str, Any], dict[str, Any]]]) -> tuple[Any, str]:
    doc, ext = plate()
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "move_copy_body",
            "Move Body 1",
            params={"mode": "relations", "relations": text},
            refs={
                "bodies": [{"kind": "face", "name": f"{ext}/cap/end"}],
                "rel_from": [a for a, _b in pairs],
                "rel_to": [b for _a, b in pairs],
            },
        )
    )
    return doc, fid


def test_three_relations_place_the_body_exactly() -> None:
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    bottom = _face(b, (0, 0, -1), 0.0)
    back = _face(b, (0, 1, 0), 50.0)
    left = _face(b, (-1, 0, 0), 0.0)
    doc, fid = _move(
        "coincident; distance 5; coincident",
        [(bottom, {"feature": "f4"}), (back, {"feature": "f3"}), (left, {"feature": "f2"})],
    )
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert volume(res.body.shape) == pytest.approx(25000, rel=1e-9)  # type: ignore[union-attr]
    got = _box(res.body.shape)  # type: ignore[union-attr]
    assert got == pytest.approx([0, 5, 0, 10, 55, 50], abs=1e-5)


def test_relations_that_cannot_hold_and_bad_text() -> None:
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    bottom = _face(b, (0, 0, -1), 0.0)
    top = _face(b, (0, 0, 1), 10.0)
    doc, fid = _move(
        "coincident; coincident", [(bottom, {"feature": "f2"}), (top, {"feature": "f2"})]
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "cannot all hold" in messages(res)
    assert parse("distance 5; angle 90", "x")[0] == ("distance", 5.0)
    from fdcad.core.features.base import FeatureError

    with pytest.raises(FeatureError, match="coincident; distance 5"):
        parse("touching", "x")


def _moved_box(**extra: Any) -> list[float]:
    doc, ext = plate()
    fid = doc.new_feature_id()
    refs: dict[str, Any] = {"bodies": [{"kind": "face", "name": f"{ext}/cap/end"}]}
    params: dict[str, Any] = {}
    for k, v in extra.items():
        (refs if k in ("pivot_point", "handle_plane") else params)[k] = v
    doc.features.append(Feature(fid, "move_copy_body", "Move Body 1", params=params, refs=refs))
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    return _box(res.body.shape)  # type: ignore[union-attr]


def test_turns_about_a_picked_pivot_and_moves_along_a_plane() -> None:
    """TR268 item 3 (D2416): the handle's pivot and axes."""
    import math

    from fdcad.core.document.model import Param

    half = Param("90", math.pi / 2)
    about_centre = _moved_box(mode="rotate", rotate_by="centroid", rz=half)
    assert about_centre == pytest.approx([0, 0, 0, 50, 50, 10], abs=1e-6)  # a square turns
    from tests.core.features.test_stone_sprue import _point

    doc2, ext2 = plate()
    pivot = _point(doc2, 0, 0, 0)
    fid = doc2.new_feature_id()
    doc2.features.append(
        Feature(
            fid,
            "move_copy_body",
            "Move Body 1",
            params={"mode": "rotate", "rotate_by": "centroid", "rz": half, "pivot": "picked"},
            refs={"bodies": [{"kind": "face", "name": f"{ext2}/cap/end"}], "pivot_point": pivot},
        )
    )
    res = rebuild(doc2)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert _box(res.body.shape) == pytest.approx([-50, 0, 0, 0, 50, 10], abs=1e-6)  # type: ignore[union-attr]
    along = _moved_box(
        mode="translate",
        translate_by="delta",
        dx=Param("5", 5.0),
        handle_axes="plane_axes",
        handle_plane={"feature": "f4"},
    )
    # The Right plane's own X is model -Z (D74), so 5 along it moves the plate down.
    assert along == pytest.approx([0, 0, -5, 50, 50, 5], abs=1e-6)
