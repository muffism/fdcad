"""TOOL_SPEC T16 items 1 to 3 in the feature panel: the new end conditions show and
hide the right fields and write the right keys."""

import math

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.naming.select import reference_for
from fdcad.ui.property_panel.panel import PropertyPanel
from fdcad.ui.session import DocumentSession
from tests.core.features.test_features import shaft
from tests.ui.test_extrude_phase2_panel import _second
from tests.ui.test_property_panel import _session


@pytest.fixture
def panel(qtbot: QtBot) -> PropertyPanel:
    widget = PropertyPanel()
    qtbot.addWidget(widget)
    return widget


def _items(panel: PropertyPanel, name: str) -> list[str]:
    box = panel.choices[name]
    return [box.itemData(i) for i in range(box.count())]


def _choose(panel: PropertyPanel, name: str, value: str) -> None:
    box = panel.choices[name]
    box.setCurrentIndex(box.findData(value))


def _hidden(panel: PropertyPanel, name: str) -> bool:
    row = panel.values[name].parentWidget()
    return row is None or row.isHidden()


# Extrude ---------------------------------------------------------------------------


def test_direction_2_list_order(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, _ext, fid = _second(qtbot)
    panel.begin(session, session.document.feature(fid), is_new=False)
    assert _items(panel, "end_condition2") == [
        "blind",
        "through_all",
        "up_to_next",
        "up_to_vertex",
        "up_to_face",
        "offset_from_face",
        "up_to_body",
    ]


def test_through_all_both_hides_direction_2_and_depth(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, _ext, fid = _second(qtbot)
    panel.begin(session, session.document.feature(fid), is_new=False)
    panel.groups["direction2"].set_checked(True)
    _choose(panel, "end_condition", "through_all_both")
    assert panel.groups["direction2"].isHidden()
    assert _hidden(panel, "depth")
    assert panel.ends[""].pick_row.isHidden() and panel.ends[""].draft_row.isHidden()
    result = panel.current_feature()
    assert result is not None
    assert result.params["end_condition"] == "through_all_both"
    assert "end_condition2" not in result.params and "depth2" not in result.params
    _choose(panel, "end_condition", "blind")
    assert not panel.groups["direction2"].isHidden()


def test_up_to_next_needs_no_pick(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, _ext, fid = _second(qtbot)
    panel.begin(session, session.document.feature(fid), is_new=False)
    _choose(panel, "end_condition", "up_to_next")
    end = panel.ends[""]
    assert end.pick_row.isHidden() and not end.wants_pick()
    assert _hidden(panel, "depth") and end.draft_row.isHidden()
    result = panel.current_feature()
    assert result is not None and result.params["end_condition"] == "up_to_next"
    assert "end" not in result.refs
    assert result.params["depth"] == Param("5.0", 5.0)  # the stored depth is kept


def test_up_to_body_takes_a_face_of_the_body(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, ext, fid = _second(qtbot)
    report = session.report
    assert report is not None
    plate = report.results[ext].body
    assert plate is not None
    face = plate.face(f"{ext}/cap/start")
    assert face is not None
    panel.begin(session, session.document.feature(fid), is_new=False)
    _choose(panel, "end_condition", "up_to_body")
    end = panel.ends[""]
    assert not end.pick_row.isHidden() and end.wants_pick()
    assert panel.current_feature() is None  # no body yet
    assert panel.set_start_pick({"feature": "f3"}) is not None  # a plane is not a body
    assert panel.set_start_pick(reference_for(plate, face)) is None
    result = panel.current_feature()
    assert result is not None and result.params["end_condition"] == "up_to_body"
    assert result.refs["end"]["name"] == f"{ext}/cap/start"
    assert "Body" in end.pick.currentText()


def test_switching_between_face_ends_keeps_the_picked_face(
    qtbot: QtBot, panel: PropertyPanel
) -> None:
    # Bug hunt E6: a face picked for Up to Face was dropped on a switch to
    # Offset from Face, and OK then asked for a face again.
    session, ext, fid = _second(qtbot)
    report = session.report
    assert report is not None
    plate = report.results[ext].body
    assert plate is not None
    face = plate.face(f"{ext}/cap/start")
    assert face is not None
    ref = reference_for(plate, face)
    panel.begin(session, session.document.feature(fid), is_new=False)
    _choose(panel, "end_condition", "up_to_face")
    assert panel.set_start_pick(ref) is None
    _choose(panel, "end_condition", "offset_from_face")
    assert not panel.end_wants_pick()
    result = panel.current_feature()
    assert result is not None and result.refs["end"] == ref
    _choose(panel, "end_condition", "up_to_vertex")  # a face does not fit
    assert panel.ends[""].pick.currentIndex() < 0


def test_boss_without_a_body_offers_no_body_ends(qtbot: QtBot, panel: PropertyPanel) -> None:
    from tests.core.features.test_features import plate

    doc, ext = plate()
    session = _session(qtbot, doc)
    panel.begin(session, doc.feature(ext), is_new=False)
    items = _items(panel, "end_condition")
    assert not {"through_all_both", "up_to_next", "up_to_body"} & set(items)
    assert items[-1] == "mid_plane"


# Revolve ---------------------------------------------------------------------------


def _revolve(qtbot: QtBot, panel: PropertyPanel, **params: object) -> DocumentSession:
    doc, rev = shaft(90, **params)
    session = _session(qtbot, doc)
    panel.begin(session, doc.feature(rev), is_new=False)
    return session


def test_revolve_lists(qtbot: QtBot, panel: PropertyPanel) -> None:
    _revolve(qtbot, panel)
    assert _items(panel, "direction") == [
        "blind",
        "through_all",
        "up_to_vertex",
        "up_to_face",
        "offset_from_face",
        "mid_plane",
    ]
    assert _items(panel, "end_condition2") == [
        "blind",
        "up_to_vertex",
        "up_to_face",
        "offset_from_face",
    ]


def test_old_revolve_saves_no_new_keys(qtbot: QtBot, panel: PropertyPanel) -> None:
    session = _revolve(qtbot, panel)
    original = session.document.features[-1]
    result = panel.current_feature()
    assert result is not None
    assert set(result.params) <= set(original.params) | {"merge", "reverse"}
    assert result.params["direction"] == "one_direction"
    assert result.refs == original.refs


def test_revolve_through_all_hides_the_angle_and_direction_2(
    qtbot: QtBot, panel: PropertyPanel
) -> None:
    _revolve(qtbot, panel)
    panel.groups["direction2"].set_checked(True)
    _choose(panel, "direction", "through_all")
    assert _hidden(panel, "angle") and panel.groups["direction2"].isHidden()
    assert panel.ends[""].pick_row.isHidden()
    result = panel.current_feature()
    assert result is not None
    assert result.params["end_condition"] == "through_all"
    assert result.params["direction"] == "one_direction"
    assert "angle2" not in result.params and "end_condition2" not in result.params


def test_revolve_up_to_face_takes_a_plane(qtbot: QtBot, panel: PropertyPanel) -> None:
    _revolve(qtbot, panel)
    _choose(panel, "direction", "up_to_face")
    end = panel.ends[""]
    assert not end.pick_row.isHidden() and _hidden(panel, "angle")
    assert end.draft_row.isHidden() and end.options_row.isHidden()
    assert panel.end_wants_pick()
    assert panel.current_feature() is None
    assert panel.set_start_pick({"feature": "f4"}) is None
    result = panel.current_feature()
    assert result is not None
    assert result.params["end_condition"] == "up_to_face"
    assert result.refs["end_ref"] == {"feature": "f4"}
    assert "end" not in result.refs
    assert result.params["angle"].value == pytest.approx(math.pi / 2)  # kept


def test_revolve_offset_is_an_angle(qtbot: QtBot, panel: PropertyPanel) -> None:
    _revolve(qtbot, panel)
    _choose(panel, "direction", "offset_from_face")
    end = panel.ends[""]
    assert not _hidden(panel, "end_offset") and end.options_row.isHidden()
    panel.set_start_pick({"feature": "f4"})
    panel.values["end_offset"].edit.setText("30")
    result = panel.current_feature()
    assert result is not None
    assert result.params["end_offset"] == Param("30", math.radians(30))
    assert "end_offset_reverse" not in result.params and "end_translate" not in result.params
    assert "draft_angle" not in result.params


def test_revolve_direction_2_up_to_vertex(qtbot: QtBot, panel: PropertyPanel) -> None:
    from tests.core.features.test_revolve_t16 import move_last_before, point_sketch

    doc, rev = shaft(90)
    sk, pid = point_sketch(doc, "f4", -7, 3)
    move_last_before(doc, sk, rev)
    session = _session(qtbot, doc)
    panel.begin(session, doc.feature(rev), is_new=False)
    panel.groups["direction2"].set_checked(True)
    _choose(panel, "end_condition2", "up_to_vertex")
    assert _hidden(panel, "angle2") and not _hidden(panel, "angle")
    end2 = panel.ends["2"]
    assert not end2.pick_row.isHidden()
    own = session.report.body if session.report is not None else None
    assert own is not None
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer

    mine = reference_for(own, TopExp_Explorer(own.shape, TopAbs_VERTEX).Current())
    assert mine is not None and "cannot end on geometry" in str(panel.set_start_pick(mine))
    point = {"feature": sk, "sketch_entity": pid}
    end2.pick.setCurrentIndex(end2._find(point))
    result = panel.current_feature()
    assert result is not None
    assert result.params["direction"] == "two_directions"
    assert result.params["end_condition2"] == "up_to_vertex"
    assert "end_condition" not in result.params and "angle2" not in result.params
    assert result.refs["end_ref2"] == point


def test_revolve_mid_plane_keeps_its_old_keys(qtbot: QtBot, panel: PropertyPanel) -> None:
    _revolve(qtbot, panel)
    _choose(panel, "direction", "mid_plane")
    assert not panel.groups["direction2"].isEnabled()
    result = panel.current_feature()
    assert result is not None
    assert result.params["direction"] == "mid_plane"
    assert "end_condition" not in result.params
