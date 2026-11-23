"""The node editor panel: canvas, node search, node settings and live ghost preview.

One graph per part (PLAN section 8 item 18). Every edit is an ``EditGraph``
command on the part's undo stack (CLAUDE.md rule 3). The preview runs in the
graph worker thread and meshes there too, so no kernel work happens on the UI
thread (CLAUDE.md rule 2).
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QMimeData, QObject, QPointF, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QScrollArea,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from fdcad.core.document.model import Feature
from fdcad.core.graph.drive import make_env
from fdcad.core.graph.engine import MAX_NODES, GraphResult, wire_problem
from fdcad.core.graph.model import Graph, Group, Node, Wire, new_graph, node_from_json, node_to_json
from fdcad.core.graph.nodes import NODE_TYPES
from fdcad.core.graph.types import GEOMETRY, PortType
from fdcad.core.graph.worker import GraphWorker
from fdcad.core.units import ExpressionError, Kind
from fdcad.ui import clipboard
from fdcad.ui.node_editor import strings
from fdcad.ui.node_editor.commands import EditGraph
from fdcad.ui.node_editor.form import NodeForm
from fdcad.ui.node_editor.scene import NodeScene
from fdcad.ui.node_editor.search import NodeSearch
from fdcad.ui.node_editor.view import NodeView

if TYPE_CHECKING:
    from fdcad.ui.session import DocumentSession

CLIPBOARD_FORMAT = "application/x-fdcad-nodes"
PREVIEW_DELAY_MS = 120
PASTE_OFFSET = 30.0
#: Narrowest the node search and settings column may be, so labels and fields fit.
SIDE_MIN_WIDTH = 230


class _Signals(QObject):
    done = Signal(object, object, int)  # GraphResult, ghost shapes, generation


def ghost_shapes(graph: Graph, result: GraphResult, selected: list[str]) -> list[Any]:
    """Shapes to preview: geometry outputs of selected nodes and of nodes whose
    geometry outputs feed nothing, except Add as Feature (its body is in the part)."""
    used = {(w.source, w.output) for w in graph.wires}
    shapes: list[Any] = []
    for node in graph.nodes:
        ntype = NODE_TYPES.get(node.type)
        res = result.nodes.get(node.id)
        if ntype is None or res is None or not res.ok:
            continue
        for port in ntype.outputs:
            if port.type not in GEOMETRY:
                continue
            leaf = (node.id, port.name) not in used and node.type != "add_as_feature"
            if node.id in selected or leaf:
                shapes.extend(_flat(res.outputs.get(port.name)))
    return shapes


def _flat(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        out: list[Any] = []
        for v in value:
            out.extend(_flat(v))
        return out
    return [value] if hasattr(value, "IsNull") and not value.IsNull() else []


class NodeEditorPanel(QWidget):
    """The dockable node editor."""

    #: The status line text changed.
    status_changed = Signal(str)

    def __init__(self, window: Any = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("node_editor")
        self.window_ = window
        self.session: DocumentSession | None = None
        self.result: GraphResult | None = None
        self.generation = 0
        self.worker = GraphWorker()
        self.signals = _Signals()
        self.signals.done.connect(self._done)
        self._pending_pos: QPointF | None = None
        self._from_form = False
        self._form_sig: tuple[Any, ...] | None = None
        #: The shapes shown as the ghost preview.
        self.ghosts: list[Any] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.toolbar = QToolBar(self)
        self.toolbar.setObjectName("node_toolbar")
        layout.addWidget(self.toolbar)
        split = QSplitter(Qt.Orientation.Horizontal, self)
        self.scene = NodeScene(self)
        self.view = NodeView(self.scene, split)
        side = QWidget(split)
        side.setMinimumWidth(SIDE_MIN_WIDTH)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        self.search = NodeSearch(side)
        self.form = NodeForm(self.set_param, side)
        self.form.reference_picker = self.pick_reference
        scroll = QScrollArea(side)
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.form)
        side_layout.addWidget(self.search, 2)
        side_layout.addWidget(scroll, 3)
        self._side, self._side_scroll = side, scroll
        split.addWidget(self.view)
        split.addWidget(side)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 1)
        layout.addWidget(split, 1)
        self.status = QLabel(strings.NO_PART, self)
        self.status.setObjectName("node_status")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(PREVIEW_DELAY_MS)
        self.timer.timeout.connect(self.run_preview)
        self.scene.nodes_moved.connect(self.move_nodes)
        self.scene.wire_requested.connect(self.add_wire)
        self.scene.selectionChanged.connect(self._selection_changed)
        self.search.chosen.connect(self._chosen)
        self.view.add_requested.connect(self._add_at)

    # Binding -------------------------------------------------------------------------

    def bind(self, session: DocumentSession | None) -> None:
        """Show the graph of ``session`` (the current part), or nothing."""
        if self.session is session:
            return
        if self.session is not None:
            with contextlib.suppress(RuntimeError, TypeError):
                self.session.graph_changed.disconnect(self._graph_changed)
                self.session.rebuilt.disconnect(self._rebuilt)
        self.session = session
        self.result = None
        if session is not None:
            session.graph_changed.connect(self._graph_changed)
            session.rebuilt.connect(self._rebuilt)
        self.refresh()
        self.view.fit()

    @property
    def graph(self) -> Graph | None:
        """The part's graph, or None when it has none yet."""
        if self.session is None or not self.session.document.graphs:
            return None
        return self.session.document.graphs[0]

    def _graph_changed(self, _gid: str) -> None:
        self.refresh()

    def _rebuilt(self, _report: object) -> None:
        self.schedule()  # model references may read new geometry

    def refresh(self) -> None:
        """Draw the graph again and schedule a preview."""
        self.scene.show_graph(self.graph, self.result)
        self._fill_form()
        if self.session is None:
            self._say(strings.NO_PART)
        elif self.graph is None or not self.graph.nodes:
            self._say(strings.EMPTY_HINT)
        self.schedule()

    def _say(self, text: str) -> None:
        self.status.setText(text)
        self.status_changed.emit(text)

    # Editing -------------------------------------------------------------------------

    def edit(self, change: Callable[[Graph], object], text: str, merge: str | None = None) -> bool:
        """Apply ``change`` to a copy of the graph and push it as one undo step.

        ``change`` may return False to cancel. A part without a graph gets one,
        in the same step.
        """
        if self.session is None:
            self._say(strings.NO_PART)  # was silent (audit C item 17, D741)
            return False
        before = self.graph
        doc = self.session.document
        after = before.copy() if before is not None else new_graph(position=doc.features[-1].id)
        if change(after) is False:
            return False
        self.session.undo.push(EditGraph(self.session, before, after, text, merge))
        return True

    def variables(self) -> dict[str, tuple[Kind, float]]:
        """The part's variables, for typed values."""
        if self.session is None:
            return {}
        from fdcad.core.rebuild.engine import document_variables

        try:
            return document_variables(self.session.document)
        except ExpressionError:
            return {}

    def add_node(self, type_name: str, pos: QPointF | None = None) -> str | None:
        """Add a node of ``type_name`` at ``pos`` (the view centre when None)."""
        ntype = NODE_TYPES.get(type_name)
        if ntype is None or self.session is None:
            return None
        graph = self.graph
        if graph is not None and len(graph.nodes) >= MAX_NODES:
            self._say(strings.TOO_MANY_NODES.format(limit=MAX_NODES))
            return None
        if pos is None:
            pos = self.view.mapToScene(self.view.viewport().rect().center())
        made: list[str] = []

        def change(g: Graph) -> None:
            nid = g.new_node_id()
            params: dict[str, Any] = {}
            if type_name == "comment":
                params["text"] = strings.COMMENT_TEXT
            g.nodes.append(Node(nid, type_name, params, round(pos.x()), round(pos.y())))
            made.append(nid)

        text = strings.UNDO_ADD_NODE.format(title=ntype.title)
        if type_name != "add_as_feature":
            self.edit(change, text)
        else:
            self.session.undo.beginMacro(text)
            self.edit(change, text)
            self._add_graph_body(made[0])
            self.session.undo.endMacro()
        if made:
            self.scene.select(made)
        return made[0] if made else None

    def _add_graph_body(self, nid: str) -> None:
        """The graph body feature that shows an Add as Feature node's body in the tree."""
        from fdcad.ui.commands.document import AddFeature

        assert self.session is not None and self.graph is not None
        doc = self.session.document
        taken = {f.name for f in doc.features}
        count = 1 + sum(1 for f in doc.features if f.type == "graph_body")
        while strings.GRAPH_BODY_NAME.format(n=count) in taken:  # names stay unique
            count += 1
        feature = Feature(
            doc.new_feature_id(),
            "graph_body",
            strings.GRAPH_BODY_NAME.format(n=count),
            refs={"graph": {"graph": self.graph.id, "output": nid}},
        )
        # Just above a rollback bar, so it is built (T14.5.1, audit D11 item 4, D719).
        self.session.undo.push(AddFeature(self.session, feature))

    def add_comment(self) -> str | None:
        """Add a comment note."""
        return self.add_node("comment")

    def delete_selected(self) -> None:
        """Delete the selected nodes and wires."""
        ids = set(self.scene.selected_ids())
        wires = set(self.scene.selected_wires())
        if not ids and not wires:
            return

        def change(g: Graph) -> None:
            g.remove_nodes(ids)
            g.wires = [w for w in g.wires if w not in wires]
            g.groups = [grp for grp in g.groups if grp.nodes]

        bodies = self._graph_bodies(ids)
        if not bodies:
            self.edit(change, strings.UNDO_DELETE)
            return
        # An Add as Feature node takes its graph body feature with it, in one step.
        from fdcad.ui.commands.document import DeleteFeature

        assert self.session is not None
        self.session.undo.beginMacro(strings.UNDO_DELETE)
        self.edit(change, strings.UNDO_DELETE)
        for fid in bodies:
            self.session.undo.push(DeleteFeature(self.session, fid))
        self.session.undo.endMacro()

    def _graph_bodies(self, ids: set[str]) -> list[str]:
        """Ids of the graph body features made by the Add as Feature nodes in ``ids``."""
        graph = self.graph
        if graph is None or self.session is None:
            return []
        out = []
        for feature in self.session.document.features:
            ref = feature.refs.get("graph") if feature.type == "graph_body" else None
            if isinstance(ref, dict) and ref.get("graph") == graph.id and ref.get("output") in ids:
                out.append(feature.id)
        return out

    def move_nodes(self, moved: dict[str, tuple[float, float]]) -> None:
        """Store where nodes were dragged to."""

        def change(g: Graph) -> None:
            for nid, (x, y) in moved.items():
                node = g.find(nid)
                if node is not None:
                    node.x, node.y = round(x), round(y)

        self.edit(change, strings.UNDO_MOVE)

    def add_wire(self, wire: Wire) -> bool:
        """Connect two ports. A single value input keeps only its newest wire."""
        graph = self.graph
        if graph is None:
            return False
        problem = wire_problem(graph, wire)
        if problem is not None:
            self._say(strings.WIRE_REFUSED.format(reason=problem))
            return False
        target = graph.node(wire.target)
        ntype = NODE_TYPES[target.type]
        port = ntype.input(wire.input)
        keeps_many = port is not None and (port.whole_list or port.type is PortType.LIST)

        def change(g: Graph) -> None:
            if not keeps_many:
                g.wires = [
                    w for w in g.wires if not (w.target == wire.target and w.input == wire.input)
                ]
            if wire not in g.wires:
                g.wires.append(wire)

        return self.edit(change, strings.UNDO_WIRE)

    def remove_wire(self, wire: Wire) -> None:
        """Disconnect a wire."""
        self.edit(
            lambda g: setattr(g, "wires", [w for w in g.wires if w != wire]), strings.UNDO_UNWIRE
        )

    def set_param(self, nid: str, name: str, value: Any, merge: str | None = None) -> None:
        """Change one stored value of a node."""
        graph = self.graph
        node = graph.find(nid) if graph is not None else None
        if node is None:
            return
        ntype = NODE_TYPES.get(node.type)
        title = ntype.title if ntype is not None else node.type
        text = (
            strings.UNDO_RUN_ANYWAY
            if name == "allow_many"
            else strings.UNDO_SETTING.format(title=title)
        )

        def change(g: Graph) -> object:
            target = g.find(nid)
            if target is None or target.params.get(name) == value:
                return False
            target.params[name] = value
            return None

        self._from_form = True  # the form already shows the new value: keep its widgets
        try:
            self.edit(change, text, merge)
        finally:
            self._from_form = False

    def group_selected(self) -> None:
        """Put the selected nodes in a new named group."""
        ids = self.scene.selected_ids()
        if not ids:
            return

        def change(g: Graph) -> None:
            number = len(g.groups) + 1
            g.groups.append(Group(g.new_group_id(), f"{strings.GROUP_NAME} {number}", list(ids)))

        self.edit(change, strings.UNDO_GROUP)

    def ungroup_selected(self) -> None:
        """Remove the groups that hold any selected node."""
        ids = set(self.scene.selected_ids())
        graph = self.graph
        if graph is None or not any(set(g.nodes) & ids for g in graph.groups):
            return
        self.edit(
            lambda g: setattr(g, "groups", [grp for grp in g.groups if not set(grp.nodes) & ids]),
            strings.UNDO_UNGROUP,
        )

    def copy_selected(self) -> int:
        """Copy the selected nodes and the wires between them to the clipboard."""
        graph = self.graph
        ids = set(self.scene.selected_ids())
        if graph is None or not ids:
            return 0
        data = {
            "nodes": [node_to_json(n) for n in graph.nodes if n.id in ids],
            "wires": [
                {"from": w.text[0], "to": w.text[1]}
                for w in graph.wires
                if w.source in ids and w.target in ids
            ],
        }
        mime = QMimeData()
        text = json.dumps(data)
        mime.setData(CLIPBOARD_FORMAT, text.encode("utf-8"))
        mime.setText(text)
        clipboard.put(mime)
        return len(data["nodes"])

    def paste(self) -> list[str]:
        """Paste copied nodes with new ids, a little offset. Pasted text is read as data only."""
        mime = QApplication.clipboard().mimeData()
        if mime is None or not mime.hasFormat(CLIPBOARD_FORMAT):
            return []
        try:
            data = json.loads(bytes(mime.data(CLIPBOARD_FORMAT).data()).decode("utf-8"))
            nodes = [node_from_json(n) for n in data.get("nodes", [])]
            wires = [(w["from"].split("."), w["to"].split(".")) for w in data.get("wires", [])]
        except (ValueError, KeyError, AttributeError, TypeError):
            self._say(strings.PASTE_DAMAGED)  # was silent (audit C item 17, D741)
            return []
        graph = self.graph
        if graph is not None and len(graph.nodes) + len(nodes) > MAX_NODES:
            self._say(strings.TOO_MANY_NODES.format(limit=MAX_NODES))
            return []
        made: list[str] = []

        def change(g: Graph) -> None:
            new_ids = {}
            for node in nodes:
                nid = g.new_node_id()
                new_ids[node.id] = nid
                g.nodes.append(
                    Node(nid, node.type, node.params, node.x + PASTE_OFFSET, node.y + PASTE_OFFSET)
                )
                made.append(nid)
            for (src, out), (dst, inp) in wires:
                if src in new_ids and dst in new_ids:
                    g.wires.append(Wire(new_ids[src], out, new_ids[dst], inp))

        if not nodes:
            return made
        outputs = [n for n in nodes if n.type == "add_as_feature"]
        if not outputs:
            self.edit(change, strings.UNDO_PASTE)
        else:
            # A pasted Add as Feature node gets its own graph body feature (D378 item 3).
            assert self.session is not None
            self.session.undo.beginMacro(strings.UNDO_PASTE)
            self.edit(change, strings.UNDO_PASTE)
            graph = self.graph
            for nid in made:
                node = graph.find(nid) if graph is not None else None
                if node is not None and node.type == "add_as_feature":
                    self._add_graph_body(nid)
            self.session.undo.endMacro()
        self.scene.select(made)
        return made

    def set_position(self, fid: str | None = None) -> bool:
        """Run the graph after feature ``fid`` (the one selected in the tree when None)."""
        if self.session is None:
            return False
        if fid is None:
            tree = getattr(self.window_, "tree", None)
            fid = tree.selected_id() if tree is not None else None
        doc = self.session.document
        feature = next((f for f in doc.features if f.id == fid), None)
        if feature is None:
            self._say(strings.POSITION_NEEDS_FEATURE)
            return False
        done = self.edit(lambda g: setattr(g, "position", feature.id), strings.UNDO_POSITION)
        if done and self.graph is not None:
            self._say(strings.POSITION_SET.format(graph=self.graph.name, feature=feature.name))
        return done

    def fit(self) -> None:
        """Show every node."""
        self.view.fit()

    def open_search(self, pos: QPointF | None = None) -> None:
        """Focus the node search; the chosen node goes at ``pos``."""
        self._pending_pos = pos
        self.search.open()

    def _add_at(self, pos: QPointF) -> None:
        self.open_search(pos)

    def _chosen(self, type_name: str) -> None:
        pos, self._pending_pos = self._pending_pos, None
        self.add_node(type_name, pos)
        self.view.setFocus()

    def pick_reference(self) -> dict[str, Any] | None:
        """A model reference from the current pick: the 3D selection, or for a curve
        reference the feature selected in the tree."""
        node = self.form.node
        if node is None or self.session is None:
            return None
        kind = str(node.params.get("kind", "face"))
        window = self.window_
        if kind == "curve":
            tree = getattr(window, "tree", None)
            fid = tree.selected_id() if tree is not None else None
            return {"feature": fid} if fid else None
        tab = getattr(window, "current", None)
        picks = list(getattr(tab, "selection", []) or [])
        report = self.session.report
        if not picks or report is None or report.body is None:
            return None
        from fdcad.core.named_items import name_of
        from fdcad.core.naming.select import reference_for

        ref = reference_for(report.body, picks[0])
        named = name_of(self.session.document, ref)  # a named item follows its name (TR152)
        return {"named": named} if named is not None else ref

    # Selection and form ----------------------------------------------------------------

    def _selection_changed(self) -> None:
        self._fill_form()
        self.schedule()

    def _form_signature(self) -> tuple[Any, ...]:
        ids = self.scene.selected_ids()
        nid = ids[0] if len(ids) == 1 else None
        graph = self.graph
        node = graph.find(nid) if graph is not None and nid is not None else None
        res = self.result.nodes.get(nid) if self.result is not None and nid is not None else None
        wired = sorted(w.input for w in graph.wires_into(nid)) if graph is not None and nid else []
        params = json.dumps(node_to_json(node), sort_keys=True, default=str) if node else ""
        state = (res.error, res.warning, res.needs_confirmation) if res is not None else None
        return (id(self.session), nid, params, tuple(wired), state)

    def _fill_form(self) -> None:
        """Show the selected node's settings. Widgets are kept while the user edits them."""
        signature = self._form_signature()
        if self._from_form:
            self._form_sig = signature
            return
        if signature == self._form_sig:
            return
        self._form_sig = signature
        ids = self.scene.selected_ids()
        nid = ids[0] if len(ids) == 1 else None
        res = self.result.nodes.get(nid) if self.result is not None and nid is not None else None
        doc = self.session.document if self.session is not None else None
        self.form.show_node(self.graph, nid, doc, self.variables(), res)
        self._fit_side()
        # New fields take their style sizes once shown, so fit again after that.
        QTimer.singleShot(0, self._fit_side)

    def _fit_side(self) -> None:
        """Widen the settings column when a node's settings need more than the minimum,
        as some fonts and styles do (round 10d)."""
        scroll = self._side_scroll
        if not isValid(scroll) or not isValid(self.form):
            return
        bar = scroll.verticalScrollBar().sizeHint().width()
        need = self.form.minimumSizeHint().width() + 2 * scroll.frameWidth() + bar
        self._side.setMinimumWidth(max(SIDE_MIN_WIDTH, need))

    # Preview -------------------------------------------------------------------------

    def schedule(self) -> None:
        """Run the preview soon; quick edits in a row run it once."""
        self.timer.start()

    def run_preview(self) -> None:
        """Evaluate the graph in the worker and show the result as a ghost."""
        self.generation += 1
        graph = self.graph
        if self.session is None or graph is None:
            self.worker.cancel()
            self._show_ghost([])
            return
        report = self.session.report
        env = make_env(
            self.session.document, graph, report.results if report else {}, self.variables()
        )
        selected = self.scene.selected_ids()
        generation = self.generation
        self._say(strings.STATUS_RUNNING)

        def done(result: GraphResult) -> None:
            shapes: list[Any] = []
            if not result.cancelled:
                with contextlib.suppress(Exception):  # display only, never break the editor
                    from fdcad.ui.viewport.meshing import mesh_for_display

                    shapes = ghost_shapes(graph, result, selected)
                    for shape in shapes:
                        mesh_for_display(shape)
            self.signals.done.emit(result, shapes, generation)

        self.worker.submit(graph, env, done)

    def _done(self, result: GraphResult, shapes: list[Any], generation: int) -> None:
        if generation != self.generation:
            return
        self._last_done = generation
        if result.cancelled:
            self._say(strings.STATUS_CANCELLED)
            return
        self.result = result
        self.scene.show_result(result)
        self._fill_form()
        errors = sum(1 for r in result.nodes.values() if r.error)
        if errors:
            self._say(strings.STATUS_ERRORS.format(count=errors))
        else:
            self._say(strings.STATUS_DONE.format(seconds=result.seconds))
        self._show_ghost(shapes)

    def _show_ghost(self, shapes: list[Any]) -> None:
        self.ghosts = shapes
        tab = getattr(self.window_, "current", None)
        show = getattr(getattr(tab, "viewport", None), "show_ghost", None)
        if show is not None:
            show(shapes)

    def wait(self, timeout_ms: int = 30000) -> bool:
        """Block until the preview is shown (tests)."""
        from PySide6.QtCore import QCoreApplication, QElapsedTimer

        clock = QElapsedTimer()
        clock.start()
        if self.timer.isActive():
            self.timer.stop()
            self.run_preview()
        target = self.generation
        while clock.elapsed() < timeout_ms:
            QCoreApplication.processEvents()
            if self._last_done == target:
                return True
        return False

    _last_done = -1

    def closeEvent(self, event: Any) -> None:  # noqa: N802  (Qt override)
        self.worker.cancel()
        super().closeEvent(event)

    def shutdown(self) -> None:
        """Stop the worker thread."""
        self.worker.shutdown()
