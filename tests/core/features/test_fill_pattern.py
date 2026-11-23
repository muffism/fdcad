"""Fill Pattern (TR57, D792)."""

from __future__ import annotations

import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.fill_pattern import layout_points, shape_outline
from tests.core.features.test_features import body, plate, rebuild, volume
from tests.core.features.test_hole import add_hole, on_top


def _fill(doc: Document, ext: str, data: dict[str, Any] | None = None, **params: Any) -> Any:
    fid = doc.new_feature_id()
    values: dict[str, Any] = {"layout": "grid", "spacing": Param("10", 10.0), **params}
    refs = {"face": [{"kind": "face", "name": f"{ext}/cap/end"}], **params.pop("_refs", {})}
    values.pop("_refs", None)
    doc.features.append(
        Feature(fid, "fill_pattern", "Fill Pattern 1", params=values, refs=refs, data=data or {})
    )
    res = rebuild(doc)[fid]
    doc.features.pop()
    return res


def _circles(**params: Any) -> dict[str, Any]:
    return {
        "shape": "circle",
        "size": Param("4", 4.0),
        "depth": Param("3", 3.0),
        **params,
    }


def test_a_grid_of_circles_with_a_margin() -> None:
    doc, ext = plate()
    start = volume(body(rebuild(doc), ext).shape)
    res = _fill(doc, ext, **_circles(margin=Param("2", 2.0)))
    assert res.state is not FeatureState.ERROR, res.issues
    assert res.extras["count"] == 25  # 5 by 5 from the middle, 10 apart
    assert start - volume(res.body.shape) == pytest.approx(25 * math.pi * 4 * 3, rel=1e-4)
    # A wider margin drops the outer ring of copies.
    assert _fill(doc, ext, **_circles(margin=Param("3.5", 3.5))).extras["count"] == 9


def test_skip_and_through_all() -> None:
    doc, ext = plate()
    start = volume(body(rebuild(doc), ext).shape)
    res = _fill(doc, ext, data={"skip": [[1, 1], [2, 1]]}, **_circles(depth=Param("0", 0.0)))
    assert res.extras["count"] == 23
    assert start - volume(res.body.shape) == pytest.approx(23 * math.pi * 4 * 10, rel=1e-4)


def test_staggered_rings_and_shapes() -> None:
    doc, ext = plate()
    staggered = _fill(doc, ext, layout="staggered", **_circles())
    rings = _fill(doc, ext, layout="rings", **_circles())
    squares = _fill(doc, ext, layout="rings", ring_shape="square", **_circles(shape="square"))
    for res in (staggered, rings, squares):
        assert res.state is not FeatureState.ERROR, res.issues
        assert res.extras["count"] > 7
    # Rings: the middle, then 6 copies 10 out.
    pts = layout_points("rings", 10.0, 10.0, 0.0, "circle", 6, 10.0)
    assert pts[0] == (0.0, 0.0) and len(pts) >= 7
    tri = layout_points("staggered", 10.0, 10.0, math.radians(60), "circle", 6, 10.0)
    assert (5.0, pytest.approx(10 * math.sin(math.radians(60)))) in [
        (round(u, 6), v) for u, v in tri
    ]
    assert (
        len(shape_outline("polygon", 4.0, 0.0, 6)) == 6
        and shape_outline("circle", 4.0, 0.0, 6) == []
    )


def test_copy_a_seed_hole() -> None:
    doc, ext, sk, top = on_top([(25, 25)])
    hole = add_hole(doc, sk, face=top, diameter=4.0, depth=3.0)
    start = volume(body(rebuild(doc), hole).shape)
    res = _fill(doc, ext, margin=Param("2", 2.0), _refs={"features": [{"feature": hole}]})
    assert res.state is not FeatureState.ERROR, res.issues
    assert res.extras["count"] == 25
    assert start - volume(res.body.shape) == pytest.approx(24 * math.pi * 4 * 3, rel=1e-4)


def test_errors() -> None:
    doc, ext = plate()
    res = _fill(doc, ext, **_circles(spacing=Param("0", 0.0)))
    assert (
        res.state is FeatureState.ERROR and "spacing must be more than 0" in res.issues[0].message
    )
    res = _fill(doc, ext)
    assert res.state is FeatureState.ERROR and "choose a shape" in res.issues[0].message


