"""Sketch speed budgets (PLAN 11.2 item 5), with a margin for slower CI runners."""

from __future__ import annotations

import time

from fdcad.core.sketch.model import Line, Sketch
from fdcad.core.sketch.solver import defined_entities, drag

#: 60 updates per second, plus 50 percent for slower runners.
DRAG_BUDGET_S = 1.5 / 60
DEFINED_BUDGET_S = 0.5


def _chain(count: int) -> tuple[Sketch, list[str]]:
    """A zig zag of joined lines with horizontal and vertical relations, about 3 entities each."""
    s = Sketch()
    origin = s.add_point(0, 0, construction=True)
    s.relate("fixed", origin)
    lines: list[str] = []
    prev = origin
    for k in range(count):
        x0, y0 = k * 5.0, (k % 2) * 5.0
        lid = s.add_line(x0, y0, x0 + 5.0, ((k + 1) % 2) * 5.0)
        line = s.entities[lid]
        assert isinstance(line, Line)
        s.relate("coincident", line.p1, prev)
        prev = line.p2
        lines.append(lid)
    return s, lines


def test_drag_keeps_up_with_200_entities() -> None:
    s, lines = _chain(67)
    assert len(s.entities) >= 200
    line = s.entities[lines[30]]
    assert isinstance(line, Line)
    x, y = s.xy(line.p2)
    drag(s, {line.p2: (x, y)})  # warm up
    start = time.perf_counter()
    for k in range(30):
        drag(s, {line.p2: (x + k * 0.1, y + k * 0.05)})
    assert (time.perf_counter() - start) / 30 < DRAG_BUDGET_S


def test_defined_state_is_quick_on_200_entities() -> None:
    s, _ = _chain(67)
    start = time.perf_counter()
    defined_entities(s)
    assert time.perf_counter() - start < DEFINED_BUDGET_S
