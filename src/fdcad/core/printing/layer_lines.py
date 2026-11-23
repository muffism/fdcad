"""Layer lines for the layer preview (TR315, D993).

The part is cut across the build direction at every layer height of the printer
profile, from its lowest point up, and the cut lines are drawn on it, to judge
small details against the layers they will print in. A tall part with very many
layers draws every n-th layer only, and says so. Kernel work: run off the UI
thread. No Qt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.features.solids import extent_along
from fdcad.core.occ import BRepAlgoAPI_Section, ShapeList

#: The most layers drawn; above it every n-th layer is drawn.
MAX_LINES = 400

Vec3 = tuple[float, float, float]


@dataclass
class LayerLines:
    """The cut edges, how many layers the part has and every how many were drawn, and
    why no lines could be worked out (``problem``, a message to show, D2635)."""

    edges: list[Any] = field(default_factory=list)
    layers: int = 0
    step: int = 1
    problem: str = ""


def layer_lines(shape: TopoDS_Shape, up: Vec3, layer_height: float) -> LayerLines:
    """Cut ``shape`` at every ``layer_height`` along ``up`` (a unit vector)."""
    out = LayerLines()
    if layer_height <= 0:
        return out
    extent = extent_along(shape, up)
    if extent is None:
        return out
    low, high = extent
    layers = int((high - low) / layer_height)
    if layers <= 0:
        return out
    out.layers = layers
    out.step = max(1, -(-layers // MAX_LINES))  # ceiling division
    direction = gp_Dir(*up)
    planes = []
    for k in range(out.step, layers + 1, out.step):
        level = low + k * layer_height
        if level >= high - 1e-9:
            break
        planes.append(gp_Pln(gp_Pnt(up[0] * level, up[1] * level, up[2] * level), direction))
    if not planes:
        return out
    from fdcad.core.features.direct import slow_for_kernel

    if slow_for_kernel(shape):
        # On spline faces even the one kernel call took 10 to 22 s, holding the
        # window (idea 68). The display mesh is cut instead (D2615).
        levels = np.array([low + k * layer_height for k in range(out.step, layers + 1, out.step)])
        try:
            out.edges = mesh_lines(shape, up, levels[levels < high - 1e-9])
        except ValueError as exc:  # the part could not be meshed: say so (D2635)
            reason = str(exc)
            out.problem = f"Layer Preview failed: {reason[:1].lower()}{reason[1:]}"
        return out
    # One kernel call for every layer (D2603): the kernel prepares the part's faces
    # once. A threaded bolt took 40 s one layer at a time and takes 17 s so.
    found = _cut(shape, [_disc(plane, _reach(shape)) for plane in planes])
    if found is None:  # the one call failed: cut each layer, keep those that work
        found = []
        for plane in planes:
            found += _cut(shape, [plane]) or []
    out.edges = found
    return out


def _reach(shape: TopoDS_Shape) -> float:
    """A half size that takes a square round any layer's centre past the whole part."""
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    low, high = box.CornerMin(), box.CornerMax()
    far = max(abs(v) for p in (low, high) for v in (p.X(), p.Y(), p.Z()))
    return 2.0 * float(far) + 10.0


def _disc(plane: gp_Pln, half: float) -> Any:
    """A square face of ``plane`` round its centre, ``half`` from the centre to a side."""
    return BRepBuilderAPI_MakeFace(plane, -half, half, -half, half).Face()


def _cut(shape: TopoDS_Shape, tools: list[Any]) -> list[Any] | None:
    """The edges where ``shape`` meets the planes or plane faces in ``tools``, or None."""
    if len(tools) == 1 and isinstance(tools[0], gp_Pln):
        section = BRepAlgoAPI_Section(shape, tools[0], False)
    else:
        args, given = ShapeList(), ShapeList()
        args.Append(shape)
        for tool in tools:
            given.Append(tool)
        section = BRepAlgoAPI_Section()
        section.SetArguments(args)
        section.SetTools(given)
    section.Approximation(False)
    section.Build()
    if not section.IsDone():
        return None
    edges = []
    explorer = TopExp_Explorer(section.Shape(), TopAbs_EDGE)
    while explorer.More():
        edges.append(explorer.Current())
        explorer.Next()
    return edges


def mesh_segments(corners: np.ndarray, up: Vec3, levels: np.ndarray) -> np.ndarray:
    """Where the triangles ``corners`` (n, 3, 3) cross each height in ``levels`` along
    ``up``: one segment (m, 2, 3) per triangle and level it crosses, all in numpy."""
    if len(corners) == 0 or len(levels) == 0:
        return np.zeros((0, 2, 3))
    levels = np.sort(np.asarray(levels, dtype=np.float64)) + 1e-9  # off the mesh's corners
    heights = corners @ np.asarray(up, dtype=np.float64)  # (n, 3)
    first = np.searchsorted(levels, heights.min(axis=1), side="right")
    last = np.searchsorted(levels, heights.max(axis=1), side="left")
    counts = np.maximum(last - first, 0)
    triangle = np.repeat(np.arange(len(corners)), counts)
    within = np.arange(int(counts.sum())) - np.repeat(np.cumsum(counts) - counts, counts)
    level = levels[np.repeat(first, counts) + within]
    points, h = corners[triangle], heights[triangle]
    crossed, found = [], []
    for a, b in ((0, 1), (1, 2), (2, 0)):
        ha, hb = h[:, a], h[:, b]
        cross = (ha - level) * (hb - level) < 0
        t = np.where(cross, (level - ha) / np.where(hb != ha, hb - ha, 1.0), 0.0)
        crossed.append(cross)
        found.append(points[:, a] + (points[:, b] - points[:, a]) * t[:, None])
    mask = np.stack(crossed, axis=1)
    where = np.stack(found, axis=1)
    two = mask.sum(axis=1) == 2
    mask, where = mask[two], where[two]
    pick = np.argsort(~mask, axis=1, kind="stable")[:, :2]
    return np.take_along_axis(where, pick[:, :, None], axis=1)


def mesh_lines(shape: TopoDS_Shape, up: Vec3, levels: np.ndarray) -> list[Any]:
    """The layer lines of ``shape`` cut from its mesh, as one compound of edges (D2615).

    The lines lie on the mesh, so they follow the shaded part as it is drawn. They are
    one shape, so the view shows them as one item, not one per edge. Raises ValueError,
    with a message to show, when the part cannot be meshed (D2635).
    """
    from OCP.BRep import BRep_Builder
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.TopoDS import TopoDS_Compound

    from fdcad.core.printing.overhang import triangles_by_face

    _faces, corners, _owner = triangles_by_face(shape)
    segments = mesh_segments(corners, up, levels)
    segments = segments[np.linalg.norm(segments[:, 1] - segments[:, 0], axis=1) > 1e-6]
    if len(segments) == 0:
        return []
    builder, compound = BRep_Builder(), TopoDS_Compound()
    builder.MakeCompound(compound)
    # One kernel edge per segment: OCP has no call that takes a whole point array, and
    # this is about 0.5 s for 28,000 segments (the lofted handle).
    for start, end in segments.tolist():
        builder.Add(compound, BRepBuilderAPI_MakeEdge(gp_Pnt(*start), gp_Pnt(*end)).Edge())
    return [compound]