def test_count_in_a_formula() -> None:
    """The number of copies can be used in an equation (TR57 item 3)."""
    from fdcad.core.equations import solve

    doc, ext = plate()
    fill = doc.new_feature_id()
    doc.features.append(
        Feature(
            fill,
            "fill_pattern",
            "Fill Pattern 1",
            params={"layout": "grid", "spacing": Param("10", 10.0), **_circles()},
            refs={"face": [{"kind": "face", "name": f"{ext}/cap/end"}]},
        )
    )
    later = doc.new_feature_id()
    doc.features.append(
        Feature(
            later,
            "fill_pattern",
            "Fill Pattern 2",
            params={
                "layout": "grid",
                "spacing": Param('="count@Fill Pattern 1" / 2.5', 0.0),
                **_circles(size=Param("2", 2.0)),
            },
            refs={"face": [{"kind": "face", "name": f"{ext}/cap/end"}]},
        )
    )
    results = rebuild(doc)
    assert results[fill].extras["count"] == 25
    # Measured in the same rebuild, so the feature below already uses it.
    assert doc.features[-1].params["spacing"].value == pytest.approx(10.0)
    assert results[later].state is not FeatureState.ERROR, results[later].issues
    assert solve(doc).namespace["count@Fill Pattern 1"][1] == 25
    assert solve(doc).namespace[f"count@{fill}"][1] == 25


def test_count_used_above_its_pattern_is_an_error() -> None:
    doc, ext = plate()
    fill = doc.new_feature_id()
    doc.features.append(
        Feature(
            fill,
            "fill_pattern",
            "Fill Pattern 1",
            params={"layout": "grid", "spacing": Param("10", 10.0), **_circles()},
            refs={"face": [{"kind": "face", "name": f"{ext}/cap/end"}]},
        )
    )
    name, value = next((k, v) for k, v in doc.feature(ext).params.items() if isinstance(v, Param))
    doc.feature(ext).params[name] = Param('="count@Fill Pattern 1"', value.value)
    results = rebuild(doc)
    assert results[ext].state is FeatureState.ERROR
    assert "measured when Fill Pattern 1 builds" in results[ext].issues[-1].message


def test_fill_a_sketch_region() -> None:
    """A closed sketch region bounds the fill instead of a face (TR57 item 1)."""
    from fdcad.core.sketch.model import Sketch
    from tests.core.features.test_features import add_sketch, rect
    from tests.core.features.test_hole import face_ref

    doc, ext = plate()
    s = Sketch()
    rect(s, 15, 15, 35, 35)
    sk = add_sketch(doc, s, face_ref(doc, ext, "cap/end"))
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "fill_pattern",
            "Fill Pattern 1",
            params={
                "layout": "grid",
                "spacing": Param("5", 5.0),
                **_circles(margin=Param("1", 1.0)),
            },
            refs={"sketch": {"feature": sk}},
        )
    )
    start = volume(body(rebuild(doc), ext).shape)
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, res.issues
    assert res.extras["count"] == 9  # 20 wide, 5 apart from the middle, 3 clear of the edge
    assert start - volume(res.body.shape) == pytest.approx(9 * math.pi * 4 * 3, rel=1e-4)


def test_fit_by_centre_and_a_negative_margin() -> None:
    doc, ext = plate()
    assert _fill(doc, ext, **_circles(margin=Param("4", 4.0))).extras["count"] == 9
    centre = _fill(doc, ext, fit="centre", **_circles(margin=Param("4", 4.0)))
    assert centre.extras["count"] == 25  # copies 5 from the edge now count
    past = _fill(doc, ext, **_circles(margin=Param("-1", -1.0), spacing=Param("12", 12.0)))
    assert past.state is not FeatureState.ERROR, past.issues
    assert (
        past.extras["count"]
        > _fill(doc, ext, **_circles(spacing=Param("12", 12.0))).extras["count"]
    )


def _tube() -> tuple[Document, str]:
    from fdcad.core.document.model import new_document
    from fdcad.core.sketch.model import Sketch
    from tests.core.features.phase3_parts import add_extrude, add_sketch

    doc = new_document()
    s = Sketch()
    s.add_circle(0, 0, 20)
    s.add_circle(0, 0, 15)
    return doc, add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 40.0)


@pytest.mark.parametrize(
    ("face", "mode", "copies"),
    [("e2", "mapped", 33), ("e2", "projected", 9), ("e4", "mapped", 27)],
)
def test_fill_a_cylinder_face(face: str, mode: str, copies: int) -> None:
    """TR398 item 1 (D1903): holes round a tube, spaced along the surface (mapped) or
    as seen from straight on (projected), cut through the wall from outside or inside."""
    from fdcad.core.features.solids import solids

    doc, ext = _tube()
    start = volume(body(rebuild(doc), ext).shape)
    res = _fill(
        doc,
        ext,
        shape="circle",
        size=Param("4", 4.0),
        margin=Param("1", 1.0),
        surface_spacing=mode,
        _refs={"face": [{"kind": "face", "name": f"{ext}/side/{face}"}]},
    )
    assert res.state is not FeatureState.ERROR, [i.message for i in res.issues]
    assert res.extras["count"] == copies
    assert len(solids(res.body.shape)) == 1
    hole = math.pi * 2 * 2 * 5  # a 4 mm hole through the 5 mm wall, about
    assert start - volume(res.body.shape) == pytest.approx(copies * hole, rel=0.05)
