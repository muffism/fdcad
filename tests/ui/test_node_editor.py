"""Node editor panel (PLAN Phase 7): adding, wiring, grouping, copy and paste, zoom and
pan, settings, ghost preview, graph position and every edit undoable. Offscreen."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QPointF, QSettings
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param, new_document
from fdcad.core.graph.model import Wire
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.node_editor.panel import NodeEditorPanel
from fdcad.ui.node_editor.tree_rows import GRAPH_ROLE
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.session import DocumentSession


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
    while win.tabs.count():
        tab = win.tabs.widget(0)
        assert isinstance(tab, DocumentTab)
        tab.session.cancel_rebuild()
        tab.session.wait()
        tab.autosaver.discard()
        win.tabs.removeTab(0)
    from fdcad.ui.node_editor.install import shutdown

    shutdown(win)
    win.close()
    win.deleteLater()


def part(qtbot: QtBot, win: MainWindow) -> DocumentTab:
    session = DocumentSession(new_document(), None, win)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = win.add_session(session)
    return tab


def editor(win: MainWindow) -> NodeEditorPanel:
    from fdcad.ui.node_editor.install import panel_of

    panel = panel_of(win)
    assert isinstance(panel, NodeEditorPanel)
    return panel


def test_panel_dock_commands_and_graph_tab(qtbot: QtBot, window: MainWindow) -> None:
    part(qtbot, window)
    for cid in (
        "graph.editor",
        "graph.add_node",
        "graph.group",
        "graph.copy",
        "graph.paste",
        "graph.delete",
        "graph.comment",
        "graph.fit",
        "graph.set_position",
        "graph.ungroup",
    ):
        assert cid in window.commands.actions
    assert window.command_tabs.index_of("graph") >= 0
    assert getattr(window, "_node_editor_panel", None) is None  # nothing loaded at startup
    window.commands.actions["graph.editor"].trigger()
    assert window.node_editor_dock.isVisible()  # type: ignore[attr-defined]
    assert editor(window).session is window.current.session  # type: ignore[union-attr]


def test_add_node_creates_the_graph_and_undo_removes_it(qtbot: QtBot, window: MainWindow) -> None:
    tab = part(qtbot, window)
    panel = editor(window)
    nid = panel.add_node("sphere", QPointF(10, 20))
    doc = tab.session.document
    assert nid == "n1" and len(doc.graphs) == 1 and doc.graphs[0].node("n1").x == 10
    assert doc.graphs[0].position == doc.features[-1].id
    assert "n1" in panel.scene.items_by_id
    tab.session.undo.undo()
    assert doc.graphs == [] and panel.scene.items_by_id == {}
    tab.session.undo.redo()
    assert doc.graphs[0].node("n1").type == "sphere"


def test_search_lists_and_filters_nodes(qtbot: QtBot, window: MainWindow) -> None:
    part(qtbot, window)
    panel = editor(window)
    panel.search.field.setText("cells")
    assert panel.search.visible_types() == ["voronoi"]
    panel.search.field.setText("")
    assert len(panel.search.visible_types()) > 50
    panel.search.field.setText("slider")
    panel.search.pick_current()
    assert panel.graph is not None and panel.graph.nodes[0].type == "slider"


def test_wiring_rules_and_undo(qtbot: QtBot, window: MainWindow) -> None:
    tab = part(qtbot, window)
    panel = editor(window)
    a = panel.add_node("value")
    b = panel.add_node("value")
    c = panel.add_node("arithmetic")
    s = panel.add_node("sphere")
    assert a and b and c and s
    assert panel.add_wire(Wire(a, "out", c, "a"))
    assert panel.add_wire(Wire(b, "out", c, "a"))  # replaces the first wire into a single input
    graph = panel.graph
    assert graph is not None and graph.wires == [Wire(b, "out", c, "a")]
    assert not panel.add_wire(Wire(s, "body", c, "b"))
    assert "cannot feed" in panel.status.text()
    assert not panel.add_wire(Wire(c, "out", c, "b"))
    tab.session.undo.undo()
    assert panel.graph is not None and panel.graph.wires == [Wire(a, "out", c, "a")]


def test_drawing_a_wire_on_the_canvas(qtbot: QtBot, window: MainWindow) -> None:
    part(qtbot, window)
    panel = editor(window)
    a = panel.add_node("value", QPointF(0, 0))
    c = panel.add_node("arithmetic", QPointF(300, 0))
    assert a and c
    scene = panel.scene
    out = scene.items_by_id[a].ports[("out", True)]
    inp = scene.items_by_id[c].ports[("b", False)]
    scene.start_wire(out)
    scene.drag_wire(inp.scenePos())
    scene.finish_wire(inp.scenePos())
    assert panel.graph is not None and Wire(a, "out", c, "b") in panel.graph.wires
    assert len(scene.wire_items) == 1


def test_move_group_comment_delete(qtbot: QtBot, window: MainWindow) -> None:
    tab = part(qtbot, window)
    panel = editor(window)
    a = panel.add_node("value", QPointF(0, 0))
    b = panel.add_node("value", QPointF(0, 80))
    assert a and b
    panel.move_nodes({a: (50.0, 60.0)})
    assert panel.graph is not None and (panel.graph.node(a).x, panel.graph.node(a).y) == (50, 60)
    tab.session.undo.undo()
    assert panel.graph is not None and panel.graph.node(a).x == 0
    panel.scene.select([a, b])
    panel.group_selected()
    assert panel.graph is not None and panel.graph.groups[0].nodes == [a, b]
    assert len(panel.scene.group_items) == 1
    panel.ungroup_selected()
    assert panel.graph is not None and panel.graph.groups == []
    note = panel.add_comment()
    assert note and panel.graph is not None and panel.graph.node(note).type == "comment"
    panel.scene.select([a])
    panel.delete_selected()
    assert panel.graph is not None and panel.graph.find(a) is None
    tab.session.undo.undo()
    assert panel.graph is not None and panel.graph.find(a) is not None


def test_copy_and_paste_gives_new_ids_and_inner_wires(qtbot: QtBot, window: MainWindow) -> None:
    part(qtbot, window)
    panel = editor(window)
    a = panel.add_node("value", QPointF(0, 0))
    c = panel.add_node("arithmetic", QPointF(200, 0))
    assert a and c
    panel.add_wire(Wire(a, "out", c, "a"))
    panel.scene.select([a, c])
    assert panel.copy_selected() == 2
    made = panel.paste()
    assert len(made) == 2 and not set(made) & {a, c}
    graph = panel.graph
    assert graph is not None and Wire(made[0], "out", made[1], "a") in graph.wires
    assert graph.node(made[0]).x == 30


def test_settings_form_typed_values_and_slider_merge(qtbot: QtBot, window: MainWindow) -> None:
    tab = part(qtbot, window)
    panel = editor(window)
    cyl = panel.add_node("cylinder")
    assert cyl
    panel.scene.select([cyl])
    field = panel.form.fields["radius"]
    field.setText("1/4in")  # type: ignore[attr-defined]
    field.editingFinished.emit()  # type: ignore[attr-defined]
    stored = panel.graph.node(cyl).params["radius"]  # type: ignore[union-attr]
    assert (
        isinstance(stored, Param) and stored.expr == "1/4in" and stored.value == pytest.approx(6.35)
    )
    slider_id = panel.add_node("slider")
    assert slider_id
    panel.scene.select([slider_id])
    steps = tab.session.undo.count()
    slider = panel.form.fields["slider"]
    for tick in (100, 200, 300):
        slider.setValue(tick)  # type: ignore[attr-defined]
    assert tab.session.undo.count() == steps + 1  # one drag, one undo step
    assert panel.graph.node(slider_id).params["value"].value == 3.0  # type: ignore[union-attr]


def test_ghost_preview_and_node_errors(qtbot: QtBot, window: MainWindow) -> None:
    tab = part(qtbot, window)
    panel = editor(window)
    sphere = panel.add_node("sphere")
    assert sphere and panel.wait()
    assert panel.result is not None and panel.result.nodes[sphere].ok
    assert len(panel.ghosts) == 1
    panel.set_param(sphere, "radius", Param("-1", -1.0))
    assert panel.wait()
    assert panel.scene.items_by_id[sphere].state == "error"
    assert "error" in panel.status.text()
    assert panel.ghosts == []
    assert tab.viewport is not None


def test_run_anyway_for_large_booleans(qtbot: QtBot, window: MainWindow) -> None:
    part(qtbot, window)
    panel = editor(window)
    box = panel.add_node("box")
    lat = panel.add_node("lattice")
    assert box and lat
    panel.set_param(lat, "cell", Param("1", 1.0))
    panel.set_param(lat, "radius", Param("0.1", 0.1))
    panel.add_wire(Wire(box, "body", lat, "body"))
    panel.scene.select([lat])
    assert panel.wait()
    button = panel.form.run_anyway
    assert button is not None
    panel.set_param(lat, "radius", Param("0.1", 0.1))  # unchanged: no extra undo step
    button.click()
    assert panel.graph is not None and panel.graph.node(lat).params["allow_many"] is True


def test_add_as_feature_puts_a_graph_body_in_the_tree(qtbot: QtBot, window: MainWindow) -> None:
    tab = part(qtbot, window)
    panel = editor(window)
    sphere = panel.add_node("sphere")
    out = panel.add_node("add_as_feature")
    assert sphere and out
    doc = tab.session.document
    body = doc.features[-1]
    assert body.type == "graph_body" and body.refs["graph"] == {"graph": "g1", "output": out}
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        panel.add_wire(Wire(sphere, "body", out, "body"))
    tab.session.wait()
    qtbot.waitUntil(
        lambda: tab.session.report is not None and tab.session.report.body is not None,
        timeout=20000,
    )
    rows = [window.tree.topLevelItem(i) for i in range(window.tree.topLevelItemCount())]
    assert any(r.data(0, GRAPH_ROLE) == "g1" for r in rows)
    steps = tab.session.undo.count()
    tab.session.undo.undo()  # the wire
    tab.session.undo.undo()  # the node and its feature, one step
    assert doc.features[-1].type != "graph_body"
    assert tab.session.undo.count() == steps


def test_set_position_from_the_tree(qtbot: QtBot, window: MainWindow) -> None:
    tab = part(qtbot, window)
    panel = editor(window)
    panel.add_node("value")
    window.tree.select("f2")
    window.tree.refresh()
    assert panel.set_position()
    assert tab.session.document.graphs[0].position == window.tree.selected_id()
    assert "now runs after" in panel.status.text()


def test_zoom_and_pan(qtbot: QtBot, window: MainWindow) -> None:
    part(qtbot, window)
    panel = editor(window)
    view = panel.view
    start = view.zoom
    view.zoom_by(2.0)
    assert view.zoom == pytest.approx(start * 2.0)
    view.zoom_by(100.0)
    assert view.zoom == pytest.approx(3.0)
    before = view.horizontalScrollBar().value()
    view.pan_by(-40, 0)
    assert view.horizontalScrollBar().value() == before + 40
    panel.add_node("value")
    view.fit()
    assert view.zoom <= 1.0


def test_delete_key_on_the_canvas(qtbot: QtBot, window: MainWindow) -> None:
    from PySide6.QtCore import Qt

    part(qtbot, window)
    panel = editor(window)
    a = panel.add_node("value")
    assert a
    panel.scene.select([a])
    panel.view.setFocus()
    qtbot.keyClick(panel.view, Qt.Key.Key_Delete)
    assert panel.graph is not None and panel.graph.find(a) is None


def test_set_param_output_drives_a_feature_and_rebuilds(qtbot: QtBot, window: MainWindow) -> None:
    from fdcad.core.graph import geometry as geo
    from fdcad.samples.graphs import slider_bracket

    session = DocumentSession(slider_bracket(), None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = window.add_session(session)
    tab.session.wait()
    qtbot.waitUntil(
        lambda: tab.session.report is not None and tab.session.report.body is not None,
        timeout=20000,
    )
    assert geo.volume(tab.session.report.body.shape) == pytest.approx(856 * 24)  # type: ignore[union-attr]
    panel = editor(window)
    width = next(n.id for n in panel.graph.nodes if n.params.get("max") == 60)  # type: ignore[union-attr]
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        panel.set_param(width, "value", Param("40", 40.0))
    tab.session.wait()
    qtbot.waitUntil(
        lambda: abs(geo.volume(tab.session.report.body.shape) - 856 * 40) < 1e-6,  # type: ignore[union-attr]
        timeout=20000,
    )
    rows = [window.tree.topLevelItem(i) for i in range(window.tree.topLevelItemCount())]
    graph_row = next(i for i, r in enumerate(rows) if r.data(0, GRAPH_ROLE) == "g1")
    names = [r.text(0) for r in rows]
    assert names.index("Right Plane") < graph_row  # the graph sits at its position


def test_node_limit_is_enforced(qtbot: QtBot, window: MainWindow) -> None:
    from fdcad.core.graph.engine import MAX_NODES
    from fdcad.core.graph.model import Node

    part(qtbot, window)
    panel = editor(window)
    panel.add_node("value")
    graph = panel.graph
    assert graph is not None
    graph.nodes.extend(Node(f"x{i}", "value", {}) for i in range(MAX_NODES - 1))
    assert panel.add_node("value") is None
    assert str(MAX_NODES) in panel.status.text()


def test_pasted_and_deleted_add_as_feature_nodes_bring_and_take_their_bodies(
    qtbot: QtBot, window: MainWindow
) -> None:
    tab = part(qtbot, window)
    panel = editor(window)
    sphere = panel.add_node("sphere")
    out = panel.add_node("add_as_feature")
    assert sphere and out
    panel.add_wire(Wire(sphere, "body", out, "body"))
    doc = tab.session.document

    def bodies() -> list[str]:
        return [str(f.refs["graph"]["output"]) for f in doc.features if f.type == "graph_body"]

    panel.scene.select([sphere, out])
    assert panel.copy_selected() == 2
    steps = tab.session.undo.count()
    made = panel.paste()
    assert bodies() == [out, made[1]]  # the pasted node has its own graph body
    assert tab.session.undo.count() == steps + 1  # one step
    panel.scene.select([out])
    panel.delete_selected()
    assert bodies() == [made[1]]  # no graph body is left without its node
    tab.session.undo.undo()
    assert bodies() == [out, made[1]]
    tab.session.undo.undo()
    assert bodies() == [out]
    tab.session.undo.redo()  # the paste again, with its graph body
    assert bodies() == [out, made[1]]


def test_graph_body_names_stay_unique_after_a_delete(qtbot: QtBot, window: MainWindow) -> None:
    tab = part(qtbot, window)
    panel = editor(window)
    first = panel.add_node("add_as_feature")
    panel.add_node("add_as_feature")
    assert first
    panel.scene.select([first])
    panel.delete_selected()
    panel.add_node("add_as_feature")
    names = [f.name for f in tab.session.document.features if f.type == "graph_body"]
    assert names == ["Graph Body 2", "Graph Body 3"]


def test_settings_of_every_node_fit_without_cutting(qtbot: QtBot, window: MainWindow) -> None:
    from fdcad.core.graph.nodes import NODE_TYPES

    part(qtbot, window)
    window.commands.actions["graph.editor"].trigger()
    panel = editor(window)
    qtbot.wait(10)
    for type_name in sorted(NODE_TYPES):
        nid = panel.add_node(type_name)
        assert nid
        panel.scene.select([nid])
        qtbot.wait(1)  # the form fills after the selection signal
        side = panel.form.parentWidget()
        assert side is not None and panel.form.node is not None
        assert panel.form.node.id == nid
        assert panel.form.minimumSizeHint().width() <= side.width(), type_name


def test_settings_fit_with_a_theme_stylesheet(qtbot: QtBot, window: MainWindow) -> None:
    """With a theme applied the Arc settings needed 234 px in a 230 px column (round 10d)."""
    from PySide6.QtWidgets import QApplication

    from fdcad.ui.preferences.settings import Theme
    from fdcad.ui.themes.theme import apply_theme

    app = QApplication.instance()
    assert isinstance(app, QApplication)
    sheet, palette = app.styleSheet(), app.palette()
    apply_theme(app, Theme.DARK)
    try:
        test_settings_of_every_node_fit_without_cutting(qtbot, window)
    finally:
        app.setStyleSheet(sheet)
        app.setPalette(palette)


def test_node_keys_leave_a_text_field_alone(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit C item 15 (D741): Backspace typed in the settings pane deleted nodes."""
    from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QLineEdit, QPushButton

    from fdcad.ui.node_editor.install import typing_in_field

    for widget, typing in ((QLineEdit(), True), (QDoubleSpinBox(), True), (QPushButton(), False)):
        qtbot.addWidget(widget)
        monkeypatch.setattr(QApplication, "focusWidget", staticmethod(lambda w=widget: w))
        assert typing_in_field() is typing


