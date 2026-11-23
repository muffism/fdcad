"""Rounds that run past the end of their edge, which the kernel cannot build (D1041).

The owner's part of 2026-11-11: a 50 by 50 by 10 block, its top edges rounded 2 mm,
its bottom face chamfered 1 mm, then a side edge rounded 2 mm. The kernel refuses the
last round at any radius from about 1.96 mm up.
"""

import math
from typing import Any

import pytest
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.GeomAbs import GeomAbs_Sphere
from OCP.gp import gp_Pnt, gp_Vec

from fdcad.core.document.model import Document, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.fillet import Item, round_edges
from fdcad.core.features.fillet_overflow import cutter, end_is_free
from fdcad.core.features.modify import edges_of
from fdcad.core.features.solids import line_ends
from fdcad.core.naming.names import NamedShape
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_chamfer import add_chamfer
from tests.core.features.test_features import add_extrude, add_sketch, body, plate, rect, volume
from tests.core.features.test_fillet import add_fillet, strip


def ball_gap(r: float) -> float:
    """Material a ball corner removes from the crease two rounds of radius r leave:
    an eighth of the solid two crossing cylinders share, less an eighth of a ball."""
    return r**3 * (2 / 3 - math.pi / 6)


def side_edges(b: NamedShape) -> list[Any]:
    """The straight edges of ``b`` that run along the plate's depth (Z)."""
    found = []
    for edge in edges_of(b.shape):
        ends = line_ends(edge)
        if ends is None:
            continue
        (x0, y0, z0), (x1, y1, z1) = ends
        if abs(x0 - x1) < 1e-9 and abs(y0 - y1) < 1e-9 and abs(z0 - z1) > 1e-6:
            found.append(edge)
    return found


def _rounded_top(radius: float = 2.0, chamfer: float = 0.0) -> tuple[Document, NamedShape]:
    """The plate with its top face's edges rounded and, if asked, its bottom chamfered."""
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    last = add_fillet(doc, radius, faces=[reference_for(b, b.face(f"{ext}/cap/end"))])
    if chamfer:
        params = {"chamfer_type": "distance_distance", "distance": Param(str(chamfer), chamfer)}
        last = add_chamfer(doc, params, faces=[reference_for(b, b.face(f"{ext}/cap/start"))])
    return doc, body(rebuild(doc), last)


def _round_a_side_edge(doc: Document, b: NamedShape, radius: float) -> tuple[str, dict[str, Any]]:
    ref = reference_for(b, side_edges(b)[0])
    assert ref is not None
    return add_fillet(doc, radius, edges=[ref]), ref


def _balls(b: NamedShape, fid: str) -> list[str]:
    """Names of the ball faces a fillet made."""
    return [
        name
        for name, face in b.faces
        if name.startswith(f"{fid}/") and BRepAdaptor_Surface(face).GetType() == GeomAbs_Sphere
    ]


def test_the_kernel_cannot_round_this_edge() -> None:
    """The case this module exists for: without it the round is an error."""
    _doc, b = _rounded_top()
    edge = side_edges(b)[0]
    assert round_edges("f99", b, [Item("e", edge, 1)], lambda _i: [(0.0, 2.0), (1.0, 2.0)]) is None


def test_side_edge_with_the_radius_of_the_top_rounds_gets_a_ball_corner() -> None:
    doc, b = _rounded_top()
    before = volume(b.shape)
    fid, ref = _round_a_side_edge(doc, b, 2.0)
    results = rebuild(doc)
    assert results[fid].state is FeatureState.OK, [i.message for i in results[fid].issues]
    done = body(results, fid)
    assert BRepCheck_Analyzer(done.shape, True, True).IsValid()
    # The cylinder along the 8 mm that is left of the edge, and the ball above it.
    assert before - volume(done.shape) == pytest.approx(strip(2) * 8 + ball_gap(2), abs=1e-6)
    assert done.face(f"{fid}/fillet/{ref['name']}") is not None
    assert len(_balls(done, fid)) == 1
    assert _balls(done, fid)[0].startswith(f"{fid}/fillet/{ref['name']}/corner_")


def test_the_owners_part_top_rounds_then_bottom_chamfer_then_a_side_edge() -> None:
    doc, b = _rounded_top(chamfer=1.0)
    before = volume(b.shape)
    fid, _ref = _round_a_side_edge(doc, b, 2.0)
    results = rebuild(doc)
    assert results[fid].state is FeatureState.OK, [i.message for i in results[fid].issues]
    done = body(results, fid)
    assert BRepCheck_Analyzer(done.shape, True, True).IsValid()
    # Measured on the owner's part: 7 mm of cylinder, the ball, and the run through
    # the chamfer, which is cut straight as the kernel cuts it.
    assert before - volume(done.shape) == pytest.approx(7.3081, abs=1e-3)
    assert len(_balls(done, fid)) == 1


def test_a_radius_unlike_the_top_rounds_runs_straight_through() -> None:
    """Top rounds of 1 mm, a side edge of 2 mm: no ball fits, so the cylinder is cut
    through to the top face. The result is a valid solid."""
    doc, b = _rounded_top(radius=1.0)
    edge = side_edges(b)[0]
    made = cutter(b, edge, 2.0, "f99/fillet/e")
    assert made is not None
    tools, names = made
    assert len(tools) == 1 and [n for n, _f in names] == ["f99/fillet/e"]
    before = volume(b.shape)
    fid, _ref = _round_a_side_edge(doc, b, 2.0)
    results = rebuild(doc)
    assert results[fid].state is FeatureState.OK, [i.message for i in results[fid].issues]
    done = body(results, fid)
    assert BRepCheck_Analyzer(done.shape, True, True).IsValid()
    assert not _balls(done, fid)
    removed = before - volume(done.shape)
    assert strip(2) * 9 < removed < strip(2) * 10  # the whole height, less what the top rounds took


def test_a_radius_wider_than_the_face_is_still_an_error() -> None:
    """The round would leave its faces: nothing is cut, and the message is the old one."""
    doc, b = _rounded_top()
    edge = side_edges(b)[0]
    assert cutter(b, edge, 60.0, "f99/fillet/e") is None
    fid, _ref = _round_a_side_edge(doc, b, 60.0)
    result = rebuild(doc)[fid]
    assert result.state is FeatureState.ERROR
    assert "failed" in result.issues[0].message


def test_an_end_against_a_wall_is_closed_and_an_end_at_a_cap_is_free() -> None:
    doc, ext = plate()
    s = Sketch()
    rect(s, 10, 10, 30, 30)
    sk = add_sketch(doc, s, {"kind": "face", "name": f"{ext}/cap/end"})
    boss = add_extrude(doc, sk, 6.0)
    b = body(rebuild(doc), boss)
    # An upright edge of the boss: from the plate's top (z = 10) to the boss's top (z = 16).
    edge = next(
        e for e in side_edges(b) if {round(p[2], 6) for p in line_ends(e) or ()} == {10.0, 16.0}
    )
    ends = line_ends(edge)
    assert ends is not None
    low, high = sorted(ends, key=lambda p: p[2])
    up = gp_Vec(0, 0, 1)
    assert not end_is_free(b.shape, edge, gp_Pnt(*low), up.Reversed())  # the plate goes on
    assert end_is_free(b.shape, edge, gp_Pnt(*high), up)  # the boss ends
