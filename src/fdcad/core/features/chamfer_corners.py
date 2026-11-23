"""Chamfer corners (TR321, D1812): how the corner looks where three chamfers meet.

``corner`` "patch" (the default) keeps the kernel's corner: a small flat triangle
where the three bevels meet. "mitre" extends the three bevel faces until they
meet in one point, so the corner is three mitre lines and no extra face: the
small tetrahedron between the triangle and that point is added (or cut, when the
point lies inside the part), and the faces that then lie on one plane are merged
back into the bevel faces, which keep their names.

"blend" (D2304) replaces the triangle with a curved face built through its three
edges and meeting each bevel tangent along the middle of the edge (the kernel's
filling with G1 edge constraints); at the triangle's three points the bevels
cannot all be tangent to one face, so a slight crease is left there.

Only triangle corners between three flat bevel faces are changed; any other
corner stays as the kernel made it and is named in a warning.
"""

from __future__ import annotations

import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid, BRepBuilderAPI_Sewing
from OCP.GeomAbs import GeomAbs_Plane
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCP.TopAbs import TopAbs_REVERSED, TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

from fdcad.core.features.base import FeatureState, Issue
from fdcad.core.features.modify import edge_faces, edges_of
from fdcad.core.features.solids import is_valid, polygon_face
from fdcad.core.naming.names import NamedShape, carry, restrict
from fdcad.core.occ import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse

CORNERS = ("patch", "mitre", "blend")

Vec3 = tuple[float, float, float]


def _plane(face: TopoDS_Face) -> tuple[np.ndarray, float] | None:
    surface = BRepAdaptor_Surface(face)
    if surface.GetType() != GeomAbs_Plane:
        return None
    pln = surface.Plane()
    d = pln.Axis().Direction()
    n = np.array([d.X(), d.Y(), d.Z()])
    if face.Orientation() == TopAbs_REVERSED:
        n = -n
    p = pln.Location()
    return n, float(n @ np.array([p.X(), p.Y(), p.Z()]))


def _vertices(face: TopoDS_Face) -> list[Vec3]:
    from OCP.BRep import BRep_Tool

    out: list[Vec3] = []
    explorer = TopExp_Explorer(face, TopAbs_VERTEX)
    while explorer.More():
        p = BRep_Tool.Pnt_s(TopoDS.Vertex(explorer.Current()))
        q = (p.X(), p.Y(), p.Z())
        if not any(np.allclose(q, r, atol=1e-7) for r in out):
            out.append(q)
        explorer.Next()
    return out


def _tetra(points: list[Vec3]) -> TopoDS_Shape | None:
    a, b, c, apex = points
    sewing = BRepBuilderAPI_Sewing(1e-7)
    for tri in ([a, b, c], [a, b, apex], [b, c, apex], [c, a, apex]):
        sewing.Add(polygon_face(tri))
    sewing.Perform()
    try:
        solid = BRepBuilderAPI_MakeSolid(TopoDS.Shell(sewing.SewedShape())).Solid()
    except Exception:  # not a closed shell: the corner is left as it is
        return None
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN

    middle = np.mean(np.array(points), axis=0)
    inside = BRepClass3d_SolidClassifier(solid, gp_Pnt(*middle), 1e-9)
    if inside.State() != TopAbs_IN:
        solid.Reverse()
    return solid


