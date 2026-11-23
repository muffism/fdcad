"""Convert tool (PHASE2_SPEC P2.8 item 5, curve features D517). Pure Python, no Qt."""

from __future__ import annotations

import itertools

from fdcad.core.sketch.curve_convert import ProjectedCurve, add_curve
from fdcad.core.sketch.ops.convert import chain_of, convert, kind_of, near
from fdcad.core.sketch.ops.geom import Vec, dist, geo
from fdcad.core.sketch.ops.pieces import Report
from fdcad.ui.sketch_tools.edit import SketchEdit
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.pick_tools import PickTool
from fdcad.ui.sketch_tools.tool_options import Option
from fdcad.ui.sketch_tools.tools import Preview

NOT_ROUND_OR_STRAIGHT = (
    "Only straight and round part edges can be converted. Click a straight or round edge."
)
CURVE_CONVERTED = "Converted {name}: {count} {curves}."
CURVE_SKIPPED = " {count} {edges} skipped because {they} to a point."
CURVE_ALREADY = "{name} is already in the sketch."
CURVE_EMPTY = "{name} has no edges that show on the sketch plane: they all project to a point."
NOT_A_CURVE = (
    "{name} is not a curve feature above this sketch. Pick a contour, projected curve, "
    "helix or other curve feature."
)


def _plural(count: int, one: str, many: str) -> str:
    return one if count == 1 else many


class ConvertTool(PickTool):
    """Click a part edge, or a curve feature in the view or the tree, to copy it into the
    sketch as fixed curves."""

    name, label = "convert", "Convert Entities"
    prompt = (
        "Click a part edge or a curve feature to copy it into the sketch, or click inside "
        "a face to copy its loops."
    )
    options = (
        Option("select_chain", "Select chain", "bool"),
        Option("inner_loops", "Inner loops", "bool"),  # TR118 (D1712)
        Option("construction", "For construction", "bool"),
    )

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.select_chain = False
        #: A face pick copies its inner loops too (TR118, D1712).
        self.inner_loops = True
        #: Ctrl is held: a click on an edge takes its whole loop (set by the canvas).
        self.ctrl = False
        #: The outline edge under the cursor.
        self.hot_edge: int | None = None
        #: Curve features above the sketch, projected onto it (set by the canvas, D517).
        self.curve_sources: list[ProjectedCurve] = []
        #: The curve feature under the cursor.
        self.hot_curve: ProjectedCurve | None = None

    def hover(self, snap: Snap) -> Snap:
        """Track the part edge or curve feature under the cursor."""
        snap = super().hover(snap)
        self.hot_edge = next(
            (i for i, poly in enumerate(self.model_lines) if near(poly, snap.xy, self.tolerance)),
            None,
        )
        self.hot_curve = None
        if self.hot_edge is None:
            self.hot_curve = next(
                (c for c in self.curve_sources if c.near(snap.xy, self.tolerance)), None
            )
        return snap

    def pick_feature(self, fid: str, name: str = "") -> bool:
        """Copy every edge of curve feature ``fid`` into the sketch (D517), one undo step.

        ``name`` is used in the note when ``fid`` is not a curve offered here.
        """
        curve = next((c for c in self.curve_sources if c.feature == fid), None)
        if curve is None:
            self.message = NOT_A_CURVE.format(name=name or fid)
            return False
        if not curve.pieces:
            self.message = CURVE_EMPTY.format(name=curve.name)
            return False
        made: list[str] = []

        def change() -> Report | None:
            made[:], _already = add_curve(self.edit.sketch, curve, self.construction)
            if not made:
                return None
            self.drawn = list(made)
            return Report()

        if not self.apply(change, CURVE_ALREADY.format(name=curve.name)):
            return False
        note = CURVE_CONVERTED.format(
            name=curve.name, count=len(made), curves=_plural(len(made), "curve", "curves")
        )
        if curve.skipped:
            note += CURVE_SKIPPED.format(
                count=curve.skipped,
                edges=_plural(curve.skipped, "edge was", "edges were"),
                they=_plural(curve.skipped, "it projects", "they project"),
            )
        self.message = note
        return True

    def _face(self, at: Vec) -> list[int]:
        """Edges of the face under ``at``: its outer loop and, with Inner loops on, its
        inner loops (TR118, D1712)."""
        from fdcad.core.sketch.ops.convert import face_loops

        found = face_loops(self.model_lines, at)
        if found is None:
            return []
        outer, inner = found
        return outer + ([i for loop in inner for i in loop] if self.inner_loops else [])

    def _picked(self) -> list[int]:
        if self.hot_edge is None:
            if self.hot_curve is None and self.cursor is not None and not self.ctrl:
                return self._face(self.cursor.xy)
            return []
        if self.select_chain or self.ctrl:
            return chain_of(self.model_lines, self.hot_edge)
        return [self.hot_edge]

    def click(self, snap: Snap) -> bool:
        """Convert the edge (or chain), or the curve feature, under the cursor."""
        self.hover(snap)
        picked = self._picked()
        if not picked and self.hot_curve is not None:
            return self.pick_feature(self.hot_curve.feature)
        if not picked:
            return False
        circles = list(self.model_circles)

        def change() -> Report | None:
            made = []
            for i in picked:
                poly = self.model_lines[i]
                if self._already(poly):
                    continue
                cid = convert(self.edit.sketch, poly, circles, self.construction)
                if cid is not None:
                    made.append(cid)
            if not made:
                return None
            self.drawn = made
            return Report()

        refused = NOT_ROUND_OR_STRAIGHT
        if all(kind_of(self.model_lines[i], circles) is not None for i in picked):
            refused = "That edge is already in the sketch."
        return self.apply(change, refused)

    def _already(self, poly: list[tuple[float, float]]) -> bool:
        """True when a fixed curve already sits on both ends of the edge."""
        sk = self.edit.sketch
        fixed = {e for r in sk.relations if r.type == "fixed" for e in r.entities}
        for c in sk.curves(True):
            if c.id not in fixed:
                continue
            g = geo(sk, c.id)
            ends = (g.at(0.0), g.at(g.sweep))
            if all(min(dist(q, p) for q in ends) < 1e-6 for p in (poly[0], poly[-1])):
                return True
        return False

    def preview(self) -> Preview:
        """Highlight the edges a click would convert."""
        out = Preview()
        for i in self._picked():
            poly = self.model_lines[i]
            out.lines += list(itertools.pairwise(poly))
        if self.hot_curve is not None:
            for poly in self.hot_curve.polylines:
                out.lines += list(itertools.pairwise(poly))
        return out
