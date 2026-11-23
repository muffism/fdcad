"""Draft, neutral plane method (PHASE2_SPEC P2.7): angle, reverse, propagation modes,
lost neutral plane and faces that cannot be drafted."""

import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.preview import build_preview
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import (
    add_extrude,
    add_sketch,
    body,
    messages,
    plate,
    volume,
)

ANGLE = math.radians(5)


def add_draft(doc: Document, faces: list[dict[str, Any]], **params: Any) -> str:
    fid = doc.new_feature_id()
    all_params: dict[str, Any] = {"angle": Param("5", ANGLE)}
    all_params.update(params)
    doc.features.append(
        Feature(
            fid,
            "draft",
            f"Draft {fid}",
            params=all_params,
            refs={"neutral": {"feature": "f2"}, "faces": faces},
        )
    )
    return fid


def _ref(doc: Document, ext: str, role: str) -> dict[str, Any]:
    b = body(rebuild(doc), ext)
    ref = reference_for(b, b.face(f"{ext}/{role}"))
    assert ref is not None
    return ref


def frustum(side: float, h: float, angle: float) -> float:
    top = side - 2 * h * math.tan(angle)
    return h / 3 * (side**2 + top**2 + side * top)


def test_one_face_tilts_inward() -> None:
    doc, ext = plate()
    fid = add_draft(doc, [_ref(doc, ext, "side/e5")])
    res = body(rebuild(doc), fid)
    removed = 0.5 * 10 * 10 * math.tan(ANGLE) * 50
    assert volume(res.shape) == pytest.approx(25000 - removed, rel=1e-6)
    assert res.face(f"{ext}/side/e5") is not None


def test_reverse_tilts_the_other_way() -> None:
    doc, ext = plate()
    fid = add_draft(doc, [_ref(doc, ext, "side/e5")], reverse=True)
    assert volume(body(rebuild(doc), fid).shape) > 25000


def test_all_faces_propagation_drafts_every_side() -> None:
    doc, _ext = plate()
    fid = add_draft(doc, [], propagation="all")
    res = body(rebuild(doc), fid)
    assert volume(res.shape) == pytest.approx(frustum(50, 10, ANGLE), rel=1e-6)


def _plate_with_hole() -> tuple[Document, str, str]:
    doc, ext = plate()
    s = Sketch()
    s.add_circle(25, 25, 5)
    sk = add_sketch(doc, s, {"feature": "f2"})
    cut = add_extrude(doc, sk, 10.0, operation="cut")
    return doc, ext, cut


def test_inner_and_outer_propagation() -> None:
    doc, _ext, cut = _plate_with_hole()
    hole = math.pi * 25 * 10
    outer = add_draft(doc, [], propagation="outer")
    v_outer = volume(body(rebuild(doc), outer).shape)
    assert v_outer == pytest.approx(frustum(50, 10, ANGLE) - hole, rel=1e-6)
    doc.features.pop()
    inner = add_draft(doc, [], propagation="inner")
    v_inner = volume(body(rebuild(doc), inner).shape)
    # The hole's wall leans so a core pulls out along the pull: the hole widens.
    assert v_inner < 25000 - hole
    assert v_inner != pytest.approx(v_outer, rel=1e-6)
    assert cut


def _filleted_plate() -> tuple[Document, str]:
    """The plate with one vertical corner rounded, so a side face joins it smoothly."""
    from fdcad.core.features.modify import edges_of

    doc, ext = plate()
    b = body(rebuild(doc), ext)
    side = b.face(f"{ext}/side/e5")
    vertical = next(e for e in edges_of(side) if _is_vertical(e))
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "fillet",
            "Fillet 1",
            params={"fillet_type": "constant", "radius": Param("3", 3.0)},
            refs={"edges": [reference_for(b, vertical)]},
        )
    )
    return doc, ext


def test_tangent_propagation_follows_smooth_faces() -> None:
    volumes = []
    for mode in ("none", "tangent"):
        doc, ext = _filleted_plate()
        fillet = doc.features[-1].id
        b = body(rebuild(doc), fillet)
        ref = reference_for(b, b.face(f"{ext}/side/e5"))
        fid = add_draft(doc, [ref], propagation=mode)
        results = rebuild(doc)
        assert results[fid].state is not FeatureState.ERROR, messages(results[fid])
        volumes.append(volume(body(results, fid).shape))
    # The kernel always carries a draft across smooth joins (D218 item 2), so None and
    # Along tangent agree here, and both tilt more than the one flat face alone.
    assert volumes[1] == pytest.approx(volumes[0], rel=1e-9)
    single = 25000 - 0.5 * 10 * 10 * math.tan(ANGLE) * 50
    assert volumes[0] < single


def _is_vertical(edge: Any) -> bool:
    from fdcad.core.features.solids import line_ends

    ends = line_ends(edge)
    return ends is not None and abs(ends[0][2] - ends[1][2]) > 1


def test_a_face_square_to_the_pull_is_refused() -> None:
    doc, ext = plate()
    fid = add_draft(doc, [_ref(doc, ext, "cap/end")])
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "square to the pull direction" in messages(res)


def test_lost_neutral_face_is_named() -> None:
    doc, ext = plate()
    fid = add_draft(doc, [_ref(doc, ext, "side/e5")])
    doc.feature(fid).refs["neutral"] = {"kind": "face", "name": "f42/cap/end"}
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "f42/cap/end was lost" in messages(res)


def test_neutral_flat_face_and_preview() -> None:
    doc, ext = plate()
    fid = add_draft(doc, [_ref(doc, ext, "side/e5")])
    doc.feature(fid).refs["neutral"] = _ref(doc, ext, "cap/end")  # top face, pull +Z
    res = body(rebuild(doc), fid)
    removed = 0.5 * 10 * 10 * math.tan(ANGLE) * 50
    # About the top face the face leans the other way: material grows below it.
    assert volume(res.shape) == pytest.approx(25000 + removed, rel=1e-6)
    geometry = build_preview(doc, doc.feature(fid), rebuild(doc))
    assert geometry.error is None and geometry.shape is not None
