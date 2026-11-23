"""Arc length sketch dimension (TOOL_SPEC T4.1, DECISIONS D515)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.equations.engine import cells
from fdcad.core.io.fdef import dumps, loads
from fdcad.core.sketch.model import Arc, Sketch, sketch_from_data, sketch_to_data
from fdcad.core.sketch.solver import SketchStatus, arc_length, measure, solve


def _arc(construction: bool = False) -> tuple[Sketch, str]:
    sk = Sketch()
    aid = sk.add_arc(0, 0, 10, 0, math.pi, construction)
    arc = sk.entities[aid]
    assert isinstance(arc, Arc)
    sk.relate("fixed", arc.center, arc.start)
    sk.dimension("radius", [aid], Param("10", 10.0))
    return sk, aid


def test_measure_follows_the_sweep_and_direction() -> None:
    sk, aid = _arc()
    assert arc_length(sk, aid) == pytest.approx(10 * math.pi)
    arc = sk.entities[aid]
    assert isinstance(arc, Arc)
    arc.ccw = False  # the other way round: the remaining half turn
    assert arc_length(sk, aid) == pytest.approx(10 * math.pi)
    end = sk.point(arc.end)
    end.x, end.y = 0.0, 10.0
    assert arc_length(sk, aid) == pytest.approx(10 * 1.5 * math.pi)


@pytest.mark.parametrize("construction", [False, True])
def test_driving_arc_length_sets_the_sweep(construction: bool) -> None:
    sk, aid = _arc(construction)
    dim = sk.dimension("arc_length", [aid], Param("5*pi", 5 * math.pi))
    result = solve(sk)
    assert result.status is SketchStatus.FULL
    arc = sk.entities[aid]
    assert isinstance(arc, Arc)
    assert sk.xy(arc.end) == pytest.approx((0.0, 10.0), abs=1e-6)
    assert measure(sk, dim) == pytest.approx(5 * math.pi)


def test_reference_arc_length_only_measures() -> None:
    sk, aid = _arc()
    dim = sk.dimension("arc_length", [aid], Param("1", 1.0), driving=False)
    result = solve(sk)
    assert result.status is SketchStatus.UNDER
    assert measure(sk, dim) == pytest.approx(10 * math.pi)


def test_arc_length_on_a_fully_defined_arc_over_defines() -> None:
    sk, aid = _arc()
    arc = sk.entities[aid]
    assert isinstance(arc, Arc)
    sk.relate("fixed", arc.end)
    sk.dimension("arc_length", [aid], Param("31.4159", 31.4159))
    assert solve(sk).status is SketchStatus.OVER


def test_file_round_trip_and_equations_name() -> None:
    sk, aid = _arc()
    sk.dimension("arc_length", [aid], Param("12", 12.0))
    data = sketch_to_data(sk)
    again = sketch_from_data(data)
    dim = again.dimensions[-1]
    assert (dim.type, dim.entities) == ("arc_length", [aid])
    doc = new_document()
    doc.features.append(
        Feature(  # a real id: opening raises a next id below the ids used (D723)
            doc.new_feature_id(), "sketch", "Sketch 1", refs={"plane": {"feature": "f2"}}, data=data
        )
    )
    text = dumps(doc)
    assert '"arc_length"' in text
    assert dumps(loads(text)) == text
    names = [c.name for c in cells(loads(text))]
    assert f"{dim.id}@Sketch 1" in names


def test_an_unknown_dimension_type_is_kept() -> None:
    """How an older FDCAD treats a type it does not know (FDEF_SPEC 6 item 5)."""
    sk, aid = _arc()
    data = sketch_to_data(sk)
    data["dimensions"].append(
        {
            "id": "d9",
            "type": "future_kind",
            "entities": [aid],
            "driving": True,
            "param": {"expr": "1", "value": 1.0},
        }
    )
    again = sketch_from_data(data)
    assert sketch_to_data(again)["dimensions"][-1]["type"] == "future_kind"
