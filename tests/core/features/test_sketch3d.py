"""3D sketch: plane sketch parts and free 3D lines (TR7, D1719)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.curves import edges_in
from fdcad.core.features.sketch3d import length_of
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Sketch, sketch_to_data


def _plane(doc: object, name: str) -> dict[str, str]:
    return {"feature": next(f.id for f in doc.features if f.name == name)}  # type: ignore[attr-defined]


def test_two_plane_parts_and_a_free_line_make_one_path() -> None:
    doc = new_document()
    front = Sketch()
    front.add_line(0.0, 0.0, 20.0, 0.0)  # along X on Front (z = 0)
    right = Sketch()
    # Right plane: its sketch X runs along -Z, Y along Y.
    right.add_line(0.0, 0.0, -30.0, 0.0)
    feature = Feature(
        doc.new_feature_id(),
        "sketch3d",
        "3D Sketch 1",
        data={
            "parts": [
                {"plane": _plane(doc, "Front Plane"), "sketch": sketch_to_data(front)},
                {"plane": _plane(doc, "Right Plane"), "sketch": sketch_to_data(right)},
            ],
            "lines": [{"kind": "line", "points": [[20.0, 0.0, 0.0], [20.0, 10.0, 5.0]]}],
        },
    )
    doc.features.append(feature)
    report = RebuildEngine().rebuild(doc)
    result = report.results[feature.id]
    assert result.state is not FeatureState.ERROR, result.issues
    curve = result.extras["curve"]
    assert len(edges_in(curve)) == 3
    assert length_of(curve) == pytest.approx(20.0 + 30.0 + (100 + 25) ** 0.5)
    assert "3 curves" in result.extras["report"][0]


def test_free_spline_and_errors() -> None:
    doc = new_document()
    spline = Feature(
        doc.new_feature_id(),
        "sketch3d",
        "3D Sketch 1",
        data={"lines": [{"kind": "spline", "points": [[0, 0, 0], [10, 5, 5], [20, 0, 10]]}]},
    )
    empty = Feature(doc.new_feature_id(), "sketch3d", "3D Sketch 2", data={})
    short = Feature(
        doc.new_feature_id(), "sketch3d", "3D Sketch 3", data={"lines": [{"points": [[0, 0, 0]]}]}
    )
    doc.features += [spline, empty, short]
    report = RebuildEngine().rebuild(doc)
    assert report.results[spline.id].state is not FeatureState.ERROR
    assert len(edges_in(report.results[spline.id].extras["curve"])) == 1
    assert "has no curves" in _messages(report.results[empty.id])
    assert "at least two points" in _messages(report.results[short.id])


def _messages(result: object) -> str:
    return " ".join(i.message for i in result.issues)  # type: ignore[attr-defined]
