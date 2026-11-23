"""Phase 3 tools in the window: commands, the Features tab, the generic panel, picks from
the view, the face helper bar, the face menu, fixes, undo and the live preview."""

from __future__ import annotations

import math

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import Fix
from fdcad.core.features.solids import volume_of
from fdcad.core.naming.names import faces_of
from fdcad.ui.body_tools import flow
from fdcad.ui.body_tools.form_widget import PickBox
from fdcad.ui.body_tools.forms import FORMS, format_skip, parse_skip
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.session import DocumentSession
from fdcad.ui.tree.row_icons import icon_name
from tests.core.features.phase3_parts import block_with_hole_and_boss
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)

BASE = 60 * 40 * 10 - math.pi * 25 * 10 + 600


def _open(qtbot: QtBot, window: MainWindow) -> tuple[DocumentTab, dict[str, str]]:  # noqa: F811
    doc, ids = block_with_hole_and_boss()
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = window.add_session(session)
    return tab, ids


def _hole_wall(tab: DocumentTab):  # type: ignore[no-untyped-def]
    report = tab.session.report
    assert report is not None and report.body is not None
    walls = [
        f
        for f in faces_of(report.body.shape)
        if BRepAdaptor_Surface(f).GetType() == GeomAbs_Cylinder
    ]
    return walls[0]


def test_commands_and_tab(window: MainWindow) -> None:  # noqa: F811
    for cid in flow.COMMAND_TYPES:
        assert cid in BY_ID and cid in window.commands.actions
        assert BY_ID[cid].keys == ()  # bindable, no default key
    tabs = window.command_tabs
    features = tabs.widget(tabs.index_of("features")).buttons()
    shown = {a.text() for b in features for a in b.group_actions}
    assert {"Move Face", "Delete Face", "Linear Pattern"} <= shown
    bodies = tabs.widget(tabs.index_of("bodies")).buttons()
    assert {"Combine", "Scale"} <= {a.text() for b in bodies for a in b.group_actions}


def test_every_form_type_is_registered_and_has_a_tree_icon() -> None:
    from fdcad.core.features import REGISTRY

    for ftype in FORMS:
        assert ftype in REGISTRY
        assert icon_name(Feature("f9", ftype, "x")).startswith("feature.")


def test_skip_text_round_trip() -> None:
    assert parse_skip("3, 5 ,2.2") == [[3, 1], [5, 1], [2, 2]]
    assert parse_skip("x") is None
    assert format_skip([[3, 1], [2, 2]]) == "3, 2.2"


