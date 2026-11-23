"""Ctrl and drag a plane's border for an offset plane (TR10, D752)."""

from __future__ import annotations

import math

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.units import UnitSystem
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.viewport.plane_drag import border_at, offset_along, rounded
from tests.ui.test_main_window import _folders, _open_plate, window

__all__ = ["_folders", "window"]

SQUARE = [(100.0, 100.0), (200.0, 100.0), (200.0, 200.0), (100.0, 200.0)]


def test_border_hit_only_near_the_outline() -> None:
    outlines = {"f1": SQUARE}
    assert border_at((150.0, 103.0), outlines) == "f1"  # near the top edge
    assert border_at((205.0, 150.0), outlines) == "f1"  # just outside the right edge
    assert border_at((150.0, 150.0), outlines) is None  # the middle is not the border
    assert border_at((150.0, 120.0), outlines) is None
    assert border_at((150.0, 103.0), {}) is None


def test_corners_in_any_order() -> None:
    """The kernel lists a face's corners edge by edge, not round the face."""
    shuffled = [SQUARE[0], SQUARE[2], SQUARE[1], SQUARE[3]]
    assert border_at((150.0, 150.0), {"f1": shuffled}) is None  # no crossing diagonal
    assert border_at((150.0, 101.0), {"f1": shuffled}) == "f1"


def test_the_nearest_of_two_outlines_wins() -> None:
    near = [(x, y + 4.0) for x, y in SQUARE]
    assert border_at((150.0, 101.0), {"f1": SQUARE, "f2": near}) == "f1"
    assert border_at((150.0, 104.0), {"f1": SQUARE, "f2": near}) == "f2"


def test_offset_along_the_normal() -> None:
    # Plane z = 0 grabbed at the origin; looking along -Y, the cursor ray at height 12.
    d = offset_along((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (5.0, 50.0, 12.0), (0.0, -1.0, 0.0))
    assert d == pytest.approx(12.0)
    below = offset_along((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (5.0, 50.0, -3.0), (0.0, -1.0, 0.0))
    assert below == pytest.approx(-3.0)
    # A slanted ray still reads the height where it passes the normal line.
    s = 1 / math.sqrt(2)
    slant = offset_along((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 10.0, 17.0), (0.0, -s, -s))
    assert slant == pytest.approx(7.0)
    # Looking straight down the normal gives no distance.
    assert offset_along((0, 0, 0), (0, 0, 1.0), (0, 0, 9.0), (0, 0, -1.0)) is None


def test_rounding_in_the_part_unit() -> None:
    assert rounded(12.26, UnitSystem.MM) == (12.5, "12.5")
    assert rounded(-7.1, UnitSystem.MM) == (7.0, "7")
    mm, typed = rounded(25.4 * 0.4321, UnitSystem.IN)
    assert typed == "0.43" and mm == pytest.approx(0.43 * 25.4)


def test_a_drag_opens_the_plane_panel_with_the_offset(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ext = _open_plate(qtbot, window)
    doc = tab.session.document
    top = next(f for f in doc.features if f.type == "plane" and f.name == "Top Plane")
    assert window.offset_plane_from_drag(top.id, -12.26)
    panel = window.reference_tool.panel
    assert panel is not None and panel.method_name == "offset"
    feature = panel.current_feature()
    assert feature.type == "ref_plane" and feature.params["method"] == "offset"
    assert feature.refs["first"] == {"feature": top.id}
    assert feature.params["distance"] == Param("12.5", 12.5)
    assert feature.params.get("flip") is True  # below the plane
    assert not any(f.id == feature.id for f in doc.features)  # only OK adds it
    window.reference_tool.wait()
    qtbot.waitUntil(lambda: panel.ok_button.isEnabled(), timeout=10000)
    window.reference_tool.accept()
    made = doc.features[-1]
    assert made.type == "ref_plane" and made.params["distance"] == Param("12.5", 12.5)


def test_a_tiny_drag_makes_nothing(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ext = _open_plate(qtbot, window)
    top = next(f for f in tab.session.document.features if f.name == "Top Plane")
    assert not window.offset_plane_from_drag(top.id, 0.1)


def test_ctrl_drag_in_the_view_reports_the_offset(qtbot: QtBot) -> None:
    """With the kernel's view (skipped offscreen): grab the Top plane's front edge in a
    front view and drag up; the reported offset is up along the plane's normal."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.gp import gp_Ax3, gp_Dir, gp_Pln, gp_Pnt
    from PySide6.QtCore import QPoint, QPointF, Qt

    from tests.ui.test_view_centre import _view

    view = _view(qtbot)
    top = gp_Pln(gp_Ax3(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0), gp_Dir(1, 0, 0)))
    face = BRepBuilderAPI_MakeFace(top, -50, 50, -50, 50).Face()
    view.show_reference_planes({"f2": face})
    view.set_view("iso")
    view._finish_turn()
    sx, sy = view._view.Convert(0.0, 0.0, 50.0)  # middle of the front edge
    dpr = view._dpr
    start = QPoint(round(sx / dpr), round(sy / dpr))
    with qtbot.waitSignal(view.plane_offset_dragged, timeout=5000) as blocker:
        qtbot.mousePress(
            view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier, start
        )
        for dy in (10, 20, 40):
            qtbot.mouseMove(view, start - QPoint(0, dy))
        qtbot.mouseRelease(
            view,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.ControlModifier,
            start - QPoint(0, 40),
        )
    fid, offset = blocker.args
    assert fid == "f2" and offset > 1.0  # up, along +Y
    # A Ctrl press away from any border is a normal pick, not a plane drag.
    middle = view._view.Convert(30.0, 0.0, -30.0)
    away = QPoint(round(middle[0] / dpr), round(middle[1] / dpr))
    assert not view._start_plane_drag(QPointF(away))


def test_ctrl_click_on_a_border_without_dragging_still_picks(qtbot: QtBot) -> None:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.gp import gp_Ax3, gp_Dir, gp_Pln, gp_Pnt
    from PySide6.QtCore import QPoint, Qt

    from tests.ui.test_view_centre import _view

    view = _view(qtbot)
    top = gp_Pln(gp_Ax3(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0), gp_Dir(1, 0, 0)))
    view.show_reference_planes({"f2": BRepBuilderAPI_MakeFace(top, -50, 50, -50, 50).Face()})
    view.set_view("iso")
    view._finish_turn()
    sx, sy = view._view.Convert(0.0, 0.0, 50.0)
    at = QPoint(round(sx / view._dpr), round(sy / view._dpr))
    dragged: list[object] = []
    view.plane_offset_dragged.connect(lambda *a: dragged.append(a))
    with qtbot.waitSignal(view.selection_changed, timeout=5000):
        qtbot.mouseClick(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier, at)
    assert dragged == []
