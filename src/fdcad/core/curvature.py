"""Curvature combs for curves and edges, a display only overlay (PLAN Phase 3,
PHASE3_SPEC P3.7 item 5, DECISIONS D292).

A comb has one tooth per sample point. Each tooth leaves the curve on the side
away from the centre of curvature, as long as the curvature times the scale.
The tips are joined into a smooth outline, so a change in curvature is easy to
see. Nothing here changes the part. Run it off the UI thread.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakePolygon
from OCP.BRepLProp import BRepLProp_CLProps
from OCP.gp import gp_Dir, gp_Pnt
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Shape

#: Sample points per edge allowed (the density slider's range).
MIN_DENSITY = 4
MAX_DENSITY = 400
#: Teeth longer than this many times the curve's size are clipped, so a tight
#: corner does not hide the rest of the comb.
_MAX_TOOTH = 2.0


@dataclass
class Comb:
    """Points on the curve, their tooth tips, and the curvature (1/mm) at each."""

    points: NDArray[np.float64]
    tips: NDArray[np.float64]
    curvature: NDArray[np.float64]


def _edges(shape: TopoDS_Shape) -> list[TopoDS_Edge]:
    out = []
    explorer = TopExp_Explorer(shape, TopAbs_EDGE)
    while explorer.More():
        out.append(TopoDS.Edge(explorer.Current()))
        explorer.Next()
    return out


def edge_comb(edge: TopoDS_Edge, density: int, scale: float) -> Comb:
    """The comb of one edge with ``density`` sample points (a bounded count)."""
    density = max(MIN_DENSITY, min(MAX_DENSITY, int(density)))
    curve = BRepAdaptor_Curve(edge)
    u0, u1 = curve.FirstParameter(), curve.LastParameter()
    params = np.linspace(u0, u1, density)
    props = BRepLProp_CLProps(curve, 2, 1e-7)
    points = np.zeros((density, 3))
    normals = np.zeros((density, 3))
    curvature = np.zeros(density)
    for i, u in enumerate(params.tolist()):
        props.SetParameter(u)
        p = props.Value()
        points[i] = (p.X(), p.Y(), p.Z())
        if props.IsTangentDefined():
            k = props.Curvature()
            if k > 1e-12:
                n = gp_Dir()
                props.Normal(n)
                normals[i] = (n.X(), n.Y(), n.Z())
                curvature[i] = k
    size = float(np.linalg.norm(points.max(axis=0) - points.min(axis=0))) or 1.0
    length = np.minimum(curvature * scale, _MAX_TOOTH * size)
    # The normal points to the centre of curvature; teeth go the other way.
    tips = points - normals * length[:, None]
    return Comb(points, tips, curvature)


def combs(shape: TopoDS_Shape, density: int, scale: float) -> list[Comb]:
    """A comb for every edge of ``shape``."""
    return [edge_comb(e, density, scale) for e in _edges(shape)]


def comb_shape(items: list[Comb]) -> TopoDS_Shape | None:
    """Teeth and outline of the combs as edges, for the 3D view."""
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    builder = BRep_Builder()
    comp = TopoDS_Compound()
    builder.MakeCompound(comp)
    count = 0
    for item in items:
        outline = BRepBuilderAPI_MakePolygon()
        for p, t in zip(item.points.tolist(), item.tips.tolist(), strict=True):
            a, b = gp_Pnt(*p), gp_Pnt(*t)
            if a.Distance(b) > 1e-9:
                builder.Add(comp, BRepBuilderAPI_MakeEdge(a, b).Edge())
                count += 1
            outline.Add(b)
        if outline.IsDone():
            builder.Add(comp, outline.Wire())
            count += 1
    return comp if count else None
