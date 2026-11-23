"""Reference geometry panel, preview, commands, tree and display (PHASE2_SPEC P2.10, D251)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Document, Feature, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.sketch.model import Sketch
from fdcad.core.units import UnitSystem
from fdcad.ui.commands.document import SetVisibility
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.reference_geometry.panel import ReferencePanel
from fdcad.ui.session import DocumentSession
from fdcad.ui.tree.row_icons import icon_name
from tests.core.features.test_features import add_extrude, add_sketch, rect


@pytest.fixture(autouse=True)
def _folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("FDCAD_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> Iterator[MainWindow]:
    settings = Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))
    win = MainWindow(settings)
    win.resize(1200, 800)
    win.show()
    win.finish_setup()
    yield win
    win.reference_tool.close()
    while win.tabs.count():
        tab = win.tabs.widget(0)
        assert isinstance(tab, DocumentTab)
        tab.session.cancel_rebuild()
        tab.session.wait()
        tab.autosaver.discard()
        win.tabs.removeTab(0)
    win.close()
    win.deleteLater()


def _plate() -> Document:
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 50, 30)
    sk = add_sketch(doc, s, {"feature": "f2"})
    add_extrude(doc, sk, 10.0)
    return doc


def _open(qtbot: QtBot, win: MainWindow, doc: Document) -> DocumentTab:
    session = DocumentSession(doc, None, win)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = win.add_session(session)
    return tab


TOP = {"kind": "face", "name": "f6/cap/end", "snapshot": {"surface": "plane"}}
BOTTOM = {"kind": "face", "name": "f6/cap/start", "snapshot": {"surface": "plane"}}


# The panel on its own -------------------------------------------------------------------


def test_panel_guesses_the_method_and_says_what_is_missing(qtbot: QtBot) -> None:
    doc = _plate()
    feature = Feature("f9", "ref_plane", "Plane 1", params={"method": "offset"})
    panel = ReferencePanel(feature, UnitSystem.MM, {}, doc.features)
    qtbot.addWidget(panel)
    assert "reference 1" in panel.message.text() and not panel.ok_button.isEnabled()
    panel.take_pick(TOP)
    assert panel.method_name == "offset"
    panel.take_pick(BOTTOM)  # a second plane: the guess becomes Mid plane
    assert panel.method_name == "mid_plane"
    f = panel.current_feature()
    assert f.refs == {"first": TOP, "second": BOTTOM} and f.params["method"] == "mid_plane"
    assert panel.missing() is None and not panel.ok_button.isEnabled()  # preview pending
    panel.set_preview(True, "")
    assert panel.ok_button.isEnabled() and "Fully defined" in panel.message.text()
    panel.set_preview(False, "Plane 1: the two planes are not parallel.")
    assert "not parallel" in panel.message.text() and not panel.ok_button.isEnabled()


def test_chosen_method_is_kept_and_values_accept_units(qtbot: QtBot) -> None:
    doc = _plate()
    feature = Feature("f9", "ref_plane", "Plane 1", params={"method": "offset"})
    panel = ReferencePanel(feature, UnitSystem.MM, {}, doc.features)
    qtbot.addWidget(panel)
    panel.method.setCurrentIndex(panel.method.findData("offset"))
    panel._method_chosen()
    panel.take_pick(TOP)
    panel.fields["distance"].edit.setText("1in")
    panel.checks["flip"].setChecked(True)
    f = panel.current_feature()
    assert f.params["distance"].value == pytest.approx(25.4) and f.params["flip"] is True
    panel.take_pick(BOTTOM)
    assert panel.method_name == "offset"  # chosen by hand: no more guessing
    panel.fields["distance"].edit.setText("=nope")
    assert panel.missing() is not None


def test_feature_menu_picks_planes_and_the_origin(qtbot: QtBot) -> None:
    doc = _plate()
    feature = Feature("f9", "ref_point", "Point 1", params={"method": "values"})
    panel = ReferencePanel(feature, UnitSystem.MM, {}, doc.features)
    qtbot.addWidget(panel)
    assert panel.rows[0].isVisibleTo(panel)  # a pick may still choose the method
    panel._method_chosen()
    assert not panel.rows[0].isVisibleTo(panel)  # X, Y and Z values need no pick
    panel.method.setCurrentIndex(panel.method.findData("sketch_point"))
    panel._method_chosen()
    names = [a.text() for a in panel.boxes[0].parentWidget().findChildren(type(panel.boxes[0]))]
    assert names
    menu = panel._feature_menu(0)
    texts = [a.text() for a in menu.actions()]
    assert "Origin" in texts and "Front Plane" in texts
    menu.actions()[texts.index("Origin")].trigger()
    assert panel.current_feature().refs["first"] == {"feature": "f1"}


# In the window ----------------------------------------------------------------------------


def test_commands_exist_with_icons_and_menu() -> None:
    for cid in (
        "feature.ref_plane",
        "feature.ref_axis",
        "feature.ref_point",
        "feature.coord_system",
    ):
        assert cid in BY_ID
    assert icon_name(Feature("f9", "ref_axis", "Axis 1")) == "feature.ref_axis"


def test_new_plane_preview_ok_undo_and_display(qtbot: QtBot, window: MainWindow) -> None:
    tab = _open(qtbot, window, _plate())
    assert window.commands.trigger("feature.ref_plane")
    tool = window.reference_tool
    panel = tool.panel
    assert panel is not None and panel.feature.name == "Plane 1"
    panel.take_pick(TOP)
    panel.fields["distance"].edit.setText("5")
    qtbot.waitUntil(lambda: panel.fully_defined, timeout=20000)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        panel.ok_button.click()
    assert tool.panel is None
    doc = tab.session.document
    plane = doc.features[-1]
    assert plane.type == "ref_plane" and plane.params["distance"].value == 5.0
    report = tab.session.report
    assert report is not None
    res = report.results[plane.id]
    assert res.state is FeatureState.OK and res.plane is not None
    assert res.plane.origin[2] == pytest.approx(15.0)
    # Shown until hidden on purpose; hiding is one undoable step.
    assert plane.id in tab.visible_plane_ids()
    tab.session.undo.push(SetVisibility(tab.session, plane.id, False))
    assert plane.id not in tab.visible_plane_ids()
    tab.session.undo.undo()
    assert plane.id in tab.visible_plane_ids()
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.undo()  # the plane itself
    assert doc.features[-1].type == "extrude"


def test_cancel_changes_nothing_and_bad_picks_block_ok(qtbot: QtBot, window: MainWindow) -> None:
    tab = _open(qtbot, window, _plate())
    tool = window.reference_tool
    tool.start("ref_plane")
    panel = tool.panel
    assert panel is not None
    lost = {"kind": "face", "name": "f6/side/e99", "snapshot": {"surface": "plane"}}
    panel.take_pick(TOP)
    panel.take_pick(lost)  # two planes: Mid plane, but the second face does not exist
    qtbot.waitUntil(lambda: bool(panel.preview_message), timeout=20000)
    assert not panel.ok_button.isEnabled()
    count = len(tab.session.document.features)
    panel.cancel_button.click()
    assert tool.panel is None and len(tab.session.document.features) == count


def test_axis_point_and_frame_draw_and_edit(qtbot: QtBot, window: MainWindow) -> None:
    doc = _plate()
    doc.features.append(
        Feature(
            "f9",
            "ref_axis",
            "Axis 1",
            params={"method": "two_planes"},
            refs={"first": {"feature": "f3"}, "second": {"feature": "f4"}},
        )
    )
    doc.features.append(
        Feature("f10", "coord_system", "Coordinate System 1", params={"method": "directions"})
    )
    doc.next_id = 11
    tab = _open(qtbot, window, doc)
    assert tab.visible_datum_ids() == ["f9", "f10"]
    assert len(tab.datum_shapes()) == 2
    tab.reference_hidden = True
    assert tab.visible_datum_ids() == []
    tab.reference_hidden = False
    window.edit_feature("f9")
    panel = window.reference_tool.panel
    assert panel is not None and panel.method_name == "two_planes"
    assert panel.picks[0] == {"feature": "f3"}
    qtbot.waitUntil(lambda: panel.fully_defined, timeout=20000)
    panel.checks["reverse"].setChecked(True)
    qtbot.waitUntil(lambda: panel.fully_defined, timeout=20000)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        panel.accept()
    assert tab.session.document.feature("f9").params.get("reverse") is True
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.undo()
    assert "reverse" not in tab.session.document.feature("f9").params


def test_tree_menu_offers_hide_and_sketch_for_reference_planes(
    qtbot: QtBot, window: MainWindow
) -> None:
    doc = _plate()
    doc.features.append(
        Feature(
            "f9",
            "ref_plane",
            "Plane 1",
            params={"method": "offset"},
            refs={"first": {"feature": "f2"}},
        )
    )
    doc.next_id = 10
    _open(qtbot, window, doc)
    tree = window.tree
    assert tree is not None
    item = tree.item_for("f9") if hasattr(tree, "item_for") else None
    if item is None:
        from fdcad.ui.tree.feature_tree import FID_ROLE

        items = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
        stack = list(items)
        while stack:
            it = stack.pop()
            if it is not None and it.data(0, FID_ROLE) == "f9":
                item = it
                break
            if it is not None:
                stack += [it.child(k) for k in range(it.childCount())]
    assert item is not None
    session = window.current.session  # type: ignore[union-attr]
    menu = tree._context_menu(session, item)
    assert menu is not None
    texts = [a.text() for a in menu.actions()]
    assert "Hide" in texts and "Sketch" in texts and "Edit Feature" in texts


# Project and Parallel to screen (D526) ----------------------------------------------------

CORNER = {"kind": "vertex", "name": "f6/v1", "snapshot": {}}


def test_project_method_guessed_with_along_normal_check(qtbot: QtBot) -> None:
    doc = _plate()
    feature = Feature("f9", "ref_plane", "Plane 1", params={"method": "offset"})
    panel = ReferencePanel(feature, UnitSystem.MM, {}, doc.features)
    qtbot.addWidget(panel)
    curved = {"kind": "face", "name": "f6/side/e9", "snapshot": {"surface": "cylinder"}}
    panel.take_pick(CORNER)
    panel.take_pick(curved)
    assert panel.method_name == "project"
    assert set(panel.checks) == {"along_normal", "flip_normal", "extra_flip"}  # TR149
    assert not panel.use_view.isVisibleTo(panel)
    panel.checks["along_normal"].setChecked(True)
    f = panel.current_feature()
    assert f.params == {"method": "project", "along_normal": True}
    assert f.refs == {"first": CORNER, "second": curved}


def test_screen_method_takes_the_view_direction_once(qtbot: QtBot) -> None:
    doc = _plate()
    feature = Feature("f9", "ref_plane", "Plane 1", params={"method": "offset"})
    panel = ReferencePanel(feature, UnitSystem.MM, {}, doc.features)
    qtbot.addWidget(panel)
    looking = [(0.0, 0.0, 1.0)]
    panel.view_direction = lambda: looking[0]
    panel.method.setCurrentIndex(panel.method.findData("screen"))
    panel._method_chosen()
    assert panel.use_view.isVisibleTo(panel)
    panel.take_pick(CORNER)
    looking[0] = (1.0, 0.0, 0.0)  # turning the view later does not move the plane
    f = panel.current_feature()
    assert (f.params["normal_x"], f.params["normal_y"], f.params["normal_z"]) == (0.0, 0.0, 1.0)
    panel.use_view.click()  # until the user takes the view again
    f = panel.current_feature()
    assert (f.params["normal_x"], f.params["normal_y"], f.params["normal_z"]) == (1.0, 0.0, 0.0)
    # Editing keeps the stored direction.
    again = ReferencePanel(f, UnitSystem.MM, {}, doc.features)
    qtbot.addWidget(again)
    assert again.screen_normal == (1.0, 0.0, 0.0) and again.missing() is None


def test_screen_method_without_a_view_says_so(qtbot: QtBot) -> None:
    doc = _plate()
    feature = Feature("f9", "ref_plane", "Plane 1", params={"method": "offset"})
    panel = ReferencePanel(feature, UnitSystem.MM, {}, doc.features)
    qtbot.addWidget(panel)
    panel.method.setCurrentIndex(panel.method.findData("screen"))
    panel._method_chosen()
    panel.take_pick(CORNER)
    assert panel.missing() == "Press Use Current View to take the view direction."
    assert "normal_x" not in panel.current_feature().params


def test_screen_plane_in_the_window(qtbot: QtBot, window: MainWindow) -> None:
    from fdcad.ui.reference_geometry import tool as tool_module

    tab = _open(qtbot, window, _plate())
    tool = window.reference_tool
    tool.start("ref_plane")
    panel = tool.panel
    assert panel is not None
    panel.view_direction = lambda: (0.0, 1.0, 0.0)
    panel.method.setCurrentIndex(panel.method.findData("screen"))
    panel._method_chosen()
    panel.take_pick({"feature": "f1"})  # the origin
    qtbot.waitUntil(lambda: panel.fully_defined, timeout=20000)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        panel.ok_button.click()
    plane = tab.session.document.features[-1]
    assert plane.params["method"] == "screen" and plane.params["normal_y"] == 1.0
    report = tab.session.report
    assert report is not None
    res = report.results[plane.id].plane
    assert res is not None and res.normal == pytest.approx((0, 1, 0))
    assert tool_module.view_direction(object()) is None


def test_sketch_points_lines_and_circles_can_be_picked(qtbot: QtBot) -> None:
    """Audit B item 3 (D718): only model faces, edges, vertices and reference features
    could be picked, though the guide promises sketch geometry."""
    doc = _plate()
    sketch = next(f for f in doc.features if f.type == "sketch")
    feature = Feature("f99", "ref_axis", "Axis 1", params={"method": "line"})
    doc.features.append(feature)
    panel = ReferencePanel(feature, UnitSystem.MM, {}, doc.features)
    qtbot.addWidget(panel)
    menu = panel._feature_menu(0)
    sub = next(a.menu() for a in menu.actions() if a.menu() is not None)
    assert sub.title() == sketch.name
    labels = [a.text() for a in sub.actions()]
    assert any(t.startswith("Line ") for t in labels) and any(
        t.startswith("Point ") for t in labels
    )
    sub.actions()[0].trigger()
    f = panel.current_feature()
    assert f.refs["first"]["feature"] == sketch.id and "sketch_entity" in f.refs["first"]


def test_a_circle_gives_its_axis() -> None:
    """Audit B item 3 (D718): arcs and circles were refused."""
    from fdcad.core.rebuild.runner import rebuild
    from fdcad.core.sketch.model import Sketch
    from tests.core.features.test_features import add_sketch

    doc = _plate()
    s = Sketch()
    cid = s.add_circle(5, 5, 2)
    sk = add_sketch(doc, s, {"feature": "f2"})
    feature = Feature(
        "f99",
        "ref_axis",
        "Axis 1",
        params={"method": "line"},
        refs={"first": {"feature": sk, "sketch_entity": cid}},
    )
    doc.features.append(feature)
    datum = rebuild(doc)["f99"].datum
    assert datum is not None and datum.direction is not None
    assert abs(abs(datum.direction[2]) - 1) < 1e-9 and datum.origin[:2] == pytest.approx((5, 5))


def test_several_offset_planes_in_one_command(qtbot: QtBot, window: MainWindow) -> None:
    """TR148 (D1925): How many 3 adds three planes, 5 mm apart, in one undo step."""
    tab = _open(qtbot, window, _plate())
    assert window.commands.trigger("feature.ref_plane")
    tool = window.reference_tool
    panel = tool.panel
    assert panel is not None
    panel.take_pick(TOP)
    panel.fields["distance"].edit.setText("5")
    assert panel.count_box is not None
    panel.count_box.setValue(3)
    qtbot.waitUntil(lambda: panel.fully_defined, timeout=20000)
    doc = tab.session.document
    before = len(doc.features)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        panel.ok_button.click()
    planes = doc.features[before:]
    assert [p.name for p in planes] == ["Plane 1", "Plane 2", "Plane 3"]
    report = tab.session.report
    assert report is not None
    heights = [report.results[p.id].plane.origin[2] for p in planes]  # type: ignore[union-attr]
    assert heights == pytest.approx([15.0, 20.0, 25.0])
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.undo()
    assert len(doc.features) == before


def test_the_tangent_plane_panel_offers_flip() -> None:
    """IDEAS 51 (D2629): Flip takes the other side of the cylinder."""
    from fdcad.ui.reference_geometry.specs import SPECS

    assert "flip" in SPECS["ref_plane"]["tangent"].checks
