"""Property panel layout and behaviour (PHASE1_CORRECTIONS L3, WORKFLOW_SPEC W6.1 to W6.5)."""

import copy

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Document, Feature
from fdcad.core.units import UnitSystem
from fdcad.ui.property_panel.panel import PropertyPanel, typed_length
from fdcad.ui.session import DocumentSession
from tests.core.features.test_features import plate, shaft


def _session(qtbot: QtBot, doc: Document) -> DocumentSession:
    session = DocumentSession(doc)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.request_rebuild()
    return session


def _new_from_last(session: DocumentSession) -> Feature:
    """Take the last feature out of the document, as if it were being created."""
    return session.document.features.pop()


@pytest.fixture
def panel(qtbot: QtBot) -> PropertyPanel:
    widget = PropertyPanel()
    qtbot.addWidget(widget)
    return widget


def test_extrude_layout_groups_and_tooltips(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, ext = plate()
    session = _session(qtbot, doc)
    panel.begin(session, doc.feature(ext), is_new=False)
    assert panel.title.text() == doc.feature(ext).name
    assert panel.ok_button.toolTip() and panel.cancel_button.toolTip()
    assert list(panel.groups) == [
        "from",
        "direction1",
        "direction2",
        "regions",
        "thin",
        "favourites",
    ]  # TR326
    assert panel.groups["direction1"].is_expanded()
    assert not panel.groups["direction2"].is_checked()
    assert not panel.groups["direction2"].is_expanded()  # folded until ticked
    assert not panel.groups["thin"].is_checked()  # Phase 2 Thin Feature, off by default
    end = panel.choices["end_condition"]
    items = [end.itemData(i) for i in range(end.count())]
    # A boss without a body: no Through All, Through All Both, Up to Next or Up to Body.
    assert items == ["blind", "up_to_vertex", "up_to_face", "offset_from_face", "mid_plane"]
    for widget in [*panel.values.values(), *panel.choices.values(), *panel.flags.values()]:
        assert isinstance(widget, QWidget) and widget.toolTip(), widget
    assert panel.sketch_box.toolTip()


def test_cut_offers_through_all_and_hides_depth(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, ext = plate()
    session = _session(qtbot, doc)
    feature = copy.deepcopy(doc.feature(ext))
    feature.params["operation"] = "cut"
    panel.begin(session, feature, is_new=True)
    end = panel.choices["end_condition"]
    end.setCurrentIndex(end.findData("through_all"))
    assert panel.values["depth"].parentWidget().isHidden()
    assert panel.groups["direction2"].isEnabled()  # D141: only Mid Plane rules it out
    end.setCurrentIndex(end.findData("mid_plane"))
    assert not panel.groups["direction2"].isEnabled()
    end.setCurrentIndex(end.findData("through_all"))
    result = panel.current_feature()
    assert result is not None and result.params["end_condition"] == "through_all"


def test_direction2_tick_sets_two_directions(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, ext = plate()
    session = _session(qtbot, doc)
    panel.begin(session, doc.feature(ext), is_new=False)
    seen: list[object] = []
    panel.values_changed.connect(seen.append)
    panel.groups["direction2"].set_checked(True)
    assert panel.groups["direction2"].is_expanded()
    panel.values["depth2"].edit.setText("3")
    feature = seen[-1]
    assert isinstance(feature, Feature)
    assert feature.params["end_condition"] == "two_directions"
    assert feature.params["depth2"].value == pytest.approx(3.0)  # type: ignore[union-attr]
    panel.groups["direction2"].set_checked(False)
    feature = panel.current_feature()
    assert feature is not None and "depth2" not in feature.params
    assert feature.params["end_condition"] == "blind"


def test_values_changed_on_every_change_and_none_when_wrong(
    qtbot: QtBot, panel: PropertyPanel
) -> None:
    doc, ext = plate()
    session = _session(qtbot, doc)
    seen: list[object] = []
    panel.values_changed.connect(seen.append)
    panel.begin(session, doc.feature(ext), is_new=False)
    assert len(seen) == 1  # the opening values, so the preview shows at once
    panel.values["depth"].edit.setText("2in")
    assert seen[-1].params["depth"].value == pytest.approx(50.8)  # type: ignore[attr-defined]
    panel.flags["reverse"].setChecked(True)
    assert seen[-1].params["reverse"] is True  # type: ignore[attr-defined]
    panel.values["depth"].edit.setText("2 parsecs")
    assert seen[-1] is None
    assert session.document.feature(ext).params["depth"].value == 10.0  # type: ignore[union-attr]


def test_drag_value_and_typed_value_stay_in_sync(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, ext = plate()
    session = _session(qtbot, doc)
    panel.begin(session, doc.feature(ext), is_new=False)
    panel.set_length("depth", 17.256)
    assert panel.values["depth"].edit.text() == "17.256"
    assert panel.values["depth"].info.text() == "= 17.26 mm"
    assert typed_length(25.4, UnitSystem.IN) == "1"
    active: list[str] = []
    panel.active_changed.connect(active.append)
    panel.groups["direction2"].set_checked(True)
    panel.set_length("depth2", 4.0)
    assert active == ["depth2"] and panel.active_param == "depth2"


def test_enter_accepts_with_one_undoable_command(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, _ext = plate()
    session = _session(qtbot, doc)
    feature = _new_from_last(session)
    finished: list[bool] = []
    panel.finished.connect(lambda: finished.append(True))
    panel.begin(session, feature, is_new=True)
    panel.values["depth"].edit.setText("12")
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        qtbot.keyClick(panel.values["depth"].edit, Qt.Key.Key_Return)
    assert finished == [True] and not panel.is_editing
    assert session.document.features[-1].params["depth"].value == 12.0  # type: ignore[union-attr]
    assert session.undo.count() == 1


def test_ok_after_undo_removed_the_feature_does_not_raise(
    qtbot: QtBot, panel: PropertyPanel
) -> None:
    # Bug hunt E7: Undo while editing a feature could remove it from the part;
    # OK then raised KeyError in the edit command.
    from fdcad.ui.commands.document import AddFeature

    doc, _ext = plate()
    session = _session(qtbot, doc)
    feature = _new_from_last(session)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.push(AddFeature(session, feature))
    panel.begin(session, session.document.feature(feature.id), is_new=False)
    panel.values["depth"].edit.setText("20")
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.undo()
    panel.accept()
    assert panel.is_editing
    assert "Cancel" in panel.message.text() and feature.name in panel.message.text()
    assert all(f.id != feature.id for f in session.document.features)
    assert session.undo.count() == 1 and session.undo.index() == 0


def test_new_cut_on_a_face_reverses_only_an_extrude() -> None:
    # Bug hunt E8: a new Revolved Cut on a face started with Reverse direction
    # pressed, which only flips which way the profile turns.
    from fdcad.core.sketch.model import Sketch, sketch_to_data
    from fdcad.ui.main_window.new_feature import new_feature

    doc, ext = plate()
    sketch = Feature(
        doc.new_feature_id(),
        "sketch",
        "Sketch 2",
        refs={"plane": {"kind": "face", "name": f"{ext}/cap/end"}},
        data=sketch_to_data(Sketch()),
    )
    doc.features.append(sketch)
    assert new_feature(doc, sketch, "extrude", "cut").params["reverse"] is True
    assert new_feature(doc, sketch, "revolve", "cut").params["reverse"] is False


def test_escape_rejects_without_changes(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, ext = plate()
    session = _session(qtbot, doc)
    panel.begin(session, doc.feature(ext), is_new=False)
    panel.values["depth"].edit.setText("99")
    qtbot.keyClick(panel.values["depth"].edit, Qt.Key.Key_Escape)
    assert not panel.is_editing
    assert session.undo.count() == 0
    assert session.document.feature(ext).params["depth"].value == 10.0  # type: ignore[union-attr]


def test_revolve_picks_the_only_centerline(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, _rev = shaft(360)
    session = _session(qtbot, doc)
    feature = _new_from_last(session)
    axis = feature.refs.pop("axis")["sketch_entity"]
    panel.begin(session, feature, is_new=True)
    assert "axis" in panel.groups and panel.axis_box.toolTip()
    assert panel.axis_box.currentData() == axis
    assert list(panel.choices) == ["direction", "end_condition2"]  # T16 item 2
    result = panel.current_feature()
    assert result is not None and result.params["direction"] == "one_direction"
    assert result.refs["axis"] == {"sketch_entity": axis}
    lines = [panel.axis_box.itemData(i) for i in range(panel.axis_box.count())]
    assert panel.set_axis(lines[-1]) and panel.axis_box.currentData() == lines[-1]
    assert not panel.set_axis("nope")


def test_merge_shown_only_for_a_boss_on_a_part(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, ext = plate()
    session = _session(qtbot, doc)
    panel.begin(session, doc.feature(ext), is_new=False)  # the first body: nothing to merge
    assert panel.flags["merge"].isHidden()
    second = copy.deepcopy(doc.feature(ext))
    second.id = "new"
    panel.begin(session, second, is_new=True)
    assert not panel.flags["merge"].isHidden()
    panel.flags["merge"].setChecked(False)
    result = panel.current_feature()
    assert result is not None and result.params["merge"] is False


def test_revolve_without_an_axis_says_pick_the_axis(qtbot: QtBot, panel: PropertyPanel) -> None:
    """T6.2.3: with no axis chosen the panel says "Pick the axis of revolution"."""
    doc, _rev = shaft(360)
    session = _session(qtbot, doc)
    feature = _new_from_last(session)
    feature.refs.pop("axis")
    panel.begin(session, feature, is_new=True)
    panel.axis_box.setCurrentIndex(-1)
    assert panel.current_feature() is None
    assert panel.message.text().startswith("Pick the axis of revolution")
    assert panel.axis_box.placeholderText().startswith("Pick the axis of revolution")


def test_up_to_face_lists_user_planes(qtbot: QtBot, panel: PropertyPanel) -> None:
    """Audit B item 4 (D718): only the three default planes were offered."""
    from fdcad.core.document.model import Feature, Param

    doc, ext = plate()
    ref = Feature(
        "f99",
        "ref_plane",
        "Plane 1",
        params={"method": "offset", "distance": Param("30", 30.0)},
        refs={"first": {"feature": "f3"}},
    )
    doc.features.insert(doc.features.index(doc.feature(ext)), ref)
    session = _session(qtbot, doc)
    panel.begin(session, doc.feature(ext), is_new=False)
    end = panel.choices["end_condition"]
    end.setCurrentIndex(end.findData("up_to_face"))
    pick = panel.ends[""].pick
    labels = [pick.itemText(i) for i in range(pick.count())]
    assert "Plane 1" in labels
    panel.reject()


def test_revolve_of_a_sketch_without_lines_says_add_a_centerline(
    qtbot: QtBot, panel: PropertyPanel
) -> None:
    """Audit B item 6 (D729): the centerline message was never shown."""
    from fdcad.core.sketch.model import Sketch, sketch_to_data

    doc, _rev = shaft(360)
    session = _session(qtbot, doc)
    feature = _new_from_last(session)
    feature.refs.pop("axis")
    sketch = doc.feature(feature.refs["sketch"]["feature"])
    only_circle = Sketch()
    only_circle.add_circle(20, 20, 5)
    sketch.data.update(sketch_to_data(only_circle))
    panel.begin(session, feature, is_new=True)
    panel.axis_box.setCurrentIndex(-1)
    assert panel.current_feature() is None
    assert "no centerline" in panel.message.text()


def test_extrude_along_a_picked_edge(qtbot: QtBot) -> None:
    """Along and Depth measured in the extrude panel (TR239, D815)."""
    from fdcad.core.document.model import new_document
    from fdcad.core.sketch.model import Sketch
    from fdcad.ui.main_window.new_feature import new_feature
    from fdcad.ui.property_panel.panel import PropertyPanel
    from tests.core.features.test_features import add_sketch, rect

    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 10, 10)
    sid = add_sketch(doc, s, {"feature": "f2"})
    session = _session(qtbot, doc)
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    panel.begin(session, new_feature(doc, doc.feature(sid), "extrude", "boss"), is_new=True)
    box = panel.direction_box
    assert box is not None and box.currentData() is None
    box.setCurrentIndex(box.findData("pick"))
    assert panel.end_wants_pick()
    assert panel.set_start_pick({"kind": "face", "name": "x"}) is not None  # not an edge
    assert panel.set_start_pick({"kind": "edge", "name": "edge(a|b)"}) is None
    along = panel.depth_along_box
    assert along is not None
    along.setCurrentIndex(along.findData("normal"))
    made = panel.current_feature()
    assert made is not None
    assert made.refs["direction"] == {"kind": "edge", "name": "edge(a|b)"}
    assert made.params["depth_along"] == "normal"
    box.setCurrentIndex(0)
    made = panel.current_feature()
    assert made is not None and "direction" not in made.refs


def test_curve_through_points_panel(qtbot: QtBot, tmp_path: object) -> None:
    """Type, load and pick points (TR61, D817)."""
    from pathlib import Path

    from fdcad.core.document.model import new_document
    from fdcad.ui.main_window.new_feature import phase2_feature
    from fdcad.ui.property_panel.forms.point_curve_form import PointCurveForm
    from fdcad.ui.property_panel.panel import PropertyPanel

    doc = new_document()
    session = _session(qtbot, doc)
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    panel.begin(session, phase2_feature(doc, "point_curve", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, PointCurveForm)
    target = Path(str(tmp_path)) / "pts.txt"
    target.write_text("x y z\n0 0 0\n0 0 10\n5 0 20\n", encoding="utf-8")
    form.file = str(target)
    assert form.reload() and form.table.rowCount() == 3
    form.closed.setChecked(True)
    made = panel.current_feature()
    assert made is not None
    assert made.data["points"] == [[0, 0, 0], [0, 0, 10], [5, 0, 20]]
    assert made.params["closed"] is True and made.data["file"] == str(target)
    form.picks.add({"kind": "vertex", "name": "vertex(a|b|c)"})
    made = panel.current_feature()
    assert made is not None and "points" not in made.data and made.refs["points"]
