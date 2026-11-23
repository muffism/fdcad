"""Thin Feature for Revolve and Revolved Cut (TOOL_SPEC T6.1 item 5, DECISIONS D523).

Sketches are on the Front plane and turn about a vertical centerline at x = 0.
"""

import itertools
import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.preview import build_preview
from fdcad.core.io import fdef
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_sketch, body, messages, shaft, volume


def p(v: float) -> Param:
    return Param(f"{v:g}", v)


def thin(**values: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in values.items():
        out[f"thin_{k}"] = p(v) if isinstance(v, float) else v
    return out


def add_revolve(
    doc: Document, sketch: Sketch, axis: str, angle: float = 360.0, **params: Any
) -> str:
    sk = add_sketch(doc, sketch, {"feature": "f2"})
    fid = doc.new_feature_id()
    all_params: dict[str, Any] = {
        "operation": "boss",
        "direction": "one_direction",
        "angle": Param(f"{angle:g}", math.radians(angle)),
    }
    all_params.update(params)
    doc.features.append(
        Feature(
            fid,
            "revolve",
            f"Revolve {fid}",
            params=all_params,
            refs={"sketch": {"feature": sk}, "axis": {"sketch_entity": axis}},
        )
    )
    return fid


def lines(points: list[tuple[float, float]], axis_line: bool = False) -> tuple[Sketch, str]:
    """An open chain through ``points`` and the axis (a centerline, or a plain line)."""
    s = Sketch()
    for a, b in itertools.pairwise(points):
        s.add_line(a[0], a[1], b[0], b[1])
    axis = s.add_line(0, -10, 0, 50, construction=not axis_line)
    return s, axis


def ok(doc: Document, fid: str) -> float:
    results = rebuild(doc)
    res = results[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    return volume(body(results, fid).shape)


def test_thin_tube_from_a_line_mid_plane() -> None:
    doc = new_document()
    s, axis = lines([(10, 0), (10, 40)])
    fid = add_revolve(doc, s, axis, **thin(type="mid_plane", thickness=2.0))
    assert ok(doc, fid) == pytest.approx(math.pi * (11**2 - 9**2) * 40, rel=1e-6)
    names = {n for n, _f in body(rebuild(doc), fid).faces}
    assert any(n.endswith("/outer") for n in names) and any(n.endswith("/inner") for n in names)
    assert any(n.endswith("/start") for n in names) and any(n.endswith("/end") for n in names)
    assert not any("/face#" in n for n in names)


def test_thin_tube_from_a_closed_profile() -> None:
    doc, rev = shaft(360, **thin(type="one_direction", thickness=1.0))
    # The wall lies inside the 10 by 40 rectangle (D211), one edge on the axis.
    assert ok(doc, rev) == pytest.approx(math.pi * (100 * 40 - (81 - 1) * 38), rel=1e-6)
    names = {n for n, _f in body(rebuild(doc), rev).faces}
    assert not any("/face#" in n for n in names)


def test_cup_from_an_l_shaped_line() -> None:
    inside = math.pi * (81 * 1 + (100 - 81) * 20)
    outside = math.pi * (121 * 1 + (121 - 100) * 20)
    found = []
    for reverse in (False, True):
        doc = new_document()
        s, axis = lines([(0, 0), (10, 0), (10, 20)])
        values = thin(type="one_direction", thickness=1.0)
        if reverse:
            values["thin_reverse"] = True
        fid = add_revolve(doc, s, axis, **values)
        found.append(ok(doc, fid))
    assert sorted(found) == pytest.approx([inside, outside], rel=1e-6)


def test_a_plain_axis_line_is_left_out_of_the_chain() -> None:
    doc = new_document()
    s, axis = lines([(10, 0), (10, 40)], axis_line=True)
    fid = add_revolve(doc, s, axis, **thin(type="mid_plane", thickness=2.0))
    assert ok(doc, fid) == pytest.approx(math.pi * (11**2 - 9**2) * 40, rel=1e-6)


def test_open_profile_needs_thin_feature() -> None:
    doc = new_document()
    s, axis = lines([(0, 0), (10, 0), (10, 20)])
    fid = add_revolve(doc, s, axis)
    assert rebuild(doc)[fid].state is FeatureState.ERROR


def test_wall_across_the_axis_is_an_error() -> None:
    doc = new_document()
    s, axis = lines([(0.5, 0), (0.5, 40)])
    fid = add_revolve(doc, s, axis, **thin(type="mid_plane", thickness=2.0))
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "the thin wall crosses the axis" in messages(res)


def test_angles_and_two_directions() -> None:
    doc = new_document()
    s, axis = lines([(10, 0), (10, 40)])
    fid = add_revolve(
        doc,
        s,
        axis,
        90.0,
        direction="two_directions",
        angle2=Param("30", math.radians(30)),
        **thin(type="mid_plane", thickness=2.0),
    )
    assert ok(doc, fid) == pytest.approx(math.pi * 40 * 40 * 120 / 360, rel=1e-6)


def test_revolved_cut_thin() -> None:
    doc, _rev = shaft(360)
    s, axis = lines([(5, 10), (5, 30)])
    cut = add_revolve(doc, s, axis, operation="cut", **thin(type="mid_plane", thickness=2.0))
    assert ok(doc, cut) == pytest.approx(math.pi * (100 * 40 - (36 - 16) * 20), rel=1e-6)


def test_cap_ends_close_a_part_turn() -> None:
    from OCP.BRepCheck import BRepCheck_Analyzer

    walls = {}
    for cap in (False, True):
        values = thin(type="one_direction", thickness=1.0)
        if cap:
            values.update(thin(cap=True, cap_thickness=1.0))
        doc, rev = shaft(90, **values)
        walls[cap] = ok(doc, rev)
        if cap:
            b = body(rebuild(doc), rev)
            assert BRepCheck_Analyzer(b.shape).IsValid()
            names = {n for n, _f in b.faces}
            assert f"{rev}/thin_cap/start" in names and f"{rev}/thin_cap/end" in names
    solid = math.pi * 100 * 40 / 4
    # Each lid adds at most a 1 mm slab across the hollow (radius below 9, 38 tall).
    assert walls[False] + 2 * 38 * 7 < walls[True] < walls[False] + 2 * 9 * 38 * 1.0
    assert walls[True] < solid


@pytest.mark.parametrize(
    "params",
    [
        {"angle": Param("360", 2 * math.pi)},
        {"end_condition": "through_all"},
    ],
)
def test_cap_ends_need_a_part_turn(params: dict[str, Any]) -> None:
    doc, rev = shaft(90, **thin(type="one_direction", thickness=1.0, cap=True, cap_thickness=1.0))
    doc.feature(rev).params.update(params)
    res = rebuild(doc)[rev]
    assert res.state is FeatureState.ERROR and "Cap ends needs" in messages(res)


def test_round_trip_and_preview() -> None:
    doc, rev = shaft(120, **thin(type="one_direction", thickness=1.0, cap=True, cap_thickness=1.5))
    text = fdef.dumps(doc)
    again = fdef.loads(text)
    assert fdef.dumps(again) == text
    assert ok(again, rev) == pytest.approx(ok(doc, rev), rel=1e-9)
    geometry = build_preview(doc, doc.feature(rev), rebuild(doc))
    assert geometry.error is None and geometry.shape is not None
    plain, _prev = shaft(90)
    assert "thin" not in fdef.dumps(plain)
