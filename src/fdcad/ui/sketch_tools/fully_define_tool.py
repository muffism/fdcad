"""Fully Define Sketch tool (TUTORIAL_REVIEW_SPEC TR35, D762). Pure Python, no Qt.

The tool panel holds what to use (the whole sketch, or the entities selected
when the tool started), Relations and Dimensions tick boxes, the dimension
scheme and the datum (the sketch origin, or a point clicked while the tool is
active). Calculate lists what would be added; Apply adds it as one undo step.
Nothing moves: new dimensions take the current sizes (``core.sketch.fully_define``).
"""

from __future__ import annotations

from fdcad.core.sketch.fully_define import FullyDefineError, Proposal, apply, origin_of, propose
from fdcad.core.sketch.model import Point
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.tool_options import Option
from fdcad.ui.sketch_tools.tools import Preview, Tool

SCOPE_CHOICES = (("sketch", "The whole sketch"), ("selected", "The selected entities"))
SCHEME_CHOICES = (("baseline", "Baseline"), ("chain", "Chain"), ("datum", "Datum Pairs"))


class FullyDefineTool(Tool):
    """Calculate, then Apply."""

    name, label = "fully_define", "Fully Define Sketch"
    options = (
        Option("scope", "Use", "choice", choices=SCOPE_CHOICES),
        Option("relations", "Add relations", "bool"),
        Option("dimensions", "Add dimensions", "bool"),
        Option("scheme", "Dimension scheme", "choice", choices=SCHEME_CHOICES),
        Option("calculate", "Calculate", "button"),
        Option("apply", "Apply", "button"),
    )

    def __init__(self, edit: object) -> None:
        super().__init__(edit)  # type: ignore[arg-type]
        self.scope = "sketch"
        self.relations = True
        self.dimensions = True
        self.scheme = "baseline"
        self.selected: list[str] = []
        #: The datum point; None is the sketch origin. A click on a point sets it.
        self.datum: str | None = None
        self.proposals: list[Proposal] | None = None
        self.message = ""
        self.units = UnitSystem.MM

    def take_selection(self, ids: list[str]) -> None:
        """The entities selected before the tool, for Use: the selected entities."""
        self.selected = [i for i in ids if i in self.edit.sketch.entities]
        if self.selected:
            self.scope = "selected"

    @property
    def prompt(self) -> str:
        """What the panel says: the result of Calculate, or what to do."""
        datum = "a picked point" if self.datum else "the sketch origin"
        if self.proposals is None:
            return f"Press Calculate. The datum is {datum}; click a point to use it instead."
        if not self.proposals:
            return "Nothing to add: the sketch is fully defined."
        rows = "; ".join(p.text(self.units) for p in self.proposals[:8])
        more = f" and {len(self.proposals) - 8} more" if len(self.proposals) > 8 else ""
        return f"Would add {len(self.proposals)}: {rows}{more}. Press Apply."

    def click(self, snap: Snap) -> bool:
        """A click on a point makes it the datum."""
        target = snap.target
        if target is not None and isinstance(self.edit.sketch.entities.get(target), Point):
            self.datum = None if target == origin_of(self.edit.sketch) else target
            self.proposals = None
            self.message = "The datum is the clicked point. Press Calculate."
        return False

    def _calculate(self) -> bool:
        entities = set(self.selected) if self.scope == "selected" and self.selected else None
        if self.scope == "selected" and not self.selected:
            self.message = "Nothing is selected. Select entities first, or use the whole sketch."
            self.proposals = None
            return False
        try:
            self.proposals = propose(
                self.edit.sketch,
                self.units,
                entities,
                relations=bool(self.relations),
                dimensions=bool(self.dimensions),
                scheme=str(self.scheme),
                datum=self.datum,
            )
        except FullyDefineError as exc:
            self.proposals = None
            self.message = f"Fully Define Sketch: {exc}"
            return False
        return False

    def option_changed(self, key: str) -> bool:
        """Calculate fills the list; Apply adds it. True when the sketch changed."""
        if key == "calculate":
            return self._calculate()
        if key == "apply":
            if self.proposals is None:
                self._calculate()
            if not self.proposals:
                if self.proposals is not None:
                    self.message = "Nothing to add: the sketch is fully defined."
                return False
            self.edit.checkpoint()
            apply(self.edit.sketch, self.proposals, self.units)
            self.message = f"Added {len(self.proposals)} relations and dimensions."
            self.proposals = None
            return True
        self.proposals = None  # another setting: calculate again
        return False

    def take_message(self) -> str:
        """The status note, cleared once read."""
        msg, self.message = self.message, ""
        return msg

    def preview(self) -> Preview:
        """The datum point."""
        out = Preview()
        datum = self.datum or origin_of(self.edit.sketch)
        if datum is not None:
            out.points.append(self.edit.sketch.xy(datum))
        return out
