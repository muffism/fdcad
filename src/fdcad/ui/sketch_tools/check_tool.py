"""Check Sketch for Feature tool (TUTORIAL_REVIEW_SPEC TR36, D763). Pure Python, no Qt.

Pick the feature kind and press Check: the panel lists what that kind cannot
accept (``core.sketch.feature_check``), or says no problems were found. Zoom to
Next Problem frames each problem in turn and selects its curves. Nothing in the
sketch changes.
"""

from __future__ import annotations

from fdcad.core.sketch.feature_check import KINDS, Problem, check_for
from fdcad.ui.sketch_tools.tool_options import Option
from fdcad.ui.sketch_tools.tools import Preview, Tool

KIND_CHOICES = tuple((key, label) for key, (label, _rule) in KINDS.items())


class CheckSketchTool(Tool):
    """Check the sketch for a feature kind; zoom from problem to problem."""

    name, label = "check_sketch", "Check Sketch"
    options = (
        Option("kind", "Feature", "choice", choices=KIND_CHOICES),
        Option("check", "Check", "button"),
        Option("next", "Zoom to Next Problem", "button"),
    )

    def __init__(self, edit: object) -> None:
        super().__init__(edit)  # type: ignore[arg-type]
        self.kind = "boss"
        self.problems: list[Problem] | None = None
        self.index = -1
        self.message = ""
        #: Where the canvas should centre next and what it should select (once read).
        self._focus: tuple[tuple[float, float] | None, list[str]] | None = None

    @property
    def prompt(self) -> str:
        """The result of the last check, or what to do."""
        label = KINDS[self.kind][0]
        if self.problems is None:
            return f"Choose the feature, then press Check. Checking for: {label}."
        if not self.problems:
            return f"No problems found for {label}."
        rows = " ".join(f"{i + 1}. {p.message}" for i, p in enumerate(self.problems[:6]))
        more = f" ({len(self.problems) - 6} more.)" if len(self.problems) > 6 else ""
        return f"{len(self.problems)} problems for {label}: {rows}{more}"

    def option_changed(self, key: str) -> bool:
        """Check runs the checks; Zoom to Next Problem moves to the next one."""
        if key == "check":
            self.problems = check_for(self.edit.sketch, str(self.kind))
            self.index = -1
            self.message = self.prompt if len(self.prompt) < 200 else ""
        elif key == "next":
            if not self.problems:
                self.message = "Nothing to zoom to. Press Check first."
                return False
            self.index = (self.index + 1) % len(self.problems)
            problem = self.problems[self.index]
            at = problem.at
            if at is None and problem.entities:
                at = self._middle(problem.entities)
            self._focus = (at, list(problem.entities))
            self.message = f"Problem {self.index + 1} of {len(self.problems)}: {problem.message}"
        else:
            self.problems = None  # another feature kind: check again
        return False

    def _middle(self, ids: list[str]) -> tuple[float, float] | None:
        sk = self.edit.sketch
        points = []
        for eid in ids:
            e = sk.entities.get(eid)
            for attr in ("p1", "p2", "center", "start", "end"):
                pid = getattr(e, attr, None)
                if isinstance(pid, str) and pid in sk.entities:
                    points.append(sk.xy(pid))
        if not points:
            return None
        return (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))

    def take_focus(self) -> tuple[tuple[float, float] | None, list[str]] | None:
        """Where to zoom and what to select, once (the canvas reads it)."""
        focus, self._focus = self._focus, None
        return focus

    def take_message(self) -> str:
        """The status note, cleared once read."""
        msg, self.message = self.message, ""
        return msg

    def preview(self) -> Preview:
        """A mark at each problem's place."""
        out = Preview()
        for p in self.problems or []:
            if p.at is not None:
                out.points.append(p.at)
        return out
