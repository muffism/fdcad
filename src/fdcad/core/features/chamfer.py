"""Chamfer: bevel the picked edges or corners (PHASE2_SPEC P2.5, DECISIONS D216).

Params:

- ``chamfer_type``: "angle_distance", "distance_distance" (default), "vertex",
  "offset_face" or "face_face" (D520).
- ``distance``: length. Angle and distance: measured on the reference face of
  each edge; ``angle``: angle from that face. Distance and distance: ``method``
  "symmetric" (one value) or "asymmetric" (``distance`` on the reference face,
  ``distance2`` on the other).
- ``flip``: optional boolean, the other face of each edge is the reference face.
- Vertex: ``distance``, ``distance2``, ``distance3`` along the three edges at the
  corner (ordered by edge name), or ``equal`` (one value for all three).

The reference face of an edge is the neighbouring face whose name sorts first.

- Offset face: ``distance`` and ``distance2`` (``method`` as above) are offsets
  measured square to the reference face and to the other face.
- Face to face: ``method`` "symmetric", "asymmetric" (``distance`` along the set 1
  face, ``distance2`` along the set 2 face) or "width" (``width``, the width of the
  chamfer face).

Refs: ``edges`` and ``faces`` (every edge of each face) for the edge types,
``vertices`` (vertex references) for the vertex type, ``faces1`` and ``faces2``
for face to face (the edges where the two sets meet).

Partial edges (TR64 item 5, D1012, symmetric Distance Distance only): ``partial``
"distance" or "percent" with ``start_distance`` and ``end_distance`` or
``start_percent`` and ``end_percent``, and ``partial_flip``, as for Fillet (D519).

Tangent Propagation (TR131, D1400): ``tangent_propagation`` False makes the bevel
of a picked edge stop square at each smooth join (symmetric Distance Distance only).

Corners (TR321, D1812, D2304): ``corner`` "patch" (default), "mitre" or "blend", see
``chamfer_corners``.

Face roles: ``chamfer/<edge name>`` and ``chamfer/<vertex name>``.
Failing edges are pinpointed like fillet edges (PLAN 5A item 5).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace

from OCP.BRep import BRep_Tool
from OCP.BRepFilletAPI import BRepFilletAPI_MakeChamfer
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face, TopoDS_Vertex

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Fix,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.fillet_faces import face_sets, shared_edges
from fdcad.core.features.modify import (
    MakerHistory,
    PartialResultError,
    changed_faces,
    edge_faces,
    edges_of,
    length,
    lost_message,
    require_body,
    resolve_edges,
    resolve_faces,
)
from fdcad.core.features.solids import breaks_solid, check_result, combine, is_valid, line_ends
from fdcad.core.naming.names import NamedFace, NamedShape, carry, restrict
from fdcad.core.occ import ShapeListMap, shape_list
from fdcad.core.units import Kind

CHAMFER_TYPES = ("angle_distance", "distance_distance", "vertex", "offset_face", "face_face")
CHAMFER_METHODS = ("symmetric", "asymmetric", "width")
_SEARCH_STEPS = 8


@dataclass
class Sizes:
    """The chamfer sizes, scaled by ``scale`` while pinpointing."""

    kind: str
    d1: float
    d2: float
    angle: float
    flip: bool
    method: str = "symmetric"
    #: Face to face: the faces of set 1, where the first distance is measured.
    first_faces: list[TopoDS_Face] = field(default_factory=list)
    #: The parameter the "Reduce" fix changes.
    param: str = "distance"
    owner: str = "Chamfer"

    def scaled(self, scale: float) -> Sizes:
        """The same chamfer with distances times ``scale``."""
        return replace(self, d1=self.d1 * scale, d2=self.d2 * scale)


def sizes(feature: Feature) -> Sizes:
    """Read and check the size parameters of an edge chamfer."""
    kind = str(feature.params.get("chamfer_type", "distance_distance"))
    d1 = length(feature, "distance", "distance")
    flip = feature.params.get("flip") is True
    if kind == "angle_distance":
        value = feature.params.get("angle")
        if not isinstance(value, Param):
            raise FeatureError(f"{feature.name}: the angle is missing. Enter an angle.")
        import math

        if not 0 < value.value < math.radians(90):
            raise FeatureError(
                f"{feature.name}: the angle must be between 0 and 90 degrees. Change it."
            )
        return Sizes(kind, d1, d1, value.value, flip)
    method = str(feature.params.get("method", "symmetric"))
    if kind == "face_face" and method == "width":
        width = length(feature, "width", "width")
        return Sizes(kind, width, width, 0.0, False, method, param="width", owner=feature.name)
    if method == "asymmetric":
        d2 = length(feature, "distance2", "second distance")
        return Sizes(kind, d1, d2, 0.0, flip, method, owner=feature.name)
    return Sizes(kind, d1, d1, 0.0, flip, method, owner=feature.name)


def _normals_along(owner: str, body: NamedShape, edge: TopoDS_Edge, first: TopoDS_Face) -> float:
    """Dot product of the outward normals of the two faces at ``edge``.

    It must be the same along the whole edge (checked at the ends and the middle).
    """
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.ShapeAnalysis import ShapeAnalysis_Surface

    from fdcad.core.features.hole import outward_normal

    faces = edge_faces(body.shape, edge)
    other = next((f for f in faces if not f.IsSame(first)), None)
    if other is None:
        raise FeatureError(
            f"{owner}: a picked edge has only one face. Pick an edge between two faces."
        )
    curve = BRepAdaptor_Curve(edge)
    u0, u1 = curve.FirstParameter(), curve.LastParameter()
    dots: list[float] = []
    for t in (0.0, 0.5, 1.0):
        p = curve.Value(u0 + (u1 - u0) * t)
        normals = []
        for face in (first, other):
            uv = ShapeAnalysis_Surface(BRep_Tool.Surface_s(face)).ValueOfUV(p, 1e-6)
            n = outward_normal(face, uv.X(), uv.Y())
            if n is None:
                raise FeatureError(
                    f"{owner}: a face next to edge {body.edge_name(edge) or ''} has no "
                    "normal at the edge. Use Distance Distance."
                )
            normals.append(n)
        a, b = normals
        dots.append(a[0] * b[0] + a[1] * b[1] + a[2] * b[2])
    if max(dots) - min(dots) > 1e-6:
        raise FeatureError(
            f"{owner}: the angle between the faces changes along edge "
            f"{body.edge_name(edge) or ''}. Use Distance Distance for this edge."
        )
    return dots[1]


def along_faces(
    owner: str, body: NamedShape, edge: TopoDS_Edge, face: TopoDS_Face, size: Sizes
) -> tuple[float, float]:
    """Distances along ``face`` and along the other face, for the kernel (D520).

    ``phi`` is the angle between the faces across the chamfered corner, so the
    normals meet at pi less phi: sin(phi) is the length of their cross product.
    """
    import math

    dot = _normals_along(owner, body, edge, face)
    phi = math.pi - math.acos(max(-1.0, min(1.0, dot)))
    if math.sin(phi) < 1e-6:
        raise FeatureError(
            f"{owner}: the faces at edge {body.edge_name(edge) or ''} meet smoothly, "
            "so there is no corner to chamfer. Pick another edge."
        )
    if size.kind == "offset_face":
        return size.d2 / math.sin(phi), size.d1 / math.sin(phi)
    if size.method == "width":
        d = size.d1 / (2 * math.sin(phi / 2))
        return d, d
    return size.d1, size.d2


def reference_face(body: NamedShape, edge: TopoDS_Edge, flip: bool) -> TopoDS_Face:
    """The face the first distance is measured on: the neighbour whose name sorts first."""
    faces = edge_faces(body.shape, edge)
    if len(faces) < 2:
        raise FeatureError("A picked edge has only one face. Pick an edge between two faces.")
    faces.sort(key=lambda f: body.primary_name(f) or "")
    return faces[1] if flip else faces[0]


def bevel(
    fid: str, body: NamedShape, items: list[tuple[str, TopoDS_Edge]], size: Sizes
) -> NamedShape | None:
    """Chamfer ``items`` on ``body``. None when the kernel cannot or the result is invalid."""
    if size.d1 <= 0 or size.d2 <= 0:
        return None
    maker = BRepFilletAPI_MakeChamfer(body.shape)
    try:
        for _name, edge in items:
            if maker.Contour(edge) != 0:
                continue
            face = reference_face(body, edge, size.flip)
            if size.first_faces:
                face = next(
                    (
                        f
                        for f in edge_faces(body.shape, edge)
                        if any(f.IsSame(g) for g in size.first_faces)
                    ),
                    face,
                )
            if size.kind == "angle_distance":
                maker.AddDA(size.d1, size.angle, edge, face)
            elif size.kind in ("offset_face", "face_face"):
                a, b = along_faces(size.owner, body, edge, face, size)
                if abs(a - b) < 1e-12:
                    maker.Add(a, edge)
                else:
                    maker.Add(a, b, edge, face)
            elif size.d1 == size.d2:
                maker.Add(size.d1, edge)
            else:
                maker.Add(size.d1, size.d2, edge, face)
        maker.Build()
    except FeatureError:
        raise
    except Exception:
        return None
    if not maker.IsDone():
        return None
    shape = maker.Shape()
    names: list[NamedFace] = carry(body.faces, MakerHistory(maker))
    for name, edge in items:
        for made in shape_list(maker.Generated(edge)):
            if made.ShapeType() == TopAbs_FACE:
                names.append((f"{fid}/chamfer/{name}", TopoDS.Face(made)))
    result = NamedShape(shape, restrict(names, shape, f"{fid}/corner"))
    return result if is_valid(body, result) and not breaks_solid(body, result) else None


def _largest(
    fid: str, body: NamedShape, item: tuple[str, TopoDS_Edge], size: Sizes
) -> float | None:
    """The largest scale below 1 at which ``item`` alone works, or None."""
    from fdcad.core.features.fillet import SMALLEST_SHARE

    low, high, best = 0.0, 1.0, None
    for _ in range(_SEARCH_STEPS):
        middle = (low + high) / 2
        if middle < SMALLEST_SHARE:  # D1043: no search among tiny bevels
            break
        if bevel(fid, body, [item], size.scaled(middle)) is not None:
            best, low = middle, middle
        else:
            high = middle
    return best


def pinpoint_chamfer(
    feature: Feature,
    body: NamedShape,
    items: list[tuple[str, TopoDS_Edge]],
    size: Sizes,
    attempt: Callable[[list[tuple[str, TopoDS_Edge]]], NamedShape | None],
) -> PartialResultError:
    """Find failing edges, build the rest and offer fixes (PLAN 5A item 5)."""
    fid, owner = feature.id, feature.name
    failed: list[tuple[str, float | None]] = []
    good: list[tuple[str, TopoDS_Edge]] = []
    for item in items:
        if attempt([item]) is not None:
            good.append(item)
        else:
            failed.append((item[0], _largest(fid, body, item, size)))
    partial = None
    kept: list[tuple[str, TopoDS_Edge]] = []
    for item in good:
        trial = attempt([*kept, item])
        if trial is not None:
            kept.append(item)
            partial = trial
        else:
            failed.append((item[0], None))
    names = [n for n, _s in failed]
    what = "width" if size.param == "width" else "distance"
    place = {n: f"edge {k}" for k, (n, _e) in enumerate(items, 1)}  # words, not stored names

    def largest(s: float) -> str:
        if size.d1 == size.d2:
            return f"largest {what} {size.d1 * s:.3g} mm"
        # The search scales both distances together, so both are given (D2644): the
        # first alone read as if only it had to change.
        return f"largest distances {size.d1 * s:.3g} and {size.d2 * s:.3g} mm"

    details = [f"{place[n]} ({largest(s)})" if s is not None else place[n] for n, s in failed]
    fixes: list[Fix] = []
    if partial is not None and size.kind != "face_face":
        fixes.append(
            Fix(
                f"Chamfer the rest (skip {len(names)} edge{'s' if len(names) != 1 else ''})",
                "skip_items",
                {"feature": fid, "items": names, "keys": ["edges"]},
            )
        )
    scales = [s for _n, s in failed if s is not None]
    if scales and len(scales) == len(failed) and size.d1 == size.d2:
        from fdcad.core.features.fillet import _round_down

        value = _round_down(size.d1 * min(scales))
        fixes.append(
            Fix(
                f"Reduce the {what} to {value:g} mm",
                "set_param",
                {"feature": fid, "param": size.param, "value": value},
            )
        )
    message = (
        f"{owner} failed on {len(names)} of {len(items)} edges: {', '.join(details)}. "
        "The chamfer is larger than the faces next to these edges allow. "
        f"Reduce the {what}, or chamfer the other edges and leave these out."
    )
    return PartialResultError(message, partial, names, fixes)


# Vertex chamfer ---------------------------------------------------------------------


def _corner_cut(
    owner: str, body: NamedShape, vertex: TopoDS_Vertex, distances: list[float], role: str
) -> NamedShape:
    """The small tetrahedron cut off a corner where three straight edges meet."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid, BRepBuilderAPI_Sewing
    from OCP.gp import gp_Pnt

    from fdcad.core.features.solids import polygon_face

    amap = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(body.shape, TopAbs_VERTEX, TopAbs_EDGE, amap)
    edges: list[TopoDS_Edge] = []
    for e in shape_list(amap.FindFromKey(vertex)):
        edge = TopoDS.Edge(e)
        if not any(edge.IsSame(x) for x in edges):
            edges.append(edge)
    if len(edges) != 3:
        raise FeatureError(
            f"{owner}: a vertex chamfer needs a corner where exactly three edges meet. "
            "Pick another vertex."
        )
    edges.sort(key=lambda e: body.edge_name(e) or "")
    p = BRep_Tool.Pnt_s(vertex)
    corner = (p.X(), p.Y(), p.Z())
    points = []
    for edge, d in zip(edges, distances, strict=True):
        ends = line_ends(edge)
        if ends is None:
            raise FeatureError(
                f"{owner}: a vertex chamfer needs three straight edges at the corner. "
                "Pick another vertex."
            )
        a, b = ends
        far = b if gp_Pnt(*a).Distance(p) < gp_Pnt(*b).Distance(p) else a
        span = gp_Pnt(*far).Distance(p)
        if d >= span - 1e-6:
            raise FeatureError(
                f"{owner}: a vertex distance is as long as its edge. Use a smaller distance."
            )
        t = d / span
        points.append(tuple(corner[i] + (far[i] - corner[i]) * t for i in range(3)))
    a, b, c = points
    faces = [
        polygon_face([corner, a, b]),
        polygon_face([corner, b, c]),
        polygon_face([corner, c, a]),
        polygon_face([a, b, c]),
    ]
    sewing = BRepBuilderAPI_Sewing(1e-6)
    for face in faces:
        sewing.Add(face)
    sewing.Perform()
    solid = BRepBuilderAPI_MakeSolid(TopoDS.Shell(sewing.SewedShape())).Solid()
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier

    classifier = BRepClass3d_SolidClassifier(solid)
    classifier.PerformInfinitePoint(1e-7)
    from OCP.TopAbs import TopAbs_IN

    if classifier.State() == TopAbs_IN:
        solid.Reverse()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape

    from fdcad.core.naming.names import faces_of

    tip = BRepBuilderAPI_MakeVertex(p).Vertex()
    slant = [f for f in faces_of(solid) if BRepExtrema_DistShapeShape(tip, f).Value() > 1e-7]
    return NamedShape(solid, [(role, f) for f in slant])


