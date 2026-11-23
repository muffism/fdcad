"""Section view: planes, the clipping chain, the panel and the command (P2.13, D253)."""

from __future__ import annotations

import math
from collections.abc import Iterator
from pathlib import Path

import pytest
from OCP.collections import Vec4_double
from OCP.Graphic3d import Graphic3d_ClipState
from PySide6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature, new_document
from fdcad.core.io import fdef
from fdcad.core.section import (
    AxisSetting,
    PlaneSetting,
    Reference,
    SectionState,
    axis_plane,
    cut_plane,
    is_cut_away,
)
from fdcad.core.sketch.model import Sketch
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.session import DocumentSession
from fdcad.ui.viewport.section_view import clip_chain
from tests.core.features.test_features import add_extrude, add_sketch, rect

FRONT = Reference((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))
RIGHT = Reference((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, -1.0))


# Planes ---------------------------------------------------------------------------------


def test_offset_reverse_and_rotation() -> None:
    p = cut_plane(PlaneSetting(FRONT, offset=5.0))
    assert p.origin == (0.0, 0.0, 5.0) and p.normal == pytest.approx((0, 0, 1))
    p = cut_plane(PlaneSetting(FRONT, reverse=True))
    assert p.normal == pytest.approx((0, 0, -1))
    p = cut_plane(PlaneSetting(FRONT, rot_x=math.pi / 2))  # about the plane's X axis
    assert p.normal == pytest.approx((0, -1, 0), abs=1e-12)
    p = cut_plane(PlaneSetting(FRONT, rot_y=math.pi / 2))
    assert abs(p.normal[0]) == pytest.approx(1.0)


def test_axis_turns_section_one() -> None:
    a = axis_plane(AxisSetting((0, 0, 0), (0, 0, 1), 0.0))
    b = axis_plane(AxisSetting((0, 0, 0), (0, 0, 1), math.pi / 2))
    assert a.normal[2] == pytest.approx(0) and b.normal[2] == pytest.approx(0)
    assert sum(x * y for x, y in zip(a.normal, b.normal, strict=True)) == pytest.approx(0)
    state = SectionState(axis=AxisSetting((1, 2, 3), (0, 0, 1)))
    assert state.cut_planes()[0].origin == (1, 2, 3)


def test_two_planes_cut_away_only_the_corner_in_front_of_both() -> None:
    state = SectionState([PlaneSetting(FRONT), PlaneSetting(RIGHT)])
    planes = state.cut_planes()
    assert is_cut_away((1, 0, 1), planes)
    assert not is_cut_away((-1, 0, 1), planes)
    assert not is_cut_away((1, 0, -1), planes)
    assert not is_cut_away((0, 0, 0), [])


@pytest.mark.parametrize(
    "point", [(1, 0, 1), (-1, 0, 1), (1, 0, -1), (-1, 0, -1), (0.5, 3, 0.2), (-2, -1, 4)]
)
def test_clip_chain_matches_the_section_rule(point: tuple[float, float, float]) -> None:
    """The viewer's clipping (probed without a GPU) hides exactly what the rule says."""
    state = SectionState([PlaneSetting(FRONT), PlaneSetting(RIGHT)])
    chain = clip_chain(state.cut_planes(), True)
    assert chain is not None and chain.IsCapping()
    hidden = (
        chain.ProbePoint(Vec4_double(*point, 1.0)) == Graphic3d_ClipState.Graphic3d_ClipState_Out
    )
    assert hidden == is_cut_away(point, state.cut_planes())


def test_single_plane_chain_and_none() -> None:
    planes = SectionState([PlaneSetting(FRONT, offset=2.0)]).cut_planes()
    chain = clip_chain(planes, False, "#112233")
    assert chain is not None and not chain.IsCapping()
    out = Graphic3d_ClipState.Graphic3d_ClipState_Out
    assert chain.ProbePoint(Vec4_double(0, 0, 3, 1)) == out
    assert chain.ProbePoint(Vec4_double(0, 0, 1, 1)) != out
    assert clip_chain([], True) is None


