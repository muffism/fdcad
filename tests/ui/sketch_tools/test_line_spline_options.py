"""Line click buffer and Relax Spline (TR115 items 3 and 4, D1314)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.freeform import default_handles
from fdcad.core.sketch.model import Line, Spline
from fdcad.core.sketch.spline_edit import relax
from fdcad.ui.main_window.context_menu import keys
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.tools import LineTool
from tests.ui.sketch_tools.p2_helpers import canvas_of, edit_of
from tests.ui.test_main_window import _folders, window

__all__ = ["_folders", "window"]


def test_a_second_click_on_top_of_the_first_makes_no_line() -> None:
    edit = edit_of()
    tool = LineTool(edit)
    tool.tolerance = 0.5
    tool.click(Snap("free", 0.0, 0.0))
    assert not tool.click(Snap("free", 0.2, 0.1))
    assert not [e for e in edit.sketch.entities.values() if isinstance(e, Line)]
    assert tool.click(Snap("free", 5.0, 0.0))
    assert len([e for e in edit.sketch.entities.values() if isinstance(e, Line)]) == 1


def _wiggly(sk) -> Spline:  # type: ignore[no-untyped-def]
    pts = [(0.0, 0.0), (5.0, 3.0), (10.0, 0.0), (15.0, 2.0)]
    hs = [(1.0, 1.0), (9.0, 9.0), (10.0, -4.0), (16.0, 3.0)]
    ps = [sk.add_point(*p) for p in pts]
    hids = [sk.add_point(*h, True) for h in hs]
    sid = sk.new_id()
    sk.entities[sid] = Spline(sid, ps, hids)
    return sk.entities[sid]  # type: ignore[no-any-return]


def test_relax_evens_inner_handles_and_keeps_the_ends() -> None:
    sk = edit_of().sketch
    sp = _wiggly(sk)
    sk.relate("fixed", sp.handles[2])
    assert relax(sk, sp.id) == 1
    even = default_handles([sk.xy(p) for p in sp.points])
    assert sk.xy(sp.handles[1]) == pytest.approx(even[1])
    assert sk.xy(sp.handles[2]) == pytest.approx((10.0, -4.0))  # pinned
    assert sk.xy(sp.handles[0]) == pytest.approx((1.0, 1.0))
    assert sk.xy(sp.handles[3]) == pytest.approx((16.0, 3.0))


def test_menu_relaxes_a_spline(qtbot: QtBot, window: MainWindow) -> None:
    sk = edit_of().sketch
    sp = _wiggly(sk)
    canvas, _panel = canvas_of(qtbot, sk)
    canvas.selection = [sp.id]
    menu = window.context_menus.build_sketch_menu(canvas)
    assert "relax_spline" in keys(menu)
    next(a for a in menu.actions() if a.data() == "relax_spline").trigger()
    spline = canvas.edit.sketch.entities[sp.id]
    assert isinstance(spline, Spline)
    assert canvas.edit.sketch.xy(spline.handles[1]) != pytest.approx((9.0, 9.0))


def test_menu_adds_a_spline_length(qtbot: QtBot, window: MainWindow) -> None:
    """TR115 item 4 (D2201): Spline Length adds a path length on the spline."""
    sk = edit_of().sketch
    sp = _wiggly(sk)
    canvas, _panel = canvas_of(qtbot, sk)
    canvas.selection = [sp.id]
    menu = window.context_menus.build_sketch_menu(canvas)
    next(a for a in menu.actions() if a.data() == "spline_length").trigger()
    (dim,) = canvas.edit.sketch.dimensions
    assert dim.type == "path_length" and dim.entities == [sp.id]
    assert dim.param.value > 15.0