def test_a_damaged_clipboard_says_so(qtbot: QtBot, window: MainWindow) -> None:
    """Audit C item 17 (D741): pasting unreadable nodes did nothing without a word."""
    from PySide6.QtCore import QMimeData

    from fdcad.ui.node_editor import strings as node_strings
    from fdcad.ui.node_editor.panel import CLIPBOARD_FORMAT

    part(qtbot, window)
    panel = editor(window)
    mime = QMimeData()
    mime.setData(CLIPBOARD_FORMAT, b"{not json")
    from fdcad.ui import clipboard

    clipboard.put(mime)  # D2617: cleared before exit
    assert panel.paste() == []
    assert panel.status.text() == node_strings.PASTE_DAMAGED


def test_a_graph_row_shows_a_failed_driving_node(qtbot: QtBot) -> None:
    """Audit E item 10.2 (D746): a graph that only drives values failed with no mark
    anywhere; its tree row now shows the error."""
    from fdcad.core.graph.engine import GraphResult, NodeResult
    from fdcad.ui.node_editor import strings as node_strings
    from fdcad.ui.node_editor.tree_rows import graph_rows
    from tests.core.graph.helpers import graph, p

    doc = new_document()
    g = graph(
        ("n1", "value", {"kind": "length", "value": p(25)}),
        ("n2", "set_variable", {"variable": "Depth"}),
        wires=("n1.out>n2.value",),
    )
    g.position = doc.features[-1].id
    doc.graphs.append(g)
    failed = GraphResult(nodes={"n2": NodeResult(error="No variable named Depth.")})
    (row,) = graph_rows(doc, g.position, results={g.id: failed})
    assert row.toolTip(0) == node_strings.GRAPH_ROW_ERROR.format(
        graph=g.name, error="No variable named Depth."
    )
    (plain,) = graph_rows(doc, g.position, results={g.id: GraphResult()})
    assert "failed" not in plain.toolTip(0)


