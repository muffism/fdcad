"""Sheet Metal tab, panels, flatten toggle, bend table and flat export (PHASE5_SPEC)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Document, Feature, new_document
from fdcad.core.features import REGISTRY
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.samples.builder import FRONT, SketchBuilder, add_sketch
from fdcad.samples.make import measure
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.session import DocumentSession
from fdcad.ui.sheet_metal import flow
from fdcad.ui.sheet_metal.forms import EDGE_FLANGE, SHEET_FORMS
from fdcad.ui.tree.row_icons import icon_name
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def _sketch_part() -> Document:
    doc = new_document()
    sk = SketchBuilder()
    sk.rectangle(0, 0, 100, 60)
    add_sketch(doc, sk, {"feature": FRONT}, "Sketch 1")
    return doc


def _open(qtbot: QtBot, window: MainWindow, doc: Document) -> DocumentTab:  # noqa: F811
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = window.add_session(session)
    return tab


def _accept(qtbot: QtBot, window: MainWindow, tab: DocumentTab) -> None:  # noqa: F811
    panel = window.panel
    assert panel is not None
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        panel.accept()


def _sheet_part(qtbot: QtBot, window: MainWindow) -> DocumentTab:  # noqa: F811
    tab = _open(qtbot, window, _sketch_part())
    assert flow.start(window, "base_flange")
    _accept(qtbot, window, tab)  # the Sheet Metal folder panel
    assert window.panel is not None and window.panel.feature is not None
    assert window.panel.feature.type == "base_flange"
    _accept(qtbot, window, tab)
    qtbot.waitUntil(lambda: tab.session.report is not None and tab.session.report.body is not None)
    return tab


def test_commands_tab_and_tree_icons(window: MainWindow) -> None:  # noqa: F811
    for cid in flow.COMMANDS:
        assert cid in BY_ID and cid in window.commands.actions
        assert BY_ID[cid].keys == () and BY_ID[cid].group == "Sheet Metal"
    tabs = window.command_tabs
    names = [tabs.tabText(i) for i in range(tabs.count())]
    assert names.index("Sheet Metal") == names.index("Evaluate") - 1
    panel = tabs.widget(names.index("Sheet Metal"))
    shown = {a.text() for b in panel.buttons() for a in b.group_actions}
    assert {"Base Flange", "Edge Flange", "Sketched Bend", "Flatten"} <= shown
    for ftype in SHEET_FORMS:
        assert ftype in REGISTRY
        assert icon_name(Feature("f9", ftype, "x")).startswith("feature.")


def test_form_fields_match_the_core_types() -> None:
    for ftype, form in SHEET_FORMS.items():
        params = {p.name for p in REGISTRY[ftype].params}
        for field in form.fields():
            if field.kind in ("picks", "sketch"):
                continue
            assert field.name in params or REGISTRY[ftype].kind_of(field.name), (ftype, field)


def test_own_lengths_appear_per_picked_edge() -> None:
    shown = {
        f.name
        for f in EDGE_FLANGE.fields()
        if f.shown({"edges": [{}, {}, {}], "end_condition": "blind"})
    }
    assert {"length", "length2", "length3"} <= shown and "length4" not in shown
    vertex = {f.name for f in EDGE_FLANGE.fields() if f.shown({"end_condition": "up_to_vertex"})}
    assert "end" in vertex and "length" not in vertex


def test_first_base_flange_adds_folder_and_flat_pattern(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = _sheet_part(qtbot, window)
    doc = tab.session.document
    types = [f.type for f in doc.features]
    assert types[4] == "sheet_metal" and types[-1] == "flatten"
    base = next(f for f in doc.features if f.type == "base_flange")
    assert base.refs["sketch"] == {"feature": "f5"}
    report = tab.session.report
    assert report is not None and report.body is not None
    assert measure(report.body.shape)["bbox"] == pytest.approx([0, 0, 0, 100, 60, 1])
    # Undo removes the Flat Pattern, the Base Flange, the folder edit, then the folder.
    undo = tab.session.undo
    assert undo.text(undo.index() - 1) == "Add Flat Pattern"
    assert undo.text(0) == "Add Sheet Metal Parameters"
    while undo.canUndo():
        undo.undo()
    assert [f.type for f in doc.features if f.type != "sketch"][-1] == "plane"


def test_flatten_toggle_is_undoable(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _sheet_part(qtbot, window)
    doc = tab.session.document
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert flow.toggle_flatten(window)
    flat = flow.flat_of(doc)
    assert flat is not None and flat.params["flattened"] is True
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.undo()
    assert doc.feature(flat.id).params["flattened"] is False


def test_edge_flange_starts_with_the_selected_edges(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    from fdcad.core.features.solids import line_ends
    from fdcad.core.naming.names import faces_of  # noqa: F401

    tab = _sheet_part(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp
    from OCP.TopoDS import TopoDS

    from fdcad.core.occ import ShapeMap

    emap = ShapeMap()
    TopExp.MapShapes_s(report.body.shape, TopAbs_EDGE, emap)
    edge = None
    for i in range(1, emap.Extent() + 1):
        e = TopoDS.Edge(emap.FindKey(i))
        ends = line_ends(e)
        if ends and all(abs(p[1] - 60) < 1e-9 and abs(p[2] - 1) < 1e-9 for p in ends):
            edge = e
    assert edge is not None
    tab.selection = [edge]
    assert flow.start(window, "edge_flange")
    panel = window.panel
    assert panel is not None and panel.feature is not None
    assert len(panel.feature.refs["edges"]) == 1
    _accept(qtbot, window, tab)
    doc = tab.session.document
    assert [f.type for f in doc.features][-2:] == ["edge_flange", "flatten"]
    report = tab.session.report
    assert report is not None and report.body is not None
    assert measure(report.body.shape)["bbox"][5] == pytest.approx(20.0)


def test_tools_need_a_sheet(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    _open(qtbot, window, _sketch_part())
    assert not flow.start(window, "edge_flange")
    assert "needs a sheet metal part" in window.status.text()
    assert not flow.toggle_flatten(window)
    assert flow.export_flat(window, "x.dxf") is None


def test_bend_table_and_parameters(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    tab = _sheet_part(qtbot, window)
    good = tmp_path / "table.csv"
    good.write_text("thickness,radius,angle,allowance\n1,1,90,2.2\n", encoding="utf-8")
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert flow.load_bend_table(window, str(good))
    folder = flow.folder_of(tab.session.document)
    assert folder is not None and folder.params["method"] == "bend_table"
    assert "1,1,90,2.2" in folder.data["bend_table"]
    bad = tmp_path / "bad.csv"
    bad.write_text("1,2\n", encoding="utf-8")
    assert not flow.load_bend_table(window, str(bad))
    assert "could not be read" in window.status.text()
    assert flow.edit_parameters(window)
    assert window.panel is not None and window.panel.feature is not None
    assert window.panel.feature.type == "sheet_metal"


def test_export_flat_and_flat_size(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    tab = _sheet_part(qtbot, window)
    for name in ("flat.dxf", "flat.svg", "flat.step"):
        target = tmp_path / name
        job = flow.export_flat(window, str(target))
        assert job is not None
        qtbot.waitUntil(lambda t=target: t.exists() and t.stat().st_size > 0, timeout=20000)
    assert "BEND_LINES" in (tmp_path / "flat.dxf").read_text(encoding="utf-8")
    flat = flow.flat_of(tab.session.document)
    assert flat is not None
    assert flow.edit(window, flat.id)
    label = window.panel.findChild(__import__("PySide6.QtWidgets").QtWidgets.QLabel, "flat_size")
    assert label is not None and label.text() == "100.00 mm x 60.00 mm"
    result = flow.flat_result(tab.session.report, tab.session.document)
    assert isinstance(result, FlatResult)


def test_format_of() -> None:
    assert flow.format_of("a.STP") == "step"
    assert flow.format_of("a.svg") == "svg"
    assert flow.format_of("a", "DXF (*.dxf)") == "dxf"


def test_flat_export_adds_the_extension() -> None:
    """Audit A item 27 (D739): "flat" was written as STEP with no extension."""
    assert flow.with_extension("flat", "dxf") == "flat.dxf"
    assert flow.with_extension("flat.txt", "step") == "flat.txt.step"
    assert flow.with_extension("flat.SVG", "svg") == "flat.SVG"


def test_build123d_export_from_the_menu(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    from fdcad.ui.build123d_export import export_build123d

    _open(qtbot, window, _sketch_part())
    target = tmp_path / "part.py"
    assert export_build123d(window, str(target)) is not None
    qtbot.waitUntil(lambda: target.exists() and target.stat().st_size > 0, timeout=20000)
    script = target.read_text(encoding="utf-8")
    compile(script, "part.py", "exec")
    assert "with BuildSketch(" in script
    found: list[str] = []
    todo = list(window.menuBar().actions())
    while todo:
        action = todo.pop()
        found.append(action.text())
        if action.menu() is not None:
            todo.extend(action.menu().actions())
    assert "build123d Script..." in found


def test_cancel_on_the_first_sheet_values_stops_base_flange(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """Bug hunt B2: Cancel on the Sheet Metal folder panel left the folder and still
    opened the Base Flange panel."""
    tab = _open(qtbot, window, _sketch_part())
    before = [f.type for f in tab.session.document.features]
    assert flow.start(window, "base_flange")
    panel = window.panel
    assert panel is not None and panel.feature is not None
    assert panel.feature.type == "sheet_metal"
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        panel.reject()
    assert not panel.is_editing
    assert [f.type for f in tab.session.document.features] == before
    assert not tab.session.undo.canUndo()


def test_unticked_flat_pattern_options_stay_off_after_ok_and_reopen(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    from fdcad.core.io.fdef import load

    tab = _sheet_part(qtbot, window)
    flat = flow.flat_of(tab.session.document)
    assert flat is not None
    assert flow.edit(window, flat.id)
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    panel.body_form.widgets["bend_lines"].setChecked(False)
    panel.body_form.widgets["bounding_box"].setChecked(False)
    _accept(qtbot, window, tab)
    stored = tab.session.document.feature(flat.id).params
    assert stored["bend_lines"] is False and stored["bounding_box"] is False
    assert flow.edit(window, flat.id)
    assert panel.body_form is not None
    assert not panel.body_form.widgets["bend_lines"].isChecked()
    assert not panel.body_form.widgets["bounding_box"].isChecked()
    panel.reject()
    path = tmp_path / "part.fdprt"
    tab.session.save(path)
    again = load(path).feature(flat.id).params
    assert again.get("bend_lines") is False and again.get("bounding_box") is False


def test_a_saved_flange_without_trim_shows_it_unticked(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    from fdcad.core.io.fdef import load

    doc = load(Path(__file__).parents[2] / "samples" / "sheet_metal_bracket.fdprt")
    flange = next(f for f in doc.features if f.type == "edge_flange")
    flange.params.pop("trim_side_bends")  # builds without trimming (false when missing)
    tab = _open(qtbot, window, doc)
    assert flow.edit(window, flange.id)
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    assert not panel.body_form.widgets["trim_side_bends"].isChecked()
    _accept(qtbot, window, tab)
    assert tab.session.document.feature(flange.id).params.get("trim_side_bends") is not True


def test_flatten_says_why_when_the_flat_pattern_is_not_built(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = _sheet_part(qtbot, window)
    doc = tab.session.document
    flat = flow.flat_of(doc)
    assert flat is not None
    flat.suppressed = True
    assert not flow.toggle_flatten(window)
    assert "suppressed" in window.status.text() and flat.params["flattened"] is False
    flat.suppressed = False
    doc.rollback = next(f.id for f in doc.features if f.type == "base_flange")
    assert not flow.toggle_flatten(window)
    assert "rollback bar" in window.status.text() and flat.params["flattened"] is False
    assert not tab.session.undo.canRedo()
