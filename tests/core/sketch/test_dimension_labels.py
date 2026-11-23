"""Stored dimension label positions (FDEF_SPEC 6 item 5, DECISIONS D150)."""

from __future__ import annotations

import copy

import pytest

from fdcad.core.io import fdef
from fdcad.core.sketch.model import sketch_from_data, sketch_to_data
from fdcad.samples.make import SAMPLE_DIR

RAW = {
    "next_entity": 4,
    "entities": [
        {"id": "e1", "type": "point", "x": 0, "y": 0, "construction": False},
        {"id": "e2", "type": "point", "x": 30, "y": 0, "construction": False},
        {"id": "e3", "type": "line", "p1": "e1", "p2": "e2", "construction": False},
    ],
    "relations": [],
    "dimensions": [
        {
            "id": "d1",
            "type": "distance",
            "entities": ["e3"],
            "driving": True,
            "param": {"expr": "30", "value": 30.0},
        }
    ],
}


def test_without_label_the_key_is_not_written() -> None:
    sketch = sketch_from_data(copy.deepcopy(RAW))
    assert sketch.dimensions[0].label is None
    assert "label" not in sketch_to_data(sketch)["dimensions"][0]


def test_label_round_trips() -> None:
    raw = copy.deepcopy(RAW)
    raw["dimensions"][0]["label"] = [2.5, -9]  # type: ignore[index]
    sketch = sketch_from_data(raw)
    assert sketch.dimensions[0].label == (2.5, -9.0)
    assert sketch_to_data(sketch)["dimensions"][0]["label"] == [2.5, -9.0]


@pytest.mark.parametrize("bad", [[1.0], "1,2", [1.0, float("nan")], {"x": 1}])
def test_bad_label_is_damaged_data(bad: object) -> None:
    raw = copy.deepcopy(RAW)
    raw["dimensions"][0]["label"] = bad  # type: ignore[index]
    with pytest.raises(ValueError):
        sketch_from_data(raw)


def test_samples_have_no_labels_and_open_unchanged() -> None:
    for path in sorted(SAMPLE_DIR.glob("*.fdprt")):
        text = path.read_text(encoding="utf-8")
        assert '"label"' not in text
        assert fdef.dumps(fdef.loads(text)) == text
