"""Dimensions to part edges in a sketch on a face (WORKFLOW_SPEC Box test, D113)."""

import pytest

from fdcad.core.sketch.model import Line
from fdcad.ui.sketch_tools.edit import centres_for_distance, smart_dimension
from fdcad.ui.sketch_tools.geometry import straight_polyline
from tests.ui.sketch_tools.test_tools import _edit


def test_straight_polyline() -> None:
    assert straight_polyline([(0, 0), (5, 0), (10, 0)]) == ((0, 0), (10, 0))
    assert straight_polyline([(0, 0), (5, 1), (10, 0)]) is None  # a curve
    assert straight_polyline([(1, 1)]) is None
    assert straight_polyline([(1, 1), (1, 1)]) is None


def test_reference_line_is_fixed_construction_and_reused() -> None:
    edit = _edit()
    first = edit.reference_line((0, 0), (0, 50))
    line = edit.sketch.entities[first]
    assert isinstance(line, Line) and line.construction
    assert any(r.type == "fixed" and r.entities == [first] for r in edit.sketch.relations)
    assert edit.reference_line((0, 50), (0, 0)) == first  # same edge, either way round
    assert edit.reference_line((0, 0), (80, 0)) != first


def test_circle_and_line_measure_from_the_centre() -> None:
    edit = _edit()
    cid = edit.sketch.add_circle(30, 20, 5)
    lid = edit.reference_line((0, 0), (0, 50))
    ids = centres_for_distance(edit.sketch, [cid, lid])
    circle = edit.sketch.entities[cid]
    assert ids == [circle.center, lid]  # type: ignore[attr-defined]
    assert smart_dimension(edit.sketch, ids) == "distance"
    dim = edit.add_dimension("distance", ids, None)
    assert dim.param.value == pytest.approx(30.0)
    assert centres_for_distance(edit.sketch, [cid]) == [cid]  # alone: still a diameter
