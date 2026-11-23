"""Mesh import and split for printing in the app (PHASE3_SPEC P3.9): open or insert a
mesh, the large mesh warning in the status bar, Convert to Solid from the panel,
and the split panel's values."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.features.base import FeatureState
from fdcad.core.io.mesh_import import stl_bytes
from fdcad.ui.main_window.new_feature import phase2_feature
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.property_panel.forms.base import REMEMBERED
from fdcad.ui.property_panel.forms.print_forms import ImportMeshForm, SplitForPrintForm
from fdcad.ui.property_panel.panel import PropertyPanel
from tests.core.features.test_features import plate
from tests.core.features.test_mesh_split import box_mesh
from tests.ui.test_phase2_flow import _folders, plate_tab, window
from tests.ui.test_property_panel import _session

__all__ = ["_folders", "window"]


@pytest.fixture
def panel(qtbot: QtBot) -> PropertyPanel:
    REMEMBERED.clear()
    widget = PropertyPanel()
    qtbot.addWidget(widget)
    return widget


def _stl(tmp_path: Path) -> Path:
    path = tmp_path / "box.stl"
    path.write_bytes(stl_bytes(box_mesh()))
    return path


def test_open_mesh_as_a_new_part(qtbot: QtBot, window: MainWindow, tmp_path: Path) -> None:
    window.open_path(_stl(tmp_path))
    tab = window.tabs.currentWidget()
    assert isinstance(tab, DocumentTab)
    session = tab.session
    qtbot.waitUntil(lambda: session.report is not None)
    feature = session.document.features[-1]
    assert feature.type == "import_mesh"
    qtbot.waitUntil(lambda: "box.stl imported" in window.status.text())
    report = session.report
    assert report is not None and report.results[feature.id].extras["triangles"] == 12


def test_large_mesh_warns_in_the_status_bar(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fdcad.core.features import import_mesh

    monkeypatch.setattr(import_mesh, "TRIANGLE_WARNING", 10)
    tab, _ext = plate_tab(qtbot, window)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        fid = window.import_flow.insert(_stl(tmp_path))
    assert fid is not None
    qtbot.waitUntil(lambda: "more than 10" in window.status.text())
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.undo()
    assert tab.session.document.embedded == {}


def test_convert_to_solid_from_the_panel(
    qtbot: QtBot, panel: PropertyPanel, tmp_path: Path
) -> None:
    from fdcad.core.features.import_mesh import part_from_mesh

    doc = part_from_mesh("box.stl", stl_bytes(box_mesh()))
    session = _session(qtbot, doc)
    feature = doc.features[-1]
    panel.begin(session, feature, is_new=False)
    form = panel.form
    assert isinstance(form, ImportMeshForm)
    assert form.count.text() == "12 triangles"
    assert form.merge.isHidden()
    form.convert.setChecked(True)
    assert not form.merge.isHidden()
    result = panel.current_feature()
    assert result is not None and result.params["convert"] is True
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        panel.accept()
    report = session.report
    assert report is not None and report.body is not None
    assert report.results[feature.id].state is FeatureState.OK
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.undo()
    assert "convert" not in doc.features[-1].params


def test_split_panel(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, _ext = plate(10.0)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "split_for_print", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, SplitForPrintForm)
    assert panel.title.text() == "Print Split 1"
    assert form.fields["build_x"].param().value == pytest.approx(220.0)
    assert form.planes.isHidden()
    form.fields["build_x"].edit.setText("30")
    form.connector.setCurrentIndex(form.connector.findData("pins"))
    form.fields["pin_diameter"].edit.setText("3")
    form.fields["pin_length"].edit.setText("6")
    assert form.fields["key_width"].parentWidget().isHidden()
    result = panel.current_feature()
    assert result is not None
    assert result.params["mode"] == "auto" and result.params["connector"] == "pins"
    assert result.params["build_x"].value == pytest.approx(30.0)
    assert "key_width" not in result.params
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        panel.accept()
    report = session.report
    assert report is not None and report.body_count == 4
    panel.begin(session, phase2_feature(doc, "split_for_print", "boss"), is_new=True)
    form = panel.form
    form.mode.setCurrentIndex(form.mode.findData("planes"))
    assert panel.current_feature() is None  # no planes picked yet
    form._add_plane(form.plane_choice.findData({"feature": "f3"}))
    result = panel.current_feature()
    assert result is not None and result.refs["planes"] == [{"feature": "f3"}]
    panel.reject()


def test_split_panel_sketch_path_and_key_draft(qtbot: QtBot, panel: PropertyPanel) -> None:
    """TR181 (D2002): Along Sketch picks a path sketch; dovetails get a key draft."""
    doc, _ext = plate(10.0)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "split_for_print", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, SplitForPrintForm)
    assert form.path.isHidden()
    form.mode.setCurrentIndex(form.mode.findData("sketch"))
    assert not form.path.isHidden() and form.planes.isHidden()
    assert panel.current_feature() is None  # no sketch yet
    sketch_id = doc.features[-2].id  # the plate's sketch
    form.path.setCurrentIndex(form.path.findData(sketch_id))
    form.connector.setCurrentIndex(form.connector.findData("dovetail"))
    assert not form.fields["key_draft"].parentWidget().isHidden()
    result = panel.current_feature()
    assert result is not None and result.refs["path"] == [{"feature": sketch_id}]
    assert "key_draft" not in result.params  # zero is not written
    form.fields["key_draft"].edit.setText("2")
    result = panel.current_feature()
    assert result is not None and result.params["key_draft"].value > 0
    panel.reject()


def test_split_panel_picks_bodies_to_cut(qtbot: QtBot, panel: PropertyPanel) -> None:
    """Parts with several bodies show Bodies to Cut; ticked, clicks pick bodies (D621)."""
    from fdcad.core.rebuild.runner import rebuild
    from fdcad.core.sketch.model import Sketch
    from fdcad.ui.strings_import import SPLIT_FACES_ONLY, SPLIT_NEEDS_BODIES
    from tests.core.features.test_features import add_extrude, add_sketch, rect
    from tests.ui.test_chamfer_panel import edges_of

    doc, ext = plate(10.0)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "split_for_print", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, SplitForPrintForm)
    assert form.body_group.isHidden()  # one body: nothing to choose
    panel.reject()

    s = Sketch()
    rect(s, 100, 0, 150, 50)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0, merge=False)
    session = _session(qtbot, doc)
    part = rebuild(doc)[doc.features[-1].id].body
    assert part is not None
    panel.begin(session, phase2_feature(doc, "split_for_print", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, SplitForPrintForm)
    assert not form.body_group.isHidden() and not form.body_group.is_checked()
    top = part.face(f"{ext}/cap/end")
    form.mode.setCurrentIndex(form.mode.findData("planes"))
    form.take_shapes(part, [top])
    assert len(form.planes.refs()) == 1 and not form.bodies.refs()
    form.body_group.set_checked(True)
    assert panel.current_feature() is None
    assert form.apply(phase2_feature(doc, "split_for_print", "boss")) == SPLIT_NEEDS_BODIES
    form.take_shapes(part, [top])
    assert len(form.bodies.refs()) == 1
    assert form.take_shapes(part, edges_of(top)[:1]) == SPLIT_FACES_ONLY
    result = panel.current_feature()
    assert result is not None and len(result.refs["bodies"]) == 1
    panel.reject()


def test_build_volume_message_counts_bodies() -> None:
    """With several bodies the message speaks of bodies, not the part (D622)."""
    from fdcad.core.printing.orientation import FitResult
    from fdcad.ui.print_tools.build_volume import BuildVolume, VolumeResult

    tool = BuildVolume.__new__(BuildVolume)
    tool.printer = "Small"
    fits = FitResult((60.0, 60.0, 10.0), (80.0, 80.0, 50.0), (), 2, 0)
    text = tool.message(VolumeResult(fits, None, None, ""), "mm")
    assert text.startswith("Each of the 2 bodies fits Small: the largest is 60.0 x 60.0")
    big = FitResult((90.0, 60.0, 10.0), (80.0, 80.0, 50.0), ("X",), 3, 1)
    text = tool.message(VolumeResult(big, None, None, ""), "mm")
    assert (
        text.startswith("Bodies too large for Small: 1 of 3. The largest is 90.0")
        and "(X too large)" in text
    )


@pytest.fixture
def _shop_printer(tmp_path: Path) -> object:
    from PySide6.QtCore import QSettings

    from fdcad.core.printing.profiles import GENERIC, PrinterProfile
    from fdcad.ui.preferences import phase4_settings as prefs
    from fdcad.ui.preferences import print_settings
    from fdcad.ui.preferences.settings import Settings

    prefs.OVERRIDE = Settings(QSettings(str(tmp_path / "shop.ini"), QSettings.Format.IniFormat))
    shop = PrinterProfile("Shop", bed_x=150.0, bed_y=140.0, height=160.0, fit_tolerance=0.35)
    print_settings.set_profiles(prefs.OVERRIDE, [GENERIC, shop], "Shop")
    yield shop
    prefs.OVERRIDE = None


def test_a_new_split_uses_the_active_printer(
    qtbot: QtBot, panel: PropertyPanel, _shop_printer: object
) -> None:
    """Spec 2 section 20 item 17 (D714): the build size and clearance were fixed."""
    REMEMBERED.clear()
    doc, _ext = plate(10.0)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "split_for_print", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, SplitForPrintForm)
    sizes = [form.fields[k].param().value for k in ("build_x", "build_y", "build_z")]
    assert sizes == pytest.approx([150.0, 140.0, 160.0])
    assert form.fields["clearance"].param().value == pytest.approx(0.35)
    panel.reject()


def test_import_mesh_panel_asks_the_file_unit(qtbot: QtBot, panel: PropertyPanel) -> None:
    """Audit D item 7 (D715): STL and OBJ were always read as millimetres."""
    from fdcad.core.features.import_mesh import part_from_mesh

    doc = part_from_mesh("box.stl", stl_bytes(box_mesh()))
    session = _session(qtbot, doc)
    panel.begin(session, doc.features[-1], is_new=False)
    form = panel.form
    assert isinstance(form, ImportMeshForm)
    assert not form.unit.isHidden() and form.unit.currentData() == "mm"
    form.unit.setCurrentIndex(form.unit.findData("in"))
    result = panel.current_feature()
    assert result is not None and result.params["file_unit"] == "in"
    panel.reject()


def test_import_mesh_panel_offers_slicer_parts(
    qtbot: QtBot, panel: PropertyPanel, tmp_path: Path
) -> None:
    """TR386 (D1205): a converted 3MF can make one body per part and keep roles."""
    from fdcad.core.features.import_mesh import part_from_mesh
    from fdcad.core.io.export import export_3mf
    from tests.core.io.test_3mf_conformance import _two_boxes

    out = tmp_path / "parts.3mf"
    export_3mf(_two_boxes(), out)
    doc = part_from_mesh("parts.3mf", out.read_bytes())
    session = _session(qtbot, doc)
    panel.begin(session, doc.features[-1], is_new=False)
    form = panel.form
    assert isinstance(form, ImportMeshForm)
    assert form.parts.isHidden()  # only for a converted mesh
    form.convert.setChecked(True)
    assert not form.parts.isHidden() and form.keep_roles.isHidden()
    form.parts.setChecked(True)
    form.keep_roles.setChecked(True)
    result = panel.current_feature()
    assert result is not None
    assert result.params["parts"] is True and result.params["keep_roles"] is True
    panel.reject()


def test_split_panel_offers_magnets_screws_and_a_glue_gap(
    qtbot: QtBot, panel: PropertyPanel
) -> None:
    """TR181 (D1211)."""
    doc, _ext = plate(10.0)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "split_for_print", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, SplitForPrintForm)
    form.connector.setCurrentIndex(form.connector.findData("screws"))
    assert not form.fields["nut_size"].parentWidget().isHidden()
    assert form.fields["magnet_depth"].parentWidget().isHidden()
    result = panel.current_feature()
    assert result is not None
    assert result.params["connector"] == "screws" and "nut_height" in result.params
    assert "glue_gap" not in result.params  # zero: not written
    form.fields["glue_gap"].edit.setText("0.2")
    result = panel.current_feature()
    assert result is not None and result.params["glue_gap"].value == pytest.approx(0.2)
    panel.reject()


def test_import_mesh_panel_repairs_and_reduces(qtbot: QtBot, panel: PropertyPanel) -> None:
    """TR186 (D1212)."""
    from fdcad.core.features.import_mesh import part_from_mesh

    doc = part_from_mesh("box.stl", stl_bytes(box_mesh()))
    session = _session(qtbot, doc)
    panel.begin(session, doc.features[-1], is_new=False)
    form = panel.form
    assert isinstance(form, ImportMeshForm)
    assert form.reduce_value.isHidden()
    form.repair.setChecked(True)
    form.reduce_mode.setCurrentIndex(form.reduce_mode.findData("percent"))
    form.reduce_value.setValue(40)
    form.keep_boundary.setChecked(True)
    result = panel.current_feature()
    assert result is not None
    assert result.params["repair"] is True and result.params["reduce_percent"] == 40
    assert result.params["keep_boundary"] is True and "reduce_error" not in result.params
    panel.reject()
