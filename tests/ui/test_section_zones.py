"""Section view zones and see through bodies (TR355, D1603)."""

from __future__ import annotations

import pytest
from OCP.collections import Vec4_double
from OCP.Graphic3d import Graphic3d_ClipState
from pytestqt.qtbot import QtBot

from fdcad.core.section import PlaneSetting, Reference, SectionState, all_zones, is_cut_away
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.section.zones import SectionExtras, zone_label
from fdcad.ui.viewport.section_view import clip_chains
from tests.ui.test_section_view import _folders, _open, window  # noqa: F401

FRONT = Reference((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))
RIGHT = Reference((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, -1.0))
OUT = Graphic3d_ClipState.Graphic3d_ClipState_Out


def test_zones_of_two_and_three_planes() -> None:
    assert all_zones(2) == [(True, True), (True, False), (False, True), (False, False)]
    assert len(all_zones(3)) == 8 and all_zones(3)[0] == (True, True, True)
    assert zone_label((True, False)) == "In front of 1, behind 2"


def test_no_zones_keeps_the_old_corner_cut() -> None:
    state = SectionState([PlaneSetting(FRONT), PlaneSetting(RIGHT)])
    assert state.cut_zones() == [state.cut_planes()]
    one = SectionState([PlaneSetting(FRONT)], zones=[(True, False)])
    assert one.cut_zones() == [one.cut_planes()]  # one plane: no zones to pick


@pytest.mark.parametrize(
    "point", [(1, 0, 1), (-1, 0, 1), (1, 0, -1), (-1, 0, -1), (0.5, 3, -0.2), (-2, -1, 4)]
)
def test_two_opposite_zones_go_and_the_chains_agree(point: tuple[float, float, float]) -> None:
    state = SectionState(
        [PlaneSetting(FRONT), PlaneSetting(RIGHT)], zones=[(True, True), (False, False)]
    )
    zones = state.cut_zones()
    expected = (point[0] > 0) == (point[2] > 0)
    assert is_cut_away(point, [], zones) == expected
    chains = clip_chains(zones, True)
    assert len(chains) == 2
    hidden = any(c.ProbePoint(Vec4_double(*point, 1.0)) == OUT for c in chains)
    assert hidden == expected


def test_extras_follow_the_plane_count(qtbot: QtBot) -> None:
    extras = SectionExtras([(True, False)], 3, [1], 0.5)
    qtbot.addWidget(extras)
    assert extras.zone_group.isHidden()
    extras.set_plane_count(2)
    assert not extras.zone_group.isHidden() and len(extras.zone_boxes) == 4
    assert extras.zones() == [(True, False)]
    extras.set_plane_count(3)
    assert len(extras.zone_boxes) == 8 and extras.zones() == []
    assert extras.see_through() == [1] and extras.see_through_level() == 0.5


def test_panel_sends_zones_and_see_through(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    tool = window.section_tool
    tool.open(tab)
    panel = tool.panel
    assert panel is not None
    panel.rows[1].setChecked(True)
    panel.rows[1].set_reference("right")
    boxes = panel.extras.zone_boxes
    assert len(boxes) == 4
    boxes[(True, True)].setChecked(True)
    boxes[(False, False)].setChecked(True)
    state = tool.state_of(tab)
    assert state is not None and state.zones == [(True, True), (False, False)]
    assert len(state.cut_zones()) == 2
    assert panel.extras.bodies.count() == 1
    seen: list[tuple[int, float]] = []
    tab.viewport.set_section_see_through = lambda s, level: seen.append((len(s), level))  # type: ignore[attr-defined]
    from PySide6.QtCore import Qt

    panel.extras.bodies.item(0).setCheckState(Qt.CheckState.Checked)
    assert tool.state_of(tab).see_through == [0]  # type: ignore[union-attr]
    assert seen[-1] == (1, pytest.approx(0.6))
    tool.turn_off(tab)
    assert seen[-1] == (0, 0.0)
