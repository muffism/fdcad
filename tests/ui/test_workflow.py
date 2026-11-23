"""Tutorial workflow (docs/WORKFLOW_SPEC.md): sketches in the view and tree, plane
picking, feature first, confirmation corner, context toolbar."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QSettings, Qt
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import new_document
from fdcad.core.sketch.model import Line
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.session import DocumentSession
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.tree.feature_tree import FID_ROLE


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
    if win.sketch_mode is not None and win.sketch_mode.is_open:
        win.sketch_mode._close()
    while win.tabs.count():
        tab = win.tabs.widget(0)
        assert isinstance(tab, DocumentTab)
        tab.session.cancel_rebuild()
        tab.session.wait()
        tab.autosaver.discard()
        win.tabs.removeTab(0)
    win.close()
    win.deleteLater()


def new_part(qtbot: QtBot, win: MainWindow) -> DocumentTab:
    session = DocumentSession(new_document(), None, win)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = win.add_session(session)
    return tab


def canvas_of(win: MainWindow) -> SketchCanvas:
    mode = win.sketch_mode
    assert mode is not None and mode.canvas is not None
    return mode.canvas


def click(qtbot: QtBot, canvas: SketchCanvas, x: float, y: float, ctrl: bool = False) -> None:
    p = canvas.to_screen((x, y))
    pos = QPoint(round(p.x()), round(p.y()))
    mods = Qt.KeyboardModifier.ControlModifier if ctrl else Qt.KeyboardModifier.NoModifier
    qtbot.mouseMove(canvas, pos)
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, mods, pos=pos)


def plane_id(tab: DocumentTab, name: str) -> str:
    return next(f.id for f in tab.session.document.features if f.name == name)


def ready_canvas(qtbot: QtBot, win: MainWindow, center: tuple[float, float]) -> SketchCanvas:
    canvas = canvas_of(win)
    qtbot.wait(30)
    canvas.scale, canvas.center = 4.0, center
    return canvas


def rectangle_sketch(qtbot: QtBot, win: MainWindow, tab: DocumentTab) -> str:
    """Draw a 40 x 30 rectangle on Front and exit. Returns the sketch id."""
    assert win.sketch_mode is not None
    win.sketch_mode.start(plane_id=plane_id(tab, "Front Plane"))
    canvas = ready_canvas(qtbot, win, (20.0, 15.0))
    canvas.set_tool("corner_rectangle")
    click(qtbot, canvas, 0, 0)
    click(qtbot, canvas, 40, 30)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert win.sketch_mode.accept()
    return tab.session.document.features[-1].id


def sketch_item_parent(win: MainWindow, sid: str) -> object:
    assert win.tree is not None
    item = win.tree.item_for(sid)
    assert item is not None
    return item.parent()


# C1, W5.2, W5.3 -------------------------------------------------------------------------


def test_finished_sketch_shows_then_nests_and_hides(qtbot: QtBot, window: MainWindow) -> None:
    tab = new_part(qtbot, window)
    sid = rectangle_sketch(qtbot, window, tab)
    doc = tab.session.document
    assert doc.feature(sid).name == "Sketch 1"
    # The finished sketch stays visible and has 3D edges to draw.
    assert tab.visible_sketch_ids() == [sid]
    assert tab.session.report is not None and sid in tab.session.report.sketch_edges

    assert window.tree is not None
    window.tree.select(sid)
    window.insert_feature("extrude", "boss")
    assert window.panel is not None
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        window.panel.accept()
    fid = doc.features[-1].id
    # Used by a feature: hidden in the view, nested under the feature in the tree.
    assert tab.visible_sketch_ids() == []
    feature_item = window.tree.item_for(fid)
    assert feature_item is not None and feature_item.childCount() == 1
    assert feature_item.child(0).data(0, FID_ROLE) == sid
    assert feature_item.parent() is None and sketch_item_parent(window, sid) is feature_item

    # Right click the feature: Edit Sketch and Edit Feature.
    menu = window.tree._context_menu(tab.session, feature_item)
    assert menu is not None
    texts = [a.text() for a in menu.actions()]
    assert texts[:2] == ["Edit Sketch", "Edit Feature"]
    menu.actions()[0].trigger()
    assert window.sketch_mode is not None and window.sketch_mode.is_open
    assert canvas_of(window).edit.feature.id == sid
    window.sketch_mode._close()

    # Show the used sketch on purpose, then hide it again.
    sketch_item = window.tree.item_for(sid)
    assert sketch_item is not None
    menu = window.tree._context_menu(tab.session, sketch_item)
    assert menu is not None
    show = next(a for a in menu.actions() if a.text() == "Show")
    show.trigger()
    assert tab.visible_sketch_ids() == [sid]
    window.tree.set_sketch_visible(sid, False)
    assert tab.visible_sketch_ids() == []


# W1 -------------------------------------------------------------------------------------


def face_with_normal(tab: DocumentTab, normal: tuple[float, float, float]) -> object:
    """The flat face of the part with this outward normal, farthest along it."""
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    from fdcad.core.features.sketch import face_plane

    report = tab.session.report
    assert report is not None and report.body is not None
    best: tuple[float, object] | None = None
    explorer = TopExp_Explorer(report.body.shape, TopAbs_FACE)
    while explorer.More():
        face = TopoDS.Face(explorer.Current())
        explorer.Next()
        plane = face_plane(face)
        if plane is None or sum(a * b for a, b in zip(plane.normal, normal, strict=True)) < 0.999:
            continue
        along = sum(a * b for a, b in zip(plane.origin, normal, strict=True))
        if best is None or along > best[0]:
            best = (along, face)
    assert best is not None
    return best[1]


def test_sketch_with_nothing_selected_asks_for_a_plane(qtbot: QtBot, window: MainWindow) -> None:
    tab = new_part(qtbot, window)
    mode = window.sketch_mode
    assert mode is not None and window.tree is not None
    window.commands.trigger("sketch.sketch")
    assert mode.picker.active and not mode.is_open
    assert window.status.text().startswith("Select a plane or flat face")
    # Escape cancels.
    window.activateWindow()
    qtbot.keyClick(window, Qt.Key.Key_Escape)
    if mode.picker.active:  # offscreen platforms may not deliver window shortcuts
        mode.picker.cancel()
    assert not mode.picker.active and not mode.is_open
    # Clicking a plane in the tree opens the sketch on it.
    window.commands.trigger("sketch.sketch")
    window.tree.select(plane_id(tab, "Top Plane"))
    assert mode.is_open and not mode.picker.active
    assert canvas_of(window).edit.feature.refs["plane"] == {"feature": plane_id(tab, "Top Plane")}
    mode._close()


def test_preselected_plane_or_face_starts_at_once(qtbot: QtBot, window: MainWindow) -> None:
    tab = new_part(qtbot, window)
    mode = window.sketch_mode
    assert mode is not None and window.tree is not None
    window.tree.select(plane_id(tab, "Right Plane"))
    mode.start()
    assert mode.is_open
    assert canvas_of(window).edit.feature.refs["plane"] == {"feature": plane_id(tab, "Right Plane")}
    mode._close()

    sid = rectangle_sketch(qtbot, window, tab)
    window.tree.select(sid)
    window.insert_feature("extrude", "boss")
    assert window.panel is not None
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        window.panel.accept()
    from fdcad.ui.main_window.plane_pick import plane_faces

    assert set(plane_faces(tab)) == {"f2", "f3", "f4"}  # shown while picking
    tab.selection = [face_with_normal(tab, (0.0, 1.0, 0.0))]
    mode.start()
    assert mode.is_open
    ref = canvas_of(window).edit.feature.refs["plane"]
    assert ref.get("kind") == "face"


# W2 -------------------------------------------------------------------------------------


def draw_rectangle(qtbot: QtBot, win: MainWindow, w: float = 40, h: float = 30) -> None:
    canvas = ready_canvas(qtbot, win, (w / 2, h / 2))
    canvas.set_tool("corner_rectangle")
    click(qtbot, canvas, 0, 0)
    click(qtbot, canvas, w, h)
    canvas.set_tool(None)


def test_feature_first_sketches_then_opens_the_panel(qtbot: QtBot, window: MainWindow) -> None:
    tab = new_part(qtbot, window)
    mode, panel, tree = window.sketch_mode, window.panel, window.tree
    assert mode is not None and panel is not None and tree is not None
    window.commands.trigger("feature.extrude")
    assert mode.picker.active  # nothing selected: pick a plane first
    tree.select(plane_id(tab, "Front Plane"))
    assert mode.is_open
    draw_rectangle(qtbot, window)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert mode.accept()
    sid = tab.session.document.features[-1].id
    assert panel.is_editing and panel.feature is not None
    assert panel.feature.name == "Extrude 1"
    assert panel.feature.refs["sketch"] == {"feature": sid}
    # Cancelling the feature keeps the sketch.
    panel.cancel()
    assert tab.session.document.features[-1].id == sid

    # Nothing selected and exactly one unused sketch: the feature uses it at once.
    tree.setCurrentItem(None)
    window.commands.trigger("feature.extruded_cut")
    assert panel.is_editing and panel.feature is not None
    assert panel.feature.refs["sketch"] == {"feature": sid}
    assert panel.feature.name == "Cut 1"
    panel.cancel()

    # A preselected plane starts the feature's sketch on it at once.
    tree.select(plane_id(tab, "Top Plane"))
    window.commands.trigger("feature.extrude")
    assert mode.is_open and not mode.picker.active
    assert canvas_of(window).edit.feature.refs["plane"] == {"feature": plane_id(tab, "Top Plane")}
    mode._close()


def test_revolve_uses_a_lone_centerline(qtbot: QtBot, window: MainWindow) -> None:
    tab = new_part(qtbot, window)
    mode, panel, tree = window.sketch_mode, window.panel, window.tree
    assert mode is not None and panel is not None and tree is not None
    tree.select(plane_id(tab, "Front Plane"))
    window.commands.trigger("feature.revolve")
    canvas = ready_canvas(qtbot, window, (10.0, 15.0))
    canvas.set_tool("centerline")
    click(qtbot, canvas, 0, 0)
    click(qtbot, canvas, 0, 30)
    canvas.set_tool("corner_rectangle")
    click(qtbot, canvas, 10, 0)
    click(qtbot, canvas, 20, 30)
    axis = next(e.id for e in canvas.edit.sketch.curves(True) if e.construction)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert mode.accept()
    assert panel.feature is not None and panel.feature.name == "Revolve 1"
    assert panel.feature.refs["axis"] == {"sketch_entity": axis}
    assert panel.axis_box.currentData() == axis
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        panel.accept()
    report = tab.session.report
    assert report is not None and report.body is not None
    # After OK the new feature is selected, not the sketch.
    assert tree.selected_id() == tab.session.document.features[-1].id


# W5.1 -----------------------------------------------------------------------------------


def test_confirmation_corner_while_sketching_and_in_a_feature(
    qtbot: QtBot, window: MainWindow
) -> None:
    tab = new_part(qtbot, window)
    mode, panel = window.sketch_mode, window.panel
    assert mode is not None and panel is not None
    mode.start(plane_id=plane_id(tab, "Front Plane"))
    assert tab.corner_shown
    assert "Exit Sketch" in tab.corner_ok.toolTip()
    assert "discards" in tab.corner_cancel.toolTip()
    draw_rectangle(qtbot, window)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.corner_ok.click()  # exit and keep
    assert not mode.is_open and tab.session.document.features[-1].type == "sketch"

    window.commands.trigger("feature.extrude")
    assert window.editing == "feature"
    assert "<b>OK</b>" in tab.corner_ok.toolTip()
    assert "<b>Cancel</b>" in tab.corner_cancel.toolTip()
    menu = window.viewport_menu()
    assert menu is not None and menu.actions()[0].text() == "OK"
    menu.close()
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        menu.actions()[0].trigger()
    assert window.editing == "" and tab.session.document.features[-1].type == "extrude"


# W3 -------------------------------------------------------------------------------------


def test_ways_to_end_a_sketch_tool(qtbot: QtBot, window: MainWindow) -> None:
    tab = new_part(qtbot, window)
    mode = window.sketch_mode
    assert mode is not None
    mode.start(plane_id=plane_id(tab, "Front Plane"))
    canvas = ready_canvas(qtbot, window, (0.0, 0.0))
    line = mode.tool_actions["line"]
    line.trigger()
    assert canvas.tool_name == "line"
    line.trigger()  # the same button again
    assert canvas.tool_name == ""
    line.trigger()
    mode.tool_actions["circle"].trigger()  # another tool
    assert canvas.tool_name == "circle"
    qtbot.keyClick(canvas, Qt.Key.Key_Escape)
    assert canvas.tool_name == ""
    mode.tool_actions["point"].trigger()
    mode.select_action.trigger()
    assert canvas.tool_name == ""
    mode.tool_actions["line"].trigger()
    assert mode.panel is not None
    mode.panel.accepted.emit()  # OK in the panel ends the tool, the sketch stays open
    assert canvas.tool_name == "" and mode.is_open
    mode.panel.accepted.emit()  # a second OK exits
    assert not mode.is_open


def test_hovering_a_circle_reveals_its_centre(qtbot: QtBot, window: MainWindow) -> None:
    tab = new_part(qtbot, window)
    mode = window.sketch_mode
    assert mode is not None
    mode.start(plane_id=plane_id(tab, "Front Plane"))
    canvas = ready_canvas(qtbot, window, (10.0, 10.0))
    canvas.set_reference([], [((10.0, 10.0), 8.0)])  # a round edge of the part
    canvas.set_tool("circle")
    near_centre = canvas.to_screen((10.6, 10.4))
    assert canvas._snap_at(near_centre).kind != "center"  # not revealed yet
    edge = canvas.to_screen((18.0, 10.0))
    qtbot.mouseMove(canvas, edge.toPoint())
    assert canvas.revealed == [(10.0, 10.0)]
    snap = canvas._snap_at(near_centre)
    assert snap.kind == "center" and snap.xy == (10.0, 10.0)
    click(qtbot, canvas, 10.6, 10.4)
    click(qtbot, canvas, 14.0, 10.0)
    circle = next(iter(canvas.edit.sketch.curves()))
    assert canvas.edit.sketch.xy(circle.center) == pytest.approx((10.0, 10.0))


def test_relation_tags_and_ctrl_click_relations(qtbot: QtBot, window: MainWindow) -> None:
    tab = new_part(qtbot, window)
    mode = window.sketch_mode
    assert mode is not None
    mode.start(plane_id=plane_id(tab, "Front Plane"))
    canvas = ready_canvas(qtbot, window, (10.0, 10.0))
    canvas.set_tool("line")
    click(qtbot, canvas, 0, 0)
    click(qtbot, canvas, 20, 0)  # horizontal, gets a tag
    canvas.set_tool(None)
    assert [t for _a, t in canvas.tag_items()] == ["horizontal"]
    canvas.repaint()
    assert canvas._tags
    mode.relations_action.trigger()  # View menu: hide the tags
    assert not canvas.show_relations
    mode.relations_action.trigger()

    canvas.set_tool("point")
    click(qtbot, canvas, 5, 12)
    click(qtbot, canvas, 6, 25)
    canvas.set_tool(None)
    click(qtbot, canvas, 5, 12, ctrl=True)
    click(qtbot, canvas, 6, 25, ctrl=True)
    assert len(canvas.selection) == 2
    assert mode.panel is not None
    assert "vertical" in mode.panel.relation_buttons
    mode.panel.relation_buttons["vertical"].click()
    sk = canvas.edit.sketch
    assert any(r.type == "vertical" and len(r.entities) == 2 for r in sk.relations)
    a, b = (sk.xy(i) for i in canvas.selection)
    assert a[0] == pytest.approx(b[0])


# W4, W5.4 -------------------------------------------------------------------------------


def dimension_line(qtbot: QtBot, canvas: SketchCanvas, at: tuple[float, float]) -> None:
    """Smart Dimension: pick the line through ``at`` and place the text below it."""
    canvas.set_tool("dimension")
    click(qtbot, canvas, *at)
    click(qtbot, canvas, at[0], at[1] - 6)


def test_smart_dimension_value_box(qtbot: QtBot, window: MainWindow) -> None:
    from fdcad.ui.sketch_tools.value_box import ValueBox

    tab = new_part(qtbot, window)
    assert window.sketch_mode is not None
    window.sketch_mode.start(plane_id=plane_id(tab, "Front Plane"))
    canvas = ready_canvas(qtbot, window, (15.0, 0.0))
    canvas.set_tool("line")
    click(qtbot, canvas, 0, 0)
    click(qtbot, canvas, 30, 0)
    dimension_line(qtbot, canvas, (15, 0))
    box = canvas.value_box
    assert isinstance(box, ValueBox) and box.isVisible()
    assert box.edit.selectedText() == box.text()  # the current value is selected
    # The rebuild arrow applies the value and keeps the box open.
    box.edit.setText("2 * 20mm")
    box.rebuild.click()
    (dim,) = canvas.edit.sketch.dimensions
    assert dim.param.value == pytest.approx(40.0) and canvas.value_box is box
    # Enter accepts; units work.
    box.edit.setText("1in")
    qtbot.keyClick(box.edit, Qt.Key.Key_Return)
    assert canvas.value_box is None
    (dim,) = canvas.edit.sketch.dimensions
    assert dim.param.value == pytest.approx(25.4)
    # Double click the dimension to change it again.
    canvas.set_tool(None)
    canvas.repaint()
    label = canvas._labels[dim.id].center().toPoint()
    qtbot.mouseDClick(canvas, Qt.MouseButton.LeftButton, pos=label)
    assert canvas.value_box is not None and canvas.value_box.text() == "1in"
    canvas.value_box.cancel.click()
    assert canvas.value_box is None


def test_feature_dimensions_on_the_model(qtbot: QtBot, window: MainWindow) -> None:
    tab = new_part(qtbot, window)
    mode, panel, tree = window.sketch_mode, window.panel, window.tree
    assert mode is not None and panel is not None and tree is not None
    tree.select(plane_id(tab, "Front Plane"))
    window.commands.trigger("feature.extrude")
    draw_rectangle(qtbot, window)
    canvas = canvas_of(window)
    dimension_line(qtbot, canvas, (20, 0))
    assert canvas.value_box is not None
    canvas.value_box.edit.setText("50")
    canvas.value_box.ok.click()
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        mode.accept()
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        panel.accept()
    fid = tab.session.document.features[-1].id
    tree.select(fid)
    assert not window.model_dims.items  # selected for the user: the part stays clean
    item = tree.item_for(fid)
    assert item is not None
    tree.itemClicked.emit(item, 0)  # the user clicks it in the tree
    keys = set(window.model_dims.items)
    assert f"{fid}:depth" in keys and len(keys) == 2
    # Double click the depth on the model and type a new value.
    box = window.model_dims.edit(f"{fid}:depth")
    assert box is not None and box.text() == "10"
    assert box.kind is not None and box.step.isVisible()  # wheel and arrow stepping (T4.2.3)
    box.edit.setText("25")
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        box.ok.click()
    depth = tab.session.document.feature(fid).params["depth"]
    assert depth.value == pytest.approx(25.0)  # type: ignore[union-attr]
    # A sketch dimension shown on the model changes the sketch.
    sketch_key = next(k for k in window.model_dims.items if not k.endswith(":depth"))
    box = window.model_dims.edit(sketch_key)
    assert box is not None
    box.edit.setText("60")
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        box.ok.click()
    report = tab.session.report
    assert report is not None and report.body is not None
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    bounds = Bnd_Box()
    BRepBndLib.Add_s(report.body.shape, bounds)
    lo, hi = bounds.CornerMin(), bounds.CornerMax()
    assert hi.X() - lo.X() == pytest.approx(60.0, abs=0.01)
    assert hi.Z() - lo.Z() == pytest.approx(25.0, abs=0.01)
    assert tab.session.undo.count() == 4  # sketch, extrude, depth, sketch dimension


# C8 -------------------------------------------------------------------------------------


def test_context_toolbar_for_planes_sketches_faces_and_features(
    qtbot: QtBot, window: MainWindow
) -> None:
    tab = new_part(qtbot, window)
    bar, tree, mode = window.context_bar, window.tree, window.sketch_mode
    assert tree is not None and mode is not None
    tree.select(plane_id(tab, "Front Plane"))
    bar.for_tree()
    # TOOL_SPEC T8.2 contents (D170 replaces D110 item 9).
    assert list(bar.buttons) == ["sketch", "normal_to", "hide"]
    assert bar.isVisible() and not bar.isActiveWindow()
    bar.buttons["sketch"].click()
    assert mode.is_open and not bar.isVisible()
    draw_rectangle(qtbot, window)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        mode.accept()
    sid = tab.session.document.features[-1].id

    tree.select(sid)
    bar.for_tree()
    assert list(bar.buttons) == ["edit_sketch", "extrude", "revolve", "hide"]
    bar.buttons["hide"].click()
    assert tab.visible_sketch_ids() == []
    tree.select(sid)
    bar.for_tree()
    assert bar.buttons["hide"].toolTip() == "Show"
    bar.buttons["hide"].click()
    tree.select(sid)
    bar.for_tree()
    bar.buttons["extrude"].click()
    assert window.panel is not None and window.panel.is_editing
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        window.panel.accept()
    fid = tab.session.document.features[-1].id

    tree.select(fid)
    bar.for_tree()
    assert list(bar.buttons) == ["edit", "edit_sketch", "hide", "delete"]
    bar.for_faces([face_with_normal(tab, (0.0, 0.0, 1.0))])  # the extrude's end face
    assert list(bar.buttons) == ["sketch", "normal_to", "hide"]  # Hide Body (D745)
    bar.buttons["sketch"].click()  # a sketch on the face
    assert mode.is_open
    assert canvas_of(window).edit.feature.refs["plane"].get("kind") == "face"
    mode._close()


def test_enter_escape_axis_pick_and_sketch_under_the_preview(
    qtbot: QtBot, window: MainWindow
) -> None:
    tab = new_part(qtbot, window)
    mode, panel, tree = window.sketch_mode, window.panel, window.tree
    assert mode is not None and panel is not None and tree is not None
    tree.select(plane_id(tab, "Front Plane"))
    window.commands.trigger("feature.revolve")
    canvas = ready_canvas(qtbot, window, (15.0, 15.0))
    canvas.set_tool("corner_rectangle")
    click(qtbot, canvas, 0, 0)
    click(qtbot, canvas, 20, 30)
    left = next(
        e.id
        for e in canvas.edit.sketch.curves()
        if isinstance(e, Line) and max(abs(canvas.edit.sketch.xy(p)[0]) for p in (e.p1, e.p2)) < 1
    )
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        mode.accept()
    sid = tab.session.document.features[-1].id
    assert panel.is_editing
    # The lines of the sketch are offered as the axis; clicking one picks it.
    assert left in tab.axis_lines(sid)
    window._axis_picked(left)
    assert panel.axis_box.currentData() == left
    # Escape in the view cancels; the sketch stays.
    window._escape()
    assert not panel.is_editing and tab.session.document.features[-1].id == sid
    # Enter in the view accepts.
    window.commands.trigger("feature.revolve")
    window._axis_picked(left)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        window.commands.trigger("edit.repeat")
    assert not panel.is_editing and tab.session.document.features[-1].type == "revolve"
    # Editing the feature shows its sketch under the preview, and hides it again after.
    assert tab.visible_sketch_ids() == []
    window.edit_feature(tab.session.document.features[-1].id)
    assert tab.visible_sketch_ids() == [sid]
    panel.reject()
    assert tab.visible_sketch_ids() == []


class _FakeView:
    def __init__(self) -> None:
        self.nav_count = 0
        self.looks: list[object] = []

    def look(self, eye: object, up: object) -> None:
        self.looks.append((eye, up))


def test_trimetric_unless_the_view_moved(qtbot: QtBot, window: MainWindow) -> None:
    from fdcad.ui.main_window.new_feature import TRIMETRIC, FeatureFlow

    tab = new_part(qtbot, window)
    flow = FeatureFlow(window)
    real, fake = tab.viewport, _FakeView()
    tab.viewport = fake
    try:
        assert window.sketch_mode is not None
        window.sketch_mode.exit_nav = 0
        assert flow.trimetric(tab) and fake.looks == [TRIMETRIC]
        fake.nav_count = 3  # the user rotated after leaving the sketch
        assert not flow.trimetric(tab)
    finally:
        tab.viewport = real
