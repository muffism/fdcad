"""Replace Face with a plane target (TR130, D1412)."""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import messages, plate, volume
from tests.core.features.test_reference_geometry import _add
from tests.core.features.test_shell import _face_ref

FRONT = "f2"  # the plate's sketch plane, z = 0


def _replace(doc: Document, faces: list[dict[str, Any]], target: dict[str, Any]) -> str:
    fid = doc.new_feature_id()
    refs = {"faces": faces, "target": target}
    doc.features.append(Feature(fid, "replace_face", "Replace Face 1", refs=refs))
    return fid


@pytest.mark.parametrize("height", [12.0, 7.0])
def test_top_face_moves_to_the_plane(height: float) -> None:
    doc, ext = plate()
    top = _face_ref(doc, ext, "cap/end")
    plane = _add(doc, "ref_plane", {"first": {"feature": FRONT}}, method="offset", distance=height)
    fid = _replace(doc, [top], {"feature": plane})
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None
    assert volume(res.body.shape) == pytest.approx(50 * 50 * height, rel=1e-6)
    assert res.body.face(f"{fid}/replaced") is not None
    assert res.body.face(f"{ext}/side/e5") is not None  # neighbours keep their names


def test_a_small_block_far_from_the_plane_origin() -> None:
    """D1087: the slab that cuts the moved face to the plane was centred on the plane's
    origin and sized from the part, so it missed a small block 600 mm away."""
    from fdcad.core.sketch.model import Sketch
    from tests.core.features.test_features import add_extrude, add_sketch, rect

    doc = __import__("fdcad.core.document.model", fromlist=["new_document"]).new_document()
    s = Sketch()
    rect(s, 600, 600, 620, 620)
    ext = add_extrude(doc, add_sketch(doc, s, {"feature": FRONT}), 10.0)
    top = _face_ref(doc, ext, "cap/end")
    plane = _add(doc, "ref_plane", {"first": {"feature": FRONT}}, method="offset", distance=15.0)
    fid = _replace(doc, [top], {"feature": plane})
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert volume(res.body.shape) == pytest.approx(20 * 20 * 15, rel=1e-6)


def test_a_curved_target_is_refused() -> None:
    from tests.core.features.test_fillet_tangent import rounded_plate

    doc, corner, b = rounded_plate()
    round_face = next(f for n, f in b.faces if n.startswith(f"{corner}/fillet/"))
    from fdcad.core.naming.select import reference_for

    top = next(f for n, f in b.faces if n.endswith("/cap/end"))
    fid = _replace(doc, [reference_for(b, top)], reference_for(b, round_face))
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "curved target is not supported" in messages(res)