def mitre(
    fid: str, owner: str, before: NamedShape, body: NamedShape
) -> tuple[NamedShape, list[Issue]]:
    """``body`` (the kernel's chamfer result) with every triangle corner between three
    flat bevel faces made a mitre."""
    current = body
    left: list[str] = []
    corners = [(n, f) for n, f in body.faces if n.startswith(f"{fid}/corner")]
    for name, _face in corners:
        face = current.face(name)
        if face is None:
            continue
        points = _vertices(face)
        own = _plane(face)
        neighbours: list[TopoDS_Face] = []
        for edge in edges_of(face):
            for other in edge_faces(current.shape, edge):
                if not other.IsSame(face) and not any(other.IsSame(x) for x in neighbours):
                    neighbours.append(other)
        planes = [_plane(f) for f in neighbours]
        bevels = all(
            (current.primary_name(f) or "").startswith(f"{fid}/chamfer/") for f in neighbours
        )
        if len(points) != 3 or own is None or len(planes) != 3 or not bevels or None in planes:
            left.append(name)
            continue
        normals = np.array([p[0] for p in planes if p is not None])
        offsets = np.array([p[1] for p in planes if p is not None])
        if abs(np.linalg.det(normals)) < 1e-9:
            left.append(name)
            continue
        apex = np.linalg.solve(normals, offsets)
        tetra = _tetra([*points, (float(apex[0]), float(apex[1]), float(apex[2]))])
        if tetra is None:
            left.append(name)
            continue
        outside = float(own[0] @ apex) > own[1]
        op = (
            BRepAlgoAPI_Fuse(current.shape, tetra)
            if outside
            else BRepAlgoAPI_Cut(current.shape, tetra)
        )
        op.Build()
        if not op.IsDone():
            left.append(name)
            continue
        names = carry(current.faces, op.History())
        unify = ShapeUpgrade_UnifySameDomain(op.Shape(), True, True, False)
        unify.Build()
        shape = unify.Shape()
        names = carry(names, unify.History())
        step = NamedShape(shape, restrict(names, shape, f"{fid}/mitre"))
        if not is_valid(before, step):
            left.append(name)
            continue
        current = step
    issues: list[Issue] = []
    if left:
        issues.append(
            Issue(
                FeatureState.WARNING,
                f"{owner}: {len(left)} corner{'s' if len(left) != 1 else ''} stayed as patches: "
                "a mitre needs three flat bevels meeting in a triangle. Use equal distances, "
                "or choose Patch corners.",
                code="corner_left",
            )
        )
    return current, issues


def blend(
    fid: str, owner: str, before: NamedShape, body: NamedShape
) -> tuple[NamedShape, list[Issue]]:
    """``body`` with every triangle corner between three bevel faces of this chamfer
    replaced by a curved face that meets the bevels smoothly (TR321, D2304)."""
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeFilling
    from OCP.BRepTools import BRepTools_ReShape
    from OCP.GeomAbs import GeomAbs_G1
    from OCP.ShapeFix import ShapeFix_Shape

    current = body
    left: list[str] = []
    for name, _face in [(n, f) for n, f in body.faces if n.startswith(f"{fid}/corner")]:
        face = current.face(name)
        if face is None:
            continue
        pairs = []
        for edge in edges_of(face):
            others = [o for o in edge_faces(current.shape, edge) if not o.IsSame(face)]
            pairs.append((edge, others[0] if others else None))
        bevels = all(
            o is not None and (current.primary_name(o) or "").startswith(f"{fid}/chamfer/")
            for _e, o in pairs
        )
        if len(pairs) != 3 or not bevels:
            left.append(name)
            continue
        try:
            fill = BRepOffsetAPI_MakeFilling()
            for edge, other in pairs:
                fill.Add(edge, other, GeomAbs_G1, True)
            fill.Build()
            if not fill.IsDone():
                raise ValueError("the corner face could not be filled")
            reshape = BRepTools_ReShape()
            reshape.Replace(face, fill.Shape())
            fixer = ShapeFix_Shape(reshape.Apply(current.shape))
            fixer.Perform()
            shape = fixer.Shape()
        except Exception:  # kernel failure: the corner stays a patch
            left.append(name)
            continue
        names = [(n, reshape.Apply(f)) for n, f in current.faces]
        named = [(n, TopoDS.Face(fixer.Context().Apply(f))) for n, f in names if not f.IsNull()]
        step = NamedShape(shape, restrict(named, shape, f"{fid}/blend"))
        if not is_valid(before, step):
            left.append(name)
            continue
        current = step
    issues: list[Issue] = []
    if left:
        issues.append(
            Issue(
                FeatureState.WARNING,
                f"{owner}: {len(left)} corner{'s' if len(left) != 1 else ''} stayed as patches: "
                "a blend needs three bevels of this chamfer meeting in a triangle. "
                "Use equal distances, or choose Patch corners.",
                code="corner_left",
            )
        )
    return current, issues
