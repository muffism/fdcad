"""Undoable commands that add an imported file to the part (CLAUDE.md rule 3).

The embedded block and the feature that uses it are added and removed together,
so undo leaves no orphan data in the file.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from fdcad.ui.commands.document import AddFeature, DocumentCommand

if TYPE_CHECKING:
    from fdcad.core.document.model import Feature
    from fdcad.ui.session import DocumentSession


class AddImport(AddFeature):
    """Add an embedded block and the import feature that reads it."""

    def __init__(
        self, session: DocumentSession, feature: Feature, block_id: str, block: dict[str, Any]
    ) -> None:
        super().__init__(session, feature)
        self.block_id = block_id
        self.block = copy.deepcopy(block)

    def apply(self) -> None:
        """Store the block, then insert the feature."""
        self.session.document.embedded[self.block_id] = copy.deepcopy(self.block)
        super().apply()

    def revert(self) -> None:
        """Remove the feature and its block."""
        super().revert()
        self.session.document.embedded.pop(self.block_id, None)


class ReplaceImport(DocumentCommand):
    """Point an import feature at a new embedded file (TR11). The old block goes when
    no other feature reads it; undo brings it back."""

    def __init__(
        self, session: DocumentSession, fid: str, block_id: str, block: dict[str, Any]
    ) -> None:
        from fdcad.core.features.import_replace import block_users

        doc = session.document
        feature = doc.feature(fid)
        super().__init__(session, f"Replace {feature.name}")
        self.fid = fid
        self.new_id, self.new_block = block_id, copy.deepcopy(block)
        self.old_id = str(feature.refs["source"]["embedded"])
        self.old_block = copy.deepcopy(doc.embedded.get(self.old_id))
        self.old_shared = [u for u in block_users(doc, self.old_id) if u != fid] != []

    def _point(self, bid: str) -> None:
        feature = self.session.document.feature(self.fid)
        feature.refs = {**feature.refs, "source": {"embedded": bid}}

    def apply(self) -> None:
        """Store the new file and read it."""
        doc = self.session.document
        doc.embedded[self.new_id] = copy.deepcopy(self.new_block)
        self._point(self.new_id)
        if not self.old_shared:
            doc.embedded.pop(self.old_id, None)

    def revert(self) -> None:
        """Read the old file again."""
        doc = self.session.document
        if self.old_block is not None:
            doc.embedded[self.old_id] = copy.deepcopy(self.old_block)
        self._point(self.old_id)
        doc.embedded.pop(self.new_id, None)
