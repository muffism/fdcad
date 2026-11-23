"""A graph never drives a value the part file cannot keep (D2671).

Arithmetic of two large numbers gave inf, and inf minus inf gave nan, with no error;
Set Feature Parameter then put it into the feature and the rebuild raised.
"""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.graph.geometry import volume
from fdcad.core.graph.nodes.base import NodeError
from fdcad.core.rebuild.engine import RebuildEngine
from tests.core.graph.helpers import graph, p
from tests.core.graph.test_nodes import run
from tests.core.graph.test_rebuild import _plate


@pytest.mark.parametrize(
    ("a", "b", "operation"),
    [(1e200, 1e200, "multiply"), (math.inf, -math.inf, "add"), (1e308, 1e308, "add")],
)
def test_arithmetic_that_leaves_the_numbers_is_a_node_error(
    a: float, b: float, operation: str
) -> None:
    with pytest.raises(NodeError, match="too large or not a number"):
        run("arithmetic", {"a": a, "b": b}, {"operation": operation})


@pytest.mark.parametrize("ntype", ["set_param", "set_variable"])
@pytest.mark.parametrize("value", [math.nan, math.inf])
def test_an_output_refuses_a_value_that_is_not_a_finite_number(ntype: str, value: float) -> None:
    params = {"feature": "f6", "param": "depth", "variable": "W"}
    with pytest.raises(NodeError, match="too large or not a number"):
        run(ntype, {"value": value}, params)


def test_the_feature_keeps_its_typed_value_and_the_graph_says_why() -> None:
    doc = new_document()
    _sid, plate = _plate(doc)
    g = graph(
        ("n1", "value", {"kind": "number", "value": p(1e200)}),
        ("n2", "arithmetic", {"operation": "multiply"}),
        ("n3", "set_param", {"feature": plate, "param": "depth"}),
        wires=("n1.out>n2.a", "n1.out>n2.b", "n2.out>n3.value"),
    )
    g.position = "f4"
    doc.graphs.append(g)
    report = RebuildEngine().rebuild(doc)
    assert report.results[plate].state is FeatureState.OK
    assert abs(volume(report.body.shape) - 40 * 30 * 10) < 1e-6  # type: ignore[union-attr]
    found = report.graphs["g1"].first_error("n3")
    assert found is not None and found[0] == "n2", found