# In the window ----------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("FDCAD_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> Iterator[MainWindow]:
    settings = Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))
    win = MainWindow(settings)
    win.resize(1200, 800)
    win.show()
    win.finish_setup()
    yield win
    win.section_tool.turn_off()
    while win.tabs.count():
        tab = win.tabs.widget(0)
        assert isinstance(tab, DocumentTab)
        tab.session.cancel_rebuild()
        tab.session.wait()
        tab.autosaver.discard()
        win.tabs.removeTab(0)
    win.close()
    win.deleteLater()


def _open(qtbot: QtBot, win: MainWindow) -> DocumentTab:
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 50, 30)
    sk = add_sketch(doc, s, {"feature": "f2"})
    add_extrude(doc, sk, 10.0)
    doc.features.append(
        Feature(
            "f7",
            "ref_axis",
            "Axis 1",
            params={"method": "two_planes"},
            refs={"first": {"feature": "f3"}, "second": {"feature": "f4"}},
        )
    )
    doc.next_id = 8
    session = DocumentSession(doc, None, win)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = win.add_session(session)
    return tab


def test_command_panel_ok_keeps_it_on_and_command_turns_it_off(
    qtbot: QtBot, window: MainWindow
) -> None:
    tab = _open(qtbot, window)
    before = fdef.dumps(tab.session.document)
    undo_count = tab.session.undo.count()
    assert "view.section" in BY_ID
    assert window.commands.trigger("view.section")
    tool = window.section_tool
    panel = tool.panel
    assert panel is not None
    state = tool.state_of(tab)
    assert state is not None and len(state.planes) == 1
    assert window.commands.actions["view.section"].isChecked()
    # Section 2 on the Right plane, offset 10, reversed.
    row = panel.rows[1]
    row.setChecked(True)
    row.set_reference("right")
    row.offset.edit.setText("10")
    row.reverse.setChecked(True)
    state = tool.state_of(tab)
    assert state is not None and len(state.planes) == 2
    second = state.cut_planes()[1]
    assert second.origin == pytest.approx((10, 0, 0)) and second.normal == pytest.approx((-1, 0, 0))
    row.set_color("#336699")
    assert tool.state_of(tab).planes[1].color == "#336699"  # type: ignore[union-attr]
    panel.ok_button.click()
    assert tool.panel is None and tool.state_of(tab) is not None
    assert window.commands.actions["view.section"].isChecked()
    # Display only: the file and the undo list do not change (P2.13 item 4).
    assert fdef.dumps(tab.session.document) == before
    assert tab.session.undo.count() == undo_count
    window.commands.trigger("view.section")
    assert tool.state_of(tab) is None
    assert not window.commands.actions["view.section"].isChecked()


def test_cancel_turns_off_and_axis_and_cap_options(qtbot: QtBot, window: MainWindow) -> None:
    tab = _open(qtbot, window)
    tool = window.section_tool
    tool.open(tab)
    panel = tool.panel
    assert panel is not None
    assert panel.axis.findData("f7") >= 0 and panel.use_axis.isEnabled()
    panel.use_axis.setChecked(True)
    panel.angle.edit.setText("90")
    state = tool.state_of(tab)
    assert state is not None and state.axis is not None
    assert state.axis.angle == pytest.approx(math.pi / 2)
    panel.show_cap.setChecked(False)
    assert tool.state_of(tab).show_cap is False  # type: ignore[union-attr]
    panel.keep_color.setChecked(False)
    panel.rows[0].set_color("#00FF00")
    panel.ok_button.click()
    state = tool.state_of(tab)
    assert state is not None and state.cap_color == "#D9822B"  # back to the default
    tool.open(tab)
    assert tool.panel is not None
    tool.panel.cancel_button.click()
    assert tool.state_of(tab) is None and tool.panel is None


