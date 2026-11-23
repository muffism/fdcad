"""Repair Sketch tool (TUTORIAL_REVIEW_SPEC_2 TR37, D1300). Pure Python, no Qt.

Type a tolerance and press Find: the panel lists the small faults
(``core.sketch.repair``). Zoom to Next Fault frames each fault in turn and
selects it; Fix repairs the fault shown (the first one until a fault is
zoomed to); Fix All repairs every fault. Each fix is one undo step and says
how far it moved points. Nothing is fixed without a press.
"""

from __future__ import annotations

from fdcad.core.sketch.repair import DEFAULT_TOLERANCE, Fault, find_faults, fix, fix_all
from fdcad.ui.sketch_tools.tool_options import Option
from fdcad.ui.sketch_tools.tools import Preview, Tool


class RepairSketchTool(Tool):
    """Find small faults; zoom to them; fix one or all."""

    name, label = "repair_sketch", "Repair Sketch"
    options = (
        Option("gap", "Tolerance", "length", tip="Gaps and segments shorter than this."),
        Option("find", "Find", "button"),
        Option("next", "Zoom to Next Fault", "button"),
        Option("fix", "Fix", "button"),
        Option("fix_all", "Fix All", "button"),
    )

    def __init__(self, edit: object) -> None:
        super().__init__(edit)  # type: ignore[arg-type]
        self.gap = DEFAULT_TOLERANCE
        self.faults: list[Fault] | None = None
        self.index = -1
        self.message = ""
        self._focus: tuple[tuple[float, float] | None, list[str]] | None = None

    @property
    def prompt(self) -> str:
        """The faults found, or what to do."""
        if self.faults is None:
            return "Type the tolerance, then press Find."
        if not self.faults:
            return "No faults found."
        rows = " ".join(f"{i + 1}. {f.message}" for i, f in enumerate(self.faults[:6]))
        more = f" ({len(self.faults) - 6} more.)" if len(self.faults) > 6 else ""
        return f"{len(self.faults)} faults: {rows}{more} Press Fix or Fix All."

    def _find(self) -> None:
        self.faults = find_faults(self.edit.sketch, max(float(self.gap), 0.0))
        self.index = -1

    def _current(self) -> Fault | None:
        if not self.faults:
            return None
        return self.faults[self.index if self.index >= 0 else 0]

    def option_changed(self, key: str) -> bool:
        """Find, Zoom to Next Fault, Fix and Fix All. True when the sketch changed."""
        if key == "find":
            self._find()
            self.message = self.prompt if len(self.prompt) < 200 else ""
            return False
        if key == "next":
            if not self.faults:
                self.message = "Nothing to zoom to. Press Find first."
                return False
            self.index = (self.index + 1) % len(self.faults)
            shown = self.faults[self.index]
            self._focus = (shown.at, list(shown.entities))
            self.message = f"Fault {self.index + 1} of {len(self.faults)}: {shown.message}"
            return False
        if key == "fix":
            if self.faults is None:
                self._find()
            fault = self._current()
            if fault is None:
                self.message = "No faults found."
                return False
            self.edit.checkpoint()
            try:
                moved = fix(self.edit.sketch, fault)
            except ValueError as exc:
                self.edit.discard_checkpoint()
                self.message = f"Fix failed: {exc}"
                self._find()
                return False
            self._find()
            self.message = f"Fixed 1 fault, moving points by up to {moved:.4g} mm."
            return True
        if key == "fix_all":
            self.edit.checkpoint()
            count, moved = fix_all(self.edit.sketch, max(float(self.gap), 0.0))
            if not count:
                self.edit.discard_checkpoint()
            self._find()
            left = f" {len(self.faults or [])} could not be fixed." if self.faults else ""
            self.message = (
                f"Fixed {count} faults, moving points by up to {moved:.4g} mm.{left}"
                if count
                else "No faults found."
            )
            return count > 0
        self.faults = None  # a new tolerance: find again
        return False

    def take_focus(self) -> tuple[tuple[float, float] | None, list[str]] | None:
        """Where to zoom and what to select, once (the canvas reads it)."""
        focus, self._focus = self._focus, None
        return focus

    def take_message(self) -> str:
        """The status note, cleared once read."""
        msg, self.message = self.message, ""
        return msg

    def preview(self) -> Preview:
        """A mark at each fault's place."""
        out = Preview()
        for f in self.faults or []:
            if f.at is not None:
                out.points.append(f.at)
        return out
