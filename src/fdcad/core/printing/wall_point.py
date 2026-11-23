"""The wall thickness at one point of a part (TR87 item 2, D1808): the hover reading of
Wall Thickness Analysis.

The point is put on the nearest face; from there a ray goes straight into the
material, against the outward normal, and the wall is the distance to where it
leaves the material again (the same measure as ``wall_thickness``, D414).
Kernel work: run it in a kernel job.
"""

from __future__ import annotations

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCP.BRepExtrema import BRepExtrema_DistShapeShape, BRepExtrema_IsInFace
from OCP.BRepLProp import BRepLProp_SLProps
from OCP.gp import gp_Dir, gp_Lin, gp_Pnt
from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
from OCP.TopAbs import TopAbs_REVERSED
from OCP.TopoDS import TopoDS, TopoDS_Shape

Vec3 = tuple[float, float, float]
#: The ray starts this far inside the surface, so it does not hit its own face.
_START = 1e-6
#: A cursor point further than this from the part reads nothing (mm).
_NEAR = 0.5


def thickness_at(shape: TopoDS_Shape, point: Vec3) -> float | None:
    """The wall under ``point`` in mm, or None when the point is off the part or the
    ray finds no other side (an open body)."""
    vertex = BRepBuilderAPI_MakeVertex(gp_Pnt(*point)).Vertex()
    dist = BRepExtrema_DistShapeShape(vertex, shape)
    if not dist.IsDone() or dist.NbSolution() == 0 or dist.Value() > _NEAR:
        return None
    for k in range(1, dist.NbSolution() + 1):
        if dist.SupportTypeShape2(k) != BRepExtrema_IsInFace:
            continue
        face = TopoDS.Face(dist.SupportOnShape2(k))
        u, v = dist.ParOnFaceS2(k)
        props = BRepLProp_SLProps(BRepAdaptor_Surface(face), u, v, 1, 1e-7)
        if not props.IsNormalDefined():
            continue
        n = props.Normal()
        if face.Orientation() == TopAbs_REVERSED:
            n.Reverse()
        on = dist.PointOnShape2(k)
        inward = gp_Dir(-n.X(), -n.Y(), -n.Z())
        start = gp_Pnt(*(on.Coord(i) + inward.Coord(i) * _START for i in (1, 2, 3)))
        hits = IntCurvesFace_ShapeIntersector()
        hits.Load(shape, 1e-7)
        hits.Perform(gp_Lin(start, inward), 0.0, 1e9)
        if not hits.IsDone() or hits.NbPnt() == 0:
            return None
        return float(min(hits.WParameter(i) for i in range(1, hits.NbPnt() + 1))) + _START
    return None
