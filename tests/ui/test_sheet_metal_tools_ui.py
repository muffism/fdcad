"""Sheet Metal tab: the later tools of D530 to D547 (panels, starting, gauge table)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features import REGISTRY
from fdcad.samples.builder import FRONT, SketchBuilder, add_sketch
from fdcad.samples.make import measure
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.sheet_metal import flow
from fdcad.ui.sheet_metal.forms import HEM, SHEET_FORMS, TAB_SLOT, UNFOLD
from fdcad.ui.tree.row_icons import icon_name
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)
from tests.ui.test_sheet_metal_ui import _accept, _open, _sheet_part

LATER = (
    "hem", "miter_flange", "jog", "closed_corner", "break_corner", "rip", "tab_slot",
    "convert_sheet", "insert_bends", "cross_break", "unfold", "fold", "form_tool",
    "sheet_tab",
    "edit_bends",
    "sheet_corner_relief",
    "extend_wall",
    "perforation",
    "flat_marks",
    "stamp",
)  # fmt: skip


def test_later_commands_forms_and_icons(window: MainWindow) -> None:  # noqa: F811
    for ftype in LATER:
        cid = f"feature.{ftype}"
        assert cid in flow.COMMANDS and cid in window.commands.actions
        assert BY_ID[cid].group == "Sheet Metal" and BY_ID[cid].keys == ()
        assert ftype in SHEET_FORMS and ftype in REGISTRY
        assert icon_name(Feature("f9", ftype, "x")) == cid
    assert "feature.gauge_table" in window.commands.actions
    tabs = window.command_tabs
    names = [tabs.tabText(i) for i in range(tabs.count())]
    panel = tabs.widget(names.index("Sheet Metal"))
    shown = {a.text() for b in panel.buttons() for a in b.group_actions}
    assert {"Hem", "Miter Flange", "Jog", "Forming Tool", "Unfold", "Fold"} <= shown


def test_panel_fields_follow_the_choices() -> None:
    rolled = {f.name for f in HEM.fields() if f.shown({"hem_type": "rolled"})}
    assert "length" not in rolled and {"radius", "angle"} <= rolled
    closed = {f.name for f in HEM.fields() if f.shown({"hem_type": "closed"})}
    assert "length" in closed and "radius" not in closed
    assert {f.name for f in TAB_SLOT.fields()} >= {"edge", "face", "tab_count", "clearance"}
    all_bends = {f.name for f in UNFOLD.fields() if f.shown({"all_bends": True})}
    assert "bends" not in all_bends


def _top_edge(tab: object) -> object:
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp
    from OCP.TopoDS import TopoDS

    from fdcad.core.features.solids import line_ends
    from fdcad.core.occ import ShapeMap

    body = tab.session.report.body  # type: ignore[attr-defined]
    emap = ShapeMap()
    TopExp.MapShapes_s(body.shape, TopAbs_EDGE, emap)
    for i in range(1, emap.Extent() + 1):
        e = TopoDS.Edge(emap.FindKey(i))
        ends = line_ends(e)
        if ends and all(abs(p[1] - 60) < 1e-9 and abs(p[2] - 1) < 1e-9 for p in ends):
            return e
    raise AssertionError("edge not found")


def test_hem_starts_with_the_selected_edge(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _sheet_part(qtbot, window)
    tab.selection = [_top_edge(tab)]
    assert flow.start(window, "hem")
    panel = window.panel
    assert panel is not None and panel.feature is not None
    assert len(panel.feature.refs["edges"]) == 1
    _accept(qtbot, window, tab)
    doc = tab.session.document
    assert [f.type for f in doc.features][-2:] == ["hem", "flatten"]
    report = tab.session.report
    assert report is not None and report.body is not None
    assert measure(report.body.shape)["bbox"][5] == pytest.approx(2.0)  # closed hem on top
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.undo()
    assert "hem" not in [f.type for f in doc.features]


def _box_part() -> Document:
    doc = new_document()
    sk = SketchBuilder()
    sk.rectangle(0, 0, 100, 60)
    sid = add_sketch(doc, sk, {"feature": FRONT}, "Sketch 1")
    params = {"operation": "boss", "end_condition": "blind", "depth": Param("30", 30.0)}
    doc.features.append(
        Feature(doc.new_feature_id(), "extrude", "Extrude 1", params=params,
                refs={"sketch": {"feature": sid}})
    )  # fmt: skip
    return doc


def test_convert_asks_for_the_folder_first(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window, _box_part())
    assert flow.start(window, "convert_sheet")
    assert window.panel is not None and window.panel.feature is not None
    assert window.panel.feature.type == "sheet_metal"
    _accept(qtbot, window, tab)
    assert window.panel.feature is not None and window.panel.feature.type == "convert_sheet"
    window.panel.reject()


def test_fold_needs_an_open_unfold(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _sheet_part(qtbot, window)
    assert not flow.start(window, "fold")
    assert "needs an Unfold" in window.status.text()
    doc = tab.session.document
    unfold = Feature(doc.new_feature_id(), "unfold", "Unfold 1", params={"all_bends": True})
    doc.features.insert(len(doc.features) - 1, unfold)
    assert flow.open_unfold(doc) == unfold.id
    assert flow.start(window, "fold")
    assert window.panel is not None and window.panel.feature is not None
    assert window.panel.feature.refs["unfold"] == {"feature": unfold.id}
    window.panel.reject()
    doc.features.insert(
        len(doc.features) - 1,
        Feature(doc.new_feature_id(), "fold", "Fold 1", refs={"unfold": {"feature": unfold.id}}),
    )
    assert flow.open_unfold(doc) is None


def test_load_gauge_table(qtbot: QtBot, window: MainWindow, tmp_path: Path) -> None:  # noqa: F811
    tab = _sheet_part(qtbot, window)
    table = tmp_path / "gauges.csv"
    table.write_text("name,thickness,radii\n16 gauge,1.5,1,2\n", encoding="utf-8")
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert flow.load_gauge_table(window, str(table), gauge="16 gauge")
    folder = flow.folder_of(tab.session.document)
    assert folder is not None and folder.params["gauge"] == "16 gauge"
    assert folder.params["thickness"].value == pytest.approx(1.5)
    report = tab.session.report
    assert report is not None and report.body is not None
    assert measure(report.body.shape)["bbox"][5] == pytest.approx(1.5)
    assert tab.session.undo.undoText() == "Load Gauge Table"
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\nx,1\n", encoding="utf-8")
    assert not flow.load_gauge_table(window, str(bad), gauge="")
    assert "could not be read" in window.status.text()


def test_cross_break_lines_are_drawn(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    from fdcad.samples.builder import face_ref

    tab = _sheet_part(qtbot, window)
    doc = tab.session.document
    top, _p = face_ref(doc, (0.0, 0.0, 1.0))
    folder = flow.folder_of(doc)
    assert folder is not None
    cross = Feature(doc.new_feature_id(), "cross_break", "Cross Break 1",
                    refs={"face": top, "sheet_metal": {"feature": folder.id}})  # fmt: skip
    doc.features.insert(len(doc.features) - 1, cross)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.request_rebuild()
    assert len(flow.bend_line_shapes(tab.session.report)) == 1


@pytest.mark.parametrize("ftype", ["base_flange", "convert_sheet", "insert_bends"])
def test_a_second_sheet_start_asks_for_a_new_folder(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    ftype: str,
) -> None:
    """TR281 (D2312): a second sheet body gets its own Sheet Metal folder, asked first."""
    from fdcad.ui import strings_sheetmetal as text

    tab = _sheet_part(qtbot, window)
    doc = tab.session.document
    assert len(flow.folders(doc)) == 1 and flow.free_folder(doc) is None
    assert flow.start(window, ftype)
    assert len(flow.folders(doc)) == 2
    assert window.panel is not None and window.panel.feature is not None
    assert window.panel.feature.type == "sheet_metal"
    assert window.status.text() == text.NEW_SHEET
    window.panel.reject()  # Cancel takes the new folder back
    qtbot.waitUntil(lambda: len(flow.folders(doc)) == 1, timeout=5000)


def test_sheet_values_stay_in_mm_in_a_part_in_inches(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    from fdcad.core.units import UnitSystem
    from tests.ui.test_sheet_metal_ui import _sketch_part

    doc = _sketch_part()
    doc.units = UnitSystem.IN
    tab = _open(qtbot, window, doc)
    assert flow.start(window, "base_flange")
    _accept(qtbot, window, tab)  # the Sheet Metal folder panel, with its defaults
    _accept(qtbot, window, tab)
    folder = flow.folder_of(tab.session.document)
    assert folder is not None
    assert folder.params["thickness"].value == pytest.approx(1.0)
    assert folder.params["radius"].value == pytest.approx(1.0)
    report = tab.session.report
    assert report is not None and report.body is not None
    assert measure(report.body.shape)["bbox"][5] == pytest.approx(1.0)
    table = tmp_path / "gauges.csv"
    table.write_text("name,thickness,radii\n16 gauge,1.5,1,2\n", encoding="utf-8")
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert flow.load_gauge_table(window, str(table), gauge="16 gauge")
    folder = flow.folder_of(tab.session.document)
    assert folder is not None
    assert folder.params["thickness"].value == pytest.approx(1.5)
    report = tab.session.report
    assert report is not None and report.body is not None
    assert measure(report.body.shape)["bbox"][5] == pytest.approx(1.5)


def test_own_relief_values_survive_ok_without_the_panel_tick(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """A file with own relief values but no "own_relief" tick (the core never reads it)."""
    from fdcad.core.io.fdef import load

    root = Path(__file__).parents[2]
    doc = load(root / "tests" / "fixtures" / "sheet_metal" / "folder_options.fdef")
    flange = next(f for f in doc.features if f.type == "edge_flange")
    assert "own_relief" not in flange.params and flange.params["relief"] == "tear"
    tab = _open(qtbot, window, doc)
    report = tab.session.report
    assert report is not None and report.body is not None
    before = measure(report.body.shape)["volume"]
    window.edit_feature(flange.id)
    _accept(qtbot, window, tab)
    params = tab.session.document.feature(flange.id).params
    assert params["relief"] == "tear" and params["corner_relief"] == "circular"
    report = tab.session.report
    assert report is not None and report.body is not None
    assert measure(report.body.shape)["volume"] == pytest.approx(before)


def test_no_gauge_brings_the_typed_values_back(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    """Audit A item 3 (D727): choosing No gauge after a gauge left the gauge's values."""
    tab = _sheet_part(qtbot, window)
    folder = flow.folder_of(tab.session.document)
    assert folder is not None
    typed = folder.params["thickness"].expr
    table = tmp_path / "gauges.csv"
    table.write_text("name,thickness,radii\n16 gauge,1.5,1,2\n", encoding="utf-8")
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert flow.load_gauge_table(window, str(table), gauge="16 gauge")
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert flow.load_gauge_table(window, str(table), gauge="")
    folder = flow.folder_of(tab.session.document)
    assert folder is not None and "gauge" not in folder.params
    assert folder.params["thickness"].expr == typed


