"""Midpoint Line (TR4, D688)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Line
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.sketch_tools.tools import make_tool
from tests.ui.sketch_tools.p2_helpers import click, edit_of, free


def _line(edit: object) -> Line:
    lines = [e for e in edit.sketch.entities.values() if isinstance(e, Line)]  # type: ignore[attr-defined]
    assert len(lines) == 1
    return lines[0]


def test_command() -> None:
    assert BY_ID["sketch.midpoint_line"].label == "Midpoint Line"


def test_line_centred_on_the_origin_stays_centred() -> None:
    edit = edit_of()
    tool = make_tool("midpoint_line", edit)
    click(edit, tool, 0, 0, snapped=True)  # the origin
    tool.hover(free(10, 3))
    assert len(tool.preview().lines) == 1
    assert click(edit, tool, 10, 3)
    line = _line(edit)
    a, b = edit.sketch.xy(line.p1), edit.sketch.xy(line.p2)
    assert a == pytest.approx((-10, -3)) and b == pytest.approx((10, 3))
    assert any(r.type == "midpoint" and line.id in r.entities for r in edit.sketch.relations)
    # A length dimension changes both ends; the middle stays on the origin.
    edit.sketch.dimension("distance", [line.id], Param("40mm", 40))
    edit.refresh()
    a, b = edit.sketch.xy(line.p1), edit.sketch.xy(line.p2)
    assert ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) == pytest.approx((0, 0), abs=1e-6)
    assert ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 == pytest.approx(40)


def test_horizontal_snap_and_typed_full_length() -> None:
    edit = edit_of()
    tool = make_tool("midpoint_line", edit)
    click(edit, tool, 5, 5)
    tool.locks["length"] = Param("30mm", 30)
    end = tool.track(free(20, 5.1))
    assert end.xy == pytest.approx((20, 5), abs=0.2)
    tool.click(end)
    edit.refresh()
    line = _line(edit)
    assert any(r.type == "horizontal" and r.entities == [line.id] for r in edit.sketch.relations)
    assert any(d.param.value == 30 for d in edit.sketch.dimensions)
    a, b = edit.sketch.xy(line.p1), edit.sketch.xy(line.p2)
    assert abs(b[0] - a[0]) == pytest.approx(30)


def test_zero_length_is_refused() -> None:
    edit = edit_of()
    tool = make_tool("midpoint_line", edit)
    click(edit, tool, 5, 5)
    assert not click(edit, tool, 5, 5)
    assert not [e for e in edit.sketch.entities.values() if isinstance(e, Line)]
