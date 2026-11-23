"""Undoable graph edits (CLAUDE.md rule 3).

Every change to a graph is one ``EditGraph`` command that keeps the graph as
JSON data before and after the change: small, and never a solid (PLAN 11.4
item 2). Moves and slider drags of the same items merge into one undo step.
"""

from __future__ import annotations

import zlib
from typing import TYPE_CHECKING, Any

from PySide6.QtGui import QUndoCommand

from fdcad.core.graph.model import Graph, graph_from_json, graph_to_json
from fdcad.ui.commands.document import DocumentCommand

if TYPE_CHECKING:
    from fdcad.ui.session import DocumentSession


def _data(graph: Graph | None) -> dict[str, Any] | None:
    return graph_to_json(graph) if graph is not None else None


class EditGraph(DocumentCommand):
    """Replace, add (``before`` None) or remove (``after`` None) a graph."""

    def __init__(
        self,
        session: DocumentSession,
        before: Graph | None,
        after: Graph | None,
        text: str,
        merge: str | None = None,
    ) -> None:
        super().__init__(session, text)
        doc = session.document
        gid = (after or before).id  # type: ignore[union-attr]
        self.gid = gid
        self.index = next((i for i, g in enumerate(doc.graphs) if g.id == gid), len(doc.graphs))
        self.before = _data(before)
        self.after = _data(after)
        self.merge = merge

    def id(self) -> int:
        """Commands with the same merge key merge (moves, slider drags)."""
        if self.merge is None:
            return -1
        return zlib.crc32(self.merge.encode("utf-8")) & 0x7FFFFFFF

    def mergeWith(self, other: QUndoCommand) -> bool:  # noqa: N802  (Qt override)
        """Keep this command's start and take the other one's end."""
        if not isinstance(other, EditGraph) or other.merge != self.merge or other.gid != self.gid:
            return False
        self.after = other.after
        return True

    def _put(self, data: dict[str, Any] | None) -> None:
        graphs = self.session.document.graphs
        current = next((i for i, g in enumerate(graphs) if g.id == self.gid), None)
        if data is None:
            if current is not None:
                del graphs[current]
            return
        graph = graph_from_json(data)
        if current is None:
            graphs.insert(min(self.index, len(graphs)), graph)
        else:
            graphs[current] = graph

    def apply(self) -> None:
        """Make the change."""
        self._put(self.after)
        self.session.graph_changed.emit(self.gid)

    def revert(self) -> None:
        """Undo the change."""
        self._put(self.before)
        self.session.graph_changed.emit(self.gid)
