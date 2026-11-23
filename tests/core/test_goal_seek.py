"""Goal Seek and value sweep (TR273, D1020)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Document, Param, Variable, new_document
from fdcad.core.goal_seek import Trials, goal_seek, sweep, target_names, variable_text
from fdcad.core.sketch.model import Sketch
from fdcad.core.units.expressions import Kind
from tests.core.features.phase3_parts import add_extrude, add_sketch, rect


def block(h: float = 10.0) -> Document:
    """A 20 x 20 block whose depth is the variable h: volume 400 h."""
    doc = new_document()
    doc.variables.append(Variable("h", Kind.LENGTH, f"{h:g}", h))
    s = Sketch()
    rect(s, 0, 0, 20, 20)
    fid = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), h)
    doc.feature(fid).params["depth"] = Param("=h", h)
    return doc


def test_targets_and_variable_text() -> None:
    doc = block()
    assert target_names(doc)[:2] == ["volume@Part", "area@Part"]
    assert variable_text(Kind.LENGTH, 12.5) == "12.5mm"
    assert variable_text(Kind.ANGLE, math.pi / 2) == "90deg"
    assert variable_text(Kind.NUMBER, 3.0) == "3"
    with pytest.raises(ValueError, match="Pick a variable"):
        Trials(doc, "nope", "volume@Part")
    with pytest.raises(ValueError, match="Pick a measured value"):
        Trials(doc, "h", "length@Nothing")


def test_sweep_leaves_the_document_alone() -> None:
    doc = block()
    steps = sweep(Trials(doc, "h", "volume@Part"), 5.0, 15.0, 3)
    assert [s.value for s in steps] == pytest.approx([5, 10, 15])
    assert [s.result for s in steps] == pytest.approx([2000, 4000, 6000])
    assert doc.variables[0].expr == "10" and doc.variables[0].value == 10
    with pytest.raises(ValueError, match="2 or more"):
        sweep(Trials(doc, "h", "volume@Part"), 1, 2, 1)


def test_goal_seek_finds_the_depth_for_a_volume() -> None:
    doc = block()
    found = goal_seek(Trials(doc, "h", "volume@Part"), 5000.0, 1.0, 30.0)
    assert found.value == pytest.approx(12.5, rel=1e-5)
    assert found.result == pytest.approx(5000, rel=1e-6)
    assert len(found.trials) < 20
    assert doc.variables[0].value == 10  # nothing changed until the user accepts


def test_goal_seek_out_of_range_says_what_to_do() -> None:
    doc = block()
    with pytest.raises(ValueError, match="Widen the range"):
        goal_seek(Trials(doc, "h", "volume@Part"), 50000.0, 1.0, 30.0)


def test_stopping() -> None:
    doc = block()
    with pytest.raises(ValueError, match="stopped"):
        goal_seek(Trials(doc, "h", "volume@Part"), 5000.0, 1.0, 30.0, cancelled=lambda: True)
