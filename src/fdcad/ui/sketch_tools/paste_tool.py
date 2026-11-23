"""Paste copied sketch entities: the copy follows the cursor until a click places it
(TUTORIAL_REVIEW_SPEC TR3.1, D685). No Qt; the canvas handles the clipboard."""

from __future__ import annotations

from fdcad.core.sketch.model import sketch_from_data
from fdcad.core.sketch.ops.clipboard import Clip, insert
from fdcad.ui.sketch_tools.edit import SketchEdit
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.tools import Preview, Tool
from fdcad.ui.sketch_tools.transform_tools import add_entity_preview

#: Format of copied sketch entities on the system clipboard.
CLIPBOARD_FORMAT = "application/x-fdcad-sketch-entities"


class PasteTool(Tool):
    """Places one copy of a clip where the user clicks, then ends."""

    name, label = "paste", "Paste"

    def __init__(self, edit: SketchEdit, clip: Clip, verb: str = "Pasted") -> None:
        super().__init__(edit)
        self.clip = clip
        #: The word the status note starts with ("Pasted", or "Inserted" for a DXF).
        self.verb = verb
        self._shape = sketch_from_data(clip.data)
        #: The new ids after the click, for the selection.
        self.placed: list[str] = []
        self.message = ""

    @property
    def prompt(self) -> str:
        """What to do."""
        return "Click to place the copy. Escape cancels."

    @property
    def busy(self) -> bool:
        """Always placing."""
        return True

    def offset(self) -> tuple[float, float]:
        """How far the copy moves from where it was copied."""
        at = self.cursor.xy if self.cursor is not None else self.clip.anchor
        return at[0] - self.clip.anchor[0], at[1] - self.clip.anchor[1]

    def click(self, snap: Snap) -> bool:
        """Place the copy (one undo step) and end."""
        self.hover(snap)
        self.edit.checkpoint()
        try:
            self.placed = insert(self.edit.sketch, self.clip, self.offset())
        except (KeyError, TypeError, ValueError):
            self.edit.discard_checkpoint()
            self.message = "The copied entities could not be pasted."
            self.finished = True
            return False
        self.drawn = list(self.placed)
        n = len(self.placed)
        self.message = f"{self.verb} {n} entit{'ies' if n != 1 else 'y'}."
        if self.clip.left_behind:
            k = self.clip.left_behind
            self.message += (
                f" {k} relation{'s' if k != 1 else ''} or dimension{'s' if k != 1 else ''}"
                " to items that were not copied left out."
            )
        self.finished = True
        return True

    def take_message(self) -> str:
        """The status note, cleared once read."""
        msg, self.message = self.message, ""
        return msg

    def cancel(self) -> bool:
        """Escape ends the paste."""
        return True

    def preview(self) -> Preview:
        """The copy at the cursor."""
        out = Preview()
        dx, dy = self.offset()
        shape = Preview()
        for eid in self._shape.entities:
            add_entity_preview(shape, self._shape, eid)
        out.lines = [((a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy)) for a, b in shape.lines]
        out.circles = [((c[0] + dx, c[1] + dy), r) for c, r in shape.circles]
        out.arcs = [((c[0] + dx, c[1] + dy), r, a0, a1) for c, r, a0, a1 in shape.arcs]
        out.points = [(p[0] + dx, p[1] + dy) for p in shape.points]
        return out
