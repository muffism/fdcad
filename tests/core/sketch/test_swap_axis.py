"""Swap axis relations (TR124, D950)."""

from __future__ import annotations

import pytest

from fdcad.core.sketch.model import Line, Sketch
from fdcad.core.sketch.solver import drag, solve
from fdcad.core.sketch.swap_axis import SwapAxisError, swap_axis_relations


def _square_rect(sk: Sketch) -> list[str]:
    corners = [(0.0, 0.0), (40.0, 0.0), (40.0, 20.0), (0.0, 20.0)]
    lines = [sk.add_line(*corners[i], *corners[(i + 1) % 4]) for i in range(4)]
    for a, b in zip(lines, lines[1:] + lines[:1], strict=True):
        la, lb = sk.entities[a], sk.entities[b]
        assert isinstance(la, Line) and isinstance(lb, Line)
        sk.relate("coincident", la.p2, lb.p1)
    for k, lid in enumerate(lines):
        sk.relate("horizontal" if k % 2 == 0 else "vertical", lid)
    return lines


def test_rectangle_becomes_free_to_turn() -> None:
    sk = Sketch()
    lines = _square_rect(sk)
    before = solve(sk).dof
    result = swap_axis_relations(sk, lines)
    assert result.reference == lines[0]
    assert len(result.removed) == 4
    kinds = sorted(r.type for r in result.added)
    assert kinds == ["parallel", "perpendicular", "perpendicular"]
    assert not [r for r in sk.relations if r.type in ("horizontal", "vertical")]
    after = solve(sk)
    assert after.solved and after.dof == before + 1  # one more freedom: the turn
    # A corner can now be dragged round and the corners stay square.
    first = sk.entities[lines[0]]
    assert isinstance(first, Line)
    assert drag(sk, {first.p2: (38.0, 10.0)})
    a, b = (sk.entities[i] for i in lines[:2])
    assert isinstance(a, Line) and isinstance(b, Line)
    ax, ay = (sk.xy(a.p2)[k] - sk.xy(a.p1)[k] for k in range(2))
    bx, by = (sk.xy(b.p2)[k] - sk.xy(b.p1)[k] for k in range(2))
    assert abs(ay) > 1.0  # it turned
    assert abs(ax * bx + ay * by) < 1e-6  # still square


def test_lines_without_axis_relations_are_refused() -> None:
    sk = Sketch()
    lid = sk.add_line(0.0, 0.0, 10.0, 5.0)
    with pytest.raises(SwapAxisError, match="Pick the lines"):
        swap_axis_relations(sk, [lid])


def test_switched_off_relations_stay() -> None:
    sk = Sketch()
    lines = _square_rect(sk)
    off = next(r for r in sk.relations if r.type == "vertical")
    off.off = True
    result = swap_axis_relations(sk, lines)
    assert off in sk.relations and off not in result.removed
    assert len(result.added) == 2
