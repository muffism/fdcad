"""The node canvas: nodes, ports, wires and group frames drawn from a graph.

The scene is drawn again from the graph after every edit. It never changes the
graph itself: it emits requests (move, wire, unwire) that the panel turns into
undoable commands (CLAUDE.md rule 3). FDCAD's own design: rounded cards with
a coloured band per category, round ports coloured by type.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from fdcad.core.graph.engine import GraphResult
from fdcad.core.graph.model import Graph, Node, Wire
from fdcad.core.graph.nodes import NODE_TYPES
from fdcad.core.graph.nodes.base import NodeType, Port
from fdcad.core.graph.types import PortType
from fdcad.ui.themes.theme import DATA, NODE_CATEGORIES, NODE_PORTS, chrome, palette
from fdcad.ui.themes.typography import Role, type_font

NODE_WIDTH = 168.0
HEADER = 24.0
ROW = 18.0
PORT_RADIUS = 5.0
COMMENT_SIZE = (180.0, 70.0)

#: Band colour per category (FDCAD's own colours, kept in the theme module).
CATEGORY_COLORS = dict(NODE_CATEGORIES)
#: Port colour per type.
PORT_COLORS = {t: NODE_PORTS[t.value] for t in PortType}


def node_height(ntype: NodeType | None) -> float:
    """Height of a node card."""
    if ntype is None:
        return HEADER + ROW
    if ntype.type_name == "comment":
        return COMMENT_SIZE[1]
    rows = max(len(ntype.inputs), len(ntype.outputs), 1)
    return HEADER + rows * ROW + 6.0


def port_position(node: Node, port: str, output: bool) -> QPointF:
    """Scene position of a port's centre."""
    ntype = NODE_TYPES.get(node.type)
    ports = (ntype.outputs if output else ntype.inputs) if ntype is not None else ()
    index = next((i for i, p in enumerate(ports) if p.name == port), 0)
    x = node.x + (NODE_WIDTH if output else 0.0)
    return QPointF(x, node.y + HEADER + ROW * index + ROW / 2 + 3.0)


class PortItem(QGraphicsItem):
    """A round port. Dragging from it draws a wire to another port."""

    def __init__(self, parent: NodeItem, port: Port, output: bool, index: int) -> None:
        super().__init__(parent)
        self.node_item = parent
        self.port = port
        self.output = output
        x = NODE_WIDTH if output else 0.0
        self.setPos(x, HEADER + ROW * index + ROW / 2 + 3.0)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setToolTip(f"{port.title}: {port.type.value}{' list' if port.whole_list else ''}")
        self.setZValue(2)

    def boundingRect(self) -> QRectF:  # noqa: N802  (Qt override)
        r = PORT_RADIUS + 3
        return QRectF(-r, -r, 2 * r, 2 * r)

    def paint(
        self, painter: QPainter, _option: QStyleOptionGraphicsItem, _widget: QWidget | None = None
    ) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(PORT_COLORS[self.port.type]))
        painter.setPen(QPen(QColor(chrome().border_strong), 1.0))
        if self.port.whole_list:
            painter.drawRoundedRect(
                QRectF(-PORT_RADIUS, -PORT_RADIUS, 2 * PORT_RADIUS, 2 * PORT_RADIUS), 2, 2
            )
        else:
            painter.drawEllipse(QPointF(0, 0), PORT_RADIUS, PORT_RADIUS)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        scene = self.scene()
        if isinstance(scene, NodeScene) and event.button() == Qt.MouseButton.LeftButton:
            scene.start_wire(self)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        scene = self.scene()
        if isinstance(scene, NodeScene):
            scene.drag_wire(event.scenePos())

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        scene = self.scene()
        if isinstance(scene, NodeScene):
            scene.finish_wire(event.scenePos())


