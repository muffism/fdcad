"""Graph rows in the feature tree: a graph shows right below the feature at its
position, so the user sees what it may read (PLAN Phase 7 cycle rule)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QTreeWidgetItem

from fdcad.core.document.model import Document
from fdcad.core.graph.drive import position_index
from fdcad.core.graph.model import Graph
from fdcad.ui.node_editor import strings
from fdcad.ui.node_editor.install import GRAPH_ROLE

__all__ = ["GRAPH_ROLE", "graph_rows"]


def drive_error(graph: Graph, result: Any) -> str | None:
    """The first error of a node that drives a variable or a value, or None.

    A graph that only drives values failed with no issue on any feature (audit E item
    10.2, D746), so its row shows it.
    """
    from fdcad.core.graph.drive import drives

    if result is None:
        return None
    for d in drives(graph):
        found = result.first_error(d.node)
        if found is not None:
            return str(found[1])
    return None


def graph_rows(
    doc: Document, fid: str, faded: bool = False, results: dict[str, Any] | None = None
) -> list[QTreeWidgetItem]:
    """Rows for the graphs positioned right after feature ``fid``; ``results`` are the
    last rebuild's graph results, to mark a graph whose driving nodes failed."""
    from fdcad.ui.icons import icon
    from fdcad.ui.themes.theme import chrome

    rows = []
    for graph in doc.graphs:
        index = position_index(doc, graph)
        if doc.features[index].id != fid:
            continue
        item = QTreeWidgetItem([strings.POSITION_ROW.format(graph=graph.name)])
        item.setData(0, GRAPH_ROLE, graph.id)
        item.setIcon(0, icon("tree.graph"))
        item.setToolTip(0, strings.POSITION_TIP.format(graph=graph.name))
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        if faded:
            item.setForeground(0, QBrush(QColor(chrome().muted)))
        error = drive_error(graph, (results or {}).get(graph.id))
        if error is not None:
            from fdcad.ui.themes.theme import palette

            item.setForeground(0, QBrush(QColor(palette().state_error)))
            item.setToolTip(0, strings.GRAPH_ROW_ERROR.format(graph=graph.name, error=error))
        rows.append(item)
    return rows
