"""Several planes or points in one command (TR148, D1925)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features.base import FeatureError
from fdcad.core.features.datum_series import series
from fdcad.core.rebuild.runner import rebuild


def _plane(doc: object, distance: float) -> Feature:
    fid = doc.new_feature_id()  # type: ignore[attr-defined]
    return Feature(
        fid,
        "ref_plane",
        "Plane 1",
        params={"method": "offset", "distance": Param(f"{distance:g}", distance)},
        refs={"first": {"feature": "f2"}},
    )


def test_offset_planes_follow_the_first_one() -> None:
    doc = new_document()
    first, extra = series(doc, _plane(doc, 10.0), 3)
    assert [f.name for f in extra] == ["Plane 2", "Plane 3"]
    assert extra[1].params["distance"].expr == '="distance@Plane 1" * 3'  # type: ignore[union-attr]
    doc.features += [first, *extra]
    results = rebuild(doc)
    heights = [results[f.id].plane.origin[2] for f in (first, *extra)]  # type: ignore[union-attr]
    assert heights == pytest.approx([10.0, 20.0, 30.0])
    first.params["distance"] = Param("5", 5.0)
    again = rebuild(doc)
    assert again[extra[1].id].plane.origin[2] == pytest.approx(15.0)  # type: ignore[union-attr]


def test_points_spread_evenly_over_a_curve() -> None:
    doc = new_document()
    point = Feature(
        doc.new_feature_id(),
        "ref_point",
        "Point 1",
        params={"method": "along_curve", "distance": Param("3", 3.0)},
        refs={"first": {"kind": "edge", "name": "edge(a|b)"}},
    )
    first, extra = series(doc, point, 5, "even")
    assert first.params["by_percent"] is True and first.params["percent"].value == 0.0  # type: ignore[union-attr]
    assert [f.params["percent"].value for f in extra] == pytest.approx([25, 50, 75, 100])  # type: ignore[union-attr]


def test_other_methods_and_counts_are_refused() -> None:
    doc = new_document()
    plane = _plane(doc, 10.0)
    with pytest.raises(FeatureError, match="from 2 to 50"):
        series(doc, plane, 1)
    plane.params["method"] = "three_points"
    with pytest.raises(FeatureError, match="offset and angle planes"):
        series(doc, plane, 3)
