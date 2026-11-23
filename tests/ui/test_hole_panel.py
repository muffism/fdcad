"""Hole Tool panel (PHASE4_SPEC P4.1): tabs, table values, click placement, existing
sketches, the insert table, the Favourites box and undo."""

from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Line, Sketch
from fdcad.ui.main_window.new_feature import phase2_feature
from fdcad.ui.preferences import phase4_settings as prefs
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.property_panel.forms.base import REMEMBERED
from fdcad.ui.property_panel.forms.hole_form import HoleForm, InsertTableDialog
from fdcad.ui.property_panel.panel import PropertyPanel
from tests.core.features.test_features import add_sketch, body, plate, volume
from tests.core.features.test_hole import face_ref
from tests.ui.test_property_panel import _session


@pytest.fixture(autouse=True)
def temp_prefs(tmp_path: Path) -> Any:
    prefs.OVERRIDE = Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))
    yield
    prefs.OVERRIDE = None


@pytest.fixture
def panel(qtbot: QtBot) -> PropertyPanel:
    REMEMBERED.clear()
    widget = PropertyPanel()
    qtbot.addWidget(widget)
    return widget


def _open(qtbot: QtBot, panel: PropertyPanel) -> tuple[Any, str, HoleForm]:
    doc, ext = plate()
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "hole", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, HoleForm)
    return session, ext, form


def test_type_tab_fills_from_the_tables(qtbot: QtBot, panel: PropertyPanel) -> None:
    _s, _ext, form = _open(qtbot, panel)
    assert form.tabs.currentIndex() == 0
    assert form.fields["diameter"].param() is not None
    assert form.fields["diameter"].param().value == pytest.approx(5.5)  # type: ignore[union-attr]
    form.choice_boxes["hole_type"].setCurrentIndex(
        form.choice_boxes["hole_type"].findData("counterbore")
    )
    assert form.fields["cbore_diameter"].param().value == pytest.approx(9.5)  # type: ignore[union-attr]
    assert form.shown("cbore_depth") and not form.shown("csk_diameter")
    form.choice_boxes["standard"].setCurrentIndex(form.choice_boxes["standard"].findData("ansi"))
    assert form.choice_boxes["size"].currentData() == "#0-80"  # smallest first (D786)
    form.choice_boxes["hole_type"].setCurrentIndex(
        form.choice_boxes["hole_type"].findData("heat_set_insert")
    )
    assert form.choice_boxes["size"].findData("M3") >= 0
    assert not form.inserts_button.isHidden()