class NodeItem(QGraphicsItem):
    """A node card: title band, input ports on the left, outputs on the right."""

    def __init__(self, node: Node) -> None:
        super().__init__()
        self.node = node
        self.ntype = NODE_TYPES.get(node.type)
        self.state = "ok"  # ok, warning, error, waiting
        self.summary = ""
        self.setPos(node.x, node.y)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setZValue(1)
        self.ports: dict[tuple[str, bool], PortItem] = {}
        if self.ntype is not None:
            for i, p in enumerate(self.ntype.inputs):
                self.ports[(p.name, False)] = PortItem(self, p, False, i)
            for i, p in enumerate(self.ntype.outputs):
                self.ports[(p.name, True)] = PortItem(self, p, True, i)

    @property
    def is_comment(self) -> bool:
        """True for a comment note."""
        return self.node.type == "comment"

    def title(self) -> str:
        """The card title."""
        if self.is_comment:
            return str(self.node.params.get("text", "")) or "Comment"
        return self.ntype.title if self.ntype is not None else self.node.type

    def boundingRect(self) -> QRectF:  # noqa: N802  (Qt override)
        w = COMMENT_SIZE[0] if self.is_comment else NODE_WIDTH
        return QRectF(-2, -2, w + 4, node_height(self.ntype) + 4)

    def paint(
        self, painter: QPainter, _option: QStyleOptionGraphicsItem, _widget: QWidget | None = None
    ) -> None:
        c, pal = chrome(), palette()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        height = node_height(self.ntype)
        if self.is_comment:
            rect = QRectF(0, 0, *COMMENT_SIZE)
            painter.setBrush(QColor(c.raised))
            painter.setPen(
                QPen(QColor(c.accent if self.isSelected() else c.border), 1.2, Qt.PenStyle.DashLine)
            )
            painter.drawRoundedRect(rect, 4, 4)
            painter.setPen(QColor(c.text))
            painter.drawText(
                rect.adjusted(8, 6, -8, -6),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                | int(Qt.TextFlag.TextWordWrap),
                self.title(),
            )
            return
        rect = QRectF(0, 0, NODE_WIDTH, height)
        border = {
            "error": pal.state_error,
            "warning": pal.state_warning,
            "waiting": pal.state_warning,
        }.get(self.state, c.border_strong)
        width = 2.2 if self.state != "ok" else 1.0
        if self.isSelected():
            border, width = c.accent, 2.2
        painter.setBrush(QColor(c.surface))
        painter.setPen(QPen(QColor(border), width))
        painter.drawRoundedRect(rect, 6, 6)
        band = QPainterPath()
        # Winding fill: the two shapes overlap, and the default rule leaves the
        # overlap, the lower half of the band, empty (D2690).
        band.setFillRule(Qt.FillRule.WindingFill)
        band.addRoundedRect(QRectF(0, 0, NODE_WIDTH, HEADER), 6, 6)
        band.addRect(QRectF(0, HEADER / 2, NODE_WIDTH, HEADER / 2))
        category = self.ntype.category if self.ntype is not None else "Display"
        painter.fillPath(
            band.simplified(), QColor(CATEGORY_COLORS.get(category, DATA["node_unknown"]))
        )
        font = type_font(Role.TITLE, painter.font())
        painter.setFont(font)
        painter.setPen(QColor(DATA["node_band_text"]))
        painter.drawText(
            QRectF(8, 0, NODE_WIDTH - 16, HEADER), int(Qt.AlignmentFlag.AlignVCenter), self.title()
        )
        font = type_font(Role.BODY, painter.font())
        painter.setFont(font)
        painter.setPen(QColor(c.text))
        if self.ntype is None:
            painter.drawText(
                QRectF(8, HEADER, NODE_WIDTH - 16, ROW),
                int(Qt.AlignmentFlag.AlignVCenter),
                self.node.type,
            )
            return
        for i, p in enumerate(self.ntype.inputs):
            y = HEADER + ROW * i + 3
            painter.drawText(
                QRectF(10, y, NODE_WIDTH / 2, ROW), int(Qt.AlignmentFlag.AlignVCenter), p.title
            )
        for i, p in enumerate(self.ntype.outputs):
            y = HEADER + ROW * i + 3
            painter.drawText(
                QRectF(NODE_WIDTH / 2 - 10, y, NODE_WIDTH / 2, ROW),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
                p.title,
            )
        if self.summary:
            painter.setPen(QColor(c.muted))
            painter.drawText(
                QRectF(0, height + 2, NODE_WIDTH, ROW),
                int(Qt.AlignmentFlag.AlignHCenter),
                self.summary,
            )

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:  # noqa: N802
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            scene = self.scene()
            if isinstance(scene, NodeScene):
                scene.node_moving(self)
        return super().itemChange(change, value)


