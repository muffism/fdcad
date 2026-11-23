"""Revolve about a straight model edge (W6.3) and revolve drag handles (W6.4)."""

import copy
import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState, PreviewHandle
from fdcad.core.features.preview import build_preview
from fdcad.core.features.solids import line_ends
from fdcad.core.io import fdef
from fdcad.core.naming.select import reference_for
from fdcad.core.occ import ShapeMap
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import (
    add_sketch,
    body,
    bounds,
    messages,
    plate,
    rect,
    shaft,
    volume,
)


def _edge_ref(doc: Document, fid: str, a: tuple[float, ...], b: tuple[float, ...]) -> Any:
    """The stored reference of the straight edge of ``fid``'s body from ``a`` to ``b``."""
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp

    named = body(rebuild(doc), fid)
    emap = ShapeMap()
    TopExp.MapShapes_s(named.shape, TopAbs_EDGE, emap)
    for i in range(1, emap.Extent() + 1):
        edge = emap.FindKey(i)
        ends = line_ends(edge)
        if ends is None:
            continue
        if {tuple(round(v, 6) for v in p) for p in ends} == {a, b}:
            ref = reference_for(named, edge)
            assert ref is not None
            return ref
    raise AssertionError("edge not found")


def ring(angle_deg: float = 360.0, **params: Any) -> tuple[Document, str, str]:
    """Plate 50 x 50 x 10, plus a 10 x 20 profile on Front revolved about the plate's x = 50 edge.

    Returns the document, the plate extrude id and the revolve id.
    """
    doc, ext = plate(10.0)
    ref = _edge_ref(doc, ext, (50.0, 0.0, 0.0), (50.0, 50.0, 0.0))
    s = Sketch()
    rect(s, 60, 0, 70, 20)
    sk = add_sketch(doc, s, {"feature": "f2"})
    fid = doc.new_feature_id()
    all_params: dict[str, Any] = {
        "operation": "boss",
        "direction": "one_direction",
        "angle": Param(str(angle_deg), math.radians(angle_deg)),
        "merge": False,
    }
    all_params.update(params)
    doc.features.append(
        Feature(
            fid,
            "revolve",
            "Revolve 1",
            params=all_params,
            refs={"sketch": {"feature": sk}, "axis": ref},
        )
    )
    return doc, ext, fid


def _tool_volume(doc: Document, fid: str) -> float:
    results = rebuild(doc)
    assert results[fid].state is not FeatureState.ERROR, messages(results[fid])
    geo = build_preview(doc, doc.feature(fid), results)
    assert geo.shape is not None, geo.error
    return volume(geo.shape)


def test_revolve_about_a_model_edge() -> None:
    doc, _ext, rev = ring()
    assert doc.feature(rev).refs["axis"]["kind"] == "edge"
    assert _tool_volume(doc, rev) == pytest.approx(math.pi * (400 - 100) * 20, rel=1e-6)
    assert rebuild(doc)[rev].state is FeatureState.OK


def test_edge_axis_follows_the_part_when_it_changes() -> None:
    doc, ext, rev = ring()
    sketch = doc.features[4]
    for ent in sketch.data["entities"]:
        if ent["type"] == "point" and ent["x"] == 50:
            ent["x"] = 55.0  # the plate gets wider; its right edge moves to x = 55
    doc.feature(ext).params["depth"] = Param("20", 20.0)
    res = rebuild(doc)[rev]
    assert res.state is FeatureState.OK, messages(res)  # found by name, no warning
    assert _tool_volume(doc, rev) == pytest.approx(math.pi * (225 - 25) * 20, rel=1e-6)


def test_edge_axis_falls_back_to_its_snapshot_with_a_warning() -> None:
    doc, _ext, rev = ring()
    doc.feature(rev).refs["axis"]["name"] = "edge(f99/cap/start|f99/side/e1)"
    res = rebuild(doc)[rev]
    assert res.state is FeatureState.WARNING
    assert "found by its position" in messages(res)


def test_missing_edge_axis_is_an_error() -> None:
    doc, _ext, rev = ring()
    ref = doc.feature(rev).refs["axis"]
    ref["name"] = "edge(f99/cap/start|f99/side/e1)"
    ref["snapshot"]["midpoint"] = [500.0, 0.0, 0.0]
    res = rebuild(doc)[rev]
    assert res.state is FeatureState.ERROR
    assert "missing reference" in messages(res)


