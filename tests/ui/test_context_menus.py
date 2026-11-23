"""Right click menus and the context toolbar (TOOL_SPEC T8, T9, owner note 6, D116 item 2).

Menus are built without running them, as the tree's ``_context_menu`` is. The
3D view does not exist on the offscreen platform, so what lies under the
cursor is passed in directly.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtWidgets import QMenu
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.chain import chain_of
from fdcad.core.sketch.model import Line
from fdcad.ui import strings
from fdcad.ui.main_window.context_menu import keys, make_vertex
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from tests.ui.test_workflow import (  # noqa: F401  (fixtures)
    _folders,
    canvas_of,
    click,
    draw_rectangle,
    face_with_normal,
    new_part,
    plane_id,
    ready_canvas,
    rectangle_sketch,
    window,
)


def _sub(menu: QMenu, title: str) -> QMenu:
    for action in menu.actions():
        sub = action.menu()
        if sub is not None and sub.title() == title:
            return sub
    raise AssertionError(f"no submenu {title}")


def _run(menu: QMenu, key: str) -> None:
    action = next(a for a in menu.actions() if a.data() == key)
    action.trigger()


def _extruded(qtbot: QtBot, win: MainWindow) -> tuple[DocumentTab, str, str]:
    tab = new_part(qtbot, win)
    sid = rectangle_sketch(qtbot, win, tab)
    assert win.tree is not None and win.panel is not None
    win.tree.select(sid)
    win.insert_feature("extrude", "boss")
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        win.panel.accept()
    return tab, sid, tab.session.document.features[-1].id


# 3D view ----------------------------------------------------------------------------------


def test_empty_view_menu_replaces_the_shortcut_bar(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = new_part(qtbot, window)
    menu = window.viewport_menu(QPointF(10, 10))
    assert menu is not None and menu.isVisible()
    assert keys(menu) == [
        "select",
        "appearance",
        "zoom_fit",
        "previous_view",
        "View Orientation",
        "Display Style",
        "Recent Commands",
    ]
    assert "view.top" in keys(_sub(menu, "View Orientation"))
    styles = _sub(menu, "Display Style")
    assert keys(styles) == [
        "style.shaded_edges",
        "style.shaded",
        "style.hidden_lines",
        "style.hidden_lines_visible",
        "style.wireframe",
    ]
    menu.close()
    # Recent Commands lists commands run lately.
    window.commands.trigger("sketch.sketch")
    assert window.sketch_mode is not None
    window.sketch_mode.picker.cancel()
    menu = window.context_menus.build_view_menu(tab, [])
    assert keys(_sub(menu, "Recent Commands")) == ["sketch.sketch"]


def test_feature_panel_menu_has_ok_cancel_reverse_and_view_items(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab, _sid, fid = _extruded(qtbot, window)
    window.edit_feature(fid)
    assert window.editing == "feature" and window.panel is not None
    menu = window.context_menus.build_view_menu(tab, [])
    assert keys(menu)[:4] == ["ok", "cancel", "reverse", "zoom_fit"]
    reverse = window.panel.flags["reverse"]
    before = reverse.isChecked()
    _run(menu, "reverse")
    assert reverse.isChecked() != before
    window.panel.reject()


def test_plane_menu_in_the_view(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = new_part(qtbot, window)
    front = plane_id(tab, "Front Plane")
    menu = window.context_menus.build_view_menu(tab, [], plane=front)
    assert keys(menu)[:4] == ["sketch", "normal_to", "hide_show", "rename"]
    _run(menu, "hide_show")
    assert front in tab.visible_plane_ids()
    menu = window.context_menus.build_view_menu(tab, [], plane=front)
    assert next(a.text() for a in menu.actions() if a.data() == "hide_show") == "Hide"
    _run(menu, "sketch")
    assert window.sketch_mode is not None and window.sketch_mode.is_open


def test_face_menu_hides_the_body_and_keyboard_menus_offer_select_other(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audit D11 items 8 and 9 (D745): no Hide Body on a face, and no Select Other when
    the menu opened from the keyboard."""
    from fdcad.ui.main_window import context_menu as cm

    tab, _sid, _fid = _extruded(qtbot, window)
    face = face_with_normal(tab, (0.0, 0.0, 1.0))
    monkeypatch.setattr(cm, "_cursor_in", lambda _tab: QPointF(5, 5))
    menu = window.context_menus.build_view_menu(tab, [face], pos=None)
    assert "select_other" in keys(menu)
    hidden: list[bool] = []
    monkeypatch.setattr(window.body_display, "hide_or_show", lambda: hidden.append(True) or True)
    _run(menu, "hide")
    assert hidden and tab.selection == [face]


