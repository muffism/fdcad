"""Intersection curves and the silhouette of the part on a sketch plane (TR6, D759).

- ``intersection_curves``: where the sketch plane cuts the part's faces.
- ``silhouette``: the outline of the part seen square to the sketch plane. The
  kernel's hidden line removal gives every visible edge of that view; an edge
  is kept when the part lies on one side of it and nothing on the other, which
  is what makes it part of the outline. On parts the kernel is slow on (free form
  faces or many faces, D2612) that took from 30 s to many minutes, so there the
  outline is found from the part's mesh instead (``mesh_outline``, D2618).

Both return a ``ProjectedCurve`` that ``curve_convert.add_curve`` adds to a
sketch as fixed curves (lines, arcs and splines). Kernel work, run in a kernel
job (CLAUDE.md 5.2); a kernel failure gives an empty result, never an error.
"""

from __future__ import annotations

import math

from OCP.gp import gp_Ax2, gp_Dir, gp_Lin, gp_Pln, gp_Pnt
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.occ import BRepAlgoAPI_Section
from fdcad.core.sketch.curve_convert import CurvePiece, ProjectedCurve
from fdcad.core.sketch.curve_projection import project_curve
from fdcad.core.sketch.profiles import SketchPlane

INTERSECTION = "intersection"
SILHOUETTE = "silhouette"
#: How far beside an outline edge (mm) the two sides are tried.
_SIDE = 0.05


def intersection_curves(shape: TopoDS_Shape, plane: SketchPlane) -> ProjectedCurve:
    """The curves where ``plane`` cuts ``shape``."""
    out = ProjectedCurve(INTERSECTION, "Intersection Curves")
    try:
        section = BRepAlgoAPI_Section(shape, gp_Pln(plane.ax3()), False)
        section.Approximation(True)
        section.Build()
        if not section.IsDone():
            return out
        out.pieces, out.skipped = project_curve(section.Shape(), plane)
    except Exception:  # reference only: an empty result, never a crash (CLAUDE.md 5.7)
        out.pieces, out.skipped = [], 0
    return out


def _hits(shape: TopoDS_Shape, plane: SketchPlane, u: float, v: float) -> bool:
    """True when the line square to the plane through (u, v) meets the part."""
    from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector

    finder = IntCurvesFace_ShapeIntersector()
    finder.Load(shape, 1e-7)
    finder.Perform(gp_Lin(plane.to_3d(u, v), gp_Dir(*plane.normal)), -1e7, 1e7)
    return bool(finder.IsDone() and finder.NbPnt() > 0)


def _on_outline(shape: TopoDS_Shape, plane: SketchPlane, piece: CurvePiece) -> bool:
    """True when the part lies on one side of the piece and not on the other."""
    line = piece.polyline(8)
    if len(line) < 2:
        return False
    k = len(line) // 2
    (ax, ay), (bx, by) = line[max(k - 1, 0)], line[min(k, len(line) - 1)]
    if (ax, ay) == (bx, by):
        (ax, ay), (bx, by) = line[0], line[-1]
    mx, my = (ax + bx) / 2, (ay + by) / 2
    length = math.hypot(bx - ax, by - ay)
    if length < 1e-9:
        return False
    nx, ny = -(by - ay) / length * _SIDE, (bx - ax) / length * _SIDE
    return _hits(shape, plane, mx + nx, my + ny) != _hits(shape, plane, mx - nx, my - ny)


def silhouette(shape: TopoDS_Shape, plane: SketchPlane) -> ProjectedCurve:
    """The outline of ``shape`` seen square to ``plane``."""
    from OCP.HLRAlgo import HLRAlgo_Projector
    from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape

    from fdcad.core.features.direct import slow_for_kernel
    from fdcad.core.sketch.mesh_outline import outline_pieces

    out = ProjectedCurve(SILHOUETTE, "Silhouette")
    try:
        if slow_for_kernel(shape):
            # The exact removal took 37 s on the nut and bolt's threads seen from the
            # side and minutes along the bolt, holding the window (idea 74).
            try:
                out.pieces = outline_pieces(shape, plane)
            except ValueError as exc:  # the part could not be meshed: say so (D2635)
                reason = str(exc)
                out.problem = f"Silhouette failed: {reason[:1].lower()}{reason[1:]}"
            return out
        algo = HLRBRep_Algo()
        algo.Add(shape)
        view = gp_Ax2(gp_Pnt(*plane.origin), gp_Dir(*plane.normal), gp_Dir(*plane.x_dir))
        algo.Projector(HLRAlgo_Projector(view))
        algo.Update()
        algo.Hide()
        result = HLRBRep_HLRToShape(algo)
        # The view's own frame: x along the sketch x, y along the sketch y, z = 0.
        flat = SketchPlane((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))
        pieces: list[CurvePiece] = []
        skipped = 0
        for part in (result.VCompound(), result.OutLineVCompound()):
            if part is None or part.IsNull():
                continue
            found, missed = project_curve(part, flat)
            pieces += found
            skipped += missed
        out.pieces = [p for p in pieces if _on_outline(shape, plane, p)]
        out.skipped = skipped
    except Exception:  # reference only: an empty result, never a crash (CLAUDE.md 5.7)
        out.pieces, out.skipped = [], 0
    return out
