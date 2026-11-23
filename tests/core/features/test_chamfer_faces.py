"""Offset face and face to face chamfers (PHASE2_SPEC P2.5 item 1, DECISIONS D520)."""

import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.modify import edges_of
from fdcad.core.io.fdef import dumps, loads
from fdcad.core.naming.names import NamedShape
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Circle, Line, Sketch
from tests.core.features.test_features import (
    add_extrude,
    add_sketch,
    body,
    bounds,
    messages,
    plate,
    volume,
)

S45 = math.sin(math.radians(45))


def length(v: float) -> Param:
    return Param(f"{v:g}", v)


def wedge() -> tuple[Document, str]:
    """A 10 mm prism over (0,0), (40,0), (40,20), (20,20): 45 degrees at the origin edge
    (between side/e5 and side/e8) and 135 degrees at (20,20) (side/e7 and side/e8)."""
    doc = new_document()
    s = Sketch()
    pts = [s.add_point(x, y) for x, y in ((0, 0), (40, 0), (40, 20), (20, 20))]
    for p, q in zip(pts, pts[1:] + pts[:1], strict=True):
        eid = s.new_id()
        s.entities[eid] = Line(eid, p, q)
    return doc, add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)


def shared_edge(b: NamedShape, a: str, c: str) -> dict[str, Any]:
    fa, fc = b.face(a), b.face(c)
    assert fa is not None and fc is not None
    edge = next(e for e in edges_of(fa) if any(e.IsSame(x) for x in edges_of(fc)))
    ref = reference_for(b, edge)
    assert ref is not None
    return ref


def face_ref(b: NamedShape, name: str) -> dict[str, Any]:
    face = b.face(name)
    assert face is not None, name
    ref = reference_for(b, face)
    assert ref is not None
    return ref


def add_chamfer(doc: Document, params: dict[str, Any], **refs: Any) -> str:
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, "chamfer", f"Chamfer {fid}", params=params, refs=refs))
    return fid


def _removed(doc: Document, ext: str, fid: str) -> tuple[float, NamedShape]:
    results = rebuild(doc)
    res = body(results, fid)
    return volume(body(results, ext).shape) - volume(res.shape), res


# Offset face -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("faces", "d1", "d2"),
    [(("e5", "e8"), 1.0, 2.0), (("e7", "e8"), 1.0, 2.0), (("e5", "e8"), 1.5, 1.5)],
)
def test_offset_face_chamfer_at_45_and_135_degrees(
    faces: tuple[str, str], d1: float, d2: float
) -> None:
    doc, ext = wedge()
    b = body(rebuild(doc), ext)
    edge = shared_edge(b, f"{ext}/side/{faces[0]}", f"{ext}/side/{faces[1]}")
    params: dict[str, Any] = {"chamfer_type": "offset_face", "distance": length(d1)}
    if d1 != d2:
        params.update(method="asymmetric", distance2=length(d2))
    fid = add_chamfer(doc, params, edges=[edge])
    removed, res = _removed(doc, ext, fid)
    # Along face distances d2 / sin and d1 / sin, at 45 or 135 degrees (same sine).
    a, c = d2 / S45, d1 / S45
    assert removed == pytest.approx(0.5 * a * c * S45 * 10, rel=1e-6)
    made = res.face(f"{fid}/chamfer/{edge['name']}")
    assert made is not None
    # The chamfer meets the other face d1 off the reference face (here y = 0).
    if faces[0] == "e5":
        assert bounds(made)[4] == pytest.approx(d1, abs=1e-6)


def test_offset_face_chamfer_on_a_round_edge() -> None:
    """The angle between the top and the side of a cylinder is 90 degrees all round."""
    doc = new_document()
    s = Sketch()
    centre = s.add_point(0, 0)
    cid = s.new_id()
    s.entities[cid] = Circle(cid, centre, 10.0)
    ext = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    b = body(rebuild(doc), ext)
    top = b.face(f"{ext}/cap/end")
    assert top is not None
    edge = reference_for(b, edges_of(top)[0])
    params = {
        "chamfer_type": "offset_face",
        "method": "asymmetric",
        "distance": length(1),
        "distance2": length(2),
    }
    fid = add_chamfer(doc, params, edges=[edge])
    removed, _res = _removed(doc, ext, fid)
    # Reference face is the top (cap sorts first): along it d2 = 2, down the side d1 = 1.
    a, c = 2.0, 1.0
    assert removed == pytest.approx(2 * math.pi * (10 - a / 3) * 0.5 * a * c, rel=1e-6)


