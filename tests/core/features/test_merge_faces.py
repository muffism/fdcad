"""Merge Faces (TR261, D787)."""

from __future__ import annotations

from typing import Any

import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.import_step import part_from_step
from fdcad.core.features.solids import volume_of
from fdcad.core.naming.names import centroid, faces_of
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.samples.step_source import colored_step_bytes


def _split_block(step: float = 0.0) -> Document:
    """Two 20 by 30 by 10 blocks side by side, fused without merging: the top, bottom,
    front and back faces are each split in two. ``step`` raises the second block."""
    a = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 20.0, 30.0, 10.0).Shape()
    b = BRepPrimAPI_MakeBox(gp_Pnt(20, 0, 0), 20.0, 30.0, 10.0 + step).Shape()
    fuse = BRepAlgoAPI_Fuse(a, b)
    return part_from_step("split.step", colored_step_bytes(fuse.Shape(), "#888888", []))


def _up(face: Any) -> bool:
    from fdcad.core.features.face_picks import outward_normal

    n = outward_normal(face)
    return n is not None and n[2] > 0.99


def _tops(doc: Document) -> list[dict[str, Any]]:
    body = rebuild(doc)[doc.features[-1].id].body
    assert body is not None
    tops = [f for _n, f in body.faces if _up(f)]
    refs = [reference_for(body, f) for f in tops]
    assert len(refs) == 2 and all(refs)
    return refs  # type: ignore[return-value]


def _merge(doc: Document, refs: dict[str, Any], **params: Any) -> Any:
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, "merge_faces", "Merge Faces 1", params=params, refs=refs))
    return rebuild(doc)[fid]


def test_two_faces_on_one_plane_become_one() -> None:
    doc = _split_block()
    before = rebuild(doc)[doc.features[-1].id].body
    assert before is not None
    res = _merge(doc, {"faces": _tops(doc)})
    assert res.state is not FeatureState.ERROR, res.issues
    assert len(faces_of(res.body.shape)) == len(faces_of(before.shape)) - 1  # only the top
    assert volume_of(res.body.shape) == pytest.approx(volume_of(before.shape))
    tops = [f for f in faces_of(res.body.shape) if centroid(f)[2] > 9.9]
    assert len(tops) == 1


def test_an_edge_between_the_faces_merges_them() -> None:
    doc = _split_block()
    body = rebuild(doc)[doc.features[-1].id].body
    assert body is not None
    from fdcad.core.features.merge_faces import inner_edges

    tops = [f for _n, f in body.faces if centroid(f)[2] > 9.9]
    edge = inner_edges(tops)[0]
    res = _merge(doc, {"edges": [reference_for(body, edge)]})
    assert res.state is not FeatureState.ERROR, res.issues
    assert len(faces_of(res.body.shape)) == len(faces_of(body.shape)) - 1


def _bent_block(rise: float) -> Document:
    """A 40 by 30 block whose top is two faces sharing an edge at x = 20: the second
    rises by ``rise`` over its 20 mm, so the two meet at a tiny angle."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Vec

    poly = BRepBuilderAPI_MakePolygon()
    for x, z in ((0, 0), (40, 0), (40, 10 + rise), (20, 10), (0, 10)):
        poly.Add(gp_Pnt(x, 0, z))
    poly.Close()
    face = BRepBuilderAPI_MakeFace(poly.Wire()).Face()
    shape = BRepPrimAPI_MakePrism(face, gp_Vec(0, 30, 0)).Shape()
    return part_from_step("bent.step", colored_step_bytes(shape, "#888888", []))


def test_nearly_one_surface_needs_a_looser_tolerance() -> None:
    doc = _bent_block(rise=0.1)  # about 0.29 degrees: more than the default 0.1
    refs = {"faces": _tops(doc)}
    res = _merge(doc, refs)
    assert res.state is FeatureState.ERROR
    assert "do not lie on one surface" in res.issues[0].message
    doc.features.pop()
    loose = _merge(doc, refs, tolerance=Param("0.2", 0.2), angle_tolerance=Param("1deg", 0.0174533))
    assert loose.state is not FeatureState.ERROR, loose.issues
    start = rebuild(doc)[doc.features[-2].id].body
    assert start is not None
    assert len(faces_of(loose.body.shape)) == len(faces_of(start.shape)) - 1


def test_faces_that_do_not_touch_say_so() -> None:
    doc = _split_block(step=0.05)  # a small step face sits between the two tops
    res = _merge(doc, {"faces": _tops(doc)})
    assert res.state is FeatureState.ERROR
    assert "do not touch" in res.issues[0].message


def test_combine_with_a_tolerance_joins_bodies_that_nearly_touch() -> None:
    """TR261 item 2: imported bodies 0.02 mm apart."""
    from fdcad.core.features.solids import compound, solids

    a = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 20.0, 30.0, 10.0).Shape()
    b = BRepPrimAPI_MakeBox(gp_Pnt(20.02, 0, 0), 20.0, 30.0, 10.0).Shape()
    doc = part_from_step("two.step", colored_step_bytes(compound([a, b]), "#888888", []))
    body = rebuild(doc)[doc.features[-1].id].body
    assert body is not None and len(solids(body.shape)) == 2
    near = [f for _n, f in body.faces if centroid(f)[0] < 1e-6]
    far = [f for _n, f in body.faces if centroid(f)[0] > 39.9]
    refs = {"bodies": [reference_for(body, near[0]), reference_for(body, far[0])]}

    def combined(**params: Any) -> int:
        fid = doc.new_feature_id()
        doc.features.append(
            Feature(fid, "combine", "Combine 1", params={"operation": "add", **params}, refs=refs)
        )
        res = rebuild(doc)[fid]
        doc.features.pop()
        assert res.body is not None
        return len(solids(res.body.shape))

    assert combined() == 2
    assert combined(tolerance=Param("0.05", 0.05)) == 1
