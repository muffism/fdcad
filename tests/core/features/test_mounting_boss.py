"""Mounting boss (PHASE4_SPEC P4.4 item 1): screw and pin types, fins with chamfer and
draft, typed and picked positions, flat and curved faces."""

import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_cosmetic_thread import shaft
from tests.core.features.test_features import body, messages, plate, volume
from tests.core.features.test_hole import face_ref


def p(v: float) -> Param:
    return Param(f"{v:g}", v)


def add_boss(doc: Document, face: dict[str, Any], **values: Any) -> str:
    fid = doc.new_feature_id()
    params: dict[str, Any] = {
        "boss_type": "screw_thread",
        "boss_diameter": p(8.0),
        "boss_height": p(12.0),
        "hole_diameter": p(3.0),
        "hole_depth": p(10.0),
        "fin_count": p(0.0),
        "pos_x": p(25.0),
        "pos_y": p(25.0),
        "pos_z": p(10.0),
    }
    for k, v in values.items():
        if isinstance(v, float) and ("angle" in k or "draft" in k):
            params[k] = Param(f"{math.degrees(v):.12g}", v)
        else:
            params[k] = p(v) if isinstance(v, float) else v
    doc.features.append(
        Feature(fid, "mounting_boss", "Mounting Boss 1", params=params, refs={"face": [face]})
    )
    return fid


def test_screw_thread_boss() -> None:
    doc, ext = plate()
    fid = add_boss(doc, face_ref(doc, ext, "cap/end"))
    b = body(rebuild(doc), fid)
    expect = 25000 + math.pi * 16 * 12 - math.pi * 2.25 * 10
    assert volume(b.shape) == pytest.approx(expect, rel=1e-6)
    names = {n for n, _f in b.faces}
    assert f"{fid}/boss/side" in names and f"{fid}/hole/wall" in names


def test_head_side_boss_and_fins() -> None:
    doc, ext = plate()
    fid = add_boss(
        doc,
        face_ref(doc, ext, "cap/end"),
        boss_type="screw_head",
        head_diameter=6.0,
        head_depth=3.0,
        hole_depth=12.0,
        fin_count=4.0,
        fin_length=4.0,
        fin_width=1.5,
        fin_height=8.0,
    )
    b = body(rebuild(doc), fid)
    a = 0.75
    inside = a * math.sqrt(16 - a * a) + 16 * math.asin(a / 4)
    fins = 4 * 8 * (8 * 1.5 - inside)
    bores = math.pi * (9 * 3 + 2.25 * 9)
    expect = 25000 + math.pi * 16 * 12 + fins - bores
    assert volume(b.shape) == pytest.approx(expect, rel=1e-6)
    feature = doc.feature(fid)
    feature.params["chamfer_distance"] = p(2.0)
    feature.params["chamfer_angle"] = Param("45", math.pi / 4)
    chamfered = volume(body(rebuild(doc), fid).shape)
    assert chamfered == pytest.approx(expect - 4 * 0.5 * 2 * 2 * 1.5, rel=1e-6)
    feature.params["fin_draft"] = Param("2", math.radians(2))
    drafted = volume(body(rebuild(doc), fid).shape)
    assert drafted < chamfered


def test_pin_and_pin_hole() -> None:
    doc, ext = plate()
    top = face_ref(doc, ext, "cap/end")
    fid = add_boss(doc, top, boss_type="pin", pin_diameter=4.0, pin_height=5.0)
    expect = 25000 + math.pi * 16 * 12 + math.pi * 4 * 5
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(expect, rel=1e-6)
    doc.feature(fid).params["boss_type"] = "pin_hole"
    expect = 25000 + math.pi * 16 * 12 - math.pi * 4 * 5
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(expect, rel=1e-6)


def test_boss_with_draft_and_on_a_curved_face() -> None:
    doc, ext, eid = shaft(radius=10.0, length=40.0)
    side = face_ref(doc, ext, f"side/{eid}")
    fid = add_boss(
        doc, side, pos_x=10.0, pos_y=0.0, pos_z=20.0, boss_draft=math.radians(3), boss_height=6.0
    )
    res = rebuild(doc)[fid]
    b = body({fid: res}, fid)
    assert res.state is FeatureState.OK
    assert volume(b.shape) > math.pi * 100 * 40 + math.pi * 16 * 4


def test_boss_checks() -> None:
    doc, ext = plate()
    fid = add_boss(doc, face_ref(doc, ext, "cap/end"), hole_diameter=9.0)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "smaller than the boss" in messages(res)
    doc.feature(fid).params["hole_diameter"] = p(3.0)
    for name in ("pos_x", "pos_y", "pos_z"):
        del doc.feature(fid).params[name]
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "no position" in messages(res)