# Face to face ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("params", "area"),
    [
        ({"distance": length(2)}, 0.5 * 2 * 2 * S45),
        (
            {"method": "asymmetric", "distance": length(1), "distance2": length(3)},
            0.5 * 1 * 3 * S45,
        ),
        (
            {"method": "width", "width": length(2), "distance": length(1)},
            0.5 * (2 / (2 * math.sin(math.radians(22.5)))) ** 2 * S45,
        ),
    ],
)
def test_face_to_face_chamfer_volumes(params: dict[str, Any], area: float) -> None:
    doc, ext = wedge()
    b = body(rebuild(doc), ext)
    full = {"chamfer_type": "face_face", **params}
    full.setdefault("method", "symmetric")
    fid = add_chamfer(
        doc,
        full,
        faces1=[face_ref(b, f"{ext}/side/e5")],
        faces2=[face_ref(b, f"{ext}/side/e8")],
    )
    removed, res = _removed(doc, ext, fid)
    assert removed == pytest.approx(area * 10, rel=1e-6)
    made = [f for n, f in res.faces if n.startswith(f"{fid}/chamfer/")]
    assert len(made) == 1
    if full["method"] == "asymmetric":
        # The first distance runs along set 1 (the face on y = 0), from x = 0 to x = 1.
        assert bounds(made[0])[0] == pytest.approx(1.0, abs=1e-6)
        assert bounds(made[0])[3] == pytest.approx(3 * S45, abs=1e-6)
    if full["method"] == "width":
        from fdcad.core.features.solids import face_area

        assert face_area(made) == pytest.approx(2 * 10, rel=1e-6)


def test_face_to_face_sets_that_do_not_meet() -> None:
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    fid = add_chamfer(
        doc,
        {"chamfer_type": "face_face", "method": "symmetric", "distance": length(1)},
        faces1=[face_ref(b, f"{ext}/cap/end")],
        faces2=[face_ref(b, f"{ext}/cap/start")],
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "do not meet at an edge" in messages(res)


def test_face_to_face_too_large_offers_the_width_fix() -> None:
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    fid = add_chamfer(
        doc,
        {
            "chamfer_type": "face_face",
            "method": "width",
            "width": length(40),
            "distance": length(1),
        },
        faces1=[face_ref(b, f"{ext}/cap/end")],
        faces2=[face_ref(b, f"{ext}/side/e5")],
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR, messages(res)
    assert "largest width" in messages(res)
    fixes = [fix for issue in res.issues for fix in issue.fixes]
    assert [f.data.get("param") for f in fixes if f.action == "set_param"] == ["width"]
    assert not [f for f in fixes if f.action == "skip_items"]


def test_new_types_round_trip_and_old_chamfers_save_unchanged() -> None:
    doc, ext = wedge()
    b = body(rebuild(doc), ext)
    edge = shared_edge(b, f"{ext}/side/e5", f"{ext}/side/e8")
    old = add_chamfer(
        doc, {"chamfer_type": "distance_distance", "method": "symmetric", "distance": length(1)},
        edges=[shared_edge(b, f"{ext}/side/e6", f"{ext}/side/e7")],
    )  # fmt: skip
    plain = dumps(doc)
    for key in ("faces1", "width", "offset_face", "face_face"):
        assert key not in plain
    off = add_chamfer(doc, {"chamfer_type": "offset_face", "distance": length(1)}, edges=[edge])
    ff = add_chamfer(
        doc,
        {"chamfer_type": "face_face", "method": "width", "width": length(1), "distance": length(1)},
        faces1=[face_ref(b, f"{ext}/cap/end")],
        faces2=[face_ref(b, f"{ext}/side/e6")],
    )
    text = dumps(doc)
    again = loads(text)
    assert dumps(again) == text
    assert again.feature(ff).params["width"] == length(1)
    first, second = rebuild(doc), rebuild(again)
    for fid in (old, off, ff):
        assert volume(body(second, fid).shape) == pytest.approx(
            volume(body(first, fid).shape), rel=1e-9
        )
