"""The edit storm itself: which numbers it edits, and that it puts each one back.

The storm (``edit_storm.py``) first edited only feature values and variables. A user
changes sketch dimensions and node values as often, so it edits those too, and it
can nudge down as well as up (``--down``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fdcad.core.document.model import Param
from fdcad.core.io import fdef
from tests.core.features import edit_storm

SAMPLES = Path(__file__).resolve().parents[3] / "samples"


def _expr(param: object) -> str:
    if isinstance(param, Param):
        return param.expr
    assert isinstance(param, dict)
    return str(param["expr"])


def test_sketch_dimensions_are_edited_and_put_back() -> None:
    doc = fdef.load(SAMPLES / "turned_shaft.fdprt")
    edits = dict(edit_storm._edits(doc))
    assert "Shaft Profile d1" in edits
    sketch = next(f for f in doc.features if f.name == "Shaft Profile")
    dim = sketch.data["dimensions"][0]
    was = _expr(dim["param"])
    edits["Shaft Profile d1"](True)
    assert dim["param"] == Param("121.2", 121.2)
    edits["Shaft Profile d1"](False)
    assert _expr(dim["param"]) == was


def test_node_values_are_edited_and_put_back() -> None:
    doc = fdef.load(SAMPLES / "graphs" / "attractor_plate.fdprt")
    edits = dict(edit_storm._edits(doc))
    node = doc.graphs[0].nodes[2]
    assert node.type == "point_grid"
    edits["Graph 1 n3 point_grid count_x"](True)
    assert node.params["count_x"] == Param("12", 12.0)
    edits["Graph 1 n3 point_grid count_x"](False)
    assert node.params["count_x"] == Param("11", 11.0)


def test_down_takes_one_percent_off_and_one_off_a_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(edit_storm, "DOWN", True)
    text, value = edit_storm._nudged("10.1 mm", 10.1, "depth") or ("", 0.0)
    assert value == pytest.approx(10.0)
    assert text.endswith(" mm")
    assert edit_storm._nudged("4", 4.0, "count1") == ("3", 3.0)
    assert edit_storm._nudged("1", 1.0, "count1") is None
