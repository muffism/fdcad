"""Pieces left by Split and Split for Print (round 10d, D620, D621).

The pieces share their cut face. Later features must not warn that they touch
along an edge, a boss on one piece must not join the pieces again, and Split for
Print cuts only the bodies picked in ``refs.bodies``.
"""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, plate, rect


def P(v: float) -> Param:  # noqa: N802
    return Param(f"{v:g}", v)


def halves(kind: str = "split_for_print") -> Document:
    """The 50 by 50 by 10 plate cut at x = 25 into two pieces."""
    doc, _ext = plate(10.0)
    fid = doc.new_feature_id()
    if kind == "split_for_print":
        params: dict[str, Any] = dict(
            mode="auto", build_x=P(30), build_y=P(100), build_z=P(100), connector="none"
        )
        doc.features.append(Feature(fid, kind, "Print Split 1", params=params))
    else:
        doc.features.append(make_plane(doc, fid))
        sid = doc.new_feature_id()
        doc.features.append(Feature(sid, "split", "Split 1", refs={"tools": [{"feature": fid}]}))
    assert len(solids(body(rebuild(doc), doc.features[-1].id).shape)) == 2
    return doc


def make_plane(doc: Document, fid: str) -> Feature:
    """A plane parallel to Right at x = 25."""
    return Feature(
        fid,
        "ref_plane",
        "Plane 1",
        params={"method": "offset", "distance": P(25)},
        refs={"first": {"feature": "f4"}},
    )


def boss(doc: Document, x0: float, y0: float, x1: float, y1: float, **params: Any) -> Any:
    s = Sketch()
    rect(s, x0, y0, x1, y1)
    sk = add_sketch(doc, s, {"feature": "f2"})
    fid = add_extrude(doc, sk, 20.0, **params)
    return rebuild(doc)[fid]


def codes(res: Any) -> set[str]:
    return {i.code for i in res.issues}


@pytest.mark.parametrize("kind", ["split_for_print", "split"])
def test_boss_on_one_piece_keeps_the_pieces_apart(kind: str) -> None:
    doc = halves(kind)
    res = boss(doc, 5, 5, 15, 15)
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert len(solids(res.body.shape)) == 2
    assert volume_of(res.body.shape) == pytest.approx(25000 + 1000, rel=1e-6)


def test_cut_across_the_seam_does_not_warn() -> None:
    doc = halves()
    res = boss(doc, 20, 20, 30, 30, operation="cut", end_condition="through_all")
    assert "zero_thickness" not in codes(res), [i.message for i in res.issues]
    assert len(solids(res.body.shape)) == 2
    assert volume_of(res.body.shape) == pytest.approx(25000 - 1000, rel=1e-6)


def test_boss_across_the_seam_joins_the_pieces() -> None:
    doc = halves()
    res = boss(doc, 20, 20, 30, 30)
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert len(solids(res.body.shape)) == 1


def test_edge_contact_on_a_piece_still_warns() -> None:
    doc = halves()
    res = boss(doc, 50, 50, 60, 60)  # meets the second piece along one edge only
    assert "zero_thickness" in codes(res)


