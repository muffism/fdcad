"""Face fillet, full round fillet and the fillet assistant (PHASE2_SPEC P2.4 items 1,
DECISIONS D518 and D519)."""

import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.io.fdef import dumps, loads
from fdcad.core.naming.names import NamedShape
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import (
    add_extrude,
    add_sketch,
    body,
    messages,
    plate,
    rect,
    volume,
)

PLATE = 50 * 50 * 10


def strip(r: float) -> float:
    """Material a 90 degree fillet of radius r removes (or adds) per mm of edge."""
    return (1 - math.pi / 4) * r * r


def rib_part(width: float = 4.0, height: float = 10.0) -> tuple[Document, str, str]:
    """The 50 by 50 by 10 plate with a rib from x 20 to 20 + width, height above the plate."""
    doc, ext = plate()
    s = Sketch()
    rect(s, 20, 0, 20 + width, 50)
    sk = add_sketch(doc, s, {"kind": "face", "name": f"{ext}/cap/end"})
    rib = add_extrude(doc, sk, height)
    return doc, ext, rib


def ref(b: NamedShape, name: str) -> dict[str, Any]:
    face = b.face(name)
    assert face is not None, name
    r = reference_for(b, face)
    assert r is not None
    return r


def add_fillet(doc: Document, params: dict[str, Any], **refs: Any) -> str:
    fid = doc.new_feature_id()
    all_params: dict[str, Any] = {"radius": Param("2", 2.0)}
    all_params.update(params)
    doc.features.append(Feature(fid, "fillet", f"Fillet {fid}", params=all_params, refs=refs))
    return fid


def _full_round(doc: Document, rib: str, b: NamedShape) -> str:
    return add_fillet(
        doc,
        {"fillet_type": "full_round"},
        faces1=[ref(b, f"{rib}/side/e8")],
        centre=[ref(b, f"{rib}/cap/end")],
        faces2=[ref(b, f"{rib}/side/e6")],
    )


# Full round --------------------------------------------------------------------------


@pytest.mark.parametrize("width", [4.0, 3.0])
def test_full_round_removes_the_exact_volume(width: float) -> None:
    doc, _ext, rib = rib_part(width)
    b = body(rebuild(doc), rib)
    before = volume(b.shape)
    fid = _full_round(doc, rib, b)
    res = body(rebuild(doc), fid)
    removed = 50 * (width * width / 2 - math.pi * width * width / 8)
    assert before - volume(res.shape) == pytest.approx(removed, rel=1e-7)
    assert res.face(f"{fid}/full_round/{rib}/cap/end") is not None
    assert res.face(f"{rib}/cap/end") is None  # the centre face is gone


