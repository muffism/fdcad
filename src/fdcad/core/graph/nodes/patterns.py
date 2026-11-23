"""Pattern nodes: attractor, 2D Voronoi cells inside a boundary and strut lattices
(cubic and octet) inside a body (PLAN Phase 7).

Distances and cell clipping run on numpy arrays; the kernel is called once per
cell or strut to make shapes and once for each boolean (CLAUDE.md 5A).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from OCP.BRepTools import BRepTools
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

from fdcad.core.graph import geometry as geo
from fdcad.core.graph.nodes.base import (
    NodeContext,
    NodeError,
    NodeType,
    Port,
    Setting,
    number_of,
    register,
    vec_of,
)
from fdcad.core.graph.nodes.lists import as_list
from fdcad.core.graph.nodes.solids import ALLOW_MANY, guard
from fdcad.core.graph.types import Plane, PortType

PATTERNS = "Pattern"
P, LEN = PortType.POINT, PortType.LENGTH
CURVE_SAMPLES = 200


def attractor_points(value: Any) -> np.ndarray:
    """Attractor points and curves as one N by 3 array (curves are sampled)."""
    from OCP.TopoDS import TopoDS_Shape

    rows: list[np.ndarray] = []
    for item in as_list(value):
        if isinstance(item, TopoDS_Shape):
            rows.append(geo.sample(geo.wire_of(item, "Attractor"), CURVE_SAMPLES))
        else:
            rows.append(np.array([vec_of(item, "Attractors")], dtype=float))
    if not rows:
        raise NodeError("Connect at least one attractor point or curve.")
    return np.vstack(rows)


@register
class Attractor(NodeType):
    """For each point, a value from Near to Far by its distance to the nearest
    attractor point or curve, reaching Far at the Radius. Points are also pushed
    away from (positive Shift) or pulled towards (negative) the attractors, most
    strongly close to them, to change their spacing."""

    type_name = "attractor"
    title = "Attractor"
    category = PATTERNS
    words = "distance field falloff influence scale spacing gradient"
    inputs = (
        Port("points", P, "Points", whole_list=True),
        Port("attractors", P, "Attractors", whole_list=True),
        Port("radius", LEN, "Radius", 50.0),
        Port("near", PortType.NUMBER, "Near", 0.2),
        Port("far", PortType.NUMBER, "Far", 1.0),
        Port("shift", LEN, "Shift", 0.0),
    )
    outputs = (
        Port("values", PortType.NUMBER, "Values"),
        Port("points", P, "Points"),
        Port("distances", LEN, "Distances"),
    )

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        pts = np.array(
            [vec_of(p, "Points") for p in as_list(args.get("points"))], dtype=float
        ).reshape(-1, 3)
        targets = attractor_points(args.get("attractors"))
        radius = number_of(args.get("radius"), "Radius")
        if radius <= 0:
            raise NodeError("The radius must be more than 0. Enter a larger radius.")
        near, far = number_of(args.get("near"), "Near"), number_of(args.get("far"), "Far")
        shift = number_of(args.get("shift"), "Shift")
        if len(pts) == 0:
            return {"values": [], "points": [], "distances": []}
        diff = pts[:, None, :] - targets[None, :, :]
        dist2 = np.einsum("ijk,ijk->ij", diff, diff)
        nearest = np.argmin(dist2, axis=1)
        d = np.sqrt(dist2[np.arange(len(pts)), nearest])
        t = np.clip(d / radius, 0.0, 1.0)
        values = near + (far - near) * t
        away = pts - targets[nearest]
        norm = np.linalg.norm(away, axis=1, keepdims=True)
        direction = np.divide(away, norm, out=np.zeros_like(away), where=norm > 1e-12)
        moved = pts + direction * (shift * (1.0 - t))[:, None]
        return {
            "values": [float(v) for v in values],
            "points": [tuple(float(c) for c in p) for p in moved],
            "distances": [float(v) for v in d],
        }


def _clip(poly: np.ndarray, normal: np.ndarray, offset: float) -> np.ndarray:
    """Keep the part of a convex polygon where ``p . normal <= offset``."""
    side = poly @ normal - offset
    keep = side <= 1e-12
    if keep.all():
        return poly
    if not keep.any():
        return poly[:0]
    out: list[np.ndarray] = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        sa, sb = side[i], side[(i + 1) % n]
        if sa <= 1e-12:
            out.append(a)
        if (sa <= 1e-12) != (sb <= 1e-12):
            out.append(a + (b - a) * (sa / (sa - sb)))
    return np.array(out)


def voronoi_cells(
    seeds: np.ndarray, lo: np.ndarray, hi: np.ndarray, gap: float
) -> list[np.ndarray]:
    """Convex Voronoi cells of 2D ``seeds`` inside the box ``lo`` to ``hi``, each
    shrunk so neighbouring cells are ``gap`` apart."""
    box = np.array([[lo[0], lo[1]], [hi[0], lo[1]], [hi[0], hi[1]], [lo[0], hi[1]]])
    cells = []
    for i, s in enumerate(seeds):
        d = np.linalg.norm(seeds - s, axis=1)
        order = np.argsort(d)
        poly = box
        for j in order:
            if j == i or d[j] < 1e-9:
                continue
            reach = float(np.max(np.linalg.norm(poly - s, axis=1))) if len(poly) else 0.0
            if d[j] / 2.0 - gap / 2.0 > reach:
                break
            normal = (seeds[j] - s) / d[j]
            mid = (seeds[j] + s) / 2.0
            poly = _clip(poly, normal, float(mid @ normal) - gap / 2.0)
            if len(poly) < 3:
                break
        cells.append(poly)
    return cells


@register
class Voronoi(NodeType):
    """2D Voronoi cells of points inside a closed flat boundary: each cell holds the
    area nearer to its point than to any other. Gap leaves a web between cells."""

    type_name = "voronoi"
    title = "Voronoi Cells"
    category = PATTERNS
    words = "cells tessellation organic honeycomb panel"
    inputs = (
        Port("boundary", PortType.CURVE, "Boundary"),
        Port("points", P, "Points", whole_list=True),
        Port("gap", LEN, "Gap", 0.0),
    )
    outputs = (Port("cells", PortType.CURVE, "Cells"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        wire = geo.wire_of(args.get("boundary"), "Boundary")
        if not geo.is_closed(wire):
            raise NodeError("The boundary is open. Connect a closed curve.")
        gap = number_of(args.get("gap"), "Gap")
        if gap < 0:
            raise NodeError("The gap cannot be negative. Enter 0 or more.")
        plane = geo.plane_of(wire)
        poly = geo.polygon_of(wire, plane)
        pts = [vec_of(p, "Points") for p in as_list(args.get("points"))]
        if not pts:
            raise NodeError("Connect the points the cells grow from.")
        uv = np.array([plane.coords(p) for p in pts], dtype=float)
        uv = uv[geo.inside_polygon(uv, poly)]
        uv = np.unique(np.round(uv, 9), axis=0)
        if len(uv) == 0:
            raise NodeError("No point lies inside the boundary. Move the points inside.")
        lo, hi = poly.min(axis=0) - 1.0, poly.max(axis=0) + 1.0
        faces = []
        for cell in voronoi_cells(uv, lo, hi, gap):
            if len(cell) < 3 or ctx.cancelled():
                continue
            faces.append(geo.face_of(geo.polyline([plane.at(u, v) for u, v in cell], True)))
        bound = wire if gap <= 0 else geo.offset(wire, -gap / 2.0)
        clipped = geo.boolean("common", faces, [geo.face_of(bound)])
        return {"cells": _outer_wires(clipped, plane, uv)}


def _outer_wires(shape: Any, plane: Plane, seeds: np.ndarray) -> list[Any]:
    """Outer curves of the faces in ``shape``, ordered by their nearest seed."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    found = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = TopoDS.Face(explorer.Current())
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, props)
        if props.Mass() > 1e-9:
            c = props.CentreOfMass()
            u, v = plane.coords((c.X(), c.Y(), c.Z()))
            nearest = int(np.argmin(np.linalg.norm(seeds - np.array([u, v]), axis=1)))
            found.append((nearest, u, v, BRepTools.OuterWire_s(face)))
        explorer.Next()
    found.sort(key=lambda t: (t[0], t[1], t[2]))
    return [w for _i, _u, _v, w in found]