def test_positions_by_clicking_then_accept_and_undo(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, ext, form = _open(qtbot, panel)
    report = session.report
    assert report is not None and report.body is not None
    top = report.body.face(f"{ext}/cap/end")
    assert not form.take_point(report.body, [top], (10.0, 10.0, 10.0))  # Type tab open
    form.tabs.setCurrentIndex(1)
    assert form.take_point(report.body, [top], (10.0, 10.0, 10.0))
    assert form.take_point(report.body, [top], (40.0, 25.0, 10.0))
    assert form.table.rowCount() == 2 and form.count.text().startswith("2")
    form.table.item(1, 1).setText("30")
    feature = panel.current_feature()
    assert feature is not None and feature.refs["face"][0]["name"] == f"{ext}/cap/end"
    assert "positions" in feature.data and "plane" in feature.refs
    count = len(session.document.features)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        panel.accept()
    doc = session.document
    assert len(doc.features) == count + 1
    hole = doc.features[-1]
    b = body(rebuild(doc), hole.id)
    assert volume(b.shape) < 25000 - 2 * 3.14 * 2.75**2 * 9.9
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.undo()
    assert len(doc.features) == count


def test_existing_sketch_point_kinds(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, ext = plate()
    top = face_ref(doc, ext, "cap/end")
    s = Sketch()
    a, b = s.add_point(10, 10), s.add_point(40, 10)
    lid = s.new_id()
    s.entities[lid] = Line(lid, a, b)
    s.add_point(25, 40)
    sk = add_sketch(doc, s, top)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "hole", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, HoleForm)
    form.tabs.setCurrentIndex(1)
    box = form.sketch_boxes["sketch"]
    box.setCurrentIndex(box.findData(sk))
    assert form.shown("use_ends") and form.count.text().startswith("3")
    form.checks["use_ends"].setChecked(False)
    assert form.count.text().startswith("1")
    feature = panel.current_feature()
    assert feature is not None
    assert feature.refs["sketch"] == {"feature": sk} and feature.params["use_ends"] is False
    assert "positions" not in feature.data


def test_up_to_face_needs_a_pick(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, ext, form = _open(qtbot, panel)
    box = form.choice_boxes["end_condition"]
    box.setCurrentIndex(box.findData("up_to_face"))
    report = session.report
    assert report is not None and report.body is not None
    form.tabs.setCurrentIndex(1)
    form.take_point(report.body, [report.body.face(f"{ext}/cap/end")], (5.0, 5.0, 10.0))
    assert panel.current_feature() is None
    form.tabs.setCurrentIndex(0)
    form.take_shapes(report.body, [report.body.face(f"{ext}/cap/start")])
    feature = panel.current_feature()
    assert feature is not None and feature.refs["up_to"][0]["name"] == f"{ext}/cap/start"


def test_favourites_box(qtbot: QtBot, panel: PropertyPanel, tmp_path: Path) -> None:
    _s, _ext, form = _open(qtbot, panel)
    fav = form.favourites_box
    form.fields["depth"].edit.setText("7")
    assert fav.save("Seven deep")
    assert prefs.favourites("hole")["Seven deep"]["depth"]["value"] == pytest.approx(7)
    path = tmp_path / "fav.json"
    prefs.export_favourites("hole", path)
    fav.names.setCurrentText("Seven deep")
    fav.delete_current()
    assert prefs.favourites("hole") == {}
    assert fav.import_file(str(path)) == 1
    panel.form.fields["depth"].edit.setText("3")
    assert panel.form.favourites_box.apply("Seven deep")
    assert panel.form.fields["depth"].param().value == pytest.approx(7)  # type: ignore[union-attr]
    panel.form.fields["depth"].edit.setText("8")
    panel.form.favourites_box.names.setCurrentText("Seven deep")
    assert panel.form.favourites_box.update_current()
    assert prefs.favourites("hole")["Seven deep"]["depth"]["value"] == pytest.approx(8)
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    assert panel.form.favourites_box.import_file(str(bad)) == 0


def test_insert_table_dialog(qtbot: QtBot) -> None:
    dialog = InsertTableDialog()
    qtbot.addWidget(dialog)
    rows = dialog.rows()
    assert rows[0]["name"] == "M2"
    dialog.table.item(0, 1).setText("3.4")
    prefs.set_insert_rows(dialog.rows())
    assert prefs.inserts()[0].diameter == pytest.approx(3.4)


def test_insert_table_refuses_a_bad_row(qtbot: QtBot) -> None:
    """Audit A item 19 (D739): a bad row was dropped without a word on OK."""
    dialog = InsertTableDialog()
    qtbot.addWidget(dialog)
    dialog.table.item(1, 2).setText("deep")
    dialog.table.insertRow(dialog.table.rowCount())  # an empty row is fine
    dialog.accept()
    assert dialog.result() != dialog.DialogCode.Accepted
    assert "Row(s) 2 " in dialog.problem.text()
    dialog.table.item(1, 2).setText("4")
    dialog.accept()
    assert dialog.result() == dialog.DialogCode.Accepted


def test_fit_tolerance_preference() -> None:
    assert prefs.fit_tolerance() == pytest.approx(0.2)
    prefs.set_fit_tolerance(0.15)
    assert prefs.fit_tolerance() == pytest.approx(0.15)


def test_own_position_widgets_follow_the_sketch_choice(qtbot: QtBot, panel: PropertyPanel) -> None:
    """Regression (D481): the loop that shows the table, Remove Point and hint once
    reused a widget variable for attribute names. Own positions show them; an
    existing sketch hides them."""
    doc, ext = plate()
    s = Sketch()
    s.add_point(25, 25)
    sk = add_sketch(doc, s, face_ref(doc, ext, "cap/end"))
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "hole", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, HoleForm)
    form.tabs.setCurrentIndex(1)
    own = [form.table, form.remove_point, form.hint]
    assert all(not w.isHidden() for w in own)
    box = form.sketch_boxes["sketch"]
    box.setCurrentIndex(box.findData(sk))
    assert all(w.isHidden() for w in own)
    box.setCurrentIndex(0)
    assert all(not w.isHidden() for w in own)


def test_head_forms_and_drill_names(qtbot: QtBot, panel: PropertyPanel) -> None:
    """TR253 (D786)."""
    _s, _ext, form = _open(qtbot, panel)
    boxes = form.choice_boxes
    boxes["hole_type"].setCurrentIndex(boxes["hole_type"].findData("counterbore"))
    boxes["cbore_head"].setCurrentIndex(boxes["cbore_head"].findData("button"))
    assert form.fields["cbore_diameter"].param().value == pytest.approx(10.5)  # type: ignore[union-attr]
    assert form.fields["cbore_depth"].param().value == pytest.approx(2.75)  # type: ignore[union-attr]
    assert form.drill_note.isHidden()  # 5.5 mm is not an inch drill
    boxes["standard"].setCurrentIndex(boxes["standard"].findData("ansi"))
    boxes["size"].setCurrentIndex(boxes["size"].findData("1/4-20"))
    boxes["hole_type"].setCurrentIndex(boxes["hole_type"].findData("tapped"))
    assert not form.drill_note.isHidden() and form.drill_note.text() == "Drill: #7"
    boxes["hole_type"].setCurrentIndex(boxes["hole_type"].findData("countersink"))
    assert not form.shown("csk_head")  # inch has one countersunk form


def test_magnet_pocket_fills_from_its_size_list(qtbot: QtBot, panel: PropertyPanel) -> None:
    """TR179, D869."""
    _doc, _sid, form = _open(qtbot, panel)
    form.choice_boxes["hole_type"].setCurrentIndex(
        form.choice_boxes["hole_type"].findData("magnet")
    )
    size = form.choice_boxes["size"]
    assert size.findData("Round 6 x 3") >= 0
    size.setCurrentIndex(size.findData("Block 20 x 10 x 3"))
    assert form.fields["diameter"].param().value == pytest.approx(10.0)  # type: ignore[union-attr]
    assert form.fields["magnet_length"].param().value == pytest.approx(20.0)  # type: ignore[union-attr]
    assert form.fields["depth"].param().value == pytest.approx(3.0)  # type: ignore[union-attr]
    assert form.shown("magnet_skin") and not form.shown("standard")


def test_dowel_fit_fills_the_diameter(qtbot: QtBot, panel: PropertyPanel) -> None:
    """TR252, D872."""
    _doc, _sid, form = _open(qtbot, panel)
    form.choice_boxes["hole_type"].setCurrentIndex(form.choice_boxes["hole_type"].findData("dowel"))
    size = form.choice_boxes["size"]
    size.setCurrentIndex(size.findData("6 mm"))
    assert form.fields["diameter"].param().value == pytest.approx(6.0)  # type: ignore[union-attr]
    fit = form.choice_boxes["dowel_fit"]
    fit.setCurrentIndex(fit.findData("slip"))
    assert form.fields["diameter"].param().value == pytest.approx(6.02)  # type: ignore[union-attr]


def test_bearing_seat_fills_from_the_designation(qtbot: QtBot, panel: PropertyPanel) -> None:
    """TR251, D873."""
    _doc, _sid, form = _open(qtbot, panel)
    kind = form.choice_boxes["hole_type"]
    kind.setCurrentIndex(kind.findData("bearing"))
    size = form.choice_boxes["size"]
    size.setCurrentIndex(size.findData("6001"))
    assert form.fields["cbore_diameter"].param().value == pytest.approx(28.0)  # type: ignore[union-attr]
    assert form.fields["bearing_width"].param().value == pytest.approx(8.0)  # type: ignore[union-attr]
    assert form.fields["diameter"].param().value == pytest.approx(20.0)  # type: ignore[union-attr]
    assert form.shown("bearing_groove") and form.shown("dowel_fit")


def test_size_carry_over_can_be_turned_off(qtbot: QtBot, panel: PropertyPanel) -> None:
    """TR66, D892."""
    _doc, _sid, form = _open(qtbot, panel)
    kind, size = form.choice_boxes["hole_type"], form.choice_boxes["size"]
    assert form.carry_size.isChecked()  # on by default: the size follows the type change
    size.setCurrentIndex(size.findData("M6"))
    kind.setCurrentIndex(kind.findData("counterbore"))
    assert size.currentData() == "M6"
    size.setCurrentIndex(size.findData("M4"))  # counterbore now remembers M4
    kind.setCurrentIndex(kind.findData("simple"))
    form.carry_size.setChecked(False)
    assert not prefs.size_carry_over()
    size.setCurrentIndex(size.findData("M10"))
    kind.setCurrentIndex(kind.findData("counterbore"))
    assert size.currentData() == "M4"  # its own last size, not M10


def test_bolt_circle_shorthand(qtbot: QtBot, panel: PropertyPanel) -> None:
    """TR407 (D913): the last clicked point becomes the centre of "4x20" holes."""
    import math

    session, ext, form = _open(qtbot, panel)
    report = session.report
    assert report is not None and report.body is not None
    top = report.body.face(f"{ext}/cap/end")
    form.tabs.setCurrentIndex(1)
    form.bolt_text.setText("4x20")
    assert not form.make_bolt_circle()  # no centre yet
    assert "centre" in form.hint.text()
    assert form.take_point(report.body, [top], (25.0, 15.0, 10.0))
    centre = form.own_points[0]
    form.bolt_text.setText("4 x")
    assert not form.make_bolt_circle() and form.table.rowCount() == 1
    form.bolt_text.setText("4x20")
    form.bolt_start.setText("45deg")
    assert form.make_bolt_circle()
    assert form.table.rowCount() == 4 and form.count.text().startswith("4")
    assert all(abs(math.dist(p, centre) - 10.0) < 1e-9 for p in form.own_points)
    x, y = form.own_points[0]
    assert abs(math.atan2(y - centre[1], x - centre[0]) - math.pi / 4) < 1e-9


def test_insert_depth_margin(qtbot: QtBot, panel: PropertyPanel) -> None:
    """TR189 item 4 (D935): the margin is added to the insert table depth."""
    dialog = InsertTableDialog()
    qtbot.addWidget(dialog)
    assert dialog.margin.value() == 0.0
    try:
        prefs.set_insert_margin(0.5)
        _s, _ext, form = _open(qtbot, panel)
        form.choice_boxes["hole_type"].setCurrentIndex(
            form.choice_boxes["hole_type"].findData("heat_set_insert")
        )
        form.choice_boxes["size"].setCurrentIndex(form.choice_boxes["size"].findData("M3"))
        form.fill_from_table()
        depth = form.fields["depth"].param()
        assert depth is not None and depth.value == pytest.approx(5.7 + 0.5)
        assert InsertTableDialog().margin.value() == 0.5
    finally:
        prefs.set_insert_margin(0.0)


def test_place_by_two_edges_makes_one_hole(qtbot: QtBot, panel: PropertyPanel) -> None:
    """TR143 item 1 (D1911): no sketch, the face and two edges, then the distances."""
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer

    session, ext, form = _open(qtbot, panel)
    report = session.report
    assert report is not None and report.body is not None
    top = report.body.face(f"{ext}/cap/end")
    form.tabs.setCurrentIndex(1)
    box = form.choice_boxes["place_by"]
    box.setCurrentIndex(box.findData("edges"))
    assert form.table.isHidden()
    assert not form.take_point(report.body, [top], (10.0, 10.0, 10.0))
    form.take_shapes(report.body, [top])
    edges = []
    ex = TopExp_Explorer(top, TopAbs_EDGE)
    while ex.More():
        edges.append(ex.Current())
        ex.Next()
    form.picks["place_edges"].list.setFocus()
    from fdcad.core.naming.select import reference_for

    for e in edges[:2]:
        ref = reference_for(report.body, e)
        assert ref is not None
        form.picks["place_edges"].add(ref)
    feature = panel.current_feature()
    assert feature is not None, form.apply(feature) if feature else None
    assert feature.params["place_by"] == "edges"
    assert len(feature.refs["place_edges"]) == 2
    assert feature.refs["plane"]["name"] == f"{ext}/cap/end"
    assert "positions" not in feature.data


def test_load_user_sizes_fills_the_user_standard(
    qtbot: QtBot, panel: PropertyPanel, tmp_path: Path
) -> None:
    """TR144 item 4 (D1914)."""
    from fdcad.core.features import hole_data

    _s, _ext, form = _open(qtbot, panel)
    bad = tmp_path / "bad.csv"
    bad.write_text("size\nx\n", encoding="utf-8")
    assert "could not be read" in form.load_user_sizes(str(bad))
    good = tmp_path / "sizes.csv"
    good.write_text("name,diameter\nM7,7\nM9,9\n", encoding="utf-8")
    assert form.load_user_sizes(str(good)).startswith("2 user hole sizes")
    box = form.choice_boxes["standard"]
    box.setCurrentIndex(box.findData("user"))
    sizes = form.choice_boxes["size"]
    assert [sizes.itemData(i) for i in range(sizes.count())][:2] == ["M7", "M9"]
    assert prefs.user_hole_text().startswith("name,diameter")
    hole_data.USER_SIZES[:] = []


def test_place_by_radial_shows_its_fields(qtbot: QtBot, panel: PropertyPanel) -> None:
    """TR397 item 1 (D1915)."""
    _s, _ext, form = _open(qtbot, panel)
    form.tabs.setCurrentIndex(1)
    box = form.choice_boxes["place_by"]
    box.setCurrentIndex(box.findData("radial"))
    values = form.values()
    assert form.shown("radial_distance", values) and form.shown("radial_angle", values)
    assert not form.shown("place_edges", values) and form.shown("hole_axis", values)
    box.setCurrentIndex(box.findData("point"))
    assert form.shown("at_point", form.values())


def test_fit_from_table_by_size_and_direction(qtbot: QtBot, panel: PropertyPanel) -> None:
    """TR412 (D1919)."""
    _s, ext, form = _open(qtbot, panel)
    assert "could not be read" in form.edit_fit_table("hole sideways 6 0.25")
    assert form.edit_fit_table("hole upright 6 0.25\nhole flat 6 0.15").startswith("Fit table")
    form.picks["face"].set_refs([{"kind": "face", "name": f"{ext}/cap/end"}])
    note = form.use_fit_table()
    assert "upright hole up to 6 mm" in note and "slicer" in note
    assert form.fields["fit_tolerance"].param().value == pytest.approx(0.25)  # type: ignore[union-attr]
    form.fields["diameter"].edit.setText("8")
    assert "No table row fits" in form.use_fit_table()
    prefs.set_fit_table_text("")
