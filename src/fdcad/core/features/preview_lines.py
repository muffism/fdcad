"""Cross lines of a Fillet or Chamfer face for the Full preview (PV3 item 2, D1032).

Each face gets lines that join its two long edges: arcs for a round, straight lines
for a chamfer. They are iso curves of the face's surface across its short direction,
at evenly spaced parameters along its length. No Qt; runs off the UI thread.
"""

from __future__ import annotations

from collections.abc import Sequence

from OCP.BRep import BRep_Tool
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCP.BRepTools import BRepTools
from OCP.GCPnts import GCPnts_AbscissaPoint
from OCP.GeomAdaptor import GeomAdaptor_Curve
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face, TopoDS_Shape

#: Spacing of the lines along a face, in millimetres, and the count bounds per face.
LINE_SPACING_MM = 3.0
MIN_LINES = 3
MAX_LINES = 40

#: Feature types whose Full preview draws cross lines.
LINE_FEATURES = frozenset({"fillet", "chamfer"})


def line_count(length: float) -> int:
    """Lines for a face ``length`` mm long, both end lines included."""
    return max(MIN_LINES, min(MAX_LINES, round(length / LINE_SPACING_MM) + 1))


def _length(curve: object, first: float, last: float) -> float:
    return float(GCPnts_AbscissaPoint.Length_s(GeomAdaptor_Curve(curve, first, last)))


def cross_lines(face: TopoDS_Face) -> list[TopoDS_Edge]:
    """The cross lines of one round or chamfer face; empty if it cannot be made."""
    surface = BRep_Tool.Surface_s(face)
    if surface is None:
        return []
    u0, u1, v0, v1 = BRepTools.UVBounds_s(face)
    um, vm = (u0 + u1) / 2, (v0 + v1) / 2
    along_v = _length(surface.UIso(um), v0, v1)  # a curve running in v at mid u
    along_u = _length(surface.VIso(vm), u0, u1)
    if along_v >= along_u:  # v runs along the edges: cross lines are curves in u
        length, lo, hi, across = along_v, v0, v1, (u0, u1)
        iso = surface.VIso
    else:
        length, lo, hi, across = along_u, u0, u1, (v0, v1)
        iso = surface.UIso
    count = line_count(length)
    edges: list[TopoDS_Edge] = []
    for i in range(count):
        t = lo + (hi - lo) * i / (count - 1)
        maker = BRepBuilderAPI_MakeEdge(iso(t), across[0], across[1])
        if maker.IsDone():
            edges.append(maker.Edge())
    return edges


def lines_of(faces: Sequence[TopoDS_Shape]) -> list[TopoDS_Edge]:
    """Cross lines of every face in ``faces``."""
    out: list[TopoDS_Edge] = []
    for face in faces:
        try:
            out.extend(cross_lines(TopoDS.Face(face)))
        except Exception:  # a face without a usable surface just has no lines
            continue
    return out