class WireItem(QGraphicsPathItem):
    """A curved wire from an output port to an input port."""

    def __init__(self, wire: Wire | None, start: QPointF, end: QPointF, color: str) -> None:
        super().__init__()
        self.wire = wire
        self.color = color
        self.setZValue(0)
        if wire is not None:
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.set_ends(start, end)

    def set_ends(self, start: QPointF, end: QPointF) -> None:
        """Redraw between two scene points."""
        path = QPainterPath(start)
        bend = max(40.0, abs(end.x() - start.x()) / 2)
        path.cubicTo(start + QPointF(bend, 0), end - QPointF(bend, 0), end)
        self.setPath(path)
        self._restyle()

    def _restyle(self) -> None:
        color = QColor(chrome().accent if self.isSelected() else self.color)
        pen = QPen(color, 3.0 if self.isSelected() else 2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self.setPen(pen)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:  # noqa: N802
        result = super().itemChange(change, value)
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self._restyle()
        return result


class GroupItem(QGraphicsItem):
    """A named frame drawn behind a group's nodes."""

    def __init__(self, gid: str, name: str, rect: QRectF) -> None:
        super().__init__()
        self.gid = gid
        self.name = name
        self.rect = rect
        self.setZValue(-1)

    def boundingRect(self) -> QRectF:  # noqa: N802  (Qt override)
        return self.rect.adjusted(-2, -2, 2, 2)

    def paint(
        self, painter: QPainter, _option: QStyleOptionGraphicsItem, _widget: QWidget | None = None
    ) -> None:
        c = chrome()
        fill = QColor(c.accent)
        fill.setAlpha(28)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(fill))
        painter.setPen(QPen(QColor(c.accent), 1.0, Qt.PenStyle.DashLine))
        painter.drawRoundedRect(self.rect, 8, 8)
        painter.setPen(QColor(c.text))
        painter.drawText(
            self.rect.adjusted(10, 4, -10, 0), int(Qt.AlignmentFlag.AlignLeft), self.name
        )


