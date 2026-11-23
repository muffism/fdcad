"""How neighbours follow a moved face: Extend, Tip and Lift (TR264, D797)."""

from __future__ import annotations

import pytest

from fdcad.core.features.base import FeatureState
from fdcad.core.features.move_follow import follow_order
from fdcad.core.naming.names import centroid
from tests.core.features.phase3_parts import length, messages, ok_body, volume_of
from tests.core.features.test_direct_editing import BASE, at, built, move


def _boss_top(body):  # type: ignore[no-untyped-def]
    (top,) = at(body, z=16)
    return top


def test_tip_slides_the_boss_top_and_tilts_its_sides() -> None:
    doc, ids, body = built()
    fid, results = move(
        doc,
        body,
        [_boss_top(body)],
        mode="translate",
        translate_by="delta",
        dx=length(3),
        dy=length(0),
        dz=length(0),
        follow="tip",
    )
    out = ok_body(results, fid)
    assert results[fid].state is FeatureState.OK, messages(results[fid])
    assert volume_of(out.shape) == pytest.approx(BASE, rel=1e-7)  # a shear keeps volume
    top = out.face(f"{ids['boss']}/cap/end")
    assert top is not None and centroid(top)[0] == pytest.approx(18)
    # The sides now lean: the boss's +x side is no longer square to the block.
    leaning = [f for f in at(out, z=13) if abs(centroid(f)[0] - 21.5) < 1e-6]
    assert len(leaning) == 1


def test_extend_ignores_a_slide_along_the_face() -> None:
    doc, _ids, body = built()
    fid, results = move(
        doc,
        body,
        [_boss_top(body)],
        mode="translate",
        translate_by="delta",
        dx=length(3),
        dy=length(0),
        dz=length(0),
    )
    out = ok_body(results, fid)
    assert volume_of(out.shape) == pytest.approx(BASE, rel=1e-7)
    assert len(at(out, x=15, z=16)) == 1  # the top stayed where it was


def test_lift_adds_new_side_faces() -> None:
    doc, _ids, body = built()
    fid, results = move(doc, body, [_boss_top(body)], mode="offset", distance=length(4),
                        follow="lift")  # fmt: skip
    out = ok_body(results, fid)
    assert results[fid].state is FeatureState.OK, messages(results[fid])
    assert volume_of(out.shape) == pytest.approx(BASE + 400, rel=1e-7)
    assert any(n.startswith(f"{fid}/lift/1/") for n, _f in out.faces)
    assert len(at(out, x=15, y=20, z=20)) == 1


def test_lift_inward_cuts() -> None:
    doc, _ids, body = built()
    fid, results = move(doc, body, [_boss_top(body)], mode="offset", distance=length(2),
                        reverse=True, follow="lift")  # fmt: skip
    out = ok_body(results, fid)
    assert volume_of(out.shape) == pytest.approx(BASE - 200, rel=1e-7)


def test_a_failing_way_falls_back_with_a_warning_unless_kept() -> None:
    """Tip cannot tilt the round hole wall around the block's top, so Extend is used."""
    doc, _ids, body = built()
    (top,) = at(body, z=10)
    fid, results = move(doc, body, [top], mode="offset", distance=length(1), follow="tip")
    res = results[fid]
    assert res.state is FeatureState.WARNING
    assert "Tip did not work" in messages(res) and "Used Extend" in messages(res)
    assert volume_of(ok_body(results, fid).shape) > BASE
    doc, _ids, body = built()
    (top,) = at(body, z=10)
    fid, results = move(
        doc, body, [top], mode="offset", distance=length(1), follow="tip", keep_solution=True
    )
    assert results[fid].state is FeatureState.ERROR
    assert "curved" in messages(results[fid])


def test_lift_refuses_a_rotation() -> None:
    from tests.core.features.phase3_parts import angle

    doc, _ids, body = built()
    (end,) = at(body, x=60)
    fid, results = move(
        doc,
        body,
        [end],
        mode="rotate",
        rotate_by="origin",
        rx=angle(0),
        ry=angle(5),
        rz=angle(0),
        ox=length(60),
        oy=length(0),
        oz=length(0),
        follow="lift",
        keep_solution=True,
    )
    assert "Lift works with Translate and Offset only" in messages(results[fid])


def test_order_of_solutions() -> None:
    assert follow_order("tip") == ["tip", "extend", "lift"]
    assert follow_order("nonsense") == ["extend", "tip", "lift"]


def test_rounds_made_again_after_the_move() -> None:
    from fdcad.core.document.model import Feature, Param
    from fdcad.core.naming.select import reference_for
    from fdcad.core.rebuild.runner import rebuild
    from tests.core.features.test_features import body as ok
    from tests.core.features.test_fillet import _plate_and_refs, add_fillet

    doc, ext, _b, refs = _plate_and_refs(4)
    rounds = add_fillet(doc, 2.0, edges=refs)
    rounded = ok(rebuild(doc), rounds)
    taken = 25000 - volume_of(rounded.shape)
    top = rounded.face(f"{ext}/cap/end")
    assert top is not None
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "move_face",
            "Move Face 1",
            params={"mode": "offset", "distance": Param("5", 5.0), "rounds": "remake"},
            refs={"faces": [reference_for(rounded, top)]},
        )
    )
    out = ok(rebuild(doc), fid)
    assert volume_of(out.shape) == pytest.approx(50 * 50 * 15 - taken, rel=1e-6)
    names = {n for n, _f in out.faces}
    assert {n for n, _f in rounded.faces if "/fillet/" in n} <= names
