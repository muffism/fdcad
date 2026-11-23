"""Copy Entities with Linked (TR122 item 2, D1315)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Line
from fdcad.core.sketch.ops.transform import Step, copy
from fdcad.core.sketch.solver import solve
from tests.ui.sketch_tools.p2_helpers import edit_of


def test_linked_copies_follow_the_original_dimension() -> None:
    edit = edit_of()
    sk = edit.sketch
    lid = sk.add_line(0.0, 0.0, 10.0, 0.0)
    dim = sk.dimension("distance", [lid], Param("10", 10.0))
    copy(sk, [lid], Step(dx=0.0, dy=5.0), 2, True, linked=True)
    links = {d.link for d in sk.dimensions}
    assert len(sk.dimensions) == 3 and len(links) == 1 and None not in links
    edit.checkpoint()
    edit.set_dimension(dim.id, Param("14", 14.0))
    edit.refresh()
    assert solve(sk).solved
    lengths = sorted(
        abs(sk.xy(e.p2)[0] - sk.xy(e.p1)[0]) for e in sk.entities.values() if isinstance(e, Line)
    )
    assert lengths == pytest.approx([14.0, 14.0, 14.0])


def test_unlinked_copies_stay_apart() -> None:
    sk = edit_of().sketch
    lid = sk.add_line(0.0, 0.0, 10.0, 0.0)
    sk.dimension("distance", [lid], Param("10", 10.0))
    copy(sk, [lid], Step(dx=0.0, dy=5.0), 1, True)
    assert all(d.link is None for d in sk.dimensions)