def test_rip_form_has_the_tube_fields() -> None:
    """TR174 item 4 (D1813)."""
    from fdcad.ui.sheet_metal.forms import RIP

    names = {f.name for f in RIP.fields()}
    assert {"tube_faces", "tube_angle", "tube_offset"} <= names


def test_miter_flange_has_an_own_relief_group() -> None:
    """TR170 (D2306)."""
    from fdcad.ui.sheet_metal.forms import MITER_FLANGE

    group = next(g for g in MITER_FLANGE.groups if g.toggle == "own_relief")
    names = {f.name for f in group.fields}
    assert {"relief", "relief_by", "relief_width", "relief_depth"} <= names
    assert "relief" not in MITER_FLANGE.defaults


def test_closed_corner_has_a_bend_region_choice() -> None:
    """TR174 (D2308)."""
    from fdcad.ui.sheet_metal.forms import CLOSED_CORNER
    from fdcad.ui.strings_sheetmetal import CHOICES, LATER_LABELS

    field = next(f for f in CLOSED_CORNER.fields() if f.name == "bend_region")
    assert field.choices == ("open", "closed") and field.default == "open"
    assert "bend_region" in LATER_LABELS and {"open", "closed"} <= set(CHOICES)


def test_form_tool_rib_ends_and_stamp_drawn_cut_fields() -> None:
    """TR283 (D2311)."""
    from fdcad.ui.sheet_metal.forms import FORM_TOOL, STAMP

    ends = next(f for f in FORM_TOOL.fields() if f.name == "rib_ends")
    assert ends.shown({"tool": "rib"}) and not ends.shown({"tool": "dimple"})
    assert "drawn_cut" in {f.name for f in STAMP.fields()}


