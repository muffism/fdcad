"""The Section Planes tree folder with drag arrows and rotation rings (TR213, D2501)."""

from __future__ import annotations

import math

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.section import PlaneSetting, Reference, SectionState, cut_plane
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.section.handle import (
    LIFT,
    PARAM,
    label,
    make_handles,
    param_of,
    parse_param,
    ring_angle,
    ring_value,
)
from fdcad.ui.section.tree_rows import SECTION_ROLE
from tests.ui.test_section_view import _folders, _open, window  # noqa: F401

FRONT = Reference((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))


def test_params_and_ring_values() -> None:
    assert param_of("offset", 0) == PARAM
    assert parse_param(PARAM) == ("offset", 0)
    assert parse_param(param_of("rot_y", 2)) == ("rot_y", 2)
    assert parse_param("depth") is None and parse_param("section_spin:1") is None
    assert ring_angle(ring_value(-0.5)) == pytest.approx(-0.5)
    assert ring_angle(ring_value(1.2)) == pytest.approx(1.2)


@pytest.mark.parametrize("rot", [(0.3, 0.0), (0.0, -0.4), (0.25, 0.5)])
def test_ring_tips_follow_the_turned_plane(rot: tuple[float, float]) -> None:
    setting = PlaneSetting(FRONT, offset=4.0, rot_x=rot[0], rot_y=rot[1])
    handles = make_handles(SectionState([setting]), 0, size=2.0)
    assert [h.param for h in handles] == [PARAM, "section_rot_x:0", "section_rot_y:0"]
    assert handles[0].tip[2] == pytest.approx(4.0)
    normal = cut_plane(setting).normal
    centre = (0.0, 0.0, 4.0)
    for ring in handles[1:]:
        tip = ring.tip
        arm = tuple(tip[i] - centre[i] for i in range(3))
        assert math.dist(tip, centre) == pytest.approx(6.0)
        # Each ring's tip stays in the turned plane, as the plane's own axes do.
        assert sum(arm[i] * normal[i] for i in range(3)) == pytest.approx(0.0, abs=1e-9)


def test_no_handles_for_a_missing_plane_or_an_axis() -> None:
    assert make_handles(SectionState([PlaneSetting()]), 1) == []
    assert len(make_handles(SectionState([PlaneSetting()]), 0)) == 1  # no size: no rings


def test_ring_label_shows_degrees() -> None:
    from fdcad.core.units import UnitSystem

    text = label(UnitSystem.MM)("section_rot_x:1", ring_value(math.radians(-30)))
    assert "-30" in text


def test_tree_folder_picks_a_plane_and_rings_turn_it(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = _open(qtbot, window)
    tree = window.tree
    assert tree is not None
    tool = window.section_tool
    tool.open(tab)
    panel = tool.panel
    assert panel is not None
    panel.rows[1].setChecked(True)
    panel.rows[1].set_reference("right")
    assert tree.section_planes == ["Section 1 (Front)", "Section 2 (Right)"]
    rows = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
    folder = next(r for r in rows if r is not None and r.data(0, SECTION_ROLE) == -1)
    assert folder.childCount() == 2
    tool.accept()  # the panel closes, the section and folder stay
    assert tool.panel is None and tree.section_planes
    tree._clicked(folder.child(1), 0)  # pick Section 2: the panel opens on it
    assert tool.panel is not None and tool.active_plane == 1
    tool.handle._dragged("section_rot_x:1", ring_value(math.radians(-20)))
    assert tool.panel.rows[1].rot_x.edit.text() == "-20"
    tool.handle._dragged("section_offset:1", LIFT + 3.0)
    state = tool.state_of(tab)
    assert state is not None and state.planes[1].offset == pytest.approx(3.0)
    menu = tree._context_menu(tab.session, folder)
    assert menu is not None
    next(a for a in menu.actions() if a.text() == "Turn Off Section").trigger()
    assert tool.state_of(tab) is None and tree.section_planes == []