def test_position_from_a_vertex() -> None:
    from fdcad.core.naming.select import reference_for

    doc, ext = plate()
    b = body(rebuild(doc), ext)
    vertex = next(
        v
        for v in _vertices(b.shape)
        if all(abs(c - t) < 1e-6 for c, t in zip(_pt(v), (50.0, 50.0, 10.0), strict=True))
    )
    ref = reference_for(b, vertex)
    assert ref is not None
    fid = add_boss(doc, face_ref(doc, ext, "cap/end"))
    doc.feature(fid).refs["position"] = [ref]
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)


def _vertices(shape: Any) -> list[Any]:
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer

    out = []
    ex = TopExp_Explorer(shape, TopAbs_VERTEX)
    while ex.More():
        out.append(ex.Current())
        ex.Next()
    return out


def _pt(v: Any) -> tuple[float, float, float]:
    from OCP.BRep import BRep_Tool
    from OCP.TopoDS import TopoDS

    p3 = BRep_Tool.Pnt_s(TopoDS.Vertex(v))
    return (p3.X(), p3.Y(), p3.Z())


def test_fin_count_from_zero_builds_with_default_fin_sizes() -> None:
    """Audit E item 9.1 (D728): it failed "the fin length value is missing"."""
    doc, ext = plate()
    fid = add_boss(doc, face_ref(doc, ext, "cap/end"))
    without = volume(body(rebuild(doc), fid).shape)
    doc.feature(fid).params["fin_count"] = p(1.0)
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None and volume(res.body.shape) > without


@pytest.mark.parametrize("at", [(20.0, 0.0), (0.0, 20.0), (-20.0, 0.0), (0.0, -20.0)])
def test_a_boss_on_a_hollow_tube_does_not_fill_the_tube(at: tuple[float, float]) -> None:
    """D1046: a 40 mm tube with 2 mm walls. Where a point of the boss's outline lay over
    the seam of the tube's face, the near crossing was missed and the far wall was taken
    for the face under the boss: the boss became a column through the inside of the
    tube that came out of the other side."""
    from fdcad.core.document.model import new_document
    from fdcad.core.sketch.model import Sketch
    from tests.core.features.test_features import add_extrude, add_sketch

    doc = new_document()
    outer = Sketch()
    circle = outer.add_circle(0.0, 0.0, 20.0)
    tube = add_extrude(doc, add_sketch(doc, outer, {"feature": "f2"}), 100.0)
    inner = Sketch()
    inner.add_circle(0.0, 0.0, 18.0)
    add_extrude(
        doc, add_sketch(doc, inner, {"feature": "f2"}), 100.0, operation="cut", reverse=False
    )
    before = volume(body(rebuild(doc), doc.features[-1].id).shape)
    assert before == pytest.approx(math.pi * (400 - 324) * 100, rel=1e-6)
    fid = add_boss(
        doc,
        face_ref(doc, tube, f"side/{circle}"),
        boss_diameter=8.0,
        boss_height=6.0,
        hole_diameter=3.0,
        hole_depth=4.0,
        pos_x=at[0],
        pos_y=at[1],
        pos_z=50.0,
    )
    b = body(rebuild(doc), fid)
    added = volume(b.shape) - before
    # The boss, a little root under it where the tube curves away, less its hole.
    plain = math.pi * 16 * 6 - math.pi * 2.25 * 4
    assert plain < added < plain + 30, added


def test_the_root_of_a_boss_never_reaches_the_far_wall(monkeypatch: pytest.MonkeyPatch) -> None:
    """D1046, as found on a lofted down tube: for one point of the boss's outline the
    crossing with the near wall was missed (the point lay over the face's seam), so the
    far wall, 36 mm down, was taken for the face under the boss and the boss was rooted
    that deep: a column through the inside of the tube."""
    from fdcad.core.features import fastening as fx

    doc, ext, _eid = shaft()
    face = next(f for n, f in body(rebuild(doc), ext).faces if "/side/" in n)
    seen: list[object] = []

    def hits(_face: object, start: object, _direction: object) -> list[tuple[float, ...]]:
        seen.append(start)
        if len(seen) == 4:  # the point over the seam: only the far wall is found
            return [(36.0, 0.0, 0.0, 0.0, 0.0)]
        return [(0.6, 0.0, 0.0, 0.0, 0.0), (36.4, 0.0, 0.0, 0.0, 0.0)]

    monkeypatch.setattr(fx, "line_hits", hits)
    ring = [(4 * math.cos(k * math.pi / 8), 4 * math.sin(k * math.pi / 8)) for k in range(16)]
    frame = fx.frame((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), None)
    assert fx.reach_down(face, frame, ring) == pytest.approx(0.6)
    assert len(seen) == 16
