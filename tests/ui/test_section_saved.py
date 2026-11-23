"""Sections saved with the part and in saved views (TR213, D1604)."""

from __future__ import annotations

import math

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import new_document
from fdcad.core.io import fdef
from fdcad.core.section import AxisSetting, PlaneSetting, Reference, SectionState
from fdcad.core.section_store import from_json, saved, set_saved, to_json
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_section_view import _folders, _open, window  # noqa: F401

RIGHT = Reference((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, -1.0))


def test_round_trip_and_damaged_data() -> None:
    state = SectionState(
        [PlaneSetting(), PlaneSetting(RIGHT, "right", True, 4.0, 0.1, 0.2, "#112233")],
        AxisSetting((1.0, 2.0, 3.0), (0.0, 0.0, 1.0), math.pi / 4),
        False,
        "#445566",
        zones=[(True, False)],
        see_through=[0],
        see_through_level=0.3,
    )
    back = from_json(to_json(state))
    assert back is not None
    assert back.planes == state.planes and back.axis == state.axis
    assert (back.show_cap, back.cap_color, back.zones) == (False, "#445566", [(True, False)])
    assert back.see_through == [0] and back.see_through_level == 0.3
    assert from_json(None) is None
    assert from_json({"planes": [{"origin": [0, 0]}]}) is None
    assert from_json({"planes": []}) is None


def test_saved_with_the_document_survives_the_file() -> None:
    doc = new_document()
    set_saved(doc, to_json(SectionState()))
    again = fdef.loads(fdef.dumps(doc))
    assert saved(again) is not None
    set_saved(again, None)
    assert saved(again) is None


def test_save_with_part_is_an_undo_step_and_opens_on(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    tool = window.section_tool
    tool.open(tab)
    panel = tool.panel
    assert panel is not None and not panel.save_box.isChecked()
    panel.rows[0].offset.edit.setText("5")
    panel.save_box.setChecked(True)
    count = tab.session.undo.count()
    panel.ok_button.click()
    assert tab.session.undo.count() == count + 1
    kept = saved(tab.session.document)
    assert kept is not None and kept.planes[0].offset == 5.0
    tab.session.undo.undo()
    assert saved(tab.session.document) is None
    tab.session.undo.redo()
    tool.turn_off(tab)
    assert tool.state_of(tab) is None
    assert tool.restore_saved(tab)
    state = tool.state_of(tab)
    assert state is not None and state.planes[0].offset == 5.0
    tool.open(tab)
    assert tool.panel is not None and tool.panel.save_box.isChecked()
    tool.panel.save_box.setChecked(False)
    tool.panel.ok_button.click()
    assert saved(tab.session.document) is None


def test_saved_view_keeps_and_shows_the_section(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    tab.viewport.camera_pose = lambda: _Pose()  # type: ignore[attr-defined]
    tab.viewport.restore_pose = lambda pose: None  # type: ignore[attr-defined]
    tool = window.section_tool
    tool.apply(tab, SectionState([PlaneSetting(offset=3.0)]))
    assert window.saved_views.save("Cut")
    assert window.saved_views.save("Plain") is True
    tool.turn_off(tab)
    assert window.saved_views.save("Plain2")
    views = {v["name"]: v for v in tab.session.document.views}
    assert "section" in views["Cut"] and "section" not in views["Plain2"]
    assert window.saved_views.go("Cut")
    state = tool.state_of(tab)
    assert state is not None and state.planes[0].offset == 3.0
    tool.turn_off(tab)
    assert window.saved_views.go("Plain2")
    assert tool.state_of(tab) is None


class _Pose:
    center = (0.0, 0.0, 0.0)
    direction = (0.0, 0.0, -1.0)
    up = (0.0, 1.0, 0.0)
    distance = 100.0
    scale = 50.0


def test_save_as_cut_feature_adds_a_section_cut(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """TR151 item 2 (D2205): the section shown becomes a Section Cut, one undo step."""
    from fdcad.core.features.solids import volume_of

    tab = _open(qtbot, window)
    tool = window.section_tool
    tool.open(tab)
    panel = tool.panel
    assert panel is not None
    session = tab.session
    before = len(session.document.features)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        panel.cut_button.click()
    assert tool.state_of(tab) is None and tool.panel is None
    added = session.document.features[before]
    assert added.type == "section_cut" and added.name == "Section Cut 1"
    report = session.report
    assert report is not None and report.body is not None
    assert volume_of(report.body.shape) == pytest.approx(50 * 30 * 5, rel=1e-6)
    session.undo.undo()
    assert len(session.document.features) == before