LATTICES = ("cubic", "octet")
_CUBIC = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
_OCTET = np.array([[1, 1, 0], [1, -1, 0], [1, 0, 1], [1, 0, -1], [0, 1, 1], [0, 1, -1]])


def strut_ends(
    lo: np.ndarray, hi: np.ndarray, cell: float, kind: str, reach: float | None = None
) -> np.ndarray:
    """Strut end points (an N by 2 by 3 array) filling the box ``lo`` to ``hi``.

    Cubic struts run along the cell edges. Octet struts join each cell corner and
    face centre to its twelve nearest neighbours. The cells start at ``lo``, so the
    last row may pass ``hi``; with ``reach`` (how far a strut's ball and sides stand
    out from its line) a strut that lies wholly further than that beyond ``hi`` is
    left out, since cutting to the box would remove all of it (D2636).
    """
    counts = np.maximum(np.ceil((hi - lo) / cell - 1e-9).astype(int), 1)
    if kind == "octet":
        steps, offsets, unit = counts * 2, _OCTET, cell / 2.0
    else:
        steps, offsets, unit = counts, _CUBIC, cell
    grid = np.stack(
        np.meshgrid(*(np.arange(s + 1) for s in steps), indexing="ij"), axis=-1
    ).reshape(-1, 3)
    if kind == "octet":
        grid = grid[grid.sum(axis=1) % 2 == 0]
    pairs = []
    for off in offsets:
        ends = grid + off
        ok = np.all((ends >= 0) & (ends <= steps), axis=1)
        pairs.append(np.stack([grid[ok], ends[ok]], axis=1))
    every = np.concatenate(pairs) if pairs else np.zeros((0, 2, 3))
    result: np.ndarray = lo + every * unit
    if reach is not None:
        near = result.min(axis=1)  # the low corner of each strut's box
        result = result[np.all(near <= hi + reach + 1e-9, axis=1)]
    return result