def test_offset_face_from_the_view(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab, _ids = _open(qtbot, window)
    panel = window.panel
    assert panel is not None
    assert flow.start(window, "feature.offset_face")
    assert panel.body_form is not None
    wall = _hole_wall(tab)
    window._selection_changed(tab, [wall])
    box = panel.body_form.widgets["faces"]
    assert isinstance(box, PickBox) and len(box.refs()) == 1
    panel.values["distance"].edit.setText("2")
    edited = panel.current_feature()
    assert edited is not None and edited.params["mode"] == "offset"
    assert edited.params["distance"] == Param("2", 2.0)
    assert "dx" not in edited.params  # hidden fields are not written
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        panel.accept()
    report = tab.session.report
    assert report is not None and report.body is not None
    assert volume_of(report.body.shape) == __import__("pytest").approx(
        24000 - math.pi * 9 * 10 + 600, rel=1e-7
    )
    # One undo step removes it again.
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.undo()
    assert tab.session.document.features[-1].type == "extrude"


def test_face_menu_starts_with_the_face_picked(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab, _ids = _open(qtbot, window)
    wall = _hole_wall(tab)
    menu = flow.face_menu(window, tab, wall)
    names = [a.objectName() for a in menu.actions()]
    assert names == ["feature.move_face", "feature.offset_face", "feature.delete_face"]
    menu.actions()[2].trigger()
    panel = window.panel
    assert panel is not None and panel.feature is not None
    assert panel.feature.type == "delete_face"
    edited = panel.current_feature()
    assert edited is not None and len(edited.refs["faces"]) == 1
    # Delete without healing is offered greyed.
    box = panel.body_form.widgets["option"]
    assert not box.model().item(box.findData("delete")).isEnabled()
    panel.reject()


def test_helper_bar_adds_related_faces(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    from fdcad.ui.body_tools.helper_bar import HelperBar

    tab, ids = _open(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    top = report.body.face(f"{ids['plate']}/cap/end")
    assert flow.start(window, "feature.delete_face")
    window._selection_changed(tab, [top])
    bar = getattr(window, "face_helper_bar", None)
    assert isinstance(bar, HelperBar)
    bar.wait()
    qtbot.waitUntil(lambda: "inner_loops" in bar.results, timeout=5000)
    assert len(bar.results["inner_loops"]) == 5
    bar.buttons["inner_loops"].click()
    panel = window.panel
    assert panel is not None
    box = panel.body_form.widgets["faces"]
    assert len(box.refs()) == 6  # the top face plus the hole wall and four boss sides
    panel.reject()


def test_drop_refs_fix_is_one_undo_step(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab, _ids = _open(qtbot, window)
    doc = tab.session.document
    report = tab.session.report
    assert report is not None and report.body is not None
    from fdcad.core.naming.select import reference_for

    wall = _hole_wall(tab)
    feature = flow.new_feature(
        doc, "delete_face", {}, {"faces": [reference_for(report.body, wall)]}
    )
    feature.refs["faces"].append({"kind": "face", "name": "lost/face", "snapshot": {}})
    from fdcad.ui.commands.document import AddFeature

    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.push(AddFeature(tab.session, feature))
    fix = Fix(
        "Keep the faces that worked",
        "drop_refs",
        {"feature": feature.id, "ref": "faces", "names": ["lost/face"]},
    )
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        window.apply_fix(feature.id, fix)
    assert len(doc.feature(feature.id).refs["faces"]) == 1
    report = tab.session.report
    assert report is not None and report.results[feature.id].state.value == "ok"
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.undo()
    assert len(doc.feature(feature.id).refs["faces"]) == 2


def test_preview_and_handles_follow_the_panel(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab, ids = _open(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    top = report.body.face(f"{ids['boss']}/cap/end")
    assert flow.start(window, "feature.offset_face", top)
    preview = window.preview
    assert preview is not None
    with qtbot.waitSignal(preview.ready, timeout=20000) as blocker:
        window.panel.values["distance"].edit.setText("3")
    data = blocker.args[0]
    assert data.geometry.shape is not None
    assert [h.param for h in data.handles] == ["distance"]
    # D1032: the preview is only the moved and stretched faces, over the unchanged part.
    assert data.geometry.replaces_part and len(data.geometry.accent) == 1
    # Dragging the arrow types the value into the field; dragging past the start flips Reverse.
    preview.drag_to("distance", 4.0)
    assert window.panel.values["distance"].edit.text() == "4"
    preview.flip("distance")
    assert window.panel.body_form.widgets["reverse"].isChecked()
    window.panel.reject()


def test_editing_a_saved_feature_restores_its_fields(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab, _ids = _open(qtbot, window)
    doc = tab.session.document
    feature = flow.new_feature(doc, "linear_pattern", {}, {})
    feature.data["skip"] = [[2, 1]]
    feature.params["second_direction"] = True
    from fdcad.ui.commands.document import AddFeature

    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.push(AddFeature(tab.session, feature))
    window.edit_feature(feature.id)
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    assert panel.body_form.widgets["skip"].text() == "2"
    assert panel.body_form.widgets["second_direction"].is_checked()
    edited = panel.current_feature()
    assert edited is not None and edited.data["skip"] == [[2, 1]]
    assert edited.params["second_direction"] is True
    panel.reject()


def test_fix_actions_match_the_core() -> None:
    from fdcad.core.features.delete_face import DROP_REFS
    from fdcad.core.features.patterns import SKIP_INSTANCES

    assert (flow.DROP_REFS, flow.SKIP_INSTANCES) == (DROP_REFS, SKIP_INSTANCES)


def _two_bodies(qtbot: QtBot, window: MainWindow, gap: float = 5.0):  # type: ignore[no-untyped-def]  # noqa: F811
    from tests.core.features.test_multibody import two_blocks

    doc, first, second, _body = two_blocks(gap=gap)
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = window.add_session(session)
    report = tab.session.report
    assert report is not None and report.body is not None
    return tab, report.body.face(f"{first}/cap/end"), report.body.face(f"{second}/cap/end")


def test_body_picks_show_body_numbers(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab, a, b = _two_bodies(qtbot, window, gap=-10.0)  # overlapping blocks
    assert flow.start(window, "feature.combine")
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    window._selection_changed(tab, [a])
    window._selection_changed(tab, [b])
    box = panel.body_form.widgets["bodies"]
    labels = [box.list.item(i).text() for i in range(box.list.count())]
    assert labels == ["Body 1", "Body 2"]
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        panel.accept()
    report = tab.session.report
    assert report is not None and report.body_count == 1


def test_another_face_of_a_picked_body_toggles_it(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """Clicking another face of Body 1 removes Body 1 instead of listing it twice."""
    tab, a, b = _two_bodies(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    first = tab.session.document.features[-3].id
    side = report.body.face(f"{first}/side/e6")
    assert flow.start(window, "feature.delete_body")
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    box = panel.body_form.widgets["bodies"]
    window._selection_changed(tab, [a])
    window._selection_changed(tab, [b])
    window._selection_changed(tab, [side])
    assert [box.list.item(i).text() for i in range(box.list.count())] == ["Body 2"]
    panel.reject()


def test_body_row_command_uses_that_body(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """Transform Handles from body row 2 picks body 2, even with a face of body 1 selected."""
    tab, a, _b = _two_bodies(qtbot, window)
    window._selection_changed(tab, [a])
    window.body_display.from_tree("transform", 1)
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    box = panel.body_form.widgets["bodies"]
    assert [box.list.item(i).text() for i in range(box.list.count())] == ["Body 2"]
    panel.reject()


def test_split_cut_button_lists_the_pieces(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    from fdcad.ui.body_tools.form_widget import ResultList

    tab, _a, _b = _two_bodies(qtbot, window)
    assert flow.start(window, "feature.split")
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    tools = panel.body_form.widgets["tools"]
    results = panel.body_form.widgets["keep"]
    assert isinstance(results, ResultList)
    # A sketch line at x = 10 cuts block A (x 0..20) only: three bodies.
    from fdcad.core.sketch.model import Sketch
    from tests.core.features.phase3_parts import add_sketch

    s = Sketch()
    s.add_line(10, -5, 10, 25)
    doc = tab.session.document
    sk = add_sketch(doc, s, {"feature": "f2"})
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.request_rebuild()
    tools.list.clear()
    tools.add({"feature": sk}, "Sketch")
    with qtbot.waitSignal(results.list.model().rowsInserted, timeout=20000):
        results.button.click()
    qtbot.waitUntil(lambda: results.list.count() == 3, timeout=20000)
    from PySide6.QtCore import Qt

    results.list.item(0).setCheckState(Qt.CheckState.Unchecked)
    edited = panel.current_feature()
    assert edited is not None and edited.data["keep"] == [2, 3]
    # Other tools number the bodies anew: the old list and its ticks are dropped.
    tools.add({"feature": "f4"}, "Right Plane")
    assert (
        results.list.count() == 0
        and results.hint.text() == "Press Cut to list the bodies the split makes."
    )
    edited = panel.current_feature()
    assert edited is not None and "keep" not in edited.data
    panel.reject()


def test_split_save_bodies_writes_ticked_bodies(  # type: ignore[no-untyped-def]
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path,
    monkeypatch,
) -> None:
    """Save Bodies writes each ticked body to its own file; the part is unchanged (D528)."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QFileDialog

    from fdcad.core.io import fdef
    from fdcad.core.rebuild.runner import rebuild
    from fdcad.core.sketch.model import Sketch
    from fdcad.ui.body_tools.form_widget import ResultList
    from tests.core.features.phase3_parts import add_sketch

    tab, _a, _b = _two_bodies(qtbot, window)
    s = Sketch()
    s.add_line(10, -5, 10, 25)
    sk = add_sketch(tab.session.document, s, {"feature": "f2"})
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.request_rebuild()
    assert flow.start(window, "feature.split")
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    tools = panel.body_form.widgets["tools"]
    results = panel.body_form.widgets["keep"]
    assert isinstance(results, ResultList)
    assert not results.save.isHidden() and not results.save.isEnabled()
    tools.list.clear()
    tools.add({"feature": sk}, "Sketch")
    results.button.click()
    qtbot.waitUntil(lambda: results.list.count() == 3, timeout=20000)
    assert results.save.isEnabled()
    results.list.item(1).setCheckState(Qt.CheckState.Unchecked)
    results.list.item(2).setText("Right block")  # a file name changes nothing in the part
    edited = panel.current_feature()
    assert edited is not None and edited.data["keep"] == [1, 3]
    results.format.setCurrentIndex(results.format.findData("fdef"))
    before = fdef.dumps(tab.session.document)
    undo_count = tab.session.undo.count()
    asked: list[str] = []

    def folder(*_a: object, **_k: object) -> str:
        asked.append("folder")
        return str(tmp_path)

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", folder)
    results.save.click()
    qtbot.waitUntil(lambda: "Saved 2 files" in results.hint.text(), timeout=30000)
    assert asked == ["folder"]
    names = sorted(p.name for p in tmp_path.glob("*.fdprt"))  # the settings file lives here too
    assert names == ["Part body 1.fdprt", "Right block.fdprt"]
    part = fdef.load(tmp_path / "Right block.fdprt")
    body = rebuild(part)[part.features[-1].id].body
    assert body is not None and abs(volume_of(body.shape) - 20 * 20 * 10) < 1e-6
    assert fdef.dumps(tab.session.document) == before
    assert tab.session.undo.count() == undo_count
    panel.reject()


def test_intersect_lists_regions_to_exclude(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """The region list fills by itself, so a region can be excluded (P3.4 item 2)."""
    from PySide6.QtCore import Qt

    from fdcad.ui.body_tools.form_widget import ResultList

    tab, a, b = _two_bodies(qtbot, window, gap=-10.0)  # overlapping blocks
    window._selection_changed(tab, [a, b])
    assert flow.start(window, "feature.intersect")
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    results = panel.body_form.widgets["exclude"]
    assert isinstance(results, ResultList)
    # Three regions: block A alone, the overlap, block B alone. Only the overlap is listed.
    qtbot.waitUntil(lambda: results.list.count() == 1, timeout=20000)
    assert results.list.item(0).text() == "Region 2"
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        panel.accept()
    fid = tab.session.document.features[-1].id
    assert flow.edit(window, fid)
    results = panel.body_form.widgets["exclude"]
    qtbot.waitUntil(lambda: results.list.count() == 1, timeout=20000)
    results.list.item(0).setCheckState(Qt.CheckState.Unchecked)
    edited = panel.current_feature()
    assert edited is not None and edited.data["exclude"] == [2]
    panel.reject()


def test_flags_on_by_default_can_be_turned_off(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """Unticking Merge result (on by default) writes false, so each region stays a body."""
    from tests.core.features.phase3_parts import ref_of

    tab, _a, b = _two_bodies(qtbot, window, gap=-10.0)
    report = tab.session.report
    assert report is not None and report.body is not None
    first = tab.session.document.features[-3].id
    side = report.body.face(f"{first}/side/e6")  # block A's side at x = 20 crosses block B
    window._selection_changed(tab, [b])
    assert flow.start(window, "feature.intersect")
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    panel.body_form.widgets["planes"].add(ref_of(report.body, side), "Face")
    panel.body_form.widgets["merge"].setChecked(False)
    edited = panel.current_feature()
    assert edited is not None and edited.params["merge"] is False
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        panel.accept()
    report = tab.session.report
    assert report is not None and report.body_count == 3  # block A and two halves of B
    assert flow.edit(window, tab.session.document.features[-1].id)
    assert not panel.body_form.widgets["merge"].isChecked()
    panel.reject()
    assert flow.start(window, "feature.scale")
    panel.body_form.widgets["uniform"].setChecked(False)
    edited = panel.current_feature()
    assert edited is not None and edited.params["uniform"] is False
    panel.reject()


def test_hole_tool_holes_are_offered_as_pattern_seeds(qtbot: QtBot) -> None:
    """Spec 2 section 20 item 1 (D712): the list showed only bosses and cuts, though the
    core already patterns Hole Tool holes."""
    from fdcad.core.document.model import Feature
    from fdcad.ui.body_tools.form_widget import FeatureList, copyable

    hole = Feature("f9", "hole", "M5 Hole")
    rib = Feature("f10", "rib", "Rib 1")
    assert copyable(hole) and not copyable(rib)
    assert not copyable(Feature("f11", "sketch", "Sketch 1"))
    widget = FeatureList([hole, rib], [])
    qtbot.addWidget(widget)
    assert [widget.item(i).text() for i in range(widget.count())] == ["M5 Hole"]


def test_axis_fields_list_the_origin_and_reference_axes(qtbot: QtBot) -> None:
    """Spec 2 section 20 item 3 (D712): axis boxes took only edges and faces."""
    from fdcad.core.document.model import Feature, new_document
    from fdcad.ui.body_tools.form_widget import PickBox
    from fdcad.ui.body_tools.forms import CIRCULAR_PATTERN

    doc = new_document()
    doc.features.append(Feature("f9", "ref_axis", "Axis 1"))
    spec = next(f for g in CIRCULAR_PATTERN.groups for f in g.fields if f.name == "axis")
    box = PickBox(spec, doc, doc.features)
    qtbot.addWidget(box)
    assert box.combo is not None
    data = [box.combo.itemData(i) for i in range(box.combo.count())]
    assert {"feature": "f1", "axis": "z"} in data and {"feature": "f9"} in data
    assert {"feature": "f2"} not in data  # planes are not axes


def test_flow_path_box_lists_curve_features(qtbot: QtBot) -> None:
    """Audit B item 17 (D730): only sketches could be the Flow Along Curve path."""
    from fdcad.core.document.model import Feature, new_document
    from fdcad.ui.body_tools.deform_forms import DEFORM_FORMS
    from fdcad.ui.body_tools.form_widget import PickBox

    doc = new_document()
    doc.features.append(Feature("f9", "helix", "Helix 1"))
    spec = next(f for g in DEFORM_FORMS["flow"].groups for f in g.fields if f.name == "path")
    box = PickBox(spec, doc, doc.features)
    qtbot.addWidget(box)
    assert box.combo is not None
    assert {"feature": "f9"} in [box.combo.itemData(i) for i in range(box.combo.count())]


def test_move_face_neighbours_and_solution_steps(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """Move Face: Neighbours, Keep This Solution, Rounds, and Previous/Next (TR264, D797)."""
    tab, ids = _open(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    top = report.body.face(f"{ids['boss']}/cap/end")
    window._selection_changed(tab, [top])
    assert flow.start(window, "feature.move_face")
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    form = panel.body_form
    shown = {f.name for f in form.shown_fields()}
    assert {"follow", "keep_solution", "rounds"} <= shown
    box = form.widgets["follow"]
    assert box.currentData() == "extend"
    form.step_solution(1)
    assert box.currentData() == "tip"
    form.step_solution(-1)
    form.step_solution(-1)
    assert box.currentData() == "lift"
    edited = panel.current_feature()
    assert edited is not None and edited.params["follow"] == "lift"
    panel.reject()


def test_rule_tick_boxes_say_what_they_do(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """Each ticked rule shows how many faces it adds or holds (TR263 item 2, D798)."""
    tab, ids = _open(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    window._selection_changed(tab, [report.body.face(f"{ids['boss']}/cap/end")])
    assert flow.start(window, "feature.move_face")
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    form = panel.body_form
    form.widgets["rule_symmetric"].setChecked(True)
    shown = {f.name for f in form.shown_fields()}
    assert {"symmetry_plane", "rule_exclude_symmetric"} <= shown
    assert "rule_exclude_coplanar" not in shown
    form._show_rule_effects({"rule:coplanar": 2.0, "rule:parallel": 3.0, "rule:symmetric": 0.0})
    assert form.widgets["rule_coplanar"].text() == "Keep coplanar faces: adds 2"
    assert form.widgets["rule_parallel"].text() == "Keep parallel and square faces: holds 3"
    assert form.widgets["rule_symmetric"].text() == "Keep symmetry: no effect"
    form._show_rule_effects({})
    assert form.widgets["rule_coplanar"].text() == "Keep coplanar faces"
    panel.reject()
