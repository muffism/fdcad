"""Lattice Fill: fill bodies with a gyroid, diamond or honeycomb lattice (TR390, D2004).

Type ``lattice_fill``. Params:

- ``lattice``: ``gyroid`` (default), ``diamond`` or ``honeycomb``.
- ``cell``: length, the size of one lattice cell (the pitch of the hexagons for
  honeycomb).
- ``wall``: length, the wall thickness.
- ``skin``: optional length: a solid outer skin this thick is kept round the
  lattice, so the fill is closed; zero or left out for the bare lattice.

Refs: ``bodies``: optional, a face of each body to fill; without any, every
body is filled.

Gyroid and diamond are sheets found on a grid (``core/lattice_field.py``) and
made into faceted solids, so they are heavy: the grid is capped and a cell too
small for the size is an error. Honeycomb is exact: hexagonal walls along Z.
On a body with curved faces the region is first made cheap to fit to: behind a
skin it is made of its triangles, else its faces are cut into patches (D2624).

Face roles: faces of the part keep their names where they remain; lattice faces
are ``<fid>/lattice#k``.
"""

from __future__ import annotations

import math
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from OCP.BOPAlgo import BOPAlgo_ShellSplitter
from OCP.BRep import BRep_Tool
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.gp import gp_Ax3, gp_Dir, gp_Pln, gp_Pnt, gp_Vec
from OCP.ShapeFix import ShapeFix_Solid
from OCP.StlAPI import StlAPI_Reader
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Shape

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.solids import (
    FUZZY_TOLERANCE,
    compound,
    polygon_face,
    solids,
)
from fdcad.core.naming.names import NamedFace, NamedShape, carry, faces_of, restrict
from fdcad.core.occ import (
    BRepAlgoAPI_Common,
    BRepAlgoAPI_Cut,
    BRepAlgoAPI_Fuse,
    ShapeList,
    ShapeMap,
    shape_list,
)
from fdcad.core.units import Kind

LATTICES = ("gyroid", "diamond", "honeycomb")
#: Most faces a gyroid or diamond sheet may have (D1099). The faces go through a
#: boolean with the body, which grows much faster than the count: 46,000 faces took
#: 14 s, and the 513,000 of a 10 mm gyroid in an 80 by 60 by 40 mm box never ended.
MOST_FACES = 60_000
#: Most crossings of lattice faces with the curved faces of the body (D2605). A
#: lattice face whose box meets the box of a curved face of the body is a surface
#: intersection in the boolean, and its weight is about its cost in milliseconds:
#: 1 for a cylinder, cone, sphere or torus, 2 for a simple freeform face, and one per
#: 20 control points for a large spline (the swept spring's face has 396 and took
#: about 20 ms a crossing). The spring's 10 mm gyroid was 51,600 crossings of that
#: face: its boolean ran for over 15 minutes and took 20 GB. Since D2624 the curved
#: faces are cut into patches first and the crossings are counted against the
#: patches, so only lattice faces near the surface count (the spring's 10 mm gyroid is
#: 63,000 now). The fill is one boolean, built once and on all cores, where it was
#: three built twice each, so the limit is twice the old one: about 15 s of one core.
MOST_CROSSINGS = 20_000
FREEFORM_WEIGHT = 2
POLES_PER_WEIGHT = 20
#: Most hexagons one honeycomb may have.
MOST_HEXAGONS = 4000
#: Patches (D2624): the faces of a curved body are cut by planes across its box this
#: share of a cell apart (two lattice triangles), at most ``MOST_CUTS`` along an axis.
PATCH_SHARE = 0.25
MOST_CUTS = 16


def _value(feature: Feature, name: str) -> float:
    value = feature.params.get(name)
    return value.value if isinstance(value, Param) else 0.0


def _box(shape: TopoDS_Shape) -> tuple[np.ndarray, np.ndarray]:
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    lo, hi = box.CornerMin(), box.CornerMax()
    return np.array([lo.X(), lo.Y(), lo.Z()]), np.array([hi.X(), hi.Y(), hi.Z()])