def test_face_edge_and_vertex_menus(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab, _sid, fid = _extruded(qtbot, window)
    face = face_with_normal(tab, (0.0, 0.0, 1.0))
    menu = window.context_menus.build_view_menu(tab, [face], pos=QPointF(5, 5))
    assert keys(menu)[:4] == ["sketch", "normal_to", "select_other", "hide"]
    assert {"feature.move_face", "feature.delete_face"} <= set(keys(menu))  # P3.1
    feature_menu = _sub(menu, "Extrude 1")
    assert [a.text() for a in feature_menu.actions()][:2] == ["Edit Sketch", "Edit Feature"]
    assert window.context_menus.feature_of(tab, face) == fid

    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer

    report = tab.session.report
    assert report is not None and report.body is not None
    edge = TopExp_Explorer(report.body.shape, TopAbs_EDGE).Current()
    menu = window.context_menus.build_view_menu(tab, [edge], pos=QPointF(5, 5))
    assert keys(menu)[:2] == ["select_other", "select_midpoint"]
    _run(menu, "select_midpoint")
    assert len(tab.selection) == 1
    assert "Midpoint" in window.status.text()


def test_cylinder_face_offers_normal_to_but_not_sketch(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer

    from fdcad.ui.main_window.context_menu import face_axis

    tab = new_part(qtbot, window)
    cylinder = BRepPrimAPI_MakeCylinder(5, 10).Shape()
    explorer = TopExp_Explorer(cylinder, TopAbs_FACE)
    side = explorer.Current()
    assert face_axis(side) is not None
    menu = window.context_menus.build_view_menu(tab, [side])
    assert "normal_to" in keys(menu) and "sketch" not in keys(menu)
    explorer.Next()
    assert face_axis(explorer.Current()) is None  # a flat end


def test_menu_opens_below_the_context_toolbar(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = new_part(qtbot, window)
    assert window.tree is not None
    window.tree.select(plane_id(tab, "Front Plane"))
    window.context_bar.for_tree()
    assert window.context_bar.isVisible()
    menu = window.viewport_menu(QPointF(10, 10))
    assert menu is not None
    bar = window.context_bar.frameGeometry()
    # Just below the bar (Qt may move it sideways to keep it on the screen).
    assert bar.bottom() <= menu.pos().y() <= bar.bottom() + 4
    menu.close()
    window.context_bar.hide()


def test_shift_f10_opens_the_tree_menu(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = new_part(qtbot, window)
    tree = window.tree
    assert tree is not None
    tree.select(plane_id(tab, "Top Plane"))
    tree.setFocus()
    window.activateWindow()
    qtbot.waitUntil(tree.hasFocus, timeout=2000)
    assert window.commands.trigger("ui.context_menu")
    menu = window.context_menus.last
    assert menu is not None and [a.text() for a in menu.actions()][:2] == ["Sketch", "Normal To"]
    menu.close()
    keys_of = window.commands.actions["ui.context_menu"].shortcuts()
    assert [k.toString() for k in keys_of] == ["Shift+F10", "Menu"]


# Sketch editor ------------------------------------------------------------------------------


def _sketch(qtbot: QtBot, win: MainWindow) -> tuple[DocumentTab, object]:
    tab = new_part(qtbot, win)
    assert win.sketch_mode is not None
    win.sketch_mode.start(plane_id=plane_id(tab, "Front Plane"))
    return tab, ready_canvas(qtbot, win, (20.0, 15.0))


def test_sketch_menus_for_tool_empty_space_entities_and_dimensions(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    _tab, _c = _sketch(qtbot, window)
    canvas = canvas_of(window)
    menus = window.context_menus
    canvas.set_tool("line")
    click(qtbot, canvas, 0, 0)
    assert keys(menus.build_sketch_menu(canvas)) == [
        "select",
        "end_chain",
        "snapping",
        "zoom_fit",
        "Snap Next Click To",
    ]
    _run(menus.build_sketch_menu(canvas), "end_chain")
    assert canvas.tool_name == "line" and not canvas.tool.busy  # type: ignore[union-attr]
    assert keys(menus.build_sketch_menu(canvas)) == [
        "select",
        "snapping",
        "zoom_fit",
        "Snap Next Click To",
    ]
    _run(menus.build_sketch_menu(canvas), "select")
    assert canvas.tool_name == ""

    empty = menus.build_sketch_menu(canvas, QPointF(2, 2))
    assert keys(empty) == [
        "select",
        "exit_sketch",
        "discard",
        "dimension",
        "snapping",
        "last_tool",
        "zoom_fit",
        "normal_to",  # T9.2 (audit D11 item 7, D719)
        "grid_spacing",  # TR102
        "show_formulas",  # TR235
        "shade_regions",  # TR335
        "show_points",
        "Show in Sketch",  # TR341
        "Layers",  # TR389
        "reference_mode",  # TR111
        "shake",  # TR372
        "lock_points",
        "free_drag",  # TR112 (D1716)
        "detach_drag",
        "cut_away",  # TR113
        "airfoil",  # TR257
        "gear",  # TR161
        "code_tag",  # TR311
        "shapes",  # TR228
        "points_file",  # TR415
        "modify_sketch",  # TR50
        "find_relations",  # TR416
    ]
    assert next(a.text() for a in empty.actions() if a.data() == "last_tool") == "Last Tool: Line"
    _run(menus.build_sketch_menu(canvas, QPointF(2, 2)), "normal_to")
    assert "already faces you" in window.status.text()
    snapping = next(a for a in empty.actions() if a.data() == "snapping")
    assert snapping.isChecked()
    snapping.trigger()
    assert not window.settings.sketch_options.snapping
    assert not canvas.options.snapping
    _run(menus.build_sketch_menu(canvas, QPointF(2, 2)), "snapping")
    assert canvas.options.snapping

    draw_rectangle(qtbot, window)
    sk = canvas.edit.sketch
    lines = [e.id for e in sk.entities.values() if isinstance(e, Line)]
    canvas.selection = lines[:2]
    menu = menus.build_sketch_menu(canvas)
    assert keys(menu)[:3] == ["delete", "construction", "dimension"]
    assert "relation.equal" in keys(_sub(menu, "Add Relation"))
    assert "fix" in keys(menu)
    before = len(sk.relations)
    _run(_sub(menu, "Add Relation"), "relation.equal")
    assert len(canvas.edit.sketch.relations) == before + 1
    assert "detach" not in keys(menu)  # ordinary geometry: nothing to detach
    # A fixed copy of a model edge can be detached (TR340, D885).
    canvas.edit.sketch.relate("fixed", lines[0])
    canvas.selection = lines[:1]
    menu = menus.build_sketch_menu(canvas)
    _run(menu, "detach")
    assert not any(
        r.type == "fixed" and lines[0] in r.entities for r in canvas.edit.sketch.relations
    )

    # Right click on one line: it becomes the selection; Select Chain takes the loop.
    mid = canvas.to_screen((20.0, 0.0))
    canvas.selection = []
    menu = menus.build_sketch_menu(canvas, mid)
    assert canvas.selection == [lines[0]] or len(canvas.selection) == 1
    _run(menu, "select_chain")
    assert sorted(canvas.selection) == sorted(lines)

    canvas.selection = [lines[0]]
    _run(menus.build_sketch_menu(canvas), "construction")
    entity = canvas.edit.sketch.entities[lines[0]]
    assert isinstance(entity, Line) and entity.construction


def test_select_chain_from_the_selection_when_nothing_is_hit(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """Audit D11 item 9 (D2681): the menu for selected sketch items (T9.8), opened from
    the keyboard (T9.12) or off the items, had no Select Chain."""
    _tab, _c = _sketch(qtbot, window)
    canvas = canvas_of(window)
    menus = window.context_menus
    draw_rectangle(qtbot, window)
    sk = canvas.edit.sketch
    lines = [e.id for e in sk.entities.values() if isinstance(e, Line)]
    canvas.selection = lines[:1]
    menu = menus.build_sketch_menu(canvas)  # Shift+F10: no position, nothing hit
    assert "select_chain" in keys(menu)
    _run(menu, "select_chain")
    assert sorted(canvas.selection) == sorted(lines)
    canvas.selection = lines[:1]
    off = menus.build_sketch_menu(canvas, QPointF(2, 2))  # a click away from the items
    assert canvas.selection == lines[:1] and "select_chain" in keys(off)


def test_dimension_menu_toggles_reference(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    _tab, _c = _sketch(qtbot, window)
    canvas = canvas_of(window)
    draw_rectangle(qtbot, window)
    line = next(e.id for e in canvas.edit.sketch.entities.values() if isinstance(e, Line))
    canvas.run(lambda: canvas.edit.add_dimension("distance", [line], None))
    did = canvas.edit.sketch.dimensions[-1].id
    canvas.selection = [did]
    menu = window.context_menus.build_sketch_menu(canvas)
    assert keys(menu) == [
        "edit_value",
        "reference",
        "display",
        "step_values",
        "switch_off",
        "Limit",  # TR342 (D1311)
        "delete",
    ]
    _run(menu, "reference")
    dim = canvas.edit.sketch.dimensions[-1]
    assert not dim.driving
    menu = window.context_menus.build_sketch_menu(canvas)
    assert keys(menu) == ["reference", "display", "switch_off", "delete"]  # cannot be typed
    assert next(a.text() for a in menu.actions() if a.data() == "reference") == "Make Driving"
    _run(menu, "reference")
    dim = canvas.edit.sketch.dimensions[-1]
    assert dim.driving and dim.param.value == pytest.approx(40.0, abs=0.5)  # mouse drawn
    canvas.undo()
    assert not canvas.edit.sketch.dimensions[-1].driving


def test_right_click_in_a_tool_opens_the_menu_and_keeps_the_tool(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    _tab, _c = _sketch(qtbot, window)
    canvas = canvas_of(window)
    canvas.set_tool("circle")
    pos = QPoint(50, 50)
    qtbot.mouseClick(canvas, Qt.MouseButton.RightButton, pos=pos)
    menu = window.context_menus.last
    assert menu is not None and menu.isVisible()
    assert keys(menu)[0] == "select"
    assert canvas.tool_name == "circle"
    menu.close()
    # A right drag is still a gesture (T10.2), not a menu.
    window.context_menus.last = None
    qtbot.mousePress(canvas, Qt.MouseButton.RightButton, pos=pos)
    qtbot.mouseMove(canvas, QPoint(50, 150))
    qtbot.mouseRelease(canvas, Qt.MouseButton.RightButton, pos=QPoint(50, 150))
    assert window.context_menus.last is None
    assert canvas.tool_name == "corner_rectangle"  # the down gesture


# Context toolbar (T8) ---------------------------------------------------------------------------


def test_context_toolbar_contents(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab, sid, fid = _extruded(qtbot, window)
    bar, tree = window.context_bar, window.tree
    assert tree is not None
    tree.select(plane_id(tab, "Front Plane"))
    bar.for_tree()
    assert list(bar.buttons) == ["sketch", "normal_to", "hide"]
    assert bar.buttons["hide"].toolTip() == "Show"
    tree.select(sid)
    bar.for_tree()
    assert list(bar.buttons) == ["edit_sketch", "extrude", "revolve", "hide"]
    tree.select(fid)
    bar.for_tree()
    assert list(bar.buttons) == ["edit", "edit_sketch", "hide", "delete"]
    assert bar.buttons["hide"].toolTip() == "Show"
    bar.buttons["hide"].click()
    assert sid in tab.visible_sketch_ids()
    bar.for_faces([face_with_normal(tab, (0.0, 0.0, 1.0))])
    assert list(bar.buttons) == ["sketch", "normal_to", "hide"]  # Hide Body (audit D11 item 8)
    bar.hide()


def test_context_toolbar_for_sketch_items(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    _tab, _c = _sketch(qtbot, window)
    canvas = canvas_of(window)
    draw_rectangle(qtbot, window)
    bar = window.context_bar
    lines = [e.id for e in canvas.edit.sketch.entities.values() if isinstance(e, Line)]
    click(qtbot, canvas, 20.0, 0.0)
    click(qtbot, canvas, 20.0, 30.0, ctrl=True)
    assert sorted(canvas.selection) == sorted([lines[0], lines[2]])
    assert bar.isVisible()
    assert "relation.equal" in bar.buttons
    assert list(bar.buttons)[-2:] == ["construction", "dimension"]
    # Audit D11 item 1 (D719): the last relation button was added twice.
    offered: list[str] = []
    real = bar.offer
    bar.offer = lambda items: (offered.extend(i[0] for i in items), real(items))[1]  # type: ignore[method-assign]
    bar.for_sketch(canvas)
    bar.offer = real  # type: ignore[method-assign]
    assert len(offered) == len(set(offered))
    before = len(canvas.edit.sketch.relations)
    bar.buttons["relation.equal"].click()
    assert len(canvas.edit.sketch.relations) == before + 1
    # Empty space clears the selection when it is more than 40 px from the picks; nearer,
    # a click places the selection's dimension (TR110, D862). Zoom in so the middle of
    # the rectangle is far from both lines, even when the canvas shifts as the context
    # bar changes before the click arrives.
    canvas.scale = max(canvas.scale, 8.0)
    canvas.update()
    click(qtbot, canvas, 20.0, 15.0)
    assert canvas.selection == []
    click(qtbot, canvas, 20.0, 0.0)
    bar.buttons["dimension"].click()
    assert canvas.tool_name == "dimension" and canvas.dim_picks == [lines[0]]
    canvas.set_tool(None)
    bar.hide()


# Tree ----------------------------------------------------------------------------------------


def test_tree_menus_follow_t9(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tab, sid, fid = _extruded(qtbot, window)
    tree = window.tree
    assert tree is not None
    front = plane_id(tab, "Front Plane")
    menu = tree._context_menu(tab.session, tree.item_for(front))  # type: ignore[arg-type]
    assert menu is not None
    assert [a.text() for a in menu.actions()][:4] == ["Sketch", "Normal To", "Show", "Rename"]
    item = tree.item_for(fid)
    assert item is not None
    texts = [a.text() for a in tree._context_menu(tab.session, item).actions()]  # type: ignore[union-attr]
    assert "Show Sketch" in texts and "Delete" in texts
    # Delete asks whether to keep the sketch; deleting both is one undo step.
    monkeypatch.setattr(tree, "ask_keep_sketch", lambda *_a: False)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tree.delete(fid)
    ids = [f.id for f in tab.session.document.features]
    assert fid not in ids and sid not in ids
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.undo()
    ids = [f.id for f in tab.session.document.features]
    assert fid in ids and sid in ids
    monkeypatch.setattr(tree, "ask_keep_sketch", lambda *_a: True)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tree.delete(fid)
    ids = [f.id for f in tab.session.document.features]
    assert fid not in ids and sid in ids
    monkeypatch.setattr(tree, "ask_keep_sketch", lambda *_a: None)
    assert tree.item_for(sid) is not None


def test_plane_rows_can_be_renamed(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = new_part(qtbot, window)
    tree = window.tree
    assert tree is not None
    front = plane_id(tab, "Front Plane")
    item = tree.item_for(front)
    assert item is not None and item.flags() & Qt.ItemFlag.ItemIsEditable
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        item.setText(0, "Datum A")
    assert tab.session.document.feature(front).name == "Datum A"


# Pure helpers --------------------------------------------------------------------------------


def test_chain_follows_shared_and_coincident_end_points() -> None:
    from fdcad.core.sketch.model import Point, Relation, Sketch

    sk = Sketch()
    for pid, x, y in (("p1", 0, 0), ("p2", 10, 0), ("p3", 10, 10), ("p4", 10, 10), ("p5", 30, 30)):
        sk.entities[pid] = Point(pid, x, y)
    sk.entities["l1"] = Line("l1", "p1", "p2")
    sk.entities["l2"] = Line("l2", "p2", "p3")
    sk.entities["l3"] = Line("l3", "p4", "p5")
    sk.entities["l4"] = Line("l4", "p5", "p5")
    assert chain_of(sk, "l1") == ["l1", "l2"]
    sk.relations.append(Relation("coincident", ["p3", "p4"]))
    assert chain_of(sk, "l1") == ["l1", "l2", "l3", "l4"]
    assert chain_of(sk, "p1") == ["p1"]
    assert chain_of(sk, "nope") == []


def test_midpoint_of_an_edge() -> None:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.gp import gp_Pnt

    from fdcad.core.naming.edges import edge_midpoint

    edge = BRepBuilderAPI_MakeEdge(gp_Pnt(0, 0, 0), gp_Pnt(10, 4, 2)).Edge()
    assert edge_midpoint(edge) == pytest.approx((5.0, 2.0, 1.0))
    vertex = make_vertex((1.0, 2.0, 3.0))
    assert not vertex.IsNull()
    assert math.isfinite(1.0)


# Select Other (T9.13, T14.3.1) ---------------------------------------------------------------


class _FakeView:
    """Stands in for the 3D view, which needs a GPU."""

    def __init__(self) -> None:
        self.marked: list[object] = []
        self.selected: list[object] = []
        self.hidden: list[object] = []
        self.shown_again = 0

    def plane_under(self, _pos: object) -> None:
        return None

    def preview_shapes(self, shapes: list[object]) -> None:
        self.marked = list(shapes)

    def select_shapes(self, shapes: list[object]) -> None:
        self.selected = list(shapes)

    def hide_face_for_now(self, face: object) -> None:
        self.hidden.append(face)

    def show_hidden_faces(self) -> None:
        self.shown_again += 1

    def mapToGlobal(self, p: QPoint) -> QPoint:  # noqa: N802
        return p


def test_select_other_lists_steps_hides_and_selects(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer

    from fdcad.ui.viewport.select_other import open_select_other, step

    tab, _sid, _fid = _extruded(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    faces = TopExp_Explorer(report.body.shape, TopAbs_FACE)
    front = faces.Current()
    faces.Next()
    back = faces.Current()
    edge = TopExp_Explorer(report.body.shape, TopAbs_EDGE).Current()
    fake = _FakeView()
    real = tab.viewport
    tab.viewport = fake
    try:
        popup = open_select_other(window, tab, QPointF(1, 1), [front, back, edge])
        assert popup is not None
        labels = [popup.rows.item(i).text() for i in range(popup.rows.count())]
        assert labels == ["Face 1 (Extrude 1)", "Face 2 (Extrude 1)", "Edge 1 (Extrude 1)"]
        assert fake.marked == [front]
        qtbot.keyClick(popup.rows, Qt.Key.Key_Tab)
        assert popup.current() == 1 and fake.marked == [back]
        qtbot.keyClick(popup.rows, Qt.Key.Key_Backtab)
        assert popup.current() == 0
        popup.step(-1)
        assert popup.current() == 2  # wraps round
        popup.hide_row(0)
        assert fake.hidden == [front]
        popup.hide_row(2)  # not a face: nothing hidden
        assert fake.hidden == [front]
        popup.choose(1)
        assert fake.selected == [back] and tab.selection == [back]
        assert fake.shown_again >= 1 and fake.marked == []
        assert open_select_other(window, tab, QPointF(1, 1), []) is None
    finally:
        tab.viewport = real
    assert step(0, 1, 0) == -1 and step(2, 1, 3) == 0


def test_appearance_from_a_face_a_tree_feature_and_the_part(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    # Owner request: colours for the part, faces and features must be easy to reach.
    tab, _sid, fid = _extruded(qtbot, window)
    face = face_with_normal(tab, (0.0, 0.0, 1.0))
    tab.selection = [face]
    menu = window.context_menus.build_view_menu(tab, [face], pos=QPointF(5, 5))
    _run(menu, "appearance")
    panel = window.appearance_tool.panel
    assert panel is not None and panel.targets[0][1][0].kind == "face"
    tree = window.tree
    assert tree is not None
    item = tree.item_for(fid)
    assert item is not None
    feature_menu = tree._context_menu(tab.session, item)
    assert feature_menu is not None
    [action] = [a for a in feature_menu.actions() if a.text() == "Appearance"]
    action.trigger()
    panel = window.appearance_tool.panel
    assert panel is not None and panel.targets[0][1][0].kind == "feature"
    assert tab.selection == []
    window.appearance_for("")
    panel = window.appearance_tool.panel
    assert panel is not None and panel.targets[0][1][0].kind == "part"


def test_context_toolbar_for_any_feature(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """Audit D11 item 6 (D719): only extrude and revolve got the toolbar."""
    from fdcad.core.document.model import Feature
    from fdcad.ui.commands.document import AddFeature

    tab, _sid, _fid = _extruded(qtbot, window)
    session = tab.session
    fillet = Feature(session.document.new_feature_id(), "fillet", "Fillet 1")
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.push(AddFeature(session, fillet))
    assert window.tree is not None
    window.tree.select(fillet.id)
    window.context_bar.for_tree()
    assert list(window.context_bar.buttons) == ["edit", "delete"]


def test_length_ratio_asks_for_the_value(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    """TR226, D870."""
    from fdcad.core.units import UnitSystem
    from fdcad.ui.main_window import context_menu as cm
    from fdcad.ui.sketch_tools.canvas import SketchCanvas
    from tests.ui.sketch_tools.p2_helpers import edit_of

    canvas = SketchCanvas(edit_of(), UnitSystem.MM)
    qtbot.addWidget(canvas)
    sk = canvas.edit.sketch
    a = sk.add_line(0, 0, 10, 0)
    b = sk.add_line(0, 5, 4, 5)
    from fdcad.ui.sketch_tools.edit import relations_for

    assert {"length_ratio", "length_difference"} <= set(relations_for(sk, [a, b]))
    monkeypatch.setattr(cm, "selected_entities", lambda _c: [a, b])
    monkeypatch.setattr(cm, "ask_relation_value", lambda _c, _r, _i: 2.0)
    cm.relate(canvas, "length_ratio")
    rel = canvas.edit.sketch.relations[-1]
    assert rel.type == "length_ratio" and rel.value == 2.0


def test_mean_dimensions_menu(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """TR306 (D911): Mean Dimensions shows for an uneven tolerance and goes back."""
    _tab, _c = _sketch(qtbot, window)
    canvas = canvas_of(window)
    draw_rectangle(qtbot, window)
    line = next(e.id for e in canvas.edit.sketch.entities.values() if isinstance(e, Line))
    canvas.run(lambda: canvas.edit.add_dimension("distance", [line], None))
    dim = canvas.edit.sketch.dimensions[-1]
    typed = dim.param.value
    canvas.selection = []
    assert "mean_dimensions" not in keys(window.context_menus.build_sketch_menu(canvas))
    dim.display = {"tolerance": "bilateral", "plus": 0.4, "minus": 0.0}
    _run(window.context_menus.build_sketch_menu(canvas), "mean_dimensions")
    dim = canvas.edit.sketch.dimensions[-1]
    assert abs(dim.param.value - (typed + 0.2)) < 1e-9
    menu = window.context_menus.build_sketch_menu(canvas)
    assert next(a.text() for a in menu.actions() if a.data() == "mean_dimensions") == (
        "Typed Dimensions"
    )
    _run(menu, "mean_dimensions")
    assert abs(canvas.edit.sketch.dimensions[-1].param.value - typed) < 1e-9


def test_convex_hull_menu(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """TR229 (D912): Convex Hull wraps two picked circles in one undo step."""
    _tab, _c = _sketch(qtbot, window)
    canvas = canvas_of(window)
    a = canvas.edit.sketch.add_circle(0, 0, 3)
    b = canvas.edit.sketch.add_circle(15, 0, 3)
    canvas.changed()
    count = len(canvas.edit.sketch.entities)
    canvas.selection = [a, b]
    _run(window.context_menus.build_sketch_menu(canvas), "convex_hull")
    assert len(canvas.edit.sketch.entities) > count
    assert sum(1 for r in canvas.edit.sketch.relations if r.type == "tangent") == 4
    canvas.edit.undo()
    assert len(canvas.edit.sketch.entities) == count


def test_recent_sketch_tools(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """TR204 (D918): sketch tools used lately, newest first, in their own list."""
    _tab, _c = _sketch(qtbot, window)
    canvas = canvas_of(window)
    for name in ("line", "circle", "line"):
        canvas.set_tool(name)
    canvas.set_tool(None)
    mode = window.sketch_mode
    assert mode is not None and mode.recent_tools[:2] == ["line", "circle"]
    sub = _sub(window.context_menus.build_sketch_menu(canvas, QPointF(2, 2)), "Recent Sketch Tools")
    assert keys(sub)[:2] == ["tool.line", "tool.circle"]
    _run(sub, "tool.circle")
    assert canvas.tool is not None and canvas.tool.name == "circle"


def test_explain_a_relation_tag(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """TR237 (D920): Explain says what a relation holds."""
    _tab, _c = _sketch(qtbot, window)
    canvas = canvas_of(window)
    sk = canvas.edit.sketch
    a = sk.add_line(0, 0, 10, 0)
    b = sk.add_line(0, 5, 10, 5)
    sk.relate("parallel", a, b)
    canvas.changed()
    index = len(sk.relations) - 1
    canvas.selection = [f"r{index}"]
    menu = window.context_menus.build_sketch_menu(canvas)
    assert keys(menu)[0] == "explain"
    seen: list[str] = []
    canvas.status_message.connect(seen.append)
    _run(menu, "explain")
    assert seen and "pointing the same way" in seen[-1]


def test_show_formulas_on_dimensions(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """TR235 (D921): the formula shows beside the value while the toggle is on."""
    from fdcad.core.document.model import Param

    _tab, _c = _sketch(qtbot, window)
    canvas = canvas_of(window)
    line = canvas.edit.sketch.add_line(0, 0, 10, 0)
    dim = canvas.edit.sketch.dimension("distance", [line], Param("=4+6", 10.0))
    type(canvas).show_formulas = False  # other tests may have left it on
    assert canvas._dimension_text(dim) == "= 10.00"
    try:
        _run(window.context_menus.build_sketch_menu(canvas, QPointF(2, 2)), "show_formulas")
        assert canvas._dimension_text(dim) == "4+6 = 10.00"
        menu = window.context_menus.build_sketch_menu(canvas, QPointF(2, 2))
        assert next(a for a in menu.actions() if a.data() == "show_formulas").isChecked()
    finally:
        type(canvas).show_formulas = False


def test_hide_construction_geometry(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """TR419 (D932): construction curves are hidden and not picked while it is on."""
    _tab, _c = _sketch(qtbot, window)
    canvas = canvas_of(window)
    sk = canvas.edit.sketch
    lid = sk.add_line(0, 0, 20, 0, construction=True)
    canvas.changed()
    at = canvas.to_screen((10.0, 0.0))
    assert canvas.pick(at) == lid
    canvas.selection = [lid]
    assert window.commands.trigger("sketch.hide_construction")
    assert canvas.hide_construction and canvas.selection == []
    assert canvas.pick(at) is None
    assert window.commands.trigger("sketch.hide_construction")
    assert not canvas.hide_construction and canvas.pick(at) == lid


def test_points_from_file(qtbot: QtBot, window: MainWindow, tmp_path: Path) -> None:  # noqa: F811
    """TR415 (D933): X and Y rows become sketch points in one undo step."""
    from fdcad.core.sketch.model import Point
    from fdcad.ui.sketch_tools.point_file_import import points_from_file

    _tab, _c = _sketch(qtbot, window)
    canvas = canvas_of(window)
    data = tmp_path / "pts.csv"
    data.write_text("x,y\n0,0\n10,5\n20,-5\n", encoding="utf-8")
    depth = canvas.edit.undo_depth
    made = points_from_file(canvas, str(data))
    assert len(made) == 3 and canvas.edit.undo_depth == depth + 1
    assert all(isinstance(canvas.edit.sketch.entities[m], Point) for m in made)
    assert points_from_file(canvas, str(tmp_path / "missing.txt")) == []


def test_shade_regions_and_points(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """TR335 (D952): shade every closed region, hide sketch points, from the menu."""
    from fdcad.ui.sketch_tools.canvas import SketchCanvas

    _tab, _c = _sketch(qtbot, window)
    canvas = canvas_of(window)
    sketch = canvas.edit.sketch
    sketch.add_circle(0, 0, 5)
    sketch.add_line(20, 0, 30, 0)
    canvas.changed()
    assert canvas.point_marks()  # centres and ends show by default
    _run(window.context_menus.build_sketch_menu(canvas), "shade_regions")
    assert SketchCanvas.shade_regions
    assert len(canvas.closed_regions()) == 1  # the circle; the open line has none
    canvas.repaint()
    _run(window.context_menus.build_sketch_menu(canvas), "show_points")
    assert not SketchCanvas.show_points
    assert canvas.point_marks() == {}
    canvas.repaint()


def test_several_dimensions_to_reference_and_back(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """TR111 (D965): picked dimensions become reference together, one undo step."""
    from fdcad.core.document.model import Param

    _tab, _c = _sketch(qtbot, window)
    canvas = canvas_of(window)
    sketch = canvas.edit.sketch
    a = sketch.add_line(0, 0, 20, 0)
    b = sketch.add_line(0, 10, 15, 10)
    d1 = sketch.dimension("distance", [a], Param("20mm", 20.0))
    d2 = sketch.dimension("distance", [b], Param("15mm", 15.0))
    canvas.changed()
    canvas.selection = [d1.id, d2.id]
    _run(window.context_menus.build_sketch_menu(canvas), "reference")
    assert not d1.driving and not d2.driving
    canvas.selection = [d1.id, d2.id]
    _run(window.context_menus.build_sketch_menu(canvas), "reference")
    found = [canvas._dimension(d1.id), canvas._dimension(d2.id)]
    assert all(d is not None and d.driving for d in found)


def test_reference_mode_makes_new_dimensions_reference(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """TR111 (D965): with the mode on, a placed dimension only measures."""
    from fdcad.ui.main_window.context_menu import toggle_reference_mode

    _tab, _c = _sketch(qtbot, window)
    canvas = canvas_of(window)
    line = canvas.edit.sketch.add_line(0, 0, 20, 0)
    canvas.changed()
    assert toggle_reference_mode(canvas)
    canvas.set_tool("dimension")
    canvas.dim_picks = [line]
    canvas._dimension_click(canvas.to_screen((10.0, 8.0)))
    dim = canvas._dimension(canvas.last_dimension or "")
    assert dim is not None and not dim.driving


def test_shake_and_lock(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """TR372 (D970): Shake Sketch picks what can move; Lock All Points stops drags."""
    _tab, _c = _sketch(qtbot, window)
    canvas = canvas_of(window)
    free = canvas.edit.sketch.add_line(5, 5, 25, 10)
    canvas.changed()
    before = canvas.edit.sketch.xy(canvas.edit.sketch.entities[free].p1)  # type: ignore[union-attr]
    _run(window.context_menus.build_sketch_menu(canvas), "shake")
    assert free in canvas.selection
    assert canvas.edit.sketch.xy(canvas.edit.sketch.entities[free].p1) == before  # type: ignore[union-attr]
    canvas.selection = []
    _run(window.context_menus.build_sketch_menu(canvas), "lock_points")
    assert canvas.points_locked
    canvas.selection = []
    _run(window.context_menus.build_sketch_menu(canvas), "lock_points")
    assert not canvas.points_locked


def test_show_in_sketch_menu(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """TR341 (D964): open end marks, tag kinds, dimension kinds and tag size."""
    from fdcad.ui.main_window.context_menu import sketch_display_menu
    from fdcad.ui.sketch_tools.canvas import SketchCanvas

    _tab, _c = _sketch(qtbot, window)
    canvas = canvas_of(window)
    sketch = canvas.edit.sketch
    line = sketch.add_line(0, 0, 20, 0)
    sketch.relate("horizontal", line)
    canvas.changed()
    assert len(canvas.open_ends()) == 2
    canvas.repaint()
    parent = QMenu()
    menu = sketch_display_menu(canvas, parent)
    texts = [a.text() for a in menu.actions() if a.text()]
    tag = strings.SHOW_TAGS_OF.format(kind=strings.RELATION_NAMES["horizontal"])
    assert strings.SHOW_OPEN_ENDS in texts and tag in texts
    next(a for a in menu.actions() if a.text() == tag).trigger()
    assert "horizontal" in SketchCanvas.hidden_tags
    assert all(t[1] != "horizontal" for t in canvas._tag_entries())
    next(a for a in menu.actions() if a.text() == strings.SHOW_DRIVING).trigger()
    assert not SketchCanvas.show_driving
    next(a for a in menu.actions() if a.text() == strings.TAG_SIZES[1.3]).trigger()
    assert SketchCanvas.tag_scale == 1.3
    next(a for a in menu.actions() if a.text() == strings.LINE_WEIGHTS[1.5]).trigger()
    assert SketchCanvas.line_scale == 1.5  # TR341 item 5 (D1013)
    canvas.repaint()


def test_swap_axis_menu(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """TR124 (D950): Swap Axis Relations on a picked square shape, one undo step."""
    _tab, _c = _sketch(qtbot, window)
    canvas = canvas_of(window)
    sketch = canvas.edit.sketch
    a = sketch.add_line(0, 0, 20, 0)
    b = sketch.add_line(20, 0, 20, 10)
    sketch.relate("horizontal", a)
    sketch.relate("vertical", b)
    canvas.changed()
    canvas.selection = [a, b]
    _run(window.context_menus.build_sketch_menu(canvas), "swap_axis")
    kinds = sorted(r.type for r in canvas.edit.sketch.relations if a in r.entities)
    assert kinds == ["perpendicular"]
    canvas.edit.undo()
    kinds = sorted(r.type for r in canvas.edit.sketch.relations if a in r.entities)
    assert kinds == ["horizontal"]


def test_slot_along_menu(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TR225 (D946): Slot Along Curves round a picked line, one undo step."""
    from fdcad.ui.main_window import context_menu

    _tab, _c = _sketch(qtbot, window)
    canvas = canvas_of(window)
    line = canvas.edit.sketch.add_line(0, 0, 20, 0)
    canvas.changed()
    count = len(canvas.edit.sketch.entities)
    canvas.selection = [line]
    monkeypatch.setattr(context_menu, "ask_slot_width", lambda _c: 4.0)
    _run(window.context_menus.build_sketch_menu(canvas), "slot_along")
    assert len(canvas.edit.sketch.entities) > count
    assert canvas.edit.sketch.entities[line].construction
    canvas.edit.undo()
    assert len(canvas.edit.sketch.entities) == count
    monkeypatch.setattr(context_menu, "ask_slot_width", lambda _c: None)
    canvas.selection = [line]
    _run(window.context_menus.build_sketch_menu(canvas), "slot_along")
    assert len(canvas.edit.sketch.entities) == count


def test_sketch_tool_with_no_sketch_open_picks_a_plane_then_draws(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """TR123 (D974): a sketch tool with no sketch open asks for a plane or face, then
    opens the sketch there with the tool ready."""
    new_part(qtbot, window)
    mode = window.sketch_mode
    assert mode is not None and not mode.is_open
    window.tree.setCurrentItem(None)
    window.commands.actions["sketch.line"].trigger()
    assert "Line" in window.status.text() and mode.picker.active
    mode.picker.pick({"feature": "f2"})
    assert mode.is_open
    canvas = canvas_of(window)
    assert canvas.tool_name == "line"


def test_link_values_menu(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TR193 (D978): picked dimensions share a name; editing one changes the others."""
    from fdcad.core.document.model import Param
    from fdcad.ui.main_window import context_menu

    _tab, _c = _sketch(qtbot, window)
    canvas = canvas_of(window)
    sketch = canvas.edit.sketch
    a = sketch.add_line(0, 0, 20, 0)
    b = sketch.add_line(0, 10, 15, 10)
    d1 = sketch.dimension("distance", [a], Param("20mm", 20.0))
    d2 = sketch.dimension("distance", [b], Param("15mm", 15.0))
    canvas.changed()
    monkeypatch.setattr(context_menu, "ask_link_name", lambda _c, _s: "Width")
    canvas.selection = [d1.id, d2.id]
    _run(window.context_menus.build_sketch_menu(canvas), "link_values")
    one, two = canvas._dimension(d1.id), canvas._dimension(d2.id)
    assert one is not None and two is not None
    assert one.link == two.link == "Width" and two.param.value == 20.0
    canvas.edit.set_dimension(two.id, Param("30mm", 30.0))
    assert one.param.value == 30.0
    canvas.selection = [d1.id, d2.id]
    _run(window.context_menus.build_sketch_menu(canvas), "unlink_values")
    assert one.link is None and two.link is None


def test_layers_menu(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TR389 (D982): a new layer with the picked line, hidden, then shown again."""
    from fdcad.ui.main_window import context_menu
    from fdcad.ui.main_window.context_menu import layers_menu

    _tab, _c = _sketch(qtbot, window)
    canvas = canvas_of(window)
    line = canvas.edit.sketch.add_line(0, 0, 20, 0)
    canvas.changed()
    monkeypatch.setattr(context_menu, "ask_layer", lambda _c: ("Guide", "#FF0000", "dashed"))
    parent = QMenu()
    menu = layers_menu(canvas, parent, [line])
    next(a for a in menu.actions() if a.text() == strings.LAYER_NEW).trigger()
    assert canvas.edit.sketch.layer_of == {line: "Guide"}
    canvas.repaint()
    menu = layers_menu(canvas, parent, [])
    show = strings.LAYER_SHOWN.format(name="Guide")
    next(a for a in menu.actions() if a.text() == show).trigger()
    assert canvas.hidden_construction(canvas.edit.sketch.entities[line])
    assert canvas.pick(canvas.to_screen((10.0, 0.0))) != line
    canvas.edit.undo()
    assert not canvas.hidden_construction(canvas.edit.sketch.entities[line])


def test_crossings_are_marked_and_switch_off(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """TR238 (D987): crossing curves and forks are found; the switch turns marks off."""
    from fdcad.ui.main_window.context_menu import sketch_display_menu
    from fdcad.ui.sketch_tools.canvas import SketchCanvas

    _tab, _c = _sketch(qtbot, window)
    canvas = canvas_of(window)
    canvas.edit.sketch.add_line(0, 0, 10, 10)
    canvas.edit.sketch.add_line(0, 10, 10, 0)
    canvas.changed()
    crosses, forks = canvas.crossing_marks()
    assert len(crosses) == 1 and forks == []
    canvas.repaint()
    parent = QMenu()
    menu = sketch_display_menu(canvas, parent)
    next(a for a in menu.actions() if a.text() == strings.SHOW_CROSSINGS).trigger()
    assert not SketchCanvas.mark_crossings
    canvas.repaint()