def test_node_title_band_is_filled_to_its_foot(qtbot: QtBot, window: MainWindow) -> None:
    """D2690: the band behind a node's title is one colour from top to foot. Its lower
    half used to be empty, so the white title stood half on the card's own colour."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtWidgets import QStyleOptionGraphicsItem

    from fdcad.ui.node_editor.scene import CATEGORY_COLORS, HEADER, NODE_WIDTH

    part(qtbot, window)
    panel = editor(window)
    panel.add_node("slider", QPointF(0, 0))
    item = panel.scene.items_by_id["n1"]
    image = QImage(int(NODE_WIDTH), 60, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    item.paint(painter, QStyleOptionGraphicsItem())
    painter.end()
    band = QColor(CATEGORY_COLORS[item.ntype.category])
    # Right of the title, a quarter and three quarters of the way down the band.
    for y in (HEADER * 0.25, HEADER * 0.75):
        assert image.pixelColor(int(NODE_WIDTH) - 12, int(y)) == band


def test_search_rows_show_title_and_category_as_two_columns(
    qtbot: QtBot, window: MainWindow
) -> None:
    """D2690: a row keeps "title category" as its text and holds both for the two
    columns; the list never scrolls sideways, so the category stays in sight."""
    from PySide6.QtCore import Qt

    from fdcad.ui.node_editor.search import CATEGORY_ROLE, TITLE_ROLE

    part(qtbot, window)
    search = editor(window).search
    search.field.setText("slider")
    row = search.list.item(0)
    title, category = row.data(TITLE_ROLE), row.data(CATEGORY_ROLE)
    assert title and category and title in row.text() and category in row.text()
    assert search.list.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
