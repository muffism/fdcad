"""A check after a boss or cut sized to the tool, not to the part (D2619, IDEAS 50).

The volume check of D705 is off on bodies of more than 100 faces, and its slack is 1
percent of the whole part, so a small boss or cut that the kernel loses on a large part
is not seen (the head badge of D1049 was 0.05 percent of a bike frame). Here a point
inside each tool solid is picked where the boolean must change the part: outside the
body for a boss, inside it for a cut. After a boss the point must be inside the result,
after a cut outside it. The test does not grow with the part:

* the point comes from the tool: a point on one of its faces is moved in along the
  face's normal to the middle (or a quarter) of the chord to the tool's far side;
* the point is placed against the body and the result by counting the faces a ray
  from it crosses. The faces a ray can reach are found from their boxes in numpy, so
  only those few faces are asked. The boxes are kept from one feature to the next,
  since a body shares nearly all of its faces with the result before it; only new
  faces are measured. Rays are tried in the order of what their faces cost to ask,
  and the first clean one counts;
* a result that looks wrong is confirmed by the kernel's own point classifier on the
  tool, the body and the result, each with a tolerance well above the boolean's fuzzy
  value. A point that lies on a surface within that tolerance, or a count with no clean
  ray, gives no verdict, and the boolean is taken as right.

Kernel work: rebuild thread only. Nothing here imports Qt.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from typing import Any

import numpy as np
from OCP.Bnd import Bnd_Box
from OCP.BOPTools import BOPTools_AlgoTools3D
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.GeomAbs import (
    GeomAbs_Cone,
    GeomAbs_Cylinder,
    GeomAbs_Plane,
    GeomAbs_Sphere,
    GeomAbs_Torus,
)
from OCP.gp import gp_Dir, gp_Lin, gp_Pnt, gp_Pnt2d, gp_Vec
from OCP.IntCurvesFace import IntCurvesFace_Intersector
from OCP.IntCurveSurface import IntCurveSurface_Tangent
from OCP.IntTools import IntTools_Context
from OCP.TopAbs import (
    TopAbs_EDGE,
    TopAbs_FACE,
    TopAbs_IN,
    TopAbs_ON,
    TopAbs_OUT,
    TopAbs_REVERSED,
    TopAbs_SOLID,
)
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Shape

from fdcad.core.occ import ShapeMap

#: Directions tried for a ray: the axes first (boxes are cut along them), then two
#: slanted ones for when every axis ray grazes an edge.
_RAYS = np.array(
    [
        (0, 0, 1),
        (0, 0, -1),
        (1, 0, 0),
        (-1, 0, 0),
        (0, 1, 0),
        (0, -1, 0),
        (0.31, 0.47, 0.83),
        (-0.53, 0.29, -0.79),
    ],
    dtype=float,
)
_RAYS /= np.linalg.norm(_RAYS, axis=1)[:, None]
#: Faces of each tool solid used to find a point inside it.
_TOOL_FACES = 3
#: Places along each chord through the tool, as a share of its length.
_ALONG = (0.5, 0.25, 0.75)
#: Most tool solids looked at in one boolean (a pattern of many copies is sampled).
_MOST_TOOLS = 12
#: The face boxes kept are cut back to the last result's when there are this many more.
_KEEP_EXTRA = 400

_ANALYTIC = (GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone, GeomAbs_Sphere, GeomAbs_Torus)

_LOCK = threading.Lock()


def _row(face: TopoDS_Shape) -> tuple[float, ...]:
    """The face's box corners, what a ray test on it costs and what making its ray
    intersector costs, in units of about 15 us. Measured: making the intersector of a
    flat face costs about 27 us an edge (2.7 ms for the plate of generated_200 with
    its 100 hole edges) and a test on it 0.4 us an edge; on a spline both cost about
    a hundred times more. So a ray across a new face with many holes, or across a
    spline, is avoided when another will do."""
    f = TopoDS.Face(face)
    kind = BRepAdaptor_Surface(f, False).GetType()
    box = Bnd_Box()
    BRepBndLib.Add_s(face, box, False)
    low, high = box.CornerMin(), box.CornerMax()
    edges = ShapeMap()
    TopExp.MapShapes_s(face, TopAbs_EDGE, edges)
    ask, make = 1.0 + edges.Extent() / 40.0, 1.0 + 2.0 * edges.Extent()
    if kind not in _ANALYTIC:
        ask, make = 100.0 + ask, 200.0 + make
    return (low.X(), low.Y(), low.Z(), high.X(), high.Y(), high.Z(), ask, make)


def _face_maps(shape: TopoDS_Shape) -> list[ShapeMap]:
    """The faces of each solid of ``shape``, one map per solid."""
    out = []
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        faces = ShapeMap()
        TopExp.MapShapes_s(explorer.Current(), TopAbs_FACE, faces)
        out.append(faces)
        explorer.Next()
    return out


class _Faces:
    """Boxes and ray intersectors of every face seen, by their number in one map."""

    def __init__(self) -> None:
        self.map = ShapeMap()
        self.boxes: np.ndarray[Any, Any] = np.empty((0, 6))
        self.cost: np.ndarray[Any, Any] = np.empty(0)
        self.make: np.ndarray[Any, Any] = np.empty(0)  # 0 once the intersector is made
        self.hits: dict[int, IntCurvesFace_Intersector] = {}
        #: The last result checked and the faces of each of its solids: the next
        #: boolean often starts from it.
        self.last: tuple[TopoDS_Shape, list[ShapeMap]] | None = None

    def add(self, shape: TopoDS_Shape) -> None:
        """Take in the faces of ``shape``; only faces not seen before are measured."""
        first = self.map.Extent()
        TopExp.MapShapes_s(shape, TopAbs_FACE, self.map)
        last = self.map.Extent()
        if last > first:
            rows = np.array([_row(self.map.FindKey(i)) for i in range(first + 1, last + 1)])
            self.boxes = np.concatenate([self.boxes, rows[:, :6]])
            self.cost = np.concatenate([self.cost, rows[:, 6]])
            self.make = np.concatenate([self.make, rows[:, 7]])

    def keep_only(self, shape: TopoDS_Shape) -> None:
        """Forget the faces that are not in ``shape``, when many have piled up."""
        kept = ShapeMap()
        TopExp.MapShapes_s(shape, TopAbs_FACE, kept)
        if self.map.Extent() <= kept.Extent() + _KEEP_EXTRA:
            return
        old = [self.map.FindIndex(kept.FindKey(i)) - 1 for i in range(1, kept.Extent() + 1)]
        keep = np.array(old, dtype=np.int64)
        self.boxes, self.cost = self.boxes[keep].reshape(-1, 6), self.cost[keep]
        self.make = self.make[keep]
        self.hits = {new: self.hits[o] for new, o in enumerate(old) if o in self.hits}
        self.map = kept

    def _hit(self, i: int) -> IntCurvesFace_Intersector:
        found = self.hits.get(i)
        if found is None:
            face = TopoDS.Face(self.map.FindKey(i + 1))
            found = self.hits[i] = IntCurvesFace_Intersector(face, 1e-7)
            self.make[i] = 0.0
        return found

    def _axis_reach(self, origin: np.ndarray[Any, Any]) -> Any:
        """``(6, faces)``: which face boxes each axis ray of ``_RAYS`` from ``origin``
        meets. A box meets an axis ray when it spans the other two coordinates."""
        low, high = self.boxes[:, :3].T - 1e-4, self.boxes[:, 3:].T + 1e-4
        o = origin[:, None]
        within = (low <= o) & (o <= high)
        side = within[[0, 1, 0]] & within[[1, 2, 2]]  # rays along z, x, y
        axes = [2, 0, 1]
        out = np.empty((6, len(self.boxes)), dtype=bool)
        out[0::2] = side & (high[axes] >= o[axes])
        out[1::2] = side & (low[axes] <= o[axes])
        return out

    @staticmethod
    def _reach(boxes: Any, origin: np.ndarray[Any, Any], ways: np.ndarray[Any, Any]) -> Any:
        """``(len(ways), len(boxes))``: which boxes each ray from ``origin`` meets."""
        low = boxes[None, :, :3] - 1e-4
        high = boxes[None, :, 3:] + 1e-4
        o = origin[None, None, :]
        w = ways[:, None, :]
        flat = w == 0
        safe = np.where(flat, 1.0, w)
        t1, t2 = (low - o) / safe, (high - o) / safe
        t_in = np.where(
            flat, np.where((low <= o) & (o <= high), -np.inf, np.inf), np.minimum(t1, t2)
        )
        t_out = np.where(flat, np.inf, np.maximum(t1, t2))
        enter, leave = t_in.max(axis=2), t_out.min(axis=2)
        return (leave >= enter) & (leave >= 0)

    def inside(self, shapes: list[list[ShapeMap]], p: np.ndarray[Any, Any]) -> list[bool] | None:
        """For each shape, given as the faces of each of its solids, True when ``p`` is
        inside one of its solids, by the faces one ray crosses (a face the shapes share
        is asked once); None when no ray gives a clean count."""
        owners = [faces for solids in shapes for faces in solids]
        group = [g for g, solids in enumerate(shapes) for _ in solids]
        reach = self._axis_reach(p)
        start = gp_Pnt(*(float(c) for c in p))
        cost = reach @ (self.cost + self.make)
        tries = [int(r) for r in np.argsort(cost, kind="stable")]
        for r in [*tries, 6, 7]:
            if r == 6:  # every axis ray grazed something: try the slanted ones
                reach = np.concatenate([reach, self._reach(self.boxes, p, _RAYS[6:])])
            line = gp_Lin(start, gp_Dir(*(float(c) for c in _RAYS[r])))
            counts = [0] * len(owners)
            clean = True
            for i in np.nonzero(reach[r])[0]:
                face = self.map.FindKey(int(i) + 1)
                mine = [k for k, faces in enumerate(owners) if faces.Contains(face)]
                if not mine:
                    continue
                hit = self._hit(int(i))
                hit.Perform(line, -1e-7, 1e100)
                for k in range(1, hit.NbPnt() + 1):
                    w = hit.WParameter(k)
                    if (
                        abs(w) < 1e-6
                        or hit.State(k) == TopAbs_ON
                        or hit.Transition(k) == IntCurveSurface_Tangent
                    ):
                        clean = False
                        break
                    if w > 0:
                        for owner in mine:
                            counts[owner] += 1
                if not clean:
                    break
            if clean:
                odd = [False] * len(shapes)
                for k, c in enumerate(counts):
                    odd[group[k]] = odd[group[k]] or c % 2 == 1
                return odd
        return None

    def chord(self, numbers: Any, p: np.ndarray[Any, Any], way: np.ndarray[Any, Any]) -> float:
        """How far a ray from ``p`` along ``way`` goes before it meets one of the faces
        numbered ``numbers`` (0 when it meets none)."""
        reach = self._reach(self.boxes[numbers], p, way[None, :])[0]
        line = gp_Lin(gp_Pnt(*(float(c) for c in p)), gp_Dir(*(float(c) for c in way)))
        nearest = np.inf
        for i in numbers[reach]:
            hit = self._hit(int(i))
            hit.Perform(line, 1e-6, 1e100)
            for k in range(1, hit.NbPnt() + 1):
                nearest = min(nearest, hit.WParameter(k))
        return float(nearest) if np.isfinite(nearest) else 0.0


_FACES = _Faces()


def _starts(face: TopoDS_Shape, context: IntTools_Context) -> tuple[Any, Any] | None:
    """A point inside ``face`` and the way into the solid there (against its normal)."""
    p, uv = gp_Pnt(), gp_Pnt2d()
    f = TopoDS.Face(face)
    if BOPTools_AlgoTools3D.PointInFace_s(f, p, uv, context) != 0:
        return None
    q, du, dv = gp_Pnt(), gp_Vec(), gp_Vec()
    BRepAdaptor_Surface(f).D1(uv.X(), uv.Y(), q, du, dv)
    n = du.Crossed(dv)
    if n.Magnitude() < 1e-12:
        return None
    if face.Orientation() != TopAbs_REVERSED:
        n.Reverse()  # into the solid
    n.Normalize()
    return np.array([p.X(), p.Y(), p.Z()]), np.array([n.X(), n.Y(), n.Z()])


def _candidates(faces: ShapeMap, numbers: Any, context: IntTools_Context) -> Any:
    """Points inside the tool whose faces are ``faces`` (numbered ``numbers``): along
    chords in from its largest faces that are quick to ask, the middle of each chord
    first."""
    boxes = _FACES.boxes[numbers]
    size = np.linalg.norm(boxes[:, 3:] - boxes[:, :3], axis=1)
    order = np.argsort(-size / np.sqrt(_FACES.cost[numbers]), kind="stable")
    for j in order[:_TOOL_FACES]:
        start = _starts(faces.FindKey(int(j) + 1), context)
        if start is None:
            continue
        p, way = start
        length = _FACES.chord(numbers, p, way)
        if length <= 0:
            continue
        for share in _ALONG:
            yield p + way * (length * share)


def _state(shape: TopoDS_Shape, p: Any, tol: float) -> Any:
    """The kernel's answer for ``p`` in ``shape``: IN in a solid, ON within ``tol`` of
    the surface of one, OUT otherwise. Each solid is asked alone (D1082)."""
    point = gp_Pnt(*(float(c) for c in p))
    on = False
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        state = BRepClass3d_SolidClassifier(explorer.Current(), point, tol).State()
        explorer.Next()
        if state == TopAbs_IN:
            return TopAbs_IN
        on = on or state == TopAbs_ON
    return TopAbs_ON if on else TopAbs_OUT


def _confirmed(boss: bool, body: Any, tool: Any, result: Any, p: Any, tol: float) -> bool:
    """True when the kernel's classifier agrees that ``p`` is well inside the tool, on
    the side of the body that must change, and on the wrong side of the result."""
    if _state(tool, p, tol) != TopAbs_IN:
        return False
    wrong = TopAbs_OUT if boss else TopAbs_IN
    return bool(_state(body, p, tol) == wrong and _state(result, p, tol) == wrong)


def tools_kept(
    operation: str, body: TopoDS_Shape, tools: Sequence[TopoDS_Shape], result: TopoDS_Shape
) -> bool:
    """False when a boss left out the material of one of its tools, or a cut left the
    material where one of its tools is (D2619). True when the result is right or no
    verdict can be had."""
    with _LOCK:
        return _tools_kept(operation == "boss", body, tools, result)


def _tools_kept(
    boss: bool, body: TopoDS_Shape, tools: Sequence[TopoDS_Shape], result: TopoDS_Shape
) -> bool:
    solids: list[TopoDS_Shape] = []
    for tool in tools:
        explorer = TopExp_Explorer(tool, TopAbs_SOLID)
        while explorer.More():
            solids.append(explorer.Current())
            explorer.Next()
    if not solids:
        return True
    if len(solids) > _MOST_TOOLS:
        picks = np.linspace(0, len(solids) - 1, _MOST_TOOLS).round().astype(int)
        solids = [solids[int(i)] for i in picks]
    result_faces = _face_maps(result)
    if not result_faces:
        return True
    last = _FACES.last
    if last is not None and last[0].IsSame(body):
        body_faces = last[1]  # the body is the last result: its faces are known
    else:
        body_faces = _face_maps(body)
        _FACES.add(body)
    _FACES.add(result)
    _FACES.last = (result, result_faces)
    context = IntTools_Context()
    try:
        for tool in solids:
            if not _tool_kept(boss, body, tool, result, body_faces, result_faces, context):
                return False
        return True
    finally:
        _FACES.keep_only(result)


def _tool_kept(
    boss: bool,
    body: TopoDS_Shape,
    tool: TopoDS_Shape,
    result: TopoDS_Shape,
    body_faces: list[ShapeMap],
    result_faces: list[ShapeMap],
    context: IntTools_Context,
) -> bool:
    faces = ShapeMap()
    TopExp.MapShapes_s(tool, TopAbs_FACE, faces)
    if faces.Extent() == 0:
        return True
    _FACES.add(tool)
    found = [_FACES.map.FindIndex(faces.FindKey(i)) - 1 for i in range(1, faces.Extent() + 1)]
    numbers = np.array(found, dtype=np.int64)
    boxes = _FACES.boxes[numbers]
    size = float(np.linalg.norm(boxes[:, 3:].max(axis=0) - boxes[:, :3].min(axis=0)))
    tol = max(1e-3, 1e-4 * size)  # far above the boolean's fuzzy value (1e-5)
    for p in _candidates(faces, numbers, context):
        places = _FACES.inside([body_faces, result_faces], p)
        if places is None:
            continue  # no clean count here
        in_body, in_result = places
        if in_body == boss:
            continue  # this point does not show the change
        if in_result == boss:
            return True
        return not _confirmed(boss, body, tool, result, p, tol)
    return True
