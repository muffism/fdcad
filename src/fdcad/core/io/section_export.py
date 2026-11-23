"""Section and outline export to DXF and SVG (TR300, DECISIONS D1204).

Two sources: the cut of the bodies at a plane, or each body's outline seen along
an axis (its shadow on a plane square to the axis). Every body has a use: cut,
engrave or ignore; each use is a layer of its own in the file. The faces can be
grown (positive) or shrunk (negative) by a kerf or tool offset, and the drawing
can be scaled. All kernel work: run it off the UI thread.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from OCP.TopoDS import TopoDS_Shape

from fdcad.core.io.export import ExportError

Vec3 = tuple[float, float, float]
USES = ("cut", "engrave", "ignore")
#: Layer names in the file, per use.
LAYERS = {"cut": "CUT", "engrave": "ENGRAVE"}
#: Stroke colours in SVG files, per use: red cuts and blue engraves, as laser
#: programs usually map them.
SVG_COLOURS = {"CUT": "#FF0000", "ENGRAVE": "#0000FF"}
#: The standard planes and axes: normal and the X direction of the drawing.
VIEWS: dict[str, tuple[Vec3, Vec3]] = {
    "top": ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
    "front": ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0)),
    "right": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
}


@dataclass(frozen=True)
class SectionJob:
    """What to draw: ``mode`` "section" (at ``offset`` along the view's normal) or
    "outline" (seen along the normal), the body ``uses``, ``kerf`` in mm and ``scale``."""

    mode: str = "section"
    view: str = "top"
    offset: float = 0.0
    kerf: float = 0.0
    scale: float = 1.0
    uses: tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        """Raise ExportError for settings that cannot work."""
        if self.mode not in ("section", "outline"):
            raise ExportError("Choose Section or Outline.")
        if self.view not in VIEWS:
            raise ExportError("Choose the Top, Front or Right plane.")
        if not self.scale > 0:
            raise ExportError("The scale must be greater than zero. Enter a larger scale.")
        if any(u not in USES for u in self.uses):
            raise ExportError("Each body is cut, engrave or ignore. Choose one of them.")


def plane_of(view: str, offset: float = 0.0) -> Any:
    """The drawing plane of ``view``, moved ``offset`` along its normal."""
    from OCP.gp import gp_Ax3, gp_Dir, gp_Pnt

    (nx, ny, nz), (xx, xy, xz) = VIEWS[view]
    return gp_Ax3(
        gp_Pnt(nx * offset, ny * offset, nz * offset), gp_Dir(nx, ny, nz), gp_Dir(xx, xy, xz)
    )


def _big_face(plane: Any, size: float) -> TopoDS_Shape:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.gp import gp_Pln

    return BRepBuilderAPI_MakeFace(gp_Pln(plane), -size, size, -size, size).Face()


def _extent(shape: TopoDS_Shape) -> float:
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    if box.IsVoid():
        return 1.0
    lo, hi = box.CornerMin(), box.CornerMax()
    reach = max(abs(v) for v in (lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()))
    return float(2.0 * reach + 10.0)


def _faces(shape: TopoDS_Shape) -> list[TopoDS_Shape]:
    from fdcad.core.naming.names import faces_of

    return list(faces_of(shape))


def section_faces(body: TopoDS_Shape, plane: Any) -> list[TopoDS_Shape]:
    """The faces where ``plane`` cuts ``body`` (none when it misses)."""
    from fdcad.core.occ import BRepAlgoAPI_Common

    common = BRepAlgoAPI_Common(body, _big_face(plane, _extent(body)))
    if not common.IsDone():
        raise ValueError("the cut through the body failed")
    return _faces(common.Shape())


def _inside_point(face: TopoDS_Shape) -> Any:
    """A point inside ``face``: the middle of one of its mesh triangles."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS

    BRepMesh_IncrementalMesh(face, 0.05, False, 0.5, False)
    loc = TopLoc_Location()
    tri = BRep_Tool.Triangulation_s(TopoDS.Face(face), loc)
    if tri is None or tri.NbTriangles() == 0:
        return None
    best, area = None, -1.0
    for k in range(1, min(tri.NbTriangles(), 64) + 1):  # a few triangles: pick the largest
        a, b, c = tri.Triangle(k).Get()
        p = [tri.Node(i).Transformed(loc.Transformation()) for i in (a, b, c)]
        u = (p[1].X() - p[0].X(), p[1].Y() - p[0].Y(), p[1].Z() - p[0].Z())
        v = (p[2].X() - p[0].X(), p[2].Y() - p[0].Y(), p[2].Z() - p[0].Z())
        cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        size = sum(x * x for x in cross)
        if size > area:
            best, area = p, size
    assert best is not None
    from OCP.gp import gp_Pnt

    return gp_Pnt(
        sum(q.X() for q in best) / 3, sum(q.Y() for q in best) / 3, sum(q.Z() for q in best) / 3
    )


def outline_faces(body: TopoDS_Shape, plane: Any) -> list[TopoDS_Shape]:
    """``body``'s shadow on ``plane`` seen along its normal, as faces in the plane.

    The edges and silhouettes of the body are projected onto the plane, split
    where they cross, and every region they bound is kept when a line along the
    normal through it meets the body. The kept regions are joined."""
    from OCP.BOPAlgo import BOPAlgo_Builder, BOPAlgo_BuilderFace
    from OCP.BRepIntCurveSurface import BRepIntCurveSurface_Inter
    from OCP.collections import List_TopoDS_Shape as TopTools_ListOfShape
    from OCP.gp import gp_Ax2, gp_Lin
    from OCP.HLRAlgo import HLRAlgo_Projector
    from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
    from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FORWARD, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    from fdcad.core.features.solids import compound
    from fdcad.core.occ import BRepAlgoAPI_Fuse

    algo = HLRBRep_Algo()
    algo.Add(body)
    axes = gp_Ax2(plane.Location(), plane.Direction(), plane.XDirection())
    algo.Projector(HLRAlgo_Projector(axes))
    algo.Update()
    algo.Hide()
    shapes = HLRBRep_HLRToShape(algo)
    parts = [
        shapes.VCompound(),
        shapes.HCompound(),
        shapes.OutLineVCompound(),
        shapes.OutLineHCompound(),
        shapes.Rg1LineVCompound(),
        shapes.Rg1LineHCompound(),
    ]
    edges = []
    for part in parts:
        if part is None or part.IsNull():
            continue
        exp = TopExp_Explorer(part, TopAbs_EDGE)
        while exp.More():
            edges.append(exp.Current())
            exp.Next()
    if not edges:
        return []
    from OCP.BRepLib import BRepLib

    for edge in edges:  # HLR edges carry only plane curves: give them 3D curves
        BRepLib.BuildCurves3d_s(edge)
    # HLR draws in the projector's own frame, on z = 0: put it back in the plane.
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Ax3, gp_Trsf

    back = gp_Trsf()
    back.SetTransformation(gp_Ax3(axes), gp_Ax3())
    flat = BRepBuilderAPI_Transform(compound(edges), back, True).Shape()
    general = BOPAlgo_Builder()
    exp = TopExp_Explorer(flat, TopAbs_EDGE)
    while exp.More():  # each edge on its own, so crossings split them
        general.AddArgument(exp.Current())
        exp.Next()
    general.Perform()
    split = general.Shape()
    size = _extent(body)
    base = _big_face(plane, size)
    builder = BOPAlgo_BuilderFace()
    builder.SetFace(TopoDS.Face(base))
    pieces = TopTools_ListOfShape()
    exp = TopExp_Explorer(split, TopAbs_EDGE)
    while exp.More():
        edge = exp.Current()
        pieces.Append(edge.Oriented(TopAbs_FORWARD))
        pieces.Append(edge.Oriented(TopAbs_REVERSED))
        exp.Next()
    builder.SetShapes(pieces)
    builder.Perform()
    kept = []
    direction = plane.Direction()
    for region in builder.Areas():
        point = _inside_point(region)
        if point is None:
            continue
        hit = BRepIntCurveSurface_Inter()
        hit.Init(body, gp_Lin(point, direction), 1e-7)
        if hit.More():
            kept.append(region)
    if not kept:
        return []
    joined = kept[0]
    if len(kept) > 1:
        args, tools = TopTools_ListOfShape(), TopTools_ListOfShape()
        args.Append(kept[0])
        for face in kept[1:]:
            tools.Append(face)
        fuse = BRepAlgoAPI_Fuse()
        fuse.SetArguments(args)
        fuse.SetTools(tools)
        fuse.Build()
        joined = fuse.Shape()
    unify = ShapeUpgrade_UnifySameDomain(joined, True, True, True)
    unify.Build()
    return _faces(unify.Shape())


def grown(faces: list[TopoDS_Shape], kerf: float) -> list[TopoDS_Shape]:
    """Each face grown by ``kerf`` (negative shrinks); 0 leaves them."""
    if abs(kerf) < 1e-9:
        return faces
    from fdcad.core.features.profile_offset import offset_face

    out = []
    for face in faces:
        try:
            out.append(offset_face(face, kerf)[0])
        except ValueError:
            raise ExportError(
                "A face could not take the offset. Enter a smaller kerf or tool offset."
            ) from None
    return out


def layered_items(bodies: list[TopoDS_Shape], job: SectionJob) -> list[tuple[str, Any]]:
    """(layer, flat item) pairs for every body that is not ignored."""
    from fdcad.core.io.flat_export import face_edges, flatten

    job.validate()
    plane = plane_of(job.view, job.offset if job.mode == "section" else 0.0)
    out: list[tuple[str, Any]] = []
    for i, body in enumerate(bodies):
        use = job.uses[i] if i < len(job.uses) else "cut"
        if use == "ignore":
            continue
        try:
            faces = (
                section_faces(body, plane) if job.mode == "section" else outline_faces(body, plane)
            )
        except ValueError as exc:
            raise ExportError(f"Body {i + 1}: {exc}. Rebuild the part and try again.") from exc
        for face in grown(faces, job.kerf / job.scale):  # the kerf is in the drawing's mm
            out += [
                (LAYERS[use], item) for item in flatten(face_edges(face), plane, 1.0 / job.scale)
            ]
    if not out:
        raise ExportError(
            "Nothing to draw: the plane misses every body, or every body is ignored. "
            "Enter another offset or pick a body to cut."
        )
    return out


def export_section(
    bodies: list[TopoDS_Shape], job: SectionJob, path: str | os.PathLike[str]
) -> int:
    """Write the drawing as DXF or SVG (by the file extension); returns the item count."""
    from fdcad.core.io.flat_export import to_dxf, to_svg

    target = Path(path)
    kind = target.suffix.lower()
    if kind not in (".dxf", ".svg"):
        raise ExportError("Choose a file name ending in .dxf or .svg.")
    pairs = layered_items(bodies, job)
    items = [item for _layer, item in pairs]
    layers = [layer for layer, _item in pairs]
    text = to_dxf(items, layers=layers) if kind == ".dxf" else to_svg(items, layers=layers)
    tmp = target.with_name(f".fdcad-{target.name}")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return len(items)
