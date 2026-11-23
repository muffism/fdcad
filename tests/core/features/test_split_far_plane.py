"""Split and Intersect with a plane whose origin is far from the body (D1062).

Found on a gearbox (2026-11-12): a block 280 mm from the part's origin was to be
split by a plane offset from the Right plane. The sheet that stands for the endless
plane was sized for the block but centred on the plane's own origin, so it did not
reach the block: "the tools do not cut through any body".
"""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, messages, rect


def _far_block_and_plane() -> tuple[object, str]:
    """A 60 by 40 by 20 block at x 500 to 560, y 260 to 300, and a plane at x = 530."""
    doc = new_document()
    s = Sketch()
    rect(s, 500, 260, 560, 300)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 20.0)
    plane = doc.new_feature_id()
    doc.features.append(
        Feature(plane, "ref_plane", "Plane 1",
                params={"method": "offset", "distance": Param("530", 530.0)},
                refs={"first": {"feature": "f4"}})
    )  # fmt: skip
    got = rebuild(doc)[plane].plane
    assert got is not None and got.origin[0] == pytest.approx(530.0)
    assert abs(got.origin[1]) < 1.0  # the plane's origin is 260 mm from the block
    return doc, plane


def test_split_by_a_plane_made_far_from_the_body() -> None:
    doc, plane = _far_block_and_plane()
    fid = doc.new_feature_id()  # type: ignore[attr-defined]
    doc.features.append(  # type: ignore[attr-defined]
        Feature(fid, "split", "Split 1", refs={"tools": [{"feature": plane}]})
    )
    res = rebuild(doc)[fid]  # type: ignore[arg-type]
    assert res.state is FeatureState.OK, messages(res)
    halves = sorted(volume_of(s) for s in solids(res.body.shape))  # type: ignore[union-attr]
    assert halves == pytest.approx([30 * 40 * 20, 30 * 40 * 20], rel=1e-9)


def test_intersect_with_a_plane_made_far_from_the_body() -> None:
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    from fdcad.core.naming.select import reference_for

    doc, plane = _far_block_and_plane()
    body = rebuild(doc)[plane].body  # type: ignore[arg-type]
    face = TopoDS.Face(TopExp_Explorer(body.shape, TopAbs_FACE).Current())  # type: ignore[union-attr]
    fid = doc.new_feature_id()  # type: ignore[attr-defined]
    doc.features.append(  # type: ignore[attr-defined]
        Feature(fid, "intersect", "Intersect 1", params={"regions": "overlap", "merge": False},
                refs={"bodies": [reference_for(body, face)], "planes": [{"feature": plane}]})
    )  # fmt: skip
    res = rebuild(doc)[fid]  # type: ignore[arg-type]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert len(solids(res.body.shape)) == 2  # type: ignore[union-attr]


def test_split_for_print_by_a_plane_made_far_from_the_body() -> None:
    """The same for Split for Printing in planes mode (D1062)."""
    doc, plane = _far_block_and_plane()
    fid = doc.new_feature_id()  # type: ignore[attr-defined]
    doc.features.append(  # type: ignore[attr-defined]
        Feature(fid, "split_for_print", "Print Split 1",
                params={"mode": "planes", "connector": "none"},
                refs={"planes": [{"feature": plane}]})
    )  # fmt: skip
    res = rebuild(doc)[fid]  # type: ignore[arg-type]
    assert res.state is FeatureState.OK, messages(res)
    assert len(solids(res.body.shape)) == 2  # type: ignore[union-attr]