def _weight(surface: Any) -> int:
    """About the cost in milliseconds of one lattice face crossing ``surface`` (an
    adaptor surface), 0 for a plane (D2605)."""
    from OCP.GeomAbs import (
        GeomAbs_BSplineSurface,
        GeomAbs_Cone,
        GeomAbs_Cylinder,
        GeomAbs_OffsetSurface,
        GeomAbs_Plane,
        GeomAbs_Sphere,
        GeomAbs_Torus,
    )

    kind = surface.GetType()
    if kind == GeomAbs_Plane:
        return 0
    if kind in (GeomAbs_Cylinder, GeomAbs_Cone, GeomAbs_Sphere, GeomAbs_Torus):
        return 1
    if kind == GeomAbs_OffsetSurface:
        return max(FREEFORM_WEIGHT, _weight(surface.BasisSurface()))
    if kind == GeomAbs_BSplineSurface:
        spline = surface.BSpline()
        poles = spline.NbUPoles() * spline.NbVPoles()
        return max(FREEFORM_WEIGHT, int(poles) // POLES_PER_WEIGHT)
    return FREEFORM_WEIGHT


def crossings(vertices: np.ndarray, tri: np.ndarray, region: TopoDS_Shape) -> int:
    """The lattice triangles that meet the box of each curved face of ``region``, each
    weighted by the cost of that face (D2605). Plane faces are left out: the face
    count limit covers them."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepBndLib import BRepBndLib

    corners = vertices[tri]
    low, high = corners.min(axis=1), corners.max(axis=1)
    total = 0
    for face in faces_of(region):  # the body's faces, not the triangles
        weight = _weight(BRepAdaptor_Surface(TopoDS.Face(face)))
        if weight == 0:
            continue
        box = Bnd_Box()
        BRepBndLib.Add_s(face, box)
        a, b = box.CornerMin(), box.CornerMax()
        meets = np.all((low <= [b.X(), b.Y(), b.Z()]) & (high >= [a.X(), a.Y(), a.Z()]), axis=1)
        total += int(np.count_nonzero(meets)) * weight
    return total


#: Larger cells tried for the one a refusal names (D2674).
_FIT_TRIES = 6


def _too_many(
    what: str, count: int, most: int, cell: float, fits_at: Callable[[float], bool] | None = None
) -> ValueError:
    """The refusal of a sheet over a limit, naming a cell that is under every limit.

    Faces per cell are fixed, so the count goes with the cube of the cell size; that
    gives the first cell to try. The grid follows the cell only, so a thicker wall
    does not help and is not named. ``fits_at(cell)`` says whether a cell is under
    the limits; the estimate is made larger until it is (D2674: at 24 mm the box
    of the D1099 test still had 62,244 faces), at most ``_FIT_TRIES`` times."""
    fits = math.ceil(cell * (count / most) ** (1 / 3))
    if fits_at is not None:
        for _ in range(_FIT_TRIES):
            if fits_at(float(fits)):
                break
            fits = max(fits + 1, math.ceil(fits * 1.08))
    return ValueError(
        f"the lattice would have {count:,} {what}, too many to build in good time "
        f"({most:,} at most); a cell of {fits} mm or more fits"
    )


def _over(
    kind: str,
    lo: np.ndarray,
    hi: np.ndarray,
    cell: float,
    wall: float,
    region: TopoDS_Shape | None,
    surface: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray, tuple[str, int, int] | None]:
    """The sheet's mesh and the first limit it is over (what, count, limit), or None."""
    from fdcad.core.lattice_field import sheet_mesh

    vertices, tri = sheet_mesh(kind, lo, hi, cell, wall, surface, 2 * _deviation(cell))
    if len(tri) > MOST_FACES:
        return vertices, tri, ("faces", len(tri), MOST_FACES)
    if region is not None and len(tri):
        crossed = crossings(vertices, tri, region)
        if crossed > MOST_CROSSINGS:
            return vertices, tri, ("crossings with curved faces", crossed, MOST_CROSSINGS)
    return vertices, tri, None


def sheet_solid(
    kind: str,
    lo: np.ndarray,
    hi: np.ndarray,
    cell: float,
    wall: float,
    region: TopoDS_Shape | None = None,
    surface: np.ndarray | None = None,
) -> TopoDS_Shape:
    """The gyroid or diamond sheet over the box as faceted solids. With ``region``,
    the body it will be fitted to, a sheet too costly to fit is refused (D2605).
    With ``surface``, the triangles of the region's faces, the sheet stops a few
    grid steps outside the region (D2624). Raises ValueError."""

    def fits_at(larger: float) -> bool:
        try:
            return _over(kind, lo, hi, larger, wall, region, surface)[2] is None
        except ValueError:
            return False

    vertices, tri, over = _over(kind, lo, hi, cell, wall, region, surface)
    if over is not None:
        raise _too_many(*over, cell, fits_at)
    if len(tri) == 0:
        raise ValueError("the lattice has no walls here")
    made = faceted(vertices, tri)
    if not made:
        raise ValueError("the lattice walls did not close")
    return compound(made)


def faceted(vertices: np.ndarray, tri: np.ndarray) -> list[TopoDS_Shape]:
    """The closed faceted solids of a mesh, one face per triangle; open parts are
    left out."""
    from fdcad.core.io.mesh_import import Mesh, stl_bytes

    mesh = Mesh(vertices.astype(np.float32), tri.astype(np.int32))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "lattice.stl"
        path.write_bytes(stl_bytes(mesh))
        faces = TopoDS_Shape()
        if not StlAPI_Reader().Read(faces, str(path)):
            raise ValueError("the lattice could not be made into faces")
    # The reader already shares each edge between its two triangles, so the faces only
    # need grouping into closed shells: the shell splitter does that in a second where
    # sewing took 29 s for 46,000 faces, with the same solids (D1099). Handing it the
    # faces one by one is a loop in Python, but a light one (0.1 s for 46,000).
    splitter = BOPAlgo_ShellSplitter()
    explorer = TopExp_Explorer(faces, TopAbs_FACE)
    while explorer.More():
        splitter.AddStartElement(explorer.Current())
        explorer.Next()
    splitter.Perform()
    made = []
    for found in splitter.Shells():
        shell = TopoDS.Shell(found)
        if BRep_Tool.IsClosed_s(shell):
            made.append(ShapeFix_Solid().SolidFromShell(shell))
    return made


def honeycomb(lo: np.ndarray, hi: np.ndarray, cell: float, wall: float) -> TopoDS_Shape:
    """Hexagonal walls ``wall`` thick at pitch ``cell`` (across the flats of a cell),
    along Z through the box. Raises ValueError."""
    if wall >= cell / 2:
        raise ValueError("the wall is too thick for the cell")
    pad = cell
    x0, y0, z0 = lo - pad
    x1, y1, z1 = hi + pad
    dx, dy = cell, cell * math.sqrt(3) / 2  # columns across the flats, rows offset
    cols = math.ceil((x1 - x0) / dx) + 1
    rows = math.ceil((y1 - y0) / dy) + 1
    if cols * rows > MOST_HEXAGONS:
        raise ValueError("the honeycomb has too many cells for this size")
    corner = (cell - wall) / math.sqrt(3)  # corner radius of the hole, flats cell - wall
    axes = gp_Ax3(gp_Pnt(0, 0, z0), gp_Dir(0, 0, 1), gp_Dir(1, 0, 0))
    plate = BRepBuilderAPI_MakeFace(gp_Pln(axes), x0, x1, y0, y1).Face()
    holes = []
    for r in range(rows):
        for c in range(cols):
            cx = x0 + c * dx + (dx / 2 if r % 2 else 0.0)
            cy = y0 + r * dy
            pts = [
                (cx + corner * math.cos(math.radians(30 + 60 * k)),
                 cy + corner * math.sin(math.radians(30 + 60 * k)), z0)
                for k in range(6)
            ]  # fmt: skip
            holes.append(polygon_face(pts))
    cut = BRepAlgoAPI_Cut(plate, compound(holes))
    cut.Build()
    if not cut.IsDone():
        raise ValueError("the honeycomb walls could not be made")
    return BRepPrimAPI_MakePrism(cut.Shape(), gp_Vec(0, 0, z1 - z0)).Shape()


def _boolean(
    kind: str, a: TopoDS_Shape, b: TopoDS_Shape, fast: bool = False, apart: bool = False
) -> tuple[TopoDS_Shape, Any]:
    # Made empty and built once: the two shape form builds at once, so setting the
    # fuzzy value after it built the boolean a second time (D2624). ``fast`` runs the
    # face pairs on all cores and tests them with oriented boxes, which leave out
    # about half the pairs of slanted lattice faces with curved patches. ``apart`` says
    # the solids of the tool are pieces of one closed lattice mesh, which cannot share
    # material, so the crossing check of D2623 is skipped (D2658).
    maker = {"common": BRepAlgoAPI_Common, "cut": BRepAlgoAPI_Cut, "fuse": BRepAlgoAPI_Fuse}[kind](
        pieces_apart=apart
    )
    first, second = ShapeList(), ShapeList()
    first.Append(a)
    second.Append(b)
    maker.SetArguments(first)
    maker.SetTools(second)
    maker.SetFuzzyValue(FUZZY_TOLERANCE)
    if fast:
        maker.SetRunParallel(True)
        maker.SetUseOBB(True)
    maker.Build()
    if not maker.IsDone():
        raise ValueError(f"the lattice {kind} failed")
    return maker.Shape(), maker


def _less(region: TopoDS_Shape, lattice: TopoDS_Shape) -> TopoDS_Shape:
    """``region`` less ``lattice`` (D2624), made as the kernel's reversed cut (the tool
    less the object) with the lattice as the object. As a tool the lattice would be
    checked for pieces that cross (D2623), a boolean of each two pieces whose boxes
    meet: 6 s for the 25 pieces of the twisted sweep at 10 mm, more than the cut. Its
    solids are the closed shells of one mesh, so they cannot cross. Raises
    ValueError."""
    from OCP.BOPAlgo import BOPAlgo_Operation

    from fdcad.core.occ import BRepAlgoAPI_BooleanOperation

    op = BRepAlgoAPI_BooleanOperation()
    op.SetNonDestructive(True)
    first, second = ShapeList(), ShapeList()
    first.Append(lattice)
    second.Append(region)
    op.SetArguments(first)
    op.SetTools(second)
    op.SetOperation(BOPAlgo_Operation.BOPAlgo_CUT21)
    op.SetFuzzyValue(FUZZY_TOLERANCE)
    op.SetRunParallel(True)
    op.SetUseOBB(True)
    op.Build()
    if not op.IsDone():
        raise ValueError("the lattice cut failed")
    return op.Shape()


def _inner(shape: TopoDS_Shape, skin: float) -> TopoDS_Shape:
    """The body shrunk by ``skin`` on every face."""
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeOffsetShape

    maker = BRepOffsetAPI_MakeOffsetShape()
    maker.PerformByJoin(shape, -skin, 1e-6)
    if not maker.IsDone() or not solids(maker.Shape()):
        raise ValueError("the skin could not be made")
    return compound(solids(maker.Shape()))


def _deviation(cell: float) -> float:
    """The chord deviation of the region's triangles (D2624): a fortieth of a cell."""
    return cell / 40.0


def _curved(shape: TopoDS_Shape) -> bool:
    from OCP.BRepAdaptor import BRepAdaptor_Surface

    return any(_weight(BRepAdaptor_Surface(TopoDS.Face(f))) > 0 for f in faces_of(shape))


def _shells(shape: TopoDS_Shape) -> list[TopoDS_Shape]:
    from OCP.TopAbs import TopAbs_SHELL

    found, explorer = [], TopExp_Explorer(shape, TopAbs_SHELL)
    while explorer.More():
        found.append(explorer.Current())
        explorer.Next()
    return found


def _planes(lo: np.ndarray, hi: np.ndarray, cell: float) -> ShapeList:
    """Planes across the box about ``PATCH_SHARE`` of a cell apart, at most
    ``MOST_CUTS`` along each axis."""
    centre, reach = (lo + hi) / 2, float(np.linalg.norm(hi - lo)) / 2 + 1.0
    tools = ShapeList()
    for axis in range(3):
        cuts = min(MOST_CUTS, math.ceil(float(hi[axis] - lo[axis]) / (cell * PATCH_SHARE)))
        for k in range(1, cuts):
            origin, normal = centre.copy(), np.zeros(3)
            origin[axis] = lo[axis] + (hi[axis] - lo[axis]) * k / cuts
            normal[axis] = 1.0
            plane = gp_Pln(gp_Pnt(*origin.tolist()), gp_Dir(*normal.tolist()))
            tools.Append(BRepBuilderAPI_MakeFace(plane, -reach, reach, -reach, reach).Face())
    return tools


def _patches(shape: TopoDS_Shape, cell: float) -> tuple[TopoDS_Shape, Any]:
    """``shape`` with its faces cut by planes across its box (D2624), and the history
    of the cut. A lattice face is only tested against a curved face whose box meets
    its own, and one large curved face has a box round the whole lattice: its patches
    have small boxes, so each lattice face meets only the patches near it. Gives
    ``shape`` and no history when the cut fails or changes the volume."""
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Solid

    from fdcad.core.features.solids import volume_of
    from fdcad.core.occ import BRepAlgoAPI_Splitter

    tools = _planes(*_box(shape), cell)
    if tools.Size() == 0:
        return shape, None
    pieces = solids(shape)
    shells = ShapeList()
    for piece in pieces:
        for shell in _shells(piece):
            shells.Append(shell)
    splitter = BRepAlgoAPI_Splitter()
    splitter.SetArguments(shells)
    splitter.SetTools(tools)
    splitter.SetRunParallel(True)
    splitter.Build()
    if not splitter.IsDone():
        return shape, None
    owners = []  # the faces each solid of ``shape`` now has
    for piece in pieces:
        owner = ShapeMap()
        for face in faces_of(piece):
            for image in shape_list(splitter.Modified(face)) or [face]:
                owner.Add(image)
        owners.append(owner)
    builder, made = BRep_Builder(), []
    for _piece in pieces:
        solid = TopoDS_Solid()
        builder.MakeSolid(solid)
        made.append(solid)
    for shell in _shells(splitter.Shape()):
        first = faces_of(shell)[0]
        index = next((i for i, owner in enumerate(owners) if owner.Contains(first)), None)
        if index is None:
            return shape, None
        builder.Add(made[index], shell)
    out = compound(made)
    before = volume_of(shape)
    if abs(volume_of(out) - before) > 1e-3 * abs(before):  # integration noise is 1e-5
        return shape, None
    return out, splitter.History()


class _Chain:
    """The histories of several steps in turn, as one history for ``carry``."""

    def __init__(self, *steps: Any) -> None:
        self._steps = [step for step in steps if step is not None]

    def images(self, shape: TopoDS_Shape) -> list[TopoDS_Shape]:
        """What ``shape`` became after all the steps (itself when unchanged)."""
        current = [shape]
        for step in self._steps:
            found = ShapeMap()
            for item in current:
                if step.IsRemoved(item):
                    continue
                for image in shape_list(step.Modified(item)) or [item]:
                    found.Add(image)
            current = [found.FindKey(i) for i in range(1, found.Extent() + 1)]
        return current

    def Modified(self, shape: TopoDS_Shape, /) -> ShapeList:  # noqa: N802 (kernel name)
        """What ``shape`` became; empty when it is unchanged."""
        found, out = self.images(shape), ShapeList()
        if len(found) == 1 and found[0].IsSame(shape):
            return out
        for item in found:
            out.Append(item)
        return out

    def IsRemoved(self, shape: TopoDS_Shape, /) -> bool:  # noqa: N802 (kernel name)
        """True when nothing is left of ``shape``."""
        return not self.images(shape)


def _hollow(body: TopoDS_Shape, voids: TopoDS_Shape) -> TopoDS_Shape:
    """``body`` less ``voids``, which lie well inside it: each closed shell of the
    voids is added to the solid round it as a cavity, so no boolean meets the body's
    faces (D2624). Falls back to the boolean when a void is not one plain shell or
    no solid of the body holds it."""
    from OCP.BRep import BRep_Builder, BRep_Tool
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.TopoDS import TopoDS_Solid

    from fdcad.core.occ import point_inside

    builder, pieces, made = BRep_Builder(), solids(body), []
    for piece in pieces:
        solid = TopoDS_Solid()
        builder.MakeSolid(solid)
        for shell in _shells(piece):
            builder.Add(solid, shell)
        made.append(solid)
    for void in solids(voids):
        shells = _shells(void)
        index: int | None = 0 if len(made) == 1 else None
        if index is None:
            corner = TopExp_Explorer(void, TopAbs_VERTEX)
            p = BRep_Tool.Pnt_s(TopoDS.Vertex(corner.Current()))
            point = (p.X(), p.Y(), p.Z())
            index = next(
                (i for i, piece in enumerate(pieces) if point_inside(piece, point, 1e-6)), None
            )
        if len(shells) != 1 or index is None:
            return _boolean("cut", body, voids, fast=True, apart=True)[0]
        builder.Add(made[index], shells[0].Reversed())
    return compound(made)


@dataclass
class Prepared:
    """A region ready for the lattice (D2624): ``shape`` is the region to fit to,
    ``split`` the history from the region to it (None when there is nothing to carry)
    and ``surface`` the triangles of its faces, an (n, 3, 3) array."""

    shape: TopoDS_Shape
    split: Any
    surface: np.ndarray


def prepare(region: TopoDS_Shape, cell: float, skin: float) -> Prepared:
    """``region`` made cheap to fit a lattice to, for a region with curved faces.

    Behind a skin the region is inside the part, so it is made of the triangles of
    its faces: a lattice face then meets flat faces only, which cost little. The
    triangles are within a twentieth of the skin (or cell) of the faces, so the skin
    stays as thick to that much. Without a skin the region is the body itself, so its
    faces stay as they are and are cut into patches."""
    from fdcad.core.features.solids import volume_of
    from fdcad.core.io.export import MeshSettings, indexed_mesh, triangles

    if skin > 1e-9:
        tris = triangles(region, MeshSettings(deviation=min(skin, cell) / 20))
        vertices, tri = indexed_mesh(tris)
        c = vertices[tri]
        inside = abs(float(np.einsum("ij,ij->i", c[:, 0], np.cross(c[:, 1], c[:, 2])).sum())) / 6
        before = volume_of(region)
        # The kernel's triangles of some offset faces miss much of the region (a quarter
        # of the swept spring's thin core): those regions keep their faces.
        if len(tri) and abs(inside - before) < 0.02 * abs(before):
            made = faceted(vertices, tri)
            if made:
                return Prepared(compound(made), None, tris.astype(np.float64))
    patched, split = _patches(region, cell)
    tris = triangles(patched, MeshSettings(deviation=_deviation(cell)))
    return Prepared(patched, split, tris.astype(np.float64))


def lattice_for(
    kind: str, regions: list[TopoDS_Shape], cell: float, wall: float, ready: list[Prepared]
) -> TopoDS_Shape:
    """One lattice over the box of all ``regions`` (D2622). With ``ready`` (curved
    regions, D2624) the sheet stops a few grid steps outside them and its cost is
    counted against them. Raises ValueError."""
    region = regions[0] if len(regions) == 1 else compound(regions)
    lo, hi = _box(region)
    if kind == "honeycomb":
        return honeycomb(lo, hi, cell, wall)
    if not ready:
        return sheet_solid(kind, lo - 0.5, hi + 0.5, cell, wall, region)
    fitted = compound([r.shape for r in ready])
    surface = np.concatenate([r.surface for r in ready])
    return sheet_solid(kind, lo - 0.5, hi + 0.5, cell, wall, fitted, surface)


def fit(
    lattice: TopoDS_Shape,
    body: TopoDS_Shape,
    names: list[NamedFace],
    region: TopoDS_Shape,
    skin: float,
    ready: Prepared | None = None,
) -> tuple[TopoDS_Shape, list[NamedFace]]:
    """``lattice`` fitted to ``region`` (``body``, or ``body`` less its skin) with the
    skin round it, and ``names`` (of the body's faces) carried. ``ready`` is the region
    prepared for a curved body (D2624). Raises ValueError."""
    if ready is None:  # planes only: as D2004 and D1099 made it
        shape, maker = _boolean("common", lattice, region)
        if skin > 1e-9:
            shell, shell_maker = _boolean("cut", body, region)
            shape, maker = _boolean("fuse", shell, shape, apart=True)  # D2658
            names = carry(names, shell_maker.History())
        return shape, carry(names, maker.History())
    if skin > 1e-9:
        # The body less the parts of the region outside the lattice: those lie inside
        # the skin, so they become cavities and the body's own faces are not touched.
        return _hollow(body, _less(ready.shape, lattice)), list(names)
    from fdcad.core.unify import unify_faces

    shape, common = _boolean("common", lattice, ready.shape, fast=True)
    # Merge the patches back into the faces they came from: only across the edges the
    # cut into patches made. Every other edge stays, so two faces of the body are never
    # merged into one, nor two lattice faces that happen to lie in one plane.
    from OCP.collections import Map_TopoDS_Shape_TopTools_ShapeMapHasher

    own = ShapeMap()  # the region's own edges, as cut into patches
    edges = ShapeMap()
    TopExp.MapShapes_s(region, TopAbs_EDGE, edges)
    for i in range(1, edges.Extent() + 1):
        for image in _Chain(ready.split).images(edges.FindKey(i)):
            own.Add(image)
    keep = Map_TopoDS_Shape_TopTools_ShapeMapHasher()
    TopExp.MapShapes_s(shape, keep)
    after = _Chain(common.History())
    edges = ShapeMap()
    TopExp.MapShapes_s(ready.shape, TopAbs_EDGE, edges)
    for i in range(1, edges.Extent() + 1):  # the edges of the patches, not the lattice
        if not own.Contains(edges.FindKey(i)):
            for image in after.images(edges.FindKey(i)):
                keep.Remove(image)
    shape, merge = unify_faces(shape, keep_map=keep)
    return shape, carry(names, _Chain(ready.split, common.History(), merge))


@register
class LatticeFill(FeatureType):
    """Fills bodies with a gyroid, diamond or honeycomb lattice."""

    type_name = "lattice_fill"
    makes_solid = True
    params = (
        ParamSpec("lattice", choices=LATTICES, default="gyroid"),
        ParamSpec("cell", kind=Kind.LENGTH),
        ParamSpec("wall", kind=Kind.LENGTH),
        ParamSpec("skin", kind=Kind.LENGTH, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Replace each body by its lattice (and skin)."""
        owner, fid = feature.name, feature.id
        whole = ctx.body
        if whole is None:
            raise FeatureError(f"{owner}: the part is empty. Add a body to fill first.")
        cell, wall, skin = _value(feature, "cell"), _value(feature, "wall"), _value(feature, "skin")
        if cell <= 0 or wall <= 0:
            raise FeatureError(f"{owner}: enter a cell size and a wall greater than zero.")
        if wall >= cell / 2:
            raise FeatureError(
                f"{owner}: the wall is too thick for the cell. Enter a thinner wall."
            )
        if skin < 0:
            raise FeatureError(f"{owner}: the skin cannot be negative. Enter zero or more.")
        kind = str(feature.params.get("lattice", "gyroid"))
        issues: list[Issue] = []
        body = whole
        indices = list(range(len(solids(whole.shape))))
        if feature.refs.get("bodies"):
            from fdcad.core.features.bodies import body_indices, sub_body

            indices, issues = body_indices(ctx, feature.refs["bodies"], owner)
            body = sub_body(whole, indices, fid)
        # Each body is filled on its own (D2622). Filled together, the skin of two
        # touching bodies could not be made, and the fuse of skin and lattice would join
        # them (D1055). One lattice is made over all of them, so the cells line up.
        from fdcad.core.features.bodies import names_on

        try:
            own = solids(body.shape)
            if len(own) < 2:
                own = [body.shape]  # one body is filled as before
            regions = [_inner(b, skin) if skin > 1e-9 else b for b in own]
            curved = any(_curved(r) for r in regions)  # D2624
            ready = [prepare(r, cell, skin) for r in regions] if curved else []
            lattice = lattice_for(kind, regions, cell, wall, ready)
            filled: list[TopoDS_Shape] = []
            names = []
            for k, (one, inside) in enumerate(zip(own, regions, strict=True)):
                part = names_on(body, one) if len(own) > 1 else body.faces
                shape, part = fit(lattice, one, part, inside, skin, ready[k] if ready else None)
                names.extend(part)
                filled.extend(solids(shape))
            shape = compound(filled)
        except ValueError as exc:
            hint = (
                "Use a larger cell or fill a smaller body."
                if "too" in str(exc)
                else "Change the cell, the wall or the skin."
            )
            raise FeatureError(f"{owner} failed: {exc}. {hint}") from exc
        pieces = solids(shape)
        if not pieces:
            raise FeatureError(
                f"{owner} failed: no lattice is left inside the body. Use a smaller cell."
            )
        shape = compound(pieces)
        named = ShapeMap()
        for _n, f in names:
            named.Add(f)
        k = 0
        for face in faces_of(shape):
            if not named.Contains(face):
                k += 1
                names.append((f"{fid}/lattice#{k}", face))
        result = NamedShape(shape, restrict(names, shape, fid))
        if len(indices) < len(solids(whole.shape)):
            from fdcad.core.features.bodies import join, rest_of

            joined = join([rest_of(whole, indices, fid), result], fid)
            assert joined is not None
            result = joined
        return FeatureResult(body=result, issues=issues)