def test_full_round_needs_parallel_flat_sides() -> None:
    doc, ext, rib = rib_part()
    b = body(rebuild(doc), rib)
    fid = add_fillet(
        doc,
        {"fillet_type": "full_round"},
        faces1=[ref(b, f"{rib}/side/e8")],
        centre=[ref(b, f"{rib}/cap/end")],
        faces2=[ref(b, f"{ext}/side/e5")],
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "parallel side faces" in messages(res)


def test_full_round_on_a_rib_lower_than_half_its_width_fails() -> None:
    doc, _ext, rib = rib_part(width=4.0, height=1.0)
    b = body(rebuild(doc), rib)
    fid = _full_round(doc, rib, b)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "shorter than half the width" in messages(res)


def test_full_round_needs_every_set() -> None:
    doc, _ext, rib = rib_part()
    b = body(rebuild(doc), rib)
    fid = add_fillet(
        doc,
        {"fillet_type": "full_round"},
        faces1=[ref(b, f"{rib}/side/e8")],
        faces2=[ref(b, f"{rib}/side/e6")],
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "Centre Face Set is empty" in messages(res)


# Face fillet -------------------------------------------------------------------------


def test_face_fillet_rounds_the_edge_where_the_sets_meet() -> None:
    doc, ext, rib = rib_part()
    b = body(rebuild(doc), rib)
    before = volume(b.shape)
    # Concave edge between the rib side and the plate top: material is added.
    fid = add_fillet(
        doc,
        {"fillet_type": "face"},
        faces1=[ref(b, f"{rib}/side/e6")],
        faces2=[ref(b, f"{ext}/cap/end#2")],
    )
    res = body(rebuild(doc), fid)
    assert volume(res.shape) - before == pytest.approx(strip(2) * 50, rel=1e-6)
    assert [n for n, _f in res.faces if n.startswith(f"{fid}/fillet/")]


def test_face_fillet_of_sets_that_do_not_meet_is_an_error() -> None:
    doc, ext, rib = rib_part()
    b = body(rebuild(doc), rib)
    fid = add_fillet(
        doc,
        {"fillet_type": "face"},
        faces1=[ref(b, f"{rib}/cap/end")],
        faces2=[ref(b, f"{ext}/cap/start")],
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "do not meet at an edge" in messages(res)


def test_face_fillet_too_large_offers_the_radius_fix_only() -> None:
    doc, ext, rib = rib_part()
    b = body(rebuild(doc), rib)
    fid = add_fillet(
        doc,
        {"fillet_type": "face", "radius": Param("30", 30.0)},
        faces1=[ref(b, f"{ext}/cap/start")],
        faces2=[ref(b, f"{ext}/side/e6")],
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    actions = [fix.action for issue in res.issues for fix in issue.fixes]
    assert "skip_items" not in actions
    assert "set_param" in actions


# Fillet assistant --------------------------------------------------------------------


def test_assistant_concave_edges_of_the_part() -> None:
    doc, _ext, rib = rib_part()
    before = volume(body(rebuild(doc), rib).shape)
    fid = add_fillet(doc, {"fillet_type": "constant"}, auto_edges=[{"convexity": "concave"}])
    res = body(rebuild(doc), fid)
    # The two edges along the foot of the rib.
    assert volume(res.shape) - before == pytest.approx(2 * strip(2) * 50, rel=1e-6)


def test_assistant_convex_edges_of_one_feature() -> None:
    doc, _ext, rib = rib_part()
    before = volume(body(rebuild(doc), rib).shape)
    fid = add_fillet(
        doc,
        {"fillet_type": "constant", "radius": Param("1", 1.0)},
        auto_edges=[{"convexity": "convex", "feature": rib}],
    )
    res = body(rebuild(doc), fid)
    names = [n for n, _f in res.faces if n.startswith(f"{fid}/fillet/")]
    # Rib top: two long edges, two short end edges; rib ends: two upright edges each.
    assert len(names) >= 4
    assert volume(res.shape) < before


def test_assistant_with_a_feature_that_is_gone_is_an_error() -> None:
    doc, _ext, _rib = rib_part()
    fid = add_fillet(doc, {}, auto_edges=[{"convexity": "convex", "feature": "f99"}])
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "f99" in messages(res)


# File --------------------------------------------------------------------------------


def test_new_types_round_trip_and_old_fillets_save_unchanged() -> None:
    doc, ext, rib = rib_part()
    b = body(rebuild(doc), rib)
    old = add_fillet(doc, {"fillet_type": "constant"}, faces=[ref(b, f"{ext}/cap/start")])
    plain = dumps(doc)
    for key in ("faces1", "centre", "auto_edges", "full_round"):
        assert key not in plain
    fr = _full_round(doc, rib, b)
    doc.feature(fr).refs  # noqa: B018
    auto = add_fillet(doc, {"fillet_type": "constant"}, auto_edges=[{"convexity": "concave"}])
    text = dumps(doc)
    again = loads(text)
    assert dumps(again) == text
    assert again.feature(fr).params["fillet_type"] == "full_round"
    assert again.feature(auto).refs["auto_edges"] == [{"convexity": "concave"}]
    first = rebuild(doc)
    second = rebuild(again)
    for fid in (old, fr, auto):
        assert volume(body(second, fid).shape) == pytest.approx(
            volume(body(first, fid).shape), rel=1e-9
        )


# Partial edges -----------------------------------------------------------------------


def _plate_edge(at_y: float) -> tuple[Document, str, dict[str, Any]]:
    """The plate and its top edge along x at y = ``at_y``."""
    from fdcad.core.features.modify import edges_of
    from tests.core.features.test_features import bounds

    doc, ext = plate()
    b = body(rebuild(doc), ext)
    top = b.face(f"{ext}/cap/end")
    assert top is not None
    edge = next(e for e in edges_of(top) if bounds(e)[1] == bounds(e)[4] == at_y)
    r = reference_for(b, edge)
    assert r is not None
    return doc, ext, r


def _partial(**params: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"fillet_type": "constant"}
    for key, value in params.items():
        out[key] = Param(f"{value:g}", float(value)) if isinstance(value, int | float) else value
    return out


@pytest.mark.parametrize(
    ("params", "span"),
    [
        (_partial(partial="percent", start_percent=25, end_percent=75), 25.0),
        (_partial(partial="distance", start_distance=10, end_distance=20), 10.0),
        (_partial(partial="distance", start_distance=0, end_distance=30), 30.0),
    ],
)
def test_partial_edge_fillet_volume_and_names(params: dict[str, Any], span: float) -> None:
    doc, ext, edge = _plate_edge(0.0)
    fid = add_fillet(doc, params, edges=[edge])
    res = body(rebuild(doc), fid)
    assert volume(res.shape) == pytest.approx(PLATE - strip(2) * span, rel=1e-6)
    assert res.face(f"{fid}/fillet/{edge['name']}") is not None
    # Faces that were only split and merged again keep their names.
    for name in (f"{ext}/cap/end", f"{ext}/side/e5", f"{ext}/cap/start"):
        assert res.face(name) is not None, name


def test_partial_flip_measures_from_the_other_end() -> None:
    from tests.core.features.test_features import bounds

    starts = []
    for flip in (False, True):
        doc, _ext, edge = _plate_edge(0.0)
        params = _partial(partial="distance", start_distance=0, end_distance=10)
        if flip:
            params["partial_flip"] = True
        fid = add_fillet(doc, params, edges=[edge])
        made = body(rebuild(doc), fid).face(f"{fid}/fillet/{edge['name']}")
        assert made is not None
        starts.append(bounds(made)[0])
    assert sorted(starts) == pytest.approx([0.0, 40.0], abs=1e-6)


def test_partial_on_two_edges() -> None:
    from fdcad.core.features.modify import edges_of
    from tests.core.features.test_features import bounds

    doc, ext, front = _plate_edge(0.0)
    b = body(rebuild(doc), ext)
    top = b.face(f"{ext}/cap/end")
    assert top is not None
    back = next(e for e in edges_of(top) if bounds(e)[1] == bounds(e)[4] == 50.0)
    params = _partial(partial="percent", start_percent=20, end_percent=60)
    fid = add_fillet(doc, params, edges=[front, reference_for(b, back)])
    res = body(rebuild(doc), fid)
    assert volume(res.shape) == pytest.approx(PLATE - 2 * strip(2) * 20, rel=1e-6)


def test_partial_range_off_the_edge_is_an_error() -> None:
    doc, _ext, edge = _plate_edge(0.0)
    params = _partial(partial="distance", start_distance=20, end_distance=60)
    fid = add_fillet(doc, params, edges=[edge])
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "must start before it ends" in messages(res)


def test_partial_keys_round_trip() -> None:
    doc, _ext, edge = _plate_edge(0.0)
    params = _partial(partial="percent", start_percent=10, end_percent=40)
    params["partial_flip"] = True
    fid = add_fillet(doc, params, edges=[edge])
    text = dumps(doc)
    again = loads(text)
    assert dumps(again) == text
    assert again.feature(fid).params["start_percent"] == Param("10", 10.0)
    assert volume(body(rebuild(again), fid).shape) == pytest.approx(PLATE - strip(2) * 15, rel=1e-6)
