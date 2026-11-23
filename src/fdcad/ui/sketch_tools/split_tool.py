"""Split Entities (TUTORIAL_REVIEW_SPEC TR2, D691). Pure Python, no Qt.

Click a line, arc, partial ellipse or spline to split it there. A circle or an
ellipse needs two clicks. Each split is one undo step and the tool keeps going.
"""

from __future__ import annotations

from fdcad.core.sketch import freeform
from fdcad.core.sketch.model import (
    Arc,
    Circle,
    Ellipse,
    EllipseArc,
    Line,
    Spline,
)
from fdcad.core.sketch.ops.geom import Vec, geo, nearest_curve
from fdcad.core.sketch.ops.pieces import Report
from fdcad.core.sketch.ops.split import SplitError, closed, split_at
from fdcad.core.sketch.ops.trim import describe
from fdcad.ui.sketch_tools.edit import SketchEdit
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.pick_tools import RELATION_LABELS, PickTool
from fdcad.ui.sketch_tools.tools import Preview
from fdcad.ui.sketch_tools.transform_tools import add_entity_preview

SPLIT = "Split {name}."
SECOND = "Click a second point on the curve. A closed curve is split in two places."


class SplitTool(PickTool):
    """Click curves where they should be split."""

    name, label = "split", "Split Entities"
    pickable = (Line, Circle, Arc, Ellipse, EllipseArc, Spline)

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        #: The first click on a closed curve: (curve id, point).
        self.pending: tuple[str, Vec] | None = None

    @property
    def prompt(self) -> str:  # type: ignore[override]
        """What to click next."""
        if self.pending is not None:
            return SECOND
        return "Click a curve where it should be split. Circles and ellipses need two points."

    @property
    def busy(self) -> bool:
        """True while a closed curve waits for its second point."""
        return self.pending is not None

    def cancel(self) -> bool:
        """Escape drops a first point, then ends the tool."""
        if self.pending is not None:
            self.pending = None
            return False
        return True

    def curve_at(self, p: Vec) -> str | None:
        """Any curve under ``p``, freeform curves too."""
        sk = self.edit.sketch
        best = nearest_curve(sk, p, self.tolerance)
        if best is not None:
            return best
        found: tuple[float, str] | None = None
        for e in sk.curves(True):
            if isinstance(e, Ellipse | EllipseArc | Spline):
                d = freeform.distance(sk, e, p)
                if d <= self.tolerance and (found is None or d < found[0]):
                    found = (d, e.id)
        return found[1] if found else None

    def click(self, snap: Snap) -> bool:
        """Split the clicked curve (a closed one on its second click)."""
        self.hover(snap)
        cid, at = self.hot, snap.xy
        if self.pending is not None:
            first_id, first = self.pending
            if cid != first_id:
                self.message = SECOND
                return False
            self.pending = None
            return self._split(cid, first, at)
        if cid is None:
            return False
        if closed(self.edit.sketch, cid):
            self.pending = (cid, at)
            self.message = SECOND
            return False
        return self._split(cid, at, None)

    def _split(self, cid: str, at: Vec, second: Vec | None) -> bool:
        name = type(self.edit.sketch.entities[cid]).__name__.lower()
        error = ""

        def change() -> Report | None:
            nonlocal error
            try:
                return split_at(self.edit.sketch, cid, at, second)
            except SplitError as exc:
                error = str(exc)
                return None

        self.edit.checkpoint()
        report = change()
        if report is None:
            self.edit.discard_checkpoint()
            self.message = error
            return False
        self.drawn = [e for e in report.entities if e in self.edit.sketch.entities]
        removed = describe(report, RELATION_LABELS)
        note = SPLIT.format(name=name.replace("ellipsearc", "partial ellipse"))
        if removed:
            note += " " + removed.replace("Removed with the deleted pieces", "Removed")
        self.message = note
        return True

    def preview(self) -> Preview:
        """The curve under the cursor and where the split goes."""
        out = Preview()
        sk = self.edit.sketch
        if self.hot is not None and self.hot in sk.entities:
            add_entity_preview(out, sk, self.hot)
            if self.cursor is not None:
                out.points.append(_on_curve(sk, self.hot, self.cursor.xy))
        if self.pending is not None:
            out.points.append(_on_curve(sk, self.pending[0], self.pending[1]))
        return out


def _on_curve(sketch: object, cid: str, at: Vec) -> Vec:
    """The point of the curve near ``at`` (for the split mark)."""
    from fdcad.core.sketch.model import Sketch

    assert isinstance(sketch, Sketch)
    ent = sketch.entities.get(cid)
    if isinstance(ent, Line | Circle | Arc):
        g = geo(sketch, cid)
        t = g.param(at)
        if g.kind == "line":
            t = min(max(t, 0.0), 1.0)
        return g.at(t)
    if isinstance(ent, Ellipse | EllipseArc):
        c, a, b, phi = freeform.axes(sketch, ent)
        return freeform.ellipse_point(c, a, b, phi, freeform.ellipse_param(c, a, b, phi, at))
    return at
