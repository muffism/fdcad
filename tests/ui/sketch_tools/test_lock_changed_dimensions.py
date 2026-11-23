"""Lock changed dimensions while dragging (TR238, D1706)."""

from __future__ import annotations

import math

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Line
from fdcad.core.sketch.solver import drag
from tests.ui.sketch_tools.p2_helpers import edit_of


def _two_lines() -> tuple[object, str, str]:
    """Two joined lines; the first has a length dimension."""
    edit = edit_of()
    sk = edit.sketch
    a = sk.add_line(0.0, 0.0, 10.0, 0.0)
    b = sk.add_line(10.0, 0.0, 10.0, 10.0)
    la, lb = sk.entities[a], sk.entities[b]
    assert isinstance(la, Line) and isinstance(lb, Line)
    sk.relate("coincident", la.p2, lb.p1)
    dim = sk.dimension("distance", [la.p1, la.p2], Param("10mm", 10.0))
    edit.refresh()
    return edit, dim.id, b


def test_solver_drag_holds_the_given_points() -> None:
    edit, _did, b = _two_lines()
    sk = edit.sketch  # type: ignore[attr-defined]
    lb = sk.entities[b]
    la = next(e for e in sk.entities.values() if isinstance(e, Line) and e.id != b)
    start = sk.xy(la.p1)
    assert drag(sk, {lb.p2: (15.0, 12.0)}, hold={la.p1, la.p2})
    assert math.dist(sk.xy(la.p1), start) < 1e-6


def test_changed_dimension_geometry_stays_while_dragging() -> None:
    edit, did, b = _two_lines()
    sk = edit.sketch  # type: ignore[attr-defined]
    lb = sk.entities[b]
    la = next(e for e in sk.entities.values() if isinstance(e, Line) and e.id != b)
    edit.set_dimension(did, Param("12mm", 12.0))  # type: ignore[attr-defined]
    edit.refresh()  # type: ignore[attr-defined]
    assert did in edit.changed_dimensions  # type: ignore[attr-defined]
    # Off: the first line may move with the drag.
    assert edit.held_points() == set()  # type: ignore[attr-defined]
    edit.lock_changed = True  # type: ignore[attr-defined]
    assert edit.held_points() == {la.p1, la.p2}  # type: ignore[attr-defined]
    before = (sk.xy(la.p1), sk.xy(la.p2))
    edit.drag_to({lb.p2: (30.0, 25.0)})  # type: ignore[attr-defined]
    assert math.dist(sk.xy(la.p1), before[0]) < 1e-6
    assert math.dist(sk.xy(la.p2), before[1]) < 1e-6


def test_the_preference_reaches_the_open_sketch(qtbot: object) -> None:
    from dataclasses import replace

    from fdcad.ui.sketch_tools.options import SketchOptions
    from tests.ui.sketch_tools.p2_helpers import canvas_of

    canvas, _panel = canvas_of(qtbot)  # type: ignore[arg-type]
    canvas.set_options(replace(SketchOptions(), lock_changed_dimensions=True))
    assert canvas.edit.lock_changed
