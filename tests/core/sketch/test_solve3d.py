"""Relations and 3D lengths for free 3D lines (TR7, D2206)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sketch3d import length_of
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Sketch, sketch_to_data
from fdcad.core.sketch.solve3d import Solve3DError, solve


def test_along_axes_and_a_length_square_up_a_path() -> None:
    lines = [[(0.0, 0.0, 0.0), (9.0, 1.0, 0.5), (10.0, 6.0, 1.0)]]
    rels = [
        {"type": "fixed", "points": ["1.1"], "at": [0.0, 0.0, 0.0]},
        {"type": "along_x", "points": ["1.1", "1.2"]},
        {"type": "along_y", "points": ["1.2", "1.3"]},
        {"type": "length", "points": ["1.1", "1.2"], "value": 12.0},
        {"type": "length", "points": ["1.2", "1.3"], "value": 5.0},
    ]
    got = solve(lines, rels)
    a, b, c = got.lines[0]
    assert a == pytest.approx((0.0, 0.0, 0.0))
    assert b == pytest.approx((12.0, 0.0, 0.0), abs=1e-7)
    assert c == pytest.approx((12.0, 5.0, 0.0), abs=1e-7)
    assert got.free == 0


def test_coincident_with_a_part_point_and_free_movements() -> None:
    lines = [[(1.0, 1.0, 1.0), (5.0, 5.0, 5.0)]]
    got = solve(lines, [{"type": "coincident", "points": ["1.1", "P1:e2"]}], {"P1:e2": (0, 0, 0)})
    assert got.lines[0][0] == pytest.approx((0.0, 0.0, 0.0))
    assert got.lines[0][1] == pytest.approx((5.0, 5.0, 5.0))  # untouched
    assert got.free == 3


def test_conflicts_and_damaged_relations_say_what_to_do() -> None:
    lines = [[(0.0, 0.0, 0.0), (5.0, 0.0, 0.0)]]
    clash = [
        {"type": "along_x", "points": ["1.1", "1.2"]},
        {"type": "along_y", "points": ["1.1", "1.2"]},
        {"type": "length", "points": ["1.1", "1.2"], "value": 3.0},
    ]
    with pytest.raises(Solve3DError, match="conflict"):
        solve(lines, clash)
    with pytest.raises(Solve3DError, match="does not exist"):
        solve(lines, [{"type": "along_x", "points": ["1.1", "2.1"]}])
    with pytest.raises(Solve3DError, match="above zero"):
        solve(lines, [{"type": "length", "points": ["1.1", "1.2"], "value": 0}])


def test_the_feature_builds_the_solved_path_tied_to_a_plane_sketch() -> None:
    doc = new_document()
    plane = {"feature": next(f.id for f in doc.features if f.name == "Front Plane")}
    front = Sketch()
    front.add_line(0.0, 0.0, 20.0, 0.0)  # points e1 (0, 0) and e2 (20, 0) on Front
    feature = Feature(
        doc.new_feature_id(),
        "sketch3d",
        "3D Sketch 1",
        data={
            "parts": [{"plane": plane, "sketch": sketch_to_data(front)}],
            "lines": [{"kind": "line", "points": [[19.0, 1.0, 0.0], [21.0, 1.0, 8.0]]}],
            "relations": [
                {"type": "coincident", "points": ["1.1", "P1:e2"]},
                {"type": "along_z", "points": ["1.1", "1.2"]},
                {"type": "length", "points": ["1.1", "1.2"], "value": 10.0},
            ],
        },
    )
    doc.features.append(feature)
    report = RebuildEngine().rebuild(doc)
    result = report.results[feature.id]
    assert result.state is not FeatureState.ERROR, result.issues
    assert length_of(result.extras["curve"]) == pytest.approx(30.0, abs=1e-6)
    assert "free movements" in result.extras["report"][1]
    feature.data["relations"].append({"type": "along_x", "points": ["1.1", "1.2"]})
    again = RebuildEngine().rebuild(doc)
    assert again.results[feature.id].state is FeatureState.ERROR
