"""Small measurements on single edges (TOOL_SPEC T9.7 Select Midpoint).

Tiny kernel work on one edge, like the other picking helpers (DECISIONS D75).
"""

from __future__ import annotations

from typing import Any


def edge_midpoint(edge: Any) -> tuple[float, float, float] | None:
    """The point halfway along an edge by length, or None when it has no length."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GCPnts import GCPnts_AbscissaPoint
    from OCP.TopoDS import TopoDS

    try:
        curve = BRepAdaptor_Curve(TopoDS.Edge(edge))
        first, last = curve.FirstParameter(), curve.LastParameter()
        length = GCPnts_AbscissaPoint.Length_s(curve)
        if length <= 0:
            return None
        param = GCPnts_AbscissaPoint(curve, length / 2, first).Parameter()
        if not first - 1e-9 <= param <= last + 1e-9:
            param = (first + last) / 2
        p = curve.Value(param)
    except Exception:  # a broken edge has no midpoint; never crash a menu
        return None
    return (p.X(), p.Y(), p.Z())