@register
class Chamfer(FeatureType):
    """Bevels edges or corners of the part with flat faces."""

    type_name = "chamfer"
    makes_solid = True
    params = (
        ParamSpec("chamfer_type", choices=CHAMFER_TYPES, default="distance_distance"),
        ParamSpec("distance", kind=Kind.LENGTH),
        ParamSpec("distance2", kind=Kind.LENGTH, optional=True),
        ParamSpec("distance3", kind=Kind.LENGTH, optional=True),
        ParamSpec("angle", kind=Kind.ANGLE, optional=True),
        ParamSpec("method", choices=CHAMFER_METHODS, optional=True),
        ParamSpec("width", kind=Kind.LENGTH, optional=True),
        ParamSpec("flip", default=False, optional=True),
        ParamSpec("equal", default=False, optional=True),
        # TR64 (D1012): partial edges, as for Fillet
        ParamSpec("partial", choices=("distance", "percent", "reference"), optional=True),
        ParamSpec("start_distance", kind=Kind.LENGTH, optional=True),
        ParamSpec("end_distance", kind=Kind.LENGTH, optional=True),
        ParamSpec("start_percent", kind=Kind.NUMBER, optional=True),
        ParamSpec("end_percent", kind=Kind.NUMBER, optional=True),
        ParamSpec("partial_flip", default=False, optional=True),
        ParamSpec("tangent_propagation", default=True, optional=True),  # TR131 (D1400)
        ParamSpec("corner", choices=("patch", "mitre", "blend"), optional=True),  # TR321
    )

    def _items(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[list[tuple[str, TopoDS_Edge]], list[Issue]]:
        body = require_body(feature, ctx)
        items: list[tuple[str, TopoDS_Edge]] = []
        issues: list[Issue] = []
        if feature.refs.get("edges"):
            items, issues = resolve_edges(feature, ctx, "edges", pieces=True)
        faces, more = resolve_faces(feature, ctx, "faces", required=False)
        issues.extend(more)
        for _name, face in faces:
            for edge in edges_of(face):
                name = body.edge_name(edge)
                if name is not None and not any(edge.IsSame(e) for _n, e in items):
                    items.append((name, edge))
        if not items:
            raise FeatureError(f"{feature.name}: nothing to chamfer. Pick edges or faces.")
        return items, issues

    def _vertices(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        from fdcad.core.features.solids import compound
        from fdcad.core.naming.resolve import resolve_vertex

        body = require_body(feature, ctx)
        refs = feature.refs.get("vertices")
        if not isinstance(refs, list) or not refs:
            raise FeatureError(f"{feature.name}: no vertex is picked. Pick a corner in the view.")
        d1 = length(feature, "distance", "distance")
        if feature.params.get("equal") is True:
            distances = [d1, d1, d1]
        else:
            distances = [
                d1,
                length(feature, "distance2", "second distance"),
                length(feature, "distance3", "third distance"),
            ]
        from OCP.gp import gp_Pnt
        from OCP.TopExp import TopExp_Explorer

        cuts: list[NamedShape] = []
        issues: list[Issue] = []
        lost: list[str] = []
        for ref in refs:
            name = str(ref.get("name", "")) if isinstance(ref, dict) else ""
            try:
                point, found = resolve_vertex(body, ref, feature.name)
            except FeatureError:
                lost.append(name)
                continue
            issues.extend(found)
            explorer = TopExp_Explorer(body.shape, TopAbs_VERTEX)
            vertex = None
            target = gp_Pnt(*point)
            while explorer.More():
                v = TopoDS.Vertex(explorer.Current())
                if BRep_Tool.Pnt_s(v).Distance(target) < 1e-6:
                    vertex = v
                    break
                explorer.Next()
            if vertex is None:
                lost.append(name)
                continue
            label = body.vertex_name(vertex) or name
            role = f"{feature.id}/chamfer/{label}"
            cuts.append(_corner_cut(feature.name, body, vertex, distances, role))
        if lost:
            raise FeatureError(lost_message(feature, ctx, lost, "item(s)"), highlight=lost)
        tool = NamedShape(compound([c.shape for c in cuts]), [nf for c in cuts for nf in c.faces])
        return combine(feature.id, feature.name, body, tool, "cut"), issues

    def _build(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        if feature.params.get("chamfer_type") == "vertex":
            return self._vertices(feature, ctx)
        body = require_body(feature, ctx)
        size = sizes(feature)
        if size.kind == "face_face":
            sets, issues = face_sets(
                feature, ctx, ("faces1", "faces2"), ("Face Set 1", "Face Set 2")
            )
            size.first_faces = [f for _n, f in sets[0]]
            items = shared_edges(feature.name, body, size.first_faces, [f for _n, f in sets[1]])
        else:
            items, issues = self._items(feature, ctx)
        if feature.params.get("partial") in ("distance", "percent", "reference"):  # TR64
            if size.kind != "distance_distance" or size.method != "symmetric":
                raise FeatureError(
                    f"{feature.name}: partial edges work with a symmetric Distance Distance "
                    "chamfer. Choose it, or turn off Partial Edges."
                )
            from fdcad.core.features.fillet_partial import partial_chamfer

            ends = None
            if feature.params.get("partial") == "reference":  # TR64 (D1401)
                from fdcad.core.features.partial_refs import end_picks

                ends, found = end_picks(feature, ctx)
                issues = issues + found
            return partial_chamfer(feature, body, items, size.d1, ends), issues
        if feature.params.get("tangent_propagation") is False and size.kind != "face_face":
            done = self._unpropagated(feature, body, items, size)
            if done is not None:
                return done, issues

        def attempt(chosen: list[tuple[str, TopoDS_Edge]]) -> NamedShape | None:
            return bevel(feature.id, body, chosen, size)

        result = attempt(items)
        if result is None:
            raise pinpoint_chamfer(feature, body, items, size, attempt)
        if feature.params.get("corner") == "mitre":  # TR321 (D1812)
            from fdcad.core.features.chamfer_corners import mitre

            result, more = mitre(feature.id, feature.name, body, result)
            issues = issues + more
        elif feature.params.get("corner") == "blend":  # TR321 (D2304)
            from fdcad.core.features.chamfer_corners import blend

            result, more = blend(feature.id, feature.name, body, result)
            issues = issues + more
        return result, issues

    def _unpropagated(
        self, feature: Feature, body: NamedShape, items: list[tuple[str, TopoDS_Edge]], size: Sizes
    ) -> NamedShape | None:
        """Tangent Propagation off (TR131, D1400): the bevel stops at each smooth join.

        None when no picked edge has a smooth join, so the usual path runs."""
        from fdcad.core.features.fillet_tangent import (
            find_again,
            middle,
            round_joined,
            split_items,
        )

        joined, plain = split_items(body, items)
        if not joined:
            return None
        if size.kind != "distance_distance" or size.method != "symmetric":
            raise FeatureError(
                f"{feature.name}: with Tangent Propagation off the chamfer must be a symmetric "
                "Distance Distance chamfer. Choose it, or turn on Tangent Propagation."
            )
        current = round_joined(
            feature.id,
            feature.name,
            body,
            joined,
            "chamfer",
            lambda _name: size.d1,
            lambda _name: None,
            chamfer=True,
        )
        rest: list[tuple[str, TopoDS_Edge]] = []
        by_name = dict(items)
        for name in plain:
            edge = find_again(current, middle(by_name[name]))
            if edge is None:
                raise FeatureError(
                    f"{feature.name}: edge {name} was swallowed by the bevels next to it. "
                    "Reduce the distance, or turn on Tangent Propagation."
                )
            rest.append((name, edge))
        if not rest:
            return current
        result = bevel(feature.id, current, rest, size)
        if result is None:
            raise pinpoint_chamfer(
                feature, current, rest, size, lambda c: bevel(feature.id, current, c, size)
            )
        return result

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Bevel the edges or corners, or fail with the items that do not work."""
        result, issues = self._build(feature, ctx)
        issues = issues + check_result(feature.id, feature.name, ctx.body, result, None)
        return FeatureResult(body=result, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The new and changed faces, for the preview."""
        body = require_body(feature, ctx)
        try:
            result, _issues = self._build(feature, ctx)
        except PartialResultError as exc:
            if exc.partial is not None:
                exc.partial = changed_faces(body.shape, exc.partial, feature.id)
            raise
        return changed_faces(body.shape, result, feature.id)
