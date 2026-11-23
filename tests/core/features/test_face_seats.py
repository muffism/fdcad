"""Face Seats on curved faces (TR405, D2009)."""

from __future__ import annotations

import math
from typing import Any

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch


def P(v: float) -> Param:  # noqa: N802
    return Param(f"{v:g}", v)


def _doc() -> tuple[Any, dict[str, Any], dict[str, Any]]:
    """A 20 mm radius cylinder 40 tall at x = 50, and a 2 mm stud seed at the origin."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder

    from fdcad.core.naming.names import faces_of
    from fdcad.core.naming.select import reference_for
    from fdcad.core.rebuild.engine import RebuildEngine

    doc = new_document()
    s = Sketch()
    s.add_circle(50, 0, 20)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 40.0)
    seed = Sketch()
    seed.add_circle(0, 0, 1)
    add_extrude(doc, add_sketch(doc, seed, {"feature": "f2"}), 3.0, merge=False)
    body = RebuildEngine().rebuild(doc).body
    side = next(f for f in faces_of(body.shape)
                if BRepAdaptor_Surface(f).GetType() == GeomAbs_Cylinder
                and abs(BRepAdaptor_Surface(f).Cylinder().Radius() - 20) < 1e-9)  # fmt: skip
    stud = next(f for f in faces_of(solids(body.shape)[1]))
    face_ref, seed_ref = reference_for(body, side), reference_for(body, stud)
    assert face_ref is not None and seed_ref is not None
    return doc, face_ref, seed_ref


def _seats(**params: Any) -> Any:
    doc, face, seed = _doc()
    fid = doc.new_feature_id()
    base = {"count_u": P(6), "count_v": P(2), "sink": P(0.5)}
    base.update(params)
    doc.features.append(Feature(fid, "face_seats", "Face Seats 1", params=base,
                                refs={"on_face": face, "seed": seed}))  # fmt: skip
    return rebuild(doc)[fid]


def test_studs_join_the_cylinder() -> None:
    res = _seats()
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert len(solids(res.body.shape)) == 1  # the seed is used up
    cylinder = math.pi * 400 * 40
    added = volume_of(res.body.shape) - cylinder
    assert 0.7 * 12 * math.pi * 3 < added < 12 * math.pi * 3


def test_dimples_cut_the_cylinder() -> None:
    res = _seats(operation="cut", sink=P(1.5))
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert volume_of(res.body.shape) < math.pi * 400 * 40
    assert any("/seat#" in name for name, _f in res.body.faces)


def test_counts_are_limited() -> None:
    res = _seats(count_u=P(500))
    assert res.state is FeatureState.ERROR and "Enter smaller counts" in res.issues[0].message


def test_seats_leave_the_other_bodies_alone() -> None:
    """D1055: found on a gearbox. The copies were fused with every other body of the
    part at once, and that joined two blocks elsewhere that were locked together with
    teeth (Interlock). Here: the same two blocks, far from the cylinder, stay two."""
    from fdcad.core.naming.names import centroid
    from fdcad.core.naming.select import reference_for
    from fdcad.core.rebuild.engine import RebuildEngine
    from tests.core.features.test_features import rect

    doc, face, seed = _doc()
    s = Sketch()
    rect(s, 100, 0, 120, 20)
    lower = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 5.0, merge=False)
    body = RebuildEngine().rebuild(doc).body
    top = next(
        f for n, f in body.faces if n.startswith(f"{lower}/") and abs(centroid(f)[2] - 5) < 1e-9
    )
    top_ref = reference_for(body, top)
    assert top_ref is not None
    s = Sketch()
    rect(s, 100, 0, 120, 20)
    add_extrude(doc, add_sketch(doc, s, top_ref), 5.0, merge=False)
    teeth = doc.new_feature_id()
    doc.features.append(Feature(teeth, "interlock", "Interlock 1",
                                params={"tooth_size": P(4), "tooth_depth": P(1)},
                                refs={"face": [top_ref]}))  # fmt: skip
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, "face_seats", "Face Seats 1",
                                params={"count_u": P(6), "count_v": P(2), "sink": P(0.5)},
                                refs={"on_face": face, "seed": seed}))  # fmt: skip
    results = rebuild(doc)
    assert results[teeth].state is FeatureState.OK, [i.message for i in results[teeth].issues]
    assert len(solids(results[teeth].body.shape)) == 4  # cylinder, seed, two blocks
    res = results[fid]
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert len(solids(res.body.shape)) == 3  # the seed is used up, the blocks stay two
    assert any(n.startswith(f"{fid}/seat#") for n, _f in res.body.faces)