def test_snapshot_direction_sets_the_turn_direction() -> None:
    doc, _ext, rev = ring(90.0)
    first = bounds(rebuild(doc)[rev].body.shape)  # type: ignore[union-attr]
    flipped = copy.deepcopy(doc)
    snap = flipped.feature(rev).refs["axis"]["snapshot"]
    snap["direction"] = [-v for v in snap["direction"]]
    second = bounds(rebuild(flipped)[rev].body.shape)  # type: ignore[union-attr]
    assert first != second  # the quarter turn went the other way round


def test_edge_off_the_sketch_plane_is_rejected() -> None:
    doc, ext, rev = ring()
    doc.feature(rev).refs["axis"] = _edge_ref(doc, ext, (50.0, 0.0, 10.0), (50.0, 50.0, 10.0))
    res = rebuild(doc)[rev]
    assert res.state is FeatureState.ERROR
    assert "not in the sketch plane" in messages(res)


def test_edge_axis_is_saved_and_reopened(tmp_path: Any) -> None:
    doc, _ext, rev = ring()
    path = tmp_path / "ring.fdef"
    fdef.save(doc, path)
    again = fdef.load(path)
    assert again.feature(rev).refs["axis"] == doc.feature(rev).refs["axis"]
    assert _tool_volume(again, rev) == pytest.approx(math.pi * 300 * 20, rel=1e-6)


# Drag handles -------------------------------------------------------------------------


def test_angle_handle_turns_about_its_axis() -> None:
    h = PreviewHandle("angle", (10, 0, 0), (0, 1, 0), math.pi / 2, 1.0, (0, 0, 0))
    assert h.is_angle and h.radius == pytest.approx(10.0)
    # Right hand rule about +Y takes +X to -Z.
    assert h.tip == pytest.approx((0.0, 0.0, -10.0), abs=1e-9)
    assert h.pointing == pytest.approx((-1.0, 0.0, 0.0), abs=1e-9)
    assert h.beyond(math.pi / 2, 10 * math.pi / 2) == pytest.approx((-10, 0, 0), abs=1e-9)
    mid = PreviewHandle("angle", (10, 5, 0), (0, 1, 0), math.pi, 2.0, (0, 0, 0))
    assert mid.tip == pytest.approx((0.0, 5.0, -10.0), abs=1e-9)
    assert mid.value_at(0.5) == pytest.approx(1.0)
    line = PreviewHandle("depth", (0, 0, 0), (0, 0, 2), 4.0)
    assert not line.is_angle and line.pointing == (0.0, 0.0, 1.0)


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({}, [("angle", 1.0)]),
        ({"direction": "mid_plane"}, [("angle", 2.0)]),
        (
            {"direction": "two_directions", "angle2": Param("30", math.radians(30))},
            [("angle", 1.0), ("angle2", 1.0)],
        ),
    ],
)
def test_revolve_preview_handles(params: dict[str, Any], expected: list[Any]) -> None:
    doc, rev = shaft(90, **params)
    results = rebuild(doc)
    geo = build_preview(doc, doc.feature(rev), results)
    assert geo.error is None
    assert [(h.param, h.scale) for h in geo.handles] == expected
    first = geo.handles[0]
    assert first.is_angle and first.radius == pytest.approx(5.0)  # profile centre at x = 5
    # The arrow sits at the end of the revolve: on the profile centre's circle.
    tip = first.tip
    assert math.hypot(tip[0], tip[2]) == pytest.approx(5.0)
    assert tip[1] == pytest.approx(20.0)
    if len(geo.handles) == 2:
        back = geo.handles[1]
        assert back.direction == pytest.approx(tuple(-v for v in first.direction))


def test_revolve_about_an_origin_axis() -> None:
    """Spec 2 section 20 item 3 (D712): an origin axis could not be the revolve axis."""
    from fdcad.core.document.model import new_document
    from tests.core.features.test_features import add_sketch, rect, volume

    doc = new_document()
    s = Sketch()
    rect(s, 10, 0, 20, 10)
    sk = add_sketch(doc, s, {"feature": "f2"})  # Front plane: the origin's Y axis lies in it
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "revolve",
            "Ring",
            params={"operation": "boss", "angle": Param("360", 2 * math.pi)},
            refs={"sketch": {"feature": sk}, "axis": {"feature": "f1", "axis": "y"}},
        )
    )
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, [i.message for i in res.issues]
    assert res.body is not None
    assert volume(res.body.shape) == pytest.approx(math.pi * (20**2 - 10**2) * 10, rel=1e-6)
