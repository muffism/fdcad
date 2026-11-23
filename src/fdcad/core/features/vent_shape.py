"""Draft and fillet of a vent's ribs, spars and fill (TR146 item 3, D2406).

Each element group of a Vent can have its own draft angle and fillet radius. The
draft leans the group's side walls so the bars get narrower going into the wall
(the neutral plane is the bars' outer face, at the group's offset). The fillet rounds
the edges of that outer face, except where a bar meets the opening's wall, so the
bars stay joined to the part. No Qt.
"""

from __future__ import annotations

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

from fdcad.core.features import fastening as fx
from fdcad.core.features.base import FeatureError
from fdcad.core.features.sketch import face_plane
from fdcad.core.naming.names import NamedShape, restrict

_TOL = 1e-4


def _faces(shape: TopoDS_Shape) -> list[TopoDS_Face]:
    out = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        out.append(TopoDS.Face(explorer.Current()))
        explorer.Next()
    return out


def _centre(face: TopoDS_Face) -> fx.Vec3:
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    c = props.CentreOfMass()
    return c.X(), c.Y(), c.Z()


def _named_sides(
    prefix: str, shape: TopoDS_Shape, up: fx.Vec3, opening: list[TopoDS_Face]
) -> NamedShape:
    """``shape`` with its walls (faces square to ``up``) named ``side/<k>``, except the
    ends that sit on the opening's wall (they stay upright so the bars stay joined)."""
    names = []
    k = 0
    for face in _faces(shape):
        plane = face_plane(face)
        if plane is not None and abs(fx.dot(plane.normal, up)) > 1 - 1e-6:
            continue  # the outer or inner face of the bars
        if _point_on_boundary(_centre(face), opening, up):
            continue
        k += 1
        names.append((f"{prefix}/side/{k}", face))
    return NamedShape(shape, restrict(names, shape, prefix))


def _on_boundary(edge: TopoDS_Shape, opening: list[TopoDS_Face], up: fx.Vec3) -> bool:
    """True when the middle of ``edge``, moved square to the opening, lies on its outline."""
    curve = BRepAdaptor_Curve(TopoDS.Edge(edge))
    mid = curve.Value((curve.FirstParameter() + curve.LastParameter()) / 2)
    return _point_on_boundary((mid.X(), mid.Y(), mid.Z()), opening, up)


def _point_on_boundary(at: fx.Vec3, opening: list[TopoDS_Face], up: fx.Vec3) -> bool:
    """True when ``at``, moved square to the opening, lies on its outline."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.gp import gp_Pnt

    plane = face_plane(opening[0])
    assert plane is not None
    lift = fx.dot(fx.sub(plane.origin, at), up)
    p = fx.add(at, up, lift)
    vertex = BRepBuilderAPI_MakeVertex(gp_Pnt(*p)).Vertex()
    for face in opening:
        edges = TopExp_Explorer(face, TopAbs_EDGE)
        while edges.More():
            dist = BRepExtrema_DistShapeShape(vertex, edges.Current())
            edges.Next()
            if dist.IsDone() and dist.Value() < 1e-3:
                return True
    return False


def shaped(
    owner: str,
    role: str,
    slab: NamedShape,
    up: fx.Vec3,
    top: fx.Vec3,
    draft: float,
    fillet: float,
    opening: list[TopoDS_Face],
) -> NamedShape:
    """``slab`` (one group's bars, pushed down from ``top`` square to ``up``) with its
    walls drafted by ``draft`` (radians) and its outer edges rounded by ``fillet`` (mm)."""
    if draft < 0 or fillet < 0:
        raise FeatureError(
            f"{owner}: the {role} draft and fillet cannot be negative. Enter positive values."
        )
    prefix = slab.faces[0][0].rsplit("/", 1)[0] if slab.faces else f"{role}"
    named = _named_sides(prefix, slab.shape, up, opening)
    if draft:
        try:
            named = fx.draft_sides(named, top, fx.neg(up), draft, "/side/")
        except FeatureError:
            raise FeatureError(
                f"{owner}: the {role} draft cannot be applied. Use a smaller angle."
            ) from None
    shape = named.shape
    if fillet:
        maker = BRepFilletAPI_MakeFillet(shape)
        count = 0
        for face in _faces(shape):
            plane = face_plane(face)
            at = _centre(face)
            if plane is None or abs(fx.dot(fx.sub(at, top), up)) > _TOL:
                continue  # only the outer face's edges are rounded
            edges = TopExp_Explorer(face, TopAbs_EDGE)
            while edges.More():
                edge = edges.Current()
                edges.Next()
                if not _on_boundary(edge, opening, up):
                    maker.Add(fillet, TopoDS.Edge(edge))
                    count += 1
        if count:
            try:
                maker.Build()
                ok = maker.IsDone()
            except Exception:
                ok = False
            if not ok:
                raise FeatureError(
                    f"{owner}: the {role} fillet failed: the radius is too large for the bars. "
                    "Reduce the fillet radius."
                )
            shape = maker.Shape()
    return NamedShape(shape, restrict([], shape, prefix))