#: Strut ends stop this many strut radii short of a node, and a ball of this many
#: radii covers the node, so struts meet only balls, never each other (DECISIONS D377).
JOINTS = {"cubic": (1.05, 1.5), "octet": (1.8, 2.1)}
#: Shortest strut, in cells: an octet strut joins a corner to a face centre.
SHORTEST = {"cubic": 1.0, "octet": math.sqrt(0.5)}


def lattice_parts(ends: np.ndarray, radius: float, kind: str) -> list[Any]:
    """Strut cylinders and node balls for strut ``ends``."""
    stop, ball = JOINTS[kind]
    shapes = []
    for a, b in ends:
        axis = b - a
        length = float(np.linalg.norm(axis))
        u = axis / length
        start = a + u * (stop * radius)
        shapes.append(
            geo.cylinder(
                (float(start[0]), float(start[1]), float(start[2])),
                (float(u[0]), float(u[1]), float(u[2])),
                radius,
                length - 2 * stop * radius,
            )
        )
    nodes = np.unique(np.round(ends.reshape(-1, 3), 9), axis=0)
    shapes.extend(geo.sphere((float(p[0]), float(p[1]), float(p[2])), ball * radius) for p in nodes)
    return shapes


@register
class Lattice(NodeType):
    """Round struts in a cubic or octet pattern with a ball at every node, filling a
    bounding body and cut to it."""

    type_name = "lattice"
    title = "Strut Lattice"
    category = PATTERNS
    words = "truss infill cellular octet cubic lightweight"
    inputs = (
        Port("body", PortType.BODY, "Bounding body"),
        Port("cell", LEN, "Cell size", 10.0),
        Port("radius", LEN, "Strut radius", 1.0),
    )
    outputs = (Port("body", PortType.BODY, "Lattice"), Port("count", PortType.NUMBER, "Struts"))
    settings = (Setting("type", "choice", "cubic", LATTICES), ALLOW_MANY)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        body = geo.shape_of(args.get("body"), "Bounding body")
        cell = number_of(args.get("cell"), "Cell size")
        radius = number_of(args.get("radius"), "Strut radius")
        if cell <= 0 or radius <= 0:
            raise NodeError("Cell size and strut radius must be more than 0. Enter larger values.")
        kind = str(ctx.setting("type", "cubic"))
        kind = kind if kind in LATTICES else "cubic"
        limit = SHORTEST[kind] * cell / (2 * JOINTS[kind][0])
        if radius >= limit:
            raise NodeError(
                f"The strut radius is too large for this cell. Use a radius under {limit:.3g} mm "
                "or a larger cell."
            )
        lo, hi = (np.array(c) for c in geo.bounds(body))
        ends = strut_ends(lo, hi, cell, kind, reach=JOINTS[kind][1] * radius)
        if len(ends) > 20000:
            raise NodeError("The lattice would have more than 20000 struts. Use a larger cell.")
        guard(ctx, len(ends))
        frame = geo.union(lattice_parts(ends, radius, kind), unify=False)
        frame = geo.boolean("common", [frame], [body], unify=False)
        if not geo.solids_of(frame):
            raise NodeError("No strut lies inside the body. Use a smaller cell.")
        return {"body": frame, "count": float(len(ends))}


def degrees(value: float) -> float:
    """Radians to degrees, for labels."""
    return math.degrees(value)