def test_second_sheet_body_with_its_own_flat_pattern(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """TR281 (D2312): the whole flow for a second sheet body."""
    from fdcad.core.features.solids import solids
    from tests.ui.test_sheet_metal_ui import _sketch_part

    doc = _sketch_part()
    sk = SketchBuilder()
    sk.rectangle(150, 0, 40, 30)
    add_sketch(doc, sk, {"feature": FRONT}, "Sketch 2")
    tab = _open(qtbot, window, doc)
    for _sheet in range(2):
        assert flow.start(window, "base_flange")
        _accept(qtbot, window, tab)  # the new Sheet Metal folder's panel
        assert window.panel is not None and window.panel.feature is not None
        assert window.panel.feature.type == "base_flange"
        _accept(qtbot, window, tab)
    doc = tab.session.document
    first, second = flow.folders(doc)
    flats = [f for f in doc.features if f.type == "flatten"]
    assert len(flats) == 2
    assert {"feature": second.id} in [f.refs.get("sheet_metal") for f in flats]
    starters = [f for f in doc.features if f.type == "base_flange"]
    assert [s.refs["sheet_metal"]["feature"] for s in starters] == [first.id, second.id]
    qtbot.waitUntil(
        lambda: tab.session.report is not None and tab.session.report.body is not None
        and len(solids(tab.session.report.body.shape)) == 2,
        timeout=20000,
    )  # fmt: skip


def test_form_tool_own_tool_fields() -> None:
    """TR279 (D2313): the own tool picks show only for the Own tool choice."""
    from fdcad.ui.sheet_metal.forms import FORM_TOOL

    fields = {f.name: f for f in FORM_TOOL.fields()}
    for name in ("tool_face", "remove_faces", "insert", "tool_angle", "mirror"):
        assert fields[name].shown({"tool": "custom"}) and not fields[name].shown({"tool": "rib"})
    assert not fields["height"].shown({"tool": "custom"})
    assert "custom" in fields["tool"].choices