def test_section_one_has_a_drag_arrow_that_moves_the_plane(
    qtbot: QtBot, window: MainWindow
) -> None:
    from fdcad.ui.section.handle import LIFT, PARAM, make_handle

    tab = _open(qtbot, window)
    assert window.commands.trigger("view.section")
    tool = window.section_tool
    panel = tool.panel
    assert panel is not None
    state = tool.state_of(tab)
    assert state is not None
    handle = make_handle(state)
    assert handle is not None and handle.param == PARAM and handle.style == "flat"
    assert handle.tip == pytest.approx((0, 0, 5))  # mid part (D580)
    assert handle.pointing == pytest.approx((0, 0, 1))
    # Dragging it types the offset into the panel and moves the plane.
    tool.handle._dragged(PARAM, LIFT + 7.5)
    assert panel.rows[0].offset.edit.text() == "7.5"
    moved = tool.state_of(tab)
    assert moved is not None and moved.cut_planes()[0].origin == pytest.approx((0, 0, 7.5))
    panel.ok_button.click()


def test_length_arrow_has_a_shaft_behind_its_head() -> None:
    from fdcad.core.features.base import PreviewHandle
    from fdcad.core.features.solids import volume_of
    from fdcad.ui.viewport.preview import arrow_shape

    handle = PreviewHandle("depth", (0, 0, 0), (0, 0, 1), 10.0)
    head_only = math.pi * (0.35 * 2) ** 2 * 2 / 3  # a cone of size 2
    assert volume_of(arrow_shape(handle, 2.0)) > head_only * 1.1


def test_section_arrow_is_flat_faces_the_viewer_and_is_never_cut() -> None:
    """D586: a flat 2D arrow, and the section planes never clip it."""
    from OCP.AIS import AIS_Shape
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Plane
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopoDS import TopoDS

    from fdcad.core.features.base import PreviewHandle
    from fdcad.ui.viewport.preview import arrow_shape
    from fdcad.ui.viewport.widget import unclipped

    handle = PreviewHandle(
        "section_offset", (0, 0, 0), (0, 0, 1), 10.0, style="flat", facing=(1, 0, 0)
    )
    arrow = arrow_shape(handle, 2.0)
    assert arrow.ShapeType() == TopAbs_FACE
    surface = BRepAdaptor_Surface(TopoDS.Face(arrow))
    assert surface.GetType() == GeomAbs_Plane
    normal = surface.Plane().Axis().Direction()
    assert abs(normal.X()) == pytest.approx(1.0)  # it faces the viewer
    mark = AIS_Shape(arrow)
    unclipped(mark)
    assert mark.ClipPlanes().ToOverrideGlobal()


def test_new_section_cuts_through_the_middle_of_the_part(qtbot: QtBot, window: MainWindow) -> None:
    # Front at offset 0 lies on the block's bottom face: the cap fought with it and
    # nothing of the part showed. A new section starts through the middle instead.
    tab = _open(qtbot, window)
    tool = window.section_tool
    tool.open(tab)
    panel = tool.panel
    assert panel is not None
    row = panel.rows[0]
    assert tool.state_of(tab).cut_planes()[0].origin == pytest.approx((0, 0, 5))  # type: ignore[union-attr]
    row.set_reference("right")
    assert row.current().offset == pytest.approx(25.0)
    row.set_reference("top")
    assert row.current().offset == pytest.approx(15.0)
    # An offset the user types stays when the plane changes.
    row.offset.edit.setText("3")
    row.offset.edit.textEdited.emit("3")
    row.set_reference("front")
    assert row.current().offset == pytest.approx(3.0)
    # Reopening keeps the section as it was left.
    row.reverse.setChecked(True)
    panel.ok_button.click()
    tool.open(tab)
    again = tool.panel.rows[0]  # type: ignore[union-attr]
    assert again.current().offset == pytest.approx(3.0) and again.reverse.isChecked()


def test_drag_arrow_label_uses_the_part_units() -> None:
    """Round 10c: the arrow label showed millimetres in an inch part, beside an inch field."""
    from fdcad.core.units import UnitSystem
    from fdcad.ui.section.handle import LIFT, PARAM, label

    assert label(UnitSystem.IN)(PARAM, LIFT + 25.4) == "1.000 in"
    assert label(UnitSystem.MM)(PARAM, LIFT - 7.5) == "-7.50 mm"
