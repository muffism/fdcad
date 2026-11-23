"""Relation groups and Equal Length of lines and arcs (TR108, D1303)."""

from __future__ import annotations

import math

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Line
from fdcad.core.sketch.solver import arc_length, solve
from fdcad.ui.sketch_tools.edit import group_numbers, relations_for
from tests.ui.sketch_tools.p2_helpers import canvas_of, edit_of


def _length(sk, lid: str) -> float:  # type: ignore[no-untyped-def]
    line = sk.entities[lid]
    assert isinstance(line, Line)
    return math.dist(sk.xy(line.p1), sk.xy(line.p2))


def test_equal_length_of_a_line_and_an_arc() -> None:
    edit = edit_of()
    sk = edit.sketch
    line = sk.add_line(0.0, 0.0, 10.0, 0.0)
    arc = sk.add_arc(20.0, 0.0, 3.0, 0.0, math.pi / 2)
    assert "equal" in relations_for(sk, [line, arc])
    edit.checkpoint()
    edit.relate("equal", [line, arc])
    edit.refresh()
    assert edit.result is not None and edit.result.solved
    assert _length(sk, line) == pytest.approx(arc_length(sk, arc), abs=1e-6)


def test_adding_to_a_group_joins_it_and_numbers_its_tags(qtbot: QtBot) -> None:
    edit = edit_of()
    sk = edit.sketch
    a = sk.add_line(0.0, 0.0, 10.0, 0.0)
    b = sk.add_line(0.0, 5.0, 10.0, 6.0)
    c = sk.add_line(0.0, 9.0, 10.0, 11.0)
    d = sk.add_line(0.0, 15.0, 10.0, 18.0)
    edit.relate("parallel", [a, b])
    edit.relate("parallel", [c, d])
    edit.relate("parallel", [b, c])  # joins both groups into one relation
    parallels = [r for r in sk.relations if r.type == "parallel"]
    assert len(parallels) == 1 and parallels[0].entities == [a, b, c, d]
    assert solve(sk).solved
    index = sk.relations.index(parallels[0])
    assert group_numbers(sk) == {index: 1}
    canvas, _panel = canvas_of(qtbot, sk)
    tags = [t for t in canvas._tag_entries() if t[2] == index]
    assert len(tags) == 4  # one numbered tag at every member


def test_a_group_that_would_not_fit_stays_apart() -> None:
    edit = edit_of()
    sk = edit.sketch
    a = sk.add_line(0.0, 0.0, 10.0, 0.0)
    b = sk.add_line(0.0, 5.0, 10.0, 6.0)
    circle = sk.add_circle(30.0, 0.0, 2.0)
    other = sk.add_circle(40.0, 0.0, 3.0)
    edit.relate("equal", [a, b])
    edit.relate("equal", [circle, other])
    assert len([r for r in sk.relations if r.type == "equal"]) == 2
    assert solve(sk).solved
