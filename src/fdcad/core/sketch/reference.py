"""Outline of the part on a sketch plane, drawn as reference while sketching.

The part is cut with the sketch plane and the cut edges are returned as
polylines in sketch coordinates. Run it off the UI thread (CLAUDE.md rule 2).
"""

from __future__ import annotations

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GCPnts import GCPnts_QuasiUniformDeflection
from OCP.GeomAbs import GeomAbs_Circle
from OCP.gp import gp_Pln
from OCP.Standard import Standard_Failure
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Shape

from fdcad.core.occ import BRepAlgoAPI_Section
from fdcad.core.sketch.profiles import SketchPlane

Polyline = list[tuple[float, float]]
#: A circle or arc of the outline: centre in sketch millimetres and radius.
RefCircle = tuple[tuple[float, float], float]


def plane_outline(
    shape: TopoDS_Shape, plane: SketchPlane, deviation: float = 0.01
) -> list[Polyline]:
    """Edges where ``shape`` meets ``plane``, as polylines in sketch millimetres.

    Returns an empty list when the part does not reach the plane or the cut fails.
    """
    return plane_section(shape, plane, deviation)[0]


def plane_section(
    shape: TopoDS_Shape, plane: SketchPlane, deviation: float = 0.01
) -> tuple[list[Polyline], list[RefCircle]]:
    """The outline polylines and the circles among its edges (so their centres can be
    snapped to, W3.2).

    On a part the kernel is slow on (free form faces or very many faces, D2612) the
    cut is made on the part's mesh in numpy, as Layer Preview does (D2615): the kernel's
    cut along a thread took 8.7 s on the nut and bolt each time a sketch opened (D2683).
    The mesh cut has no circles to snap to."""
    from fdcad.core.features.direct import slow_for_kernel

    if slow_for_kernel(shape):
        try:
            return mesh_section(shape, plane), []
        except ValueError:  # the part could not be meshed: no reference outline
            return [], []
    ax = plane.ax3()
    o, x, y = ax.Location(), ax.XDirection(), ax.YDirection()
    try:
        section = BRepAlgoAPI_Section(shape, gp_Pln(ax), False)
        section.Approximation(False)
        section.Build()
        if not section.IsDone():
            return [], []
        result = section.Shape()
    except Standard_Failure:
        return [], []
    out: list[Polyline] = []
    circles: list[RefCircle] = []

    def to_2d(px: float, py: float, pz: float) -> tuple[float, float]:
        dx, dy, dz = px - o.X(), py - o.Y(), pz - o.Z()
        return (dx * x.X() + dy * x.Y() + dz * x.Z(), dx * y.X() + dy * y.Y() + dz * y.Z())

    explorer = TopExp_Explorer(result, TopAbs_EDGE)
    while explorer.More():
        edge = TopoDS.Edge(explorer.Current())
        explorer.Next()
        try:
            curve = BRepAdaptor_Curve(edge)
            points = GCPnts_QuasiUniformDeflection(curve, deviation)
        except Standard_Failure:
            continue
        if not points.IsDone():
            continue
        if curve.GetType() == GeomAbs_Circle:
            circ = curve.Circle()
            c = circ.Location()
            circles.append((to_2d(c.X(), c.Y(), c.Z()), circ.Radius()))
        line: Polyline = []
        for i in range(1, points.NbPoints() + 1):
            p = points.Value(i)
            line.append(to_2d(p.X(), p.Y(), p.Z()))
        if len(line) >= 2:
            out.append(line)
    return out, circles


def behind(shape: TopoDS_Shape, plane: SketchPlane) -> TopoDS_Shape:
    """The part of ``shape`` behind the sketch plane (on the side away from its normal),
    for Cut Away while sketching (TR113, D844). The part itself is not changed."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeHalfSpace
    from OCP.gp import gp_Pln

    from fdcad.core.occ import BRepAlgoAPI_Common

    face = BRepBuilderAPI_MakeFace(gp_Pln(plane.ax3())).Face()
    n = plane.normal
    o = plane.to_3d(0.0, 0.0)
    from OCP.gp import gp_Pnt

    inside = gp_Pnt(o.X() - n[0], o.Y() - n[1], o.Z() - n[2])
    half = BRepPrimAPI_MakeHalfSpace(face, inside).Solid()
    common = BRepAlgoAPI_Common(shape, half)
    common.Build()
    return common.Shape() if common.IsDone() else shape


def mesh_section(shape: TopoDS_Shape, plane: SketchPlane) -> list[Polyline]:
    """Where ``plane`` cuts the mesh of ``shape``, one polyline per cut triangle edge
    pair, in sketch millimetres (D2683). Raises ValueError when the part cannot be
    meshed."""
    import numpy as np

    from fdcad.core.printing.layer_lines import mesh_segments
    from fdcad.core.printing.overhang import triangles_by_face

    ax = plane.ax3()
    o, x, y, n = ax.Location(), ax.XDirection(), ax.YDirection(), ax.Direction()
    origin = np.array([o.X(), o.Y(), o.Z()])
    normal = (n.X(), n.Y(), n.Z())
    _faces, corners, _owner = triangles_by_face(shape)
    level = float(np.dot(origin, normal))
    segments = mesh_segments(corners, normal, np.array([level]))
    if len(segments) == 0:
        return []
    frame = np.array([[x.X(), x.Y(), x.Z()], [y.X(), y.Y(), y.Z()]])
    flat = (segments - origin) @ frame.T  # (m, 2, 2) in sketch millimetres
    flat = flat[np.linalg.norm(flat[:, 1] - flat[:, 0], axis=1) > 1e-6]
    return [[(a[0], a[1]), (b[0], b[1])] for a, b in flat.tolist()]
