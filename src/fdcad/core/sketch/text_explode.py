"""Explode sketch text into curves (TUTORIAL_REVIEW_SPEC_2 TR121 item 1, D1713).

The text's glyph outlines (``text.layout``) become plain sketch curves the user can
edit: straight edges become lines, round edges arcs, and the rest splines through
points along them. Joined ends share a Coincident relation, the text item goes,
and nothing is fixed. ``explode_pieces`` is kernel work (run it off the UI
thread); ``apply_explode`` only edits the sketch.
"""

from __future__ import annotations

import math
from typing import Any

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Line
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

from fdcad.core.sketch.curve_convert import CurvePiece, add_piece
from fdcad.core.sketch.model import Sketch, curve_ends
from fdcad.core.sketch.text import layout

Vec = tuple[float, float]
#: Points along each glyph edge that is not straight or round.
SPLINE_POINTS = 9


def _piece(edge: Any) -> CurvePiece | None:
    curve = BRepAdaptor_Curve(edge)
    t0, t1 = curve.FirstParameter(), curve.LastParameter()
    p0, p1 = curve.Value(t0), curve.Value(t1)
    a, b = (p0.X(), p0.Y()), (p1.X(), p1.Y())
    kind = curve.GetType()
    if kind == GeomAbs_Line:
        return CurvePiece("line", (a, b)) if math.dist(a, b) > 1e-6 else None
    if kind == GeomAbs_Circle:
        circ = curve.Circle()
        c = (circ.Location().X(), circ.Location().Y())
        a0, a1 = math.atan2(a[1] - c[1], a[0] - c[0]), math.atan2(b[1] - c[1], b[0] - c[0])
        if circ.Axis().Direction().Z() < 0:  # runs clockwise: swap the ends
            a, b, a0, a1 = b, a, a1, a0
        return CurvePiece("arc", (a, b), c, circ.Radius(), (a0, a1))
    pts = []
    for k in range(SPLINE_POINTS):
        p = curve.Value(t0 + (t1 - t0) * k / (SPLINE_POINTS - 1))
        pts.append((p.X(), p.Y()))
    return CurvePiece("spline", tuple(pts))


def explode_pieces(sketch: Sketch, text_id: str) -> list[CurvePiece]:
    """The curve pieces of text item ``text_id``'s outlines. Kernel work."""
    t = next((x for x in sketch.texts if x.id == text_id), None)
    if t is None:
        raise ValueError(f"No text {text_id} in the sketch.")
    out: list[CurvePiece] = []
    for face in layout(t, sketch):
        explorer = TopExp_Explorer(face, TopAbs_EDGE)
        while explorer.More():
            piece = _piece(TopoDS.Edge(explorer.Current()))
            if piece is not None:
                out.append(piece)
            explorer.Next()
    return out


def apply_explode(sketch: Sketch, text_id: str, pieces: list[CurvePiece]) -> list[str]:
    """Replace text item ``text_id`` with free curves from ``pieces``, joined where their
    ends meet. Returns the new curve ids."""
    made = [add_piece(sketch, piece) for piece in pieces]
    new = set(made)
    sketch.relations = [
        r for r in sketch.relations if not (r.type == "fixed" and set(r.entities) <= new)
    ]
    ends = [p for cid in made for p in (curve_ends(sketch.entities[cid]) or ())]  # type: ignore[arg-type]
    grid: dict[tuple[int, int], list[str]] = {}
    for pid in ends:
        x, y = sketch.xy(pid)
        key = (round(x * 1e4), round(y * 1e4))
        here = grid.setdefault(key, [])
        if here:
            sketch.relate("coincident", here[0], pid)
        here.append(pid)
    sketch.texts = [t for t in sketch.texts if t.id != text_id]
    return made
