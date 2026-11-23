"""Sketch pictures and the document's embedded image blocks (PHASE2_SPEC P2.9, D279).

OK in a sketch writes the sketch and the image blocks its pictures need as one
undoable command; image blocks no sketch uses any more leave the document with
it (CLAUDE.md rule 3).
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from fdcad.core.document.model import Document
from fdcad.core.sketch.picture import referenced_blocks
from fdcad.ui.commands.document import DocumentCommand

if TYPE_CHECKING:
    from fdcad.ui.session import DocumentSession
    from fdcad.ui.sketch_tools.edit import SketchEdit


def picture_blocks(doc: Document, edit: SketchEdit) -> dict[str, dict[str, Any]]:
    """The document's image blocks that the open sketch's pictures use."""
    used = {p.block for p in edit.sketch.pictures}
    return {k: v for k, v in doc.embedded.items() if k in used and isinstance(v, dict)}


class WithPictures(DocumentCommand):
    """Runs a sketch command and adds or removes the image blocks around it."""

    def __init__(
        self, session: DocumentSession, inner: DocumentCommand, blocks: dict[str, dict[str, Any]]
    ) -> None:
        super().__init__(session, inner.text())
        self.inner = inner
        self.new_blocks = copy.deepcopy(blocks)
        self.removed: dict[str, Any] = {}

    def apply(self) -> None:
        """Make the change, add the new blocks, drop image blocks nothing uses."""
        doc = self.session.document
        self.inner.apply()
        for key, block in self.new_blocks.items():
            doc.embedded[key] = copy.deepcopy(block)
        used = referenced_blocks(doc.features)
        self.removed = {
            k: v
            for k, v in doc.embedded.items()
            if isinstance(v, dict) and v.get("type") == "image" and k not in used
        }
        for key in self.removed:
            del doc.embedded[key]

    def revert(self) -> None:
        """Undo the change and put the blocks back as they were."""
        doc = self.session.document
        for key in self.new_blocks:
            doc.embedded.pop(key, None)
        doc.embedded.update(copy.deepcopy(self.removed))
        self.inner.revert()


def with_pictures(
    session: DocumentSession, command: DocumentCommand, edit: SketchEdit
) -> DocumentCommand:
    """``command`` wrapped so its sketch's new image blocks enter the document."""
    doc = session.document
    used = {p.block for p in edit.sketch.pictures}
    new = {k: v for k, v in edit.blocks.items() if k in used and k not in doc.embedded}
    had_pictures = any(
        isinstance(v, dict) and v.get("type") == "image" for v in doc.embedded.values()
    )
    if not new and not had_pictures:
        return command
    return WithPictures(session, command, new)
