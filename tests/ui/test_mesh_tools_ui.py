"""Imported meshes in the app (PLAN Phase 3, PHASE3_SPEC P3.9, DECISIONS D412): Subtract from
the part in the panel, the Measure box for a mesh picked in the tree, and the cut of a
reference mesh in the section panel."""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from fdcad.core.io.mesh_import import stl_bytes
from fdcad.core.measure import Value
from fdcad.core.units import UnitSystem
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.measure.box import format_value
from fdcad.ui.property_panel.forms.print_forms import ImportMeshForm
from fdcad.ui.property_panel.panel import PropertyPanel
from tests.core.features.test_mesh_split import box_mesh
from tests.ui.test_measure_ui import _rows
from tests.ui.test_mesh_split_ui import panel  # noqa: F401  (fixture)
from tests.ui.test_phase2_flow import _folders, window  # noqa: F401  (fixtures)
from tests.ui.test_property_panel import _session


def _mesh_tab(qtbot: QtBot, window: MainWindow, tmp_path: Path) -> DocumentTab:  # noqa: F811
    path = tmp_path / "box.stl"
    path.write_bytes(stl_bytes(box_mesh(20, 30, 40)))
    window.open_path(path)
    tab = window.tabs.currentWidget()
    assert isinstance(tab, DocumentTab)
    qtbot.waitUntil(lambda: tab.session.report is not None, timeout=20000)
    return tab


def test_count_and_volume_values() -> None:
    assert format_value(Value("triangles", "count", 123456.0), UnitSystem.MM, 2) == "123,456"
    assert format_value(Value("volume", "volume", 1000.0), UnitSystem.MM, 1) == "1000.0 mm^3"
    assert format_value(Value("volume", "volume", 25.4**3), UnitSystem.IN, 2) == "1.00 in^3"


def test_subtract_from_the_part_in_the_panel(qtbot: QtBot, panel: PropertyPanel) -> None:  # noqa: F811
    from fdcad.core.features.import_mesh import part_from_mesh

    doc = part_from_mesh("box.stl", stl_bytes(box_mesh()))
    session = _session(qtbot, doc)
    panel.begin(session, doc.features[-1], is_new=False)
    form = panel.form
    assert isinstance(form, ImportMeshForm)
    assert form.subtract.isHidden()  # only for a converted mesh
    form.convert.setChecked(True)
    assert not form.subtract.isHidden()
    form.merge.setChecked(True)
    form.subtract.setChecked(True)  # Merge and Subtract exclude each other
    assert not form.merge.isChecked()
    result = panel.current_feature()
    assert result is not None
    assert result.params["subtract"] is True and "merge" not in result.params
    form.convert.setChecked(False)
    result = panel.current_feature()
    assert result is not None and "subtract" not in result.params
    panel.reject()


def test_measure_a_mesh_picked_in_the_tree(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    tab = _mesh_tab(qtbot, window, tmp_path)
    fid = tab.session.document.features[-1].id
    assert window.commands.trigger("evaluate.measure")
    assert _rows(window) == {}
    assert window.tree is not None
    window.tree.select(fid)
    rows = _rows(window)
    assert rows["Triangles"] == "12"
    assert rows["Size X, Y, Z"] == "20.00, 30.00, 40.00 mm"
    assert rows["Area"] == f"{2 * (600 + 800 + 1200):.2f} mm^2"
    assert rows["Volume"] == "24000.00 mm^3"
    box = window.measure_tool.box
    assert box is not None and box.picks.count() == 1
    window.measure_tool.close()


def test_section_panel_reports_the_mesh_cut(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    from fdcad.core.section import SectionState
    from fdcad.ui.section.tool import mesh_lines

    tab = _mesh_tab(qtbot, window, tmp_path)
    tool = window.section_tool
    tool.open(tab)
    side = tool.panel
    assert side is not None
    # The default Front plane (the XY plane) touches the box's bottom, so move it up 10 mm.
    side.rows[0].offset.edit.setText("10")
    qtbot.waitUntil(lambda: not side.mesh_info.isHidden(), timeout=5000)
    text = side.mesh_info.text()
    assert "Mesh 1: cut area 600.00 mm^2, outline 100.00 mm." in text
    lines = mesh_lines(tab, SectionState())
    assert all(isinstance(line, str) for line in lines)
    tool.turn_off(tab)
    assert tool.panel is None


def test_export_of_a_reference_mesh_says_to_convert_it(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    """Export of a part showing an imported mesh said "The part is empty"."""
    from fdcad.ui import strings

    tab = _mesh_tab(qtbot, window, tmp_path)
    name = tab.session.document.features[-1].name
    window.export("stl", tmp_path / "out.stl")
    assert window.status.text() == strings.EXPORT_MESH_ONLY.format(name=name)
    assert "Convert to Solid" in window.status.text()
    assert not (tmp_path / "out.stl").exists()