def test_split_for_print_cuts_only_the_picked_body() -> None:
    doc, ext = plate(10.0)
    s = Sketch()
    rect(s, 100, 0, 150, 50)
    sk = add_sketch(doc, s, {"feature": "f2"})
    other = add_extrude(doc, sk, 10.0, merge=False)
    part = body(rebuild(doc), other)
    assert len(solids(part.shape)) == 2
    face = part.face(f"{ext}/cap/end")
    assert face is not None
    ref = reference_for(part, face)
    fid = doc.new_feature_id()
    params = dict(mode="auto", build_x=P(30), build_y=P(100), build_z=P(100), connector="none")
    doc.features.append(
        Feature(fid, "split_for_print", "Print Split 1", params=params, refs={"bodies": [ref]})
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    # The plate is cut in two; the second body is left whole although it is too wide.
    assert len(solids(res.body.shape)) == 3
    assert volume_of(res.body.shape) == pytest.approx(50000, rel=1e-6)
    doc.features[-1].refs.clear()
    res = rebuild(doc)[fid]
    assert len(solids(res.body.shape)) == 4  # both bodies cut without a pick


def test_lip_and_groove_on_the_cut_rim_of_a_split_enclosure() -> None:
    """Shell a box, cut it in two, lip on one piece and groove in the other (D622)."""
    from pathlib import Path

    from fdcad.core.io import fdef

    doc = fdef.load(Path(__file__).parents[3] / "samples" / "printable_enclosure.fdprt")
    doc.features = doc.features[:7]  # box and shell, 2 mm walls, 40 mm tall
    doc.features.append(
        Feature(
            "p1",
            "ref_plane",
            "Middle",
            params={"method": "offset", "distance": P(20)},
            refs={"first": {"feature": "f2"}},
        )
    )
    planes = {"planes": [{"feature": "p1"}]}
    params: dict[str, Any] = {"mode": "planes", "connector": "none"}
    doc.features.append(
        Feature("s1", "split_for_print", "Print Split 1", params=params, refs=planes)
    )
    split = body(rebuild(doc), "s1")
    before = [volume_of(s) for s in solids(split.shape)]
    rim = split.face("s1/cut1")
    assert rim is not None
    ref = reference_for(split, rim)
    sizes = {"lip_width": P(1), "lip_height": P(2), "spacing": P(0.2), "gap": P(0.2)}
    rims = {"lip_faces": [ref], "groove_faces": [ref]}
    doc.features.append(Feature("lg", "lip_groove", "Lip 1", params=sizes, refs=rims))
    res = rebuild(doc)["lg"]
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    pieces = solids(res.body.shape)
    assert len(pieces) == 2  # the lip does not join the pieces
    lip = 2 * (2 * 1.0 * (96 + 66) + 3.141592653589793 * 1.0**2)
    groove = 2.2 * (2 * 1.2 * (96 + 66) + 3.141592653589793 * 1.2**2)
    after = [volume_of(s) for s in pieces]
    assert after[0] == pytest.approx(before[0] + lip, rel=1e-6)
    assert after[1] == pytest.approx(before[1] - groove, rel=1e-6)
    # D1083: a groove narrower than the lip leaves the lip running into the other piece.
    sizes = {"lip_width": P(1), "lip_height": P(2), "link": False, "groove_width": P(0.5),
             "groove_height": P(2.2)}  # fmt: skip
    doc.features[-1] = Feature("lg", "lip_groove", "Lip 1", params=sizes, refs=rims)
    res = rebuild(doc)["lg"]
    assert res.state is FeatureState.WARNING
    clash = [i.message for i in res.issues if i.code == "lip_clash"]
    assert clash and "the lip runs into the other body (" in clash[0]


def split_enclosure() -> Document:
    """The enclosure sample cut in two at mid height right after its shell."""
    from pathlib import Path

    from fdcad.core.io import fdef

    doc = fdef.load(Path(__file__).parents[3] / "samples" / "printable_enclosure.fdprt")
    plane = Feature(
        "p1",
        "ref_plane",
        "Middle",
        params={"method": "offset", "distance": P(20)},
        refs={"first": {"feature": "f2"}},
    )
    split = Feature(
        "s1",
        "split_for_print",
        "Print Split 1",
        params={"mode": "planes", "connector": "none"},
        refs={"planes": [{"feature": "p1"}]},
    )
    doc.features[7:7] = [plane, split]
    return doc


def test_snap_hook_and_boss_against_the_wall_stay_in_their_piece() -> None:
    """A tall hook or boss that meets the other piece joins only its own (D622)."""
    doc = split_enclosure()
    hook = doc.feature("f15")
    hook.params.update(body_height=P(30), pos_x=P(2))
    boss = doc.feature("f9")
    boss.params["boss_height"] = P(30)
    results = rebuild(doc)
    for fid in ("f9", "f15"):
        res = results[fid]
        assert res.state is not FeatureState.ERROR, [i.message for i in res.issues]
        assert len(solids(res.body.shape)) == 2, fid


def test_snap_groove_keeps_the_body_order() -> None:
    """Body colours go by body number, so a groove must not move its body (round 10d)."""
    doc = split_enclosure()
    doc.feature("f15").params.update(body_height=P(22), pos_x=P(2))
    split = body(rebuild(doc), "f16")
    before = [volume_of(s) for s in solids(split.shape)]
    lid = split.face("f6/cap/end")
    assert lid is not None
    params = {
        "groove_clearance": P(0.2),
        "gap_clearance": P(0.2),
        "offset_width": P(0.3),
        "gap_height": P(0.5),
    }
    refs = {"hook": {"feature": "f15"}, "body": [reference_for(split, lid)]}
    doc.features.append(Feature("g1", "snap_groove", "Groove 1", params=params, refs=refs))
    res = rebuild(doc)["g1"]
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    after = [volume_of(s) for s in solids(res.body.shape)]
    assert after[0] == pytest.approx(before[0])  # the bottom piece is not touched
    assert after[1] < before[1]  # the groove is in the lid, still the second body


def test_snap_groove_with_no_gap_above_the_head() -> None:
    """A gap height of 0 is a valid value; it made a side of zero length (round 10d)."""
    doc = split_enclosure()
    doc.feature("f15").params.update(body_height=P(22), pos_x=P(2))
    split = body(rebuild(doc), "f16")
    lid = split.face("f6/cap/end")
    assert lid is not None
    params = {"gap_height": P(0), "groove_clearance": P(0.2), "offset_width": P(0.3)}
    refs = {"hook": {"feature": "f15"}, "body": [reference_for(split, lid)]}
    doc.features.append(Feature("g1", "snap_groove", "Groove 1", params=params, refs=refs))
    res = rebuild(doc)["g1"]
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert volume_of(res.body.shape) < volume_of(split.shape)


def test_snap_groove_refuses_the_hook_body() -> None:
    """The groove never cuts the body that holds the hook (round 10d)."""
    from pathlib import Path

    from fdcad.core.io import fdef

    doc = fdef.load(Path(__file__).parents[3] / "samples" / "printable_enclosure.fdprt")
    part = body(rebuild(doc), "f16")
    lid = part.face("f6/cap/end")
    assert lid is not None
    refs = {"hook": {"feature": "f15"}, "body": [reference_for(part, lid)]}
    doc.features.append(Feature("g1", "snap_groove", "Groove 1", params={}, refs=refs))
    res = rebuild(doc)["g1"]
    assert res.state is FeatureState.ERROR
    assert "holds the snap hook" in res.issues[0].message
