"""Lip and Groove extras: rim by edges, jump gaps, follow the wall's draft (TR146 item 2,
D2407)."""

from __future__ import annotations

import math

import pytest
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.lip_groove import inner_wires
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, volume
from tests.core.features.test_lip_groove import SHELLED, add_lg, open_box, ring_area


def _inner_edge_refs(doc, shell: str) -> list[dict]:  # type: ignore[no-untyped-def,type-arg]
    part = body(rebuild(doc), shell)
    rim = next(f for n, f in part.faces if n.endswith("cap/end"))
    out = []
    explorer = TopExp_Explorer(inner_wires(rim)[0], TopAbs_EDGE)
    while explorer.More():
        ref = reference_for(part, explorer.Current())
        explorer.Next()
        if ref is not None:
            out.append(ref)
    return out


def test_the_rim_picked_by_its_inner_edges() -> None:
    doc, shell, _rim = open_box()
    edges = _inner_edge_refs(doc, shell)
    assert edges
    fid = add_lg(doc, lip_width=1.0, lip_height=2.0)
    doc.feature(fid).refs["lip_edges"] = edges[:1]
    b = body(rebuild(doc), fid)
    assert volume(b.shape) == pytest.approx(SHELLED + ring_area(1.0) * 2.0, rel=1e-6)


def test_jump_gaps_leaves_a_plain_rim_alone_and_follow_wall_on_upright_walls() -> None:
    doc, _shell, rim = open_box()
    fid = add_lg(doc, lip_faces=[rim], lip_width=1.0, lip_height=2.0)
    doc.feature(fid).params["jump_gaps"] = Param("3", 3.0)  # no notches: the same lip
    doc.feature(fid).params["follow_wall"] = True  # upright walls: no lean
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.OK, messages(res)
    assert volume(res.body.shape) == pytest.approx(  # type: ignore[union-attr]
        SHELLED + ring_area(1.0) * 2.0, rel=1e-3
    )


def test_a_lip_leans_with_a_drafted_wall() -> None:
    from fdcad.core.features.lip_groove import wall_lean
    from tests.core.features.test_features import plate
    from tests.core.features.test_hole import face_ref
    from tests.core.features.test_shell import add_shell

    doc, ext = plate()
    doc.feature(ext).params["draft_angle"] = Param("5deg", math.radians(5))
    shell = add_shell(doc, 2.0, faces=[face_ref(doc, ext, "cap/end")])
    rim_ref = face_ref(doc, ext, "cap/end")
    res = rebuild(doc)
    assert res[shell].state is not FeatureState.ERROR, messages(res[shell])
    part = body(res, shell)
    rim = next(f for n, f in part.faces if n.endswith(f"{ext}/cap/end"))
    from fdcad.core.features.lip_groove import _filled

    opening = _filled(inner_wires(rim)[0])
    lean = wall_lean(part.shape, rim, opening, (0.0, 0.0, 1.0))
    assert abs(lean) == pytest.approx(math.radians(5), abs=1e-6)  # the wall's own draft
    fid = add_lg(doc, lip_faces=[rim_ref], lip_width=1.0, lip_height=2.0)
    plain = rebuild(doc)[fid]
    doc.feature(fid).params["follow_wall"] = True
    leaning = rebuild(doc)[fid]
    assert leaning.state is not FeatureState.ERROR, messages(leaning)
    assert volume(leaning.body.shape) != pytest.approx(  # type: ignore[union-attr]
        volume(plain.body.shape),
        rel=1e-6,  # type: ignore[union-attr]
    )


def test_jump_gaps_runs_the_lip_across_a_rib_at_the_rim() -> None:
    from fdcad.core.sketch.model import Sketch
    from tests.core.features.test_features import add_extrude, add_sketch, rect

    doc, shell, rim = open_box()
    s = Sketch()
    rect(s, 1.5, 24.5, 10, 25.5)  # a rib from the wall, its top flush with the rim
    rib = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    part = body(rebuild(doc), rib)
    ribbed = volume(part.shape)
    top = next(f for _n, f in part.faces if inner_wires(f))  # the rim, now with a notch
    rim = reference_for(part, top)
    fid = add_lg(doc, lip_faces=[rim], lip_width=1.0, lip_height=2.0)
    around = rebuild(doc)[fid]
    assert around.state is not FeatureState.ERROR, messages(around)
    doc.feature(fid).params["jump_gaps"] = Param("2", 2.0)
    across = rebuild(doc)[fid]
    assert across.state is not FeatureState.ERROR, messages(across)
    assert volume(across.body.shape) == pytest.approx(  # type: ignore[union-attr]
        ribbed + ring_area(1.0) * 2.0,
        rel=1e-4,  # the closed notch corners round a little
    )
    assert volume(around.body.shape) > volume(across.body.shape)  # type: ignore[union-attr]
    _ = shell
