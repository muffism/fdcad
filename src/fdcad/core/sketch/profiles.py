"""Turn a checked sketch into planar OpenCascade faces (one per region, holes included).

Each face edge is mapped back to the sketch entity that made it, so features can
name the faces they create (`PLAN.md` section 6).
"""

from __future__ import annotations

import copy
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakeVertex,
    BRepBuilderAPI_MakeWire,
)
from OCP.Geom import Geom_BSplineCurve
from OCP.gp import gp_Ax2, gp_Ax3, gp_Circ, gp_Dir, gp_Elips, gp_Pln, gp_Pnt
from OCP.OCP.collections import Array1_double, Array1_gp_Pnt, Array1_int
from OCP.ShapeFix import ShapeFix_Face
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face, TopoDS_Vertex, TopoDS_Wire

from fdcad.core.sketch.freeform import axes, bezier_poles
from fdcad.core.sketch.model import Arc, Circle, Ellipse, EllipseArc, Line, Point, Sketch, Spline
from fdcad.core.sketch.regions import HalfEdge, Region, Regions, compute
from fdcad.core.sketch.topology import Loop, SketchIssue, check, crossings, find_loops, nest

Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class SketchPlane:
    """Placement of a sketch: origin, normal and the direction of the sketch X axis."""

    origin: Vec3
    normal: Vec3
    x_dir: Vec3

    def ax3(self) -> gp_Ax3:
        """The plane as an OpenCascade coordinate system."""
        return gp_Ax3(gp_Pnt(*self.origin), gp_Dir(*self.normal), gp_Dir(*self.x_dir))

    def to_3d(self, u: float, v: float) -> gp_Pnt:
        """Map sketch coordinates (mm) to a model point."""
        ax = self.ax3()
        o, x, y = ax.Location(), ax.XDirection(), ax.YDirection()
        return gp_Pnt(
            o.X() + u * x.X() + v * y.X(),
            o.Y() + u * x.Y() + v * y.Y(),
            o.Z() + u * x.Z() + v * y.Z(),
        )

    def to_2d(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        """Map a model point to sketch coordinates (u, v) and its height above the plane."""
        ax = self.ax3()
        o, xd, yd, n = ax.Location(), ax.XDirection(), ax.YDirection(), ax.Direction()
        dx, dy, dz = x - o.X(), y - o.Y(), z - o.Z()
        return (
            dx * xd.X() + dy * xd.Y() + dz * xd.Z(),
            dx * yd.X() + dy * yd.Y() + dz * yd.Z(),
            dx * n.X() + dy * n.Y() + dz * n.Z(),
        )


# Default planes (DECISIONS D67). Y is up (FDEF_SPEC 5.2).
BASIS_PLANES: dict[str, SketchPlane] = {
    "xy": SketchPlane((0, 0, 0), (0, 0, 1), (1, 0, 0)),  # Front: sketch Y is model +Y
    "xz": SketchPlane((0, 0, 0), (0, 1, 0), (1, 0, 0)),  # Top: sketch Y is model -Z
    "yz": SketchPlane((0, 0, 0), (1, 0, 0), (0, 0, -1)),  # Right: sketch Y is model +Y
}


class ProfileError(ValueError):
    """The sketch cannot make a profile. ``issues`` lists what to fix."""

    def __init__(self, message: str, issues: list[SketchIssue] | None = None) -> None:
        super().__init__(message)
        self.issues = issues or []


@dataclass
class Profile:
    """Planar faces from a sketch, with each face edge mapped to its sketch entity."""

    faces: list[TopoDS_Face]
    edge_entities: list[tuple[TopoDS_Edge, str]] = field(default_factory=list)

    def entity_of(self, edge: TopoDS_Edge) -> str | None:
        """Sketch entity id that made ``edge``, or None.

        When a curve is split by crossings and several of its pieces bound the
        profile, the second and later pieces along the curve are ``e3#2``, ``e3#3``
        (FDEF_SPEC 8 item 6).
        """
        for e, eid in self.edge_entities:
            if e.IsSame(edge):
                return eid
        return None


class _EdgeMaker:
    def __init__(self, sketch: Sketch, plane: SketchPlane) -> None:
        self.sketch = sketch
        self.plane = plane
        self.vertices: dict[str, TopoDS_Vertex] = {}
        self.edges: dict[str, TopoDS_Edge] = {}

    def vertex(self, pid: str) -> TopoDS_Vertex:
        key = self._node_key(pid)
        if key not in self.vertices:
            self.vertices[key] = BRepBuilderAPI_MakeVertex(
                self.plane.to_3d(*self.sketch.xy(pid))
            ).Vertex()
        return self.vertices[key]

    def _node_key(self, pid: str) -> str:
        x, y = self.sketch.xy(pid)
        return f"{round(x, 6)},{round(y, 6)}"

    def circle(self, center: str, radius: float) -> gp_Circ:
        axis = gp_Ax2(
            self.plane.to_3d(*self.sketch.xy(center)),
            gp_Dir(*self.plane.normal),
            gp_Dir(*self.plane.x_dir),
        )
        return gp_Circ(axis, radius)

    def edge(self, cid: str) -> TopoDS_Edge:
        if cid in self.edges:
            return self.edges[cid]
        ent = self.sketch.entities[cid]
        if isinstance(ent, Line):
            maker = BRepBuilderAPI_MakeEdge(self.vertex(ent.p1), self.vertex(ent.p2))
        elif isinstance(ent, Circle):
            maker = BRepBuilderAPI_MakeEdge(self.circle(ent.center, ent.radius))
        elif isinstance(ent, Arc):
            circ = self.circle(ent.center, self.sketch.radius(cid))
            start, end = (ent.start, ent.end) if ent.ccw else (ent.end, ent.start)
            maker = BRepBuilderAPI_MakeEdge(circ, self.vertex(start), self.vertex(end))
        elif isinstance(ent, Ellipse | EllipseArc | Spline):
            maker = self._freeform(ent)
        else:
            raise ProfileError(
                f"{cid} is not a curve. Delete it from the sketch and draw it again."
            )
        if not maker.IsDone():
            raise ProfileError(f"Curve {cid} is too small or degenerate. Delete or resize it.")
        self.edges[cid] = maker.Edge()
        return self.edges[cid]

    def _dir(self, d: tuple[float, float]) -> gp_Dir:
        o = self.plane.to_3d(0.0, 0.0)
        p = self.plane.to_3d(d[0], d[1])
        return gp_Dir(p.X() - o.X(), p.Y() - o.Y(), p.Z() - o.Z())

    def _freeform(self, ent: Ellipse | EllipseArc | Spline) -> BRepBuilderAPI_MakeEdge:
        """Exact edges of ellipses and splines (D278)."""
        if isinstance(ent, Spline):
            poles2 = bezier_poles(self.sketch, ent)
            pieces = (len(poles2) - 1) // 3
            poles = Array1_gp_Pnt(1, len(poles2))
            for i, (u, v) in enumerate(poles2, start=1):
                poles.SetValue(i, self.plane.to_3d(u, v))
            knots = Array1_double(1, pieces + 1)
            mults = Array1_int(1, pieces + 1)
            for k in range(pieces + 1):
                knots.SetValue(k + 1, float(k))
                mults.SetValue(k + 1, 4 if k in (0, pieces) else 3)
            curve = Geom_BSplineCurve(poles, knots, mults, 3)
            start, end = ent.points[0], ent.points[-1]
            if math.dist(self.sketch.xy(start), self.sketch.xy(end)) < 1e-9:
                return BRepBuilderAPI_MakeEdge(curve)
            return BRepBuilderAPI_MakeEdge(curve, self.vertex(start), self.vertex(end))
        c, a, b, phi = axes(self.sketch, ent)
        if a < b or b <= 1e-9:
            raise ProfileError(
                f"Ellipse {ent.id} has a minor axis longer than its major axis. "
                "Drag the axis ends so the major axis is the longer one."
            )
        axis = gp_Ax2(
            self.plane.to_3d(*c),
            gp_Dir(*self.plane.normal),
            self._dir((math.cos(phi), math.sin(phi))),
        )
        elips = gp_Elips(axis, a, b)
        if isinstance(ent, Ellipse):
            return BRepBuilderAPI_MakeEdge(elips)
        return BRepBuilderAPI_MakeEdge(elips, self.vertex(ent.start), self.vertex(ent.end))

    def wire(self, loop: Loop, want_ccw: bool) -> TopoDS_Wire:
        maker = BRepBuilderAPI_MakeWire()
        for cid in loop.curves:
            maker.Add(self.edge(cid))
        if not maker.IsDone():
            raise ProfileError(
                "A contour could not be joined into a closed loop. "
                "Check that the contour's end points meet."
            )
        wire = maker.Wire()
        if (loop.signed_area > 0) != want_ccw:
            wire = TopoDS.Wire(wire.Reversed())
        return wire


def build_profile(sketch: Sketch, plane: SketchPlane, regions: Regions | None = None) -> Profile:
    """Faces for every closed region of ``sketch`` plus its text (P4.8). Raises ProfileError.

    A sketch with text and no curves is a profile of the text alone.
    """
    if not sketch.texts:
        return _curve_profile(sketch, plane, regions)
    from fdcad.core.sketch.model import Point
    from fdcad.core.sketch.text import TextError, text_faces

    try:
        letters = text_faces(sketch, plane)
    except TextError as exc:
        raise ProfileError(str(exc)) from exc
    if all(isinstance(e, Point) for e in sketch.entities.values()):
        return Profile(letters, [])
    profile = _curve_profile(sketch, plane, regions)
    return Profile(profile.faces + letters, profile.edge_entities)


def _curve_profile(sketch: Sketch, plane: SketchPlane, regions: Regions | None = None) -> Profile:
    """Faces for every closed region of the sketch curves. Raises ProfileError with the issues.

    Open contours, branches and duplicates are errors. Curves that cross split the
    sketch into regions (D116 item 1); then every outline is used with its holes,
    as for a sketch without crossings. ``regions`` may pass regions already
    computed for this sketch.
    """
    issues = check(sketch)
    if issues:
        raise ProfileError(issues[0].message, issues)
    if crossings(sketch):
        crossing, apart = _split_crossing(sketch)
        if not apart:
            _no_freeform(sketch)
            found = regions if regions is not None else compute(sketch)
            return region_profile(sketch, plane, found, found.default())
        # Shapes that cross nothing (splines and ellipses too) are built on their own
        # (audit D2 item 1, D706).
        _no_freeform(crossing)
        found = compute(crossing)
        first = region_profile(crossing, plane, found, found.default())
        second = _curve_profile(apart, plane)
        if _overlap(first.faces, second.faces):
            raise ProfileError(
                "A shape that does not cross other curves lies over curves that cross. "
                "Trim the crossing curves so each contour is closed on its own."
            )
        return Profile(first.faces + second.faces, first.edge_entities + second.edge_entities)
    loops = find_loops(sketch)
    if not loops:
        raise ProfileError("The sketch has no closed contour. Draw a closed shape to use it.")
    maker = _EdgeMaker(sketch, plane)
    pln = gp_Pln(plane.ax3())
    faces: list[TopoDS_Face] = []
    for outer, holes in nest(loops):
        face_maker = BRepBuilderAPI_MakeFace(pln, maker.wire(outer, want_ccw=True), True)
        for hole in holes:
            face_maker.Add(maker.wire(hole, want_ccw=False))
        if not face_maker.IsDone():
            raise ProfileError(
                "A region of the sketch could not be made into a face. "
                "Check for tiny or overlapping curves in the sketch."
            )
        fixer = ShapeFix_Face(face_maker.Face())
        fixer.Perform()
        faces.append(fixer.Face())
    return Profile(faces, [(edge, cid) for cid, edge in maker.edges.items()])


def _split_crossing(sketch: Sketch) -> tuple[Sketch, Sketch | None]:
    """The sketch as the groups of joined curves that take part in a crossing, and the
    rest (None when every group crosses). Each keeps all points; construction curves
    stay with the crossing part, where regions ignore them."""
    from fdcad.core.sketch.model import curve_ends
    from fdcad.core.sketch.topology import _Nodes, intersections

    nodes = _Nodes(sketch)
    curves = sketch.curves()
    group = {c.id: c.id for c in curves}

    def find(cid: str) -> str:
        while group[cid] != cid:
            group[cid] = group[group[cid]]
            cid = group[cid]
        return cid

    by_node: dict[str, str] = {}
    for c in curves:
        for pid in curve_ends(c) or ():
            node = nodes.find(pid)
            if node in by_node:
                group[find(c.id)] = find(by_node[node])
            else:
                by_node[node] = c.id
    crossing: set[str] = set()
    for issue in intersections(sketch):
        a, b = issue.entities[0], issue.entities[1]
        group[find(a)] = find(b)
        crossing.update((a, b))
    roots = {find(cid) for cid in crossing}
    apart = {c.id for c in curves if find(c.id) not in roots}
    if not apart:
        return sketch, None

    def subset(keep: Callable[[str, Any], bool]) -> Sketch:
        part = copy.copy(sketch)
        part.entities = {k: e for k, e in sketch.entities.items() if keep(k, e)}
        return part

    return (
        subset(lambda k, e: k not in apart),
        subset(lambda k, e: k in apart or isinstance(e, Point)),
    )


def _overlap(a: list[TopoDS_Face], b: list[TopoDS_Face]) -> bool:
    """True when faces of ``a`` and ``b`` share area or one lies inside the other."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    from fdcad.core.occ import BRepAlgoAPI_Common

    for fa in a:
        box_a = Bnd_Box()
        BRepBndLib.Add_s(fa, box_a)
        for fb in b:
            box_b = Bnd_Box()
            BRepBndLib.Add_s(fb, box_b)
            if box_a.IsOut(box_b):
                continue
            common = BRepAlgoAPI_Common(fa, fb)
            common.Build()
            if not common.IsDone():
                return True
            props = GProp_GProps()
            BRepGProp.SurfaceProperties_s(common.Shape(), props)
            if props.Mass() > 1e-9:
                return True
    return False


def _no_freeform(sketch: Sketch) -> None:
    """Crossing curves need exact formulas that ellipses and splines lack (D278)."""
    ids = [c.id for c in sketch.curves() if isinstance(c, Ellipse | EllipseArc | Spline)]
    if ids:
        raise ProfileError(
            "Ellipses and splines cannot be used where curves cross. "
            "Trim the crossing curves so each contour is closed on its own.",
            [
                SketchIssue(
                    "freeform",
                    ids,
                    "This curve is used where curves cross. Trim it at the crossing.",
                )
            ],
        )


def region_profile(
    sketch: Sketch, plane: SketchPlane, regions: Regions, chosen: list[Region]
) -> Profile:
    """Faces covering the ``chosen`` regions (T5.3.3). Touching regions make one face."""
    if regions.issues:
        raise ProfileError(regions.issues[0].message, regions.issues)
    if not chosen:
        raise ProfileError("The sketch has no closed region. Draw a closed shape to use it.")
    maker = _PieceEdges(sketch, plane, regions)
    pln = gp_Pln(plane.ax3())
    faces = [maker.face(pln, loops) for loops in regions.union(chosen)]
    return Profile(faces, maker.named_edges())


def region_face(
    sketch: Sketch, plane: SketchPlane, regions: Regions, region: Region
) -> TopoDS_Face:
    """One region as a face, holes included (for showing regions in the 3D view)."""
    maker = _PieceEdges(sketch, plane, regions)
    return maker.face(gp_Pln(plane.ax3()), region.loops())


class _PieceEdges:
    """Kernel edges for region pieces, sharing vertices, named after their curves."""

    def __init__(self, sketch: Sketch, plane: SketchPlane, regions: Regions) -> None:
        self.sketch, self.plane, self.regions = sketch, plane, regions
        self.vertices: dict[int, TopoDS_Vertex] = {}
        self.edges: dict[int, TopoDS_Edge] = {}

    def vertex(self, index: int, u: float, v: float) -> TopoDS_Vertex:
        if index not in self.vertices:
            self.vertices[index] = BRepBuilderAPI_MakeVertex(self.plane.to_3d(u, v)).Vertex()
        return self.vertices[index]

    def edge(self, k: int) -> TopoDS_Edge:
        if k in self.edges:
            return self.edges[k]
        piece = self.regions.pieces[k]
        if piece.centre is None:
            maker = BRepBuilderAPI_MakeEdge(
                self.vertex(piece.start, *piece.a), self.vertex(piece.end, *piece.b)
            )
        else:
            axis = gp_Ax2(
                self.plane.to_3d(*piece.centre),
                gp_Dir(*self.plane.normal),
                gp_Dir(*self.plane.x_dir),
            )
            circ = gp_Circ(axis, piece.radius)
            if piece.start == piece.end:
                maker = BRepBuilderAPI_MakeEdge(circ)
            else:
                maker = BRepBuilderAPI_MakeEdge(
                    circ,
                    self.vertex(piece.start, *piece.at(piece.t0)),
                    self.vertex(piece.end, *piece.at(piece.t1)),
                )
        if not maker.IsDone():
            raise ProfileError(
                f"Curve {piece.entity} is too small or degenerate. Delete or resize it."
            )
        self.edges[k] = maker.Edge()
        return self.edges[k]

    def wire(self, loop: list[HalfEdge]) -> TopoDS_Wire:
        maker = BRepBuilderAPI_MakeWire()
        for k, forward in loop:
            edge = self.edge(k)
            maker.Add(edge if forward else TopoDS.Edge(edge.Reversed()))
        if not maker.IsDone():
            raise ProfileError(
                "A region could not be joined into a closed loop. "
                "Check that the contour's end points meet."
            )
        return maker.Wire()

    def face(self, pln: gp_Pln, loops: list[list[HalfEdge]]) -> TopoDS_Face:
        face_maker = BRepBuilderAPI_MakeFace(pln, self.wire(loops[0]), True)
        for hole in loops[1:]:
            face_maker.Add(self.wire(hole))
        if not face_maker.IsDone():
            raise ProfileError(
                "A region of the sketch could not be made into a face. "
                "Check for tiny or overlapping curves in the sketch."
            )
        fixer = ShapeFix_Face(face_maker.Face())
        fixer.Perform()
        return fixer.Face()

    def named_edges(self) -> list[tuple[TopoDS_Edge, str]]:
        """Each edge with its curve id; later pieces of one curve get ``#2``, ``#3``."""
        by_entity: dict[str, list[int]] = {}
        for k in self.edges:
            by_entity.setdefault(self.regions.pieces[k].entity, []).append(k)
        out: list[tuple[TopoDS_Edge, str]] = []
        for entity, ks in by_entity.items():
            ks.sort(key=lambda k: _along(self.regions, k))
            for n, k in enumerate(ks, start=1):
                out.append((self.edges[k], entity if n == 1 else f"{entity}#{n}"))
        return out


def _along(regions: Regions, k: int) -> float:
    """Where a piece starts along its curve, for ordering pieces of one curve."""
    piece = regions.pieces[k]
    if piece.centre is None:
        same = [p for p in regions.pieces if p.entity == piece.entity]
        first = same[0].a
        return (piece.a[0] - first[0]) ** 2 + (piece.a[1] - first[1]) ** 2
    return piece.t0
