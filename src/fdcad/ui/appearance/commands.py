"""Undoable colour changes (PHASE2_SPEC P2.11, CLAUDE.md rule 3, D254).

A colour change needs no rebuild: it only redraws the part, like showing or
hiding a sketch (D114).
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from fdcad.core.appearance import Target, with_color
from fdcad.ui.commands.document import DocumentCommand

if TYPE_CHECKING:
    from fdcad.ui.session import DocumentSession


class SetAppearance(DocumentCommand):
    """Set or remove the colour of one or more targets, as one step."""

    def __init__(
        self,
        session: DocumentSession,
        targets: list[Target],
        color: str | None,
        text: str,
    ) -> None:
        super().__init__(session, text)
        self.before: dict[str, Any] = copy.deepcopy(session.document.appearance)
        after = self.before
        for target in targets:
            after = with_color(after, target, color)
        self.after: dict[str, Any] = after

    def apply(self) -> None:
        """Store the new colours."""
        self.session.document.appearance = copy.deepcopy(self.after)

    def revert(self) -> None:
        """Store the old colours."""
        self.session.document.appearance = copy.deepcopy(self.before)

    def redo(self) -> None:
        """Redraw only; the solid does not change."""
        self.apply()
        self.session.display_changed.emit()

    def undo(self) -> None:
        """Redraw only."""
        self.revert()
        self.session.display_changed.emit()