class NodeScene(QGraphicsScene):
    """Draws a graph and reports what the user drags."""

    #: Node id to its new (x, y), after a drag ends.
    nodes_moved = Signal(object)
    #: A new wire the user drew.
    wire_requested = Signal(object)

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.graph: Graph | None = None
        self.items_by_id: dict[str, NodeItem] = {}
        self.wire_items: list[WireItem] = []
        self.group_items: list[GroupItem] = []
        self._drag_from: PortItem | None = None
        self._ghost: WireItem | None = None
        self._moving = False

    # Drawing -----------------------------------------------------------------------

    def show_graph(self, graph: Graph | None, result: GraphResult | None = None) -> None:
        """Draw ``graph`` again, keeping the selection by node id."""
        selected = self.selected_ids()
        blocked = self.blockSignals(True)  # no selection signals for items being replaced
        self.items_by_id, self.wire_items, self.group_items = {}, [], []
        self.clear()
        self._ghost = None
        self.graph = graph
        try:
            if graph is None:
                return
            for node in graph.nodes:
                item = NodeItem(node)
                self.addItem(item)
                self.items_by_id[node.id] = item
                item.setSelected(node.id in selected)
            for wire in graph.wires:
                self._add_wire(wire)
            self._draw_groups()
            if result is not None:
                self.show_result(result)
        finally:
            self.blockSignals(blocked)

    def _add_wire(self, wire: Wire) -> None:
        a, b = self.items_by_id.get(wire.source), self.items_by_id.get(wire.target)
        if a is None or b is None:
            return
        port = a.ports.get((wire.output, True))
        color = PORT_COLORS[port.port.type] if port is not None else DATA["node_unknown"]
        item = WireItem(
            wire,
            port_position(a.node, wire.output, True),
            port_position(b.node, wire.input, False),
            color,
        )
        self.addItem(item)
        self.wire_items.append(item)

    def _draw_groups(self) -> None:
        for item in self.group_items:
            self.removeItem(item)
        self.group_items = []
        if self.graph is None:
            return
        for group in self.graph.groups:
            members = [self.items_by_id[n] for n in group.nodes if n in self.items_by_id]
            if not members:
                continue
            rect = QRectF()
            for m in members:
                rect = rect.united(m.sceneBoundingRect())
            item = GroupItem(group.id, group.name, rect.adjusted(-14, -26, 14, 14))
            self.addItem(item)
            self.group_items.append(item)

    def show_result(self, result: GraphResult) -> None:
        """Colour nodes by their state and show their errors as tooltips."""
        for nid, item in self.items_by_id.items():
            res = result.nodes.get(nid)
            if res is None:
                item.state, tip = "ok", ""
            elif res.needs_confirmation:
                item.state, tip = "waiting", res.error or ""
            elif res.error is not None:
                item.state, tip = "error", res.error
            elif res.warning is not None:
                item.state, tip = "warning", res.warning
            else:
                item.state, tip = "ok", ""
            item.summary = summarize(res.outputs) if res is not None and res.ok else ""
            item.setToolTip(tip)
            item.update()

    # Selection -----------------------------------------------------------------------

    def selected_ids(self) -> list[str]:
        """Ids of the selected nodes."""
        return [i.node.id for i in self.items_by_id.values() if i.isSelected()]

    def selected_wires(self) -> list[Wire]:
        """The selected wires."""
        return [w.wire for w in self.wire_items if w.isSelected() and w.wire is not None]

    def select(self, ids: list[str]) -> None:
        """Select exactly these nodes."""
        self.clearSelection()
        for nid in ids:
            if nid in self.items_by_id:
                self.items_by_id[nid].setSelected(True)

    # Moving --------------------------------------------------------------------------

    def node_moving(self, item: NodeItem) -> None:
        """Keep wires and groups attached while a node is dragged."""
        self._moving = True
        node = item.node
        x, y = item.pos().x(), item.pos().y()
        moved = Node(node.id, node.type, node.params, x, y)
        for w in self.wire_items:
            if w.wire is None:
                continue
            if w.wire.source == node.id or w.wire.target == node.id:
                src = self.items_by_id[w.wire.source]
                dst = self.items_by_id[w.wire.target]
                sn = (
                    moved
                    if src is item
                    else Node(src.node.id, src.node.type, {}, src.pos().x(), src.pos().y())
                )
                dn = (
                    moved
                    if dst is item
                    else Node(dst.node.id, dst.node.type, {}, dst.pos().x(), dst.pos().y())
                )
                w.set_ends(
                    port_position(sn, w.wire.output, True), port_position(dn, w.wire.input, False)
                )

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        super().mouseReleaseEvent(event)
        if self._moving:
            self._moving = False
            moved = {
                nid: (item.pos().x(), item.pos().y())
                for nid, item in self.items_by_id.items()
                if (item.pos().x(), item.pos().y()) != (item.node.x, item.node.y)
            }
            if moved:
                self.nodes_moved.emit(moved)

    # Wiring --------------------------------------------------------------------------

    def start_wire(self, port: PortItem) -> None:
        """Begin drawing a wire from ``port``."""
        self._drag_from = port
        centre = port.scenePos()
        self._ghost = WireItem(None, centre, centre, PORT_COLORS[port.port.type])
        self.addItem(self._ghost)

    def drag_wire(self, pos: QPointF) -> None:
        """Follow the mouse while drawing a wire."""
        if self._drag_from is None or self._ghost is None:
            return
        start = self._drag_from.scenePos()
        if self._drag_from.output:
            self._ghost.set_ends(start, pos)
        else:
            self._ghost.set_ends(pos, start)

    def finish_wire(self, pos: QPointF) -> None:
        """End a wire on the port under ``pos``, if any."""
        origin, ghost = self._drag_from, self._ghost
        self._drag_from, self._ghost = None, None
        if ghost is not None:
            self.removeItem(ghost)
        if origin is None:
            return
        target = self.port_at(pos)
        if target is None or target.output == origin.output:
            return
        out, inp = (origin, target) if origin.output else (target, origin)
        self.wire_requested.emit(
            Wire(out.node_item.node.id, out.port.name, inp.node_item.node.id, inp.port.name)
        )

    def port_at(self, pos: QPointF) -> PortItem | None:
        """The port under a scene point, with a little slack."""
        slack = PORT_RADIUS + 4
        for item in self.items(QRectF(pos.x() - slack, pos.y() - slack, 2 * slack, 2 * slack)):
            if isinstance(item, PortItem):
                return item
        return None


def summarize(outputs: dict[str, Any]) -> str:
    """A short text of a node's first output, shown under the card."""
    if not outputs:
        return ""
    value = next(iter(outputs.values()))
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.4g}"
    if isinstance(value, tuple) and len(value) == 3:
        return "(" + ", ".join(f"{v:.3g}" for v in value) + ")"
    if isinstance(value, list):
        return f"{len(value)} items"
    return ""
