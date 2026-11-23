"""Pick the faces, edges or vertices inside, outside or touching a box, cylinder or
sphere (TUTORIAL_REVIEW_SPEC_2 TR329, D2208).

Each item is sampled (a vertex is its point; an edge 9 points along it; a face the
points of its edges and its centre) and the samples are tested against the volume
with numpy in one pass. Inside: every sample is in the volume. Outside: none is.
Touching: some are and some are not. Kernel work: run ``pick_in_volume`` off the
UI thread. No Qt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

SHAPES = ("box", "cylinder", "sphere")
MODES = ("inside", "outside", "touching")
KINDS = ("face", "edge", "vertex")
EDGE_SAMPLES = 9

Vec3 = tuple[float, float, float]


class PickVolumeError(ValueError):
    """The volume cannot be used; the message says what to do."""


@dataclass(frozen=True)
class PickVolume:
    """A box (``size``: x, y and z lengths), a cylinder (``radius`` and ``size[2]``, its
    length, along ``axis``) or a sphere (``radius``), centred on ``centre``."""

    shape: str
    centre: Vec3
    size: Vec3 = (10.0, 10.0, 10.0)
    radius: float = 5.0
    axis: Vec3 = (0.0, 0.0, 1.0)

    def check(self) -> None:
        """Raise PickVolumeError when a size is zero or less or the shape is unknown."""
        if self.shape not in SHAPES:
            raise PickVolumeError(
                f"Unknown pick volume '{self.shape}'. Pick box, cylinder or sphere."
            )
        if self.shape == "box" and min(self.size) <= 0:
            raise PickVolumeError("Every box size must be above zero. Enter larger sizes.")
        if self.shape != "box" and self.radius <= 0:
            raise PickVolumeError("The radius must be above zero. Enter a larger radius.")
        if self.shape == "cylinder" and self.size[2] <= 0:
            raise PickVolumeError("The cylinder length must be above zero. Enter a larger length.")
        if math.hypot(*self.axis) < 1e-12:
            raise PickVolumeError("The cylinder axis has no direction. Pick X, Y or Z.")

    def contains(self, points: np.ndarray) -> np.ndarray:
        """For each row of ``points`` (n by 3, mm), True when it is in the volume."""
        d = points - np.asarray(self.centre, dtype=float)
        tol = 1e-7
        if self.shape == "sphere":
            return np.asarray(np.einsum("ij,ij->i", d, d) <= (self.radius + tol) ** 2)
        if self.shape == "box":
            half = np.asarray(self.size, dtype=float) / 2 + tol
            return np.asarray(np.all(np.abs(d) <= half, axis=1))
        a = np.asarray(self.axis, dtype=float)
        a = a / np.linalg.norm(a)
        along = d @ a
        across = d - np.outer(along, a)
        near = np.abs(along) <= self.size[2] / 2 + tol
        return np.asarray(
            near & (np.einsum("ij,ij->i", across, across) <= (self.radius + tol) ** 2)
        )


def _edge_points(edge: Any) -> list[Vec3]:
    from OCP.BRepAdaptor import BRepAdaptor_Curve

    curve = BRepAdaptor_Curve(edge)
    a, b = curve.FirstParameter(), curve.LastParameter()
    out = []
    for i in range(EDGE_SAMPLES):
        p = curve.Value(a + (b - a) * i / (EDGE_SAMPLES - 1))
        out.append((p.X(), p.Y(), p.Z()))
    return out


def _samples(item: Any, kind: str) -> list[Vec3]:
    from OCP.BRep import BRep_Tool
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    if kind == "vertex":
        p = BRep_Tool.Pnt_s(TopoDS.Vertex(item))
        return [(p.X(), p.Y(), p.Z())]
    if kind == "edge":
        return _edge_points(TopoDS.Edge(item))
    out: list[Vec3] = []
    ex = TopExp_Explorer(item, TopAbs_EDGE)
    while ex.More():
        out += _edge_points(TopoDS.Edge(ex.Current()))
        ex.Next()
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(item, props)
    c = props.CentreOfMass()
    out.append((c.X(), c.Y(), c.Z()))
    return out


def pick_in_volume(shape: Any, volume: PickVolume, mode: str, kind: str) -> list[Any]:
    """The faces, edges or vertices (``kind``) of ``shape`` that are ``mode`` (inside,
    outside or touching) the volume, each once. Kernel work."""
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
    from OCP.TopExp import TopExp

    from fdcad.core.occ import ShapeMap

    volume.check()
    if mode not in MODES or kind not in KINDS:
        raise PickVolumeError("Pick inside, outside or touching, and faces, edges or vertices.")
    found = ShapeMap()
    TopExp.MapShapes_s(
        shape, {"face": TopAbs_FACE, "edge": TopAbs_EDGE, "vertex": TopAbs_VERTEX}[kind], found
    )
    items = [found.FindKey(i) for i in range(1, found.Extent() + 1)]
    if not items:
        return []
    counts: list[int] = []
    points: list[Vec3] = []
    for item in items:
        pts = _samples(item, kind)
        counts.append(len(pts))
        points += pts
    inside = volume.contains(np.asarray(points, dtype=float))
    starts = np.concatenate([[0], np.cumsum(counts)[:-1]])
    hits = np.add.reduceat(inside.astype(int), starts)
    total = np.asarray(counts)
    if mode == "inside":
        keep = hits == total
    elif mode == "outside":
        keep = hits == 0
    else:
        keep = (hits > 0) & (hits < total)
    return [item for item, k in zip(items, keep, strict=True) if k]
