"""Kernel helpers shared by the direct editing features (PHASE3_SPEC P3.1, DECISIONS D232).

Move Face, Delete Face and the face based patterns and mirrors all start
from a list of picked faces on the finished part. The methods, each chosen
because OpenCascade does it reliably:

- ``patch``: remove faces and grow the neighbours until they meet
  (``BRepAlgoAPI_Defeaturing``). Used by Delete and Patch, and to find the
  volume a group of faces encloses.
- ``offset_faces``: move faces along their own normals by per face distances
  while the neighbours stretch (``BRepOffset_MakeOffset`` in skin mode with
  intersection joins). Used by Offset, and by Translate when every picked face
  is flat: moving a flat face by a vector is the same as offsetting it by the
  vector's normal part, since its neighbours decide its outline.
- ``tilt_faces``: turn flat faces about the line where the old and the new
  plane meet (``BRepOffsetAPI_DraftAngle``). Used by Rotate for flat faces.
- ``feature_volumes`` and ``move_volumes``: the material a face group adds
  (a boss) and the material it removes (a hole or pocket), found by patching
  the group away. Moving or copying the group moves those volumes and adds
  or cuts them again. Used by Translate and Rotate when the faces are curved,
  by Copy, and by face patterns and mirrors.

Kernel exceptions never escape these helpers: they raise FeatureError with a
message that names the face and says what to do (CLAUDE.md rule 7).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Any

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Defeaturing
from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.GeomAbs import GeomAbs_Intersection
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt, gp_Trsf
from OCP.TopAbs import TopAbs_FACE, TopAbs_FORWARD, TopAbs_REVERSED
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

from fdcad.core.features.base import BuildContext, FeatureError, Issue, Vec3
from fdcad.core.features.booleans import result_shape
from fdcad.core.features.lookup import resolve_face
from fdcad.core.features.solids import (
    FUZZY_TOLERANCE,
    _unify,
    compound,
    solids,
    volume_of,
)
from fdcad.core.naming.names import NamedFace, NamedShape, carry, faces_of, restrict
from fdcad.core.occ import ShapeList, ShapeListMap, ShapeMap, shape_list
from fdcad.core.plane_normal import plane_normal

#: Volumes below this (mm3) count as nothing.
_TINY_VOLUME = 1e-6
#: Faces above which a face move tries a slab before the whole body offset (D1105).
SLAB_FIRST_FACES = 600
_ANGLE_TOL = 1e-9


# References -----------------------------------------------------------------------


def face_refs(refs: Any) -> list[dict[str, Any]]:
    """The face references in a ``refs`` list (other items are skipped)."""
    if not isinstance(refs, list):
        return []
    return [r for r in refs if isinstance(r, dict) and r.get("kind") == "face"]


def resolve_faces(
    ctx: BuildContext, refs: Any, owner: str, what: str = "faces"
) -> tuple[list[TopoDS_Face], list[str], list[Issue]]:
    """Resolve a list of face references on the part before the feature.

    Returns the faces, their stored names (for messages) and any warnings.
    Raises FeatureError when the list is empty or a face is lost.
    """
    items = face_refs(refs)
    if not items:
        raise FeatureError(f"{owner}: pick one or more {what} in the view.")
    faces: list[TopoDS_Face] = []
    names: list[str] = []
    issues: list[Issue] = []
    for ref in items:
        face, found = resolve_face(ctx.body, ref, owner)
        if any(face.IsSame(f) for f in faces):
            continue
        faces.append(face)
        names.append(str(ref.get("name", "")))
        issues.extend(found)
    return faces, names, issues


def short_name(name: str) -> str:
    """A face name as shown in messages."""
    return name or "a face"


# Checks -----------------------------------------------------------------------------


def valid_solid(shape: TopoDS_Shape) -> bool:
    """True when ``shape`` holds at least one solid and the kernel finds it valid."""
    if shape.IsNull() or not solids(shape):
        return False
    if not BRepCheck_Analyzer(shape, True, True).IsValid():
        return False
    return volume_of(shape) > _TINY_VOLUME


def _same_solid_count(before: TopoDS_Shape, after: TopoDS_Shape) -> bool:
    return len(solids(before)) == len(solids(after))


class _History:
    """Adapts a kernel history (Modified, IsDeleted) to what ``carry`` needs."""

    def __init__(
        self, modified: Callable[[TopoDS_Shape], ShapeList], deleted: Callable[[TopoDS_Shape], bool]
    ) -> None:
        self._modified, self._deleted = modified, deleted

    def Modified(self, shape: TopoDS_Shape, /) -> ShapeList:  # noqa: N802
        return self._modified(shape)

    def IsRemoved(self, shape: TopoDS_Shape, /) -> bool:  # noqa: N802
        return self._deleted(shape)


def _finish(fid: str, named: list[NamedFace], shape: TopoDS_Shape) -> NamedShape:
    """Merge faces that now lie on one surface and keep the names."""
    return _unify(NamedShape(shape, restrict(named, shape, fid)), fid)


# Patch ------------------------------------------------------------------------------


def patch(
    body: NamedShape, faces: Sequence[TopoDS_Face], fid: str, owner: str, labels: Sequence[str]
) -> NamedShape:
    """Remove ``faces`` and grow the neighbouring faces until they meet (Delete and Patch).

    On a part of several bodies only the body holding the faces is worked on (D1101):
    the kernel rebuilds every body it is given, and two bodies whose faces touch could
    come back split another way, so the faces of bodies nobody picked were renamed and
    a rebuild from the cache differed from a full one.

    Raises FeatureError naming the faces when the kernel cannot close the gap.
    """
    from fdcad.core.features.bodies import in_body_of, solid_of_face

    if faces and len(solids(body.shape)) > 1:
        index = solid_of_face(body.shape, faces[0])
        if index >= 0 and all(solid_of_face(body.shape, f) == index for f in faces[1:]):
            return in_body_of(
                body, faces[0], fid, lambda one: _patch_part(one, faces, fid, owner, labels)
            )
    return _patch_part(body, faces, fid, owner, labels)


#: Faces round a gap that grow on within this angle of the removed faces' normal only
#: widen into a tube (D2608): cos 5 degrees.
STRAIGHT_ON = math.cos(math.radians(5.0))


def grows_straight_on(shape: TopoDS_Shape, faces: Sequence[TopoDS_Face]) -> bool:
    """True when the faces round ``faces`` cannot close the gap (D2608).

    Delete and Patch grows each face next to the gap across its edge. When every one
    of them grows straight on along the removed faces' outward normal, and none of
    them goes round the gap (as the top of a plate goes round a hole), they only make
    an open tube: the end cap of a boss or a loft. The kernel then fails, but on the
    spline sides of a loft it took three to four minutes to find that out.
    """
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.BRepTools import BRepTools
    from OCP.gp import gp_Pnt2d, gp_Vec
    from OCP.ShapeAnalysis import ShapeAnalysis_Surface
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_IN

    from fdcad.core.features.hole import outward_normal

    removed = ShapeMap()
    for face in faces:
        removed.Add(face)
    around = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_FACE, around)
    seen = 0
    for i in range(1, around.Extent() + 1):
        owners = [TopoDS.Face(f) for f in shape_list(around.FindFromIndex(i))]
        gone = [f for f in owners if removed.Contains(f)]
        kept = [f for f in owners if not removed.Contains(f)]
        if len(gone) != 1 or len(kept) != 1:
            continue  # inside the removed faces, or not on the gap at all
        edge = TopoDS.Edge(around.FindKey(i))
        face, neighbour = gone[0], kept[0]
        outer = BRepTools.OuterWire_s(neighbour)
        wire_edges = ShapeMap()
        TopExp.MapShapes_s(outer, TopAbs_EDGE, wire_edges)
        if not wire_edges.Contains(edge):
            return False  # the neighbour goes round the gap and can cover it
        curve = BRepAdaptor_Curve(edge)
        mid = (curve.FirstParameter() + curve.LastParameter()) / 2
        point, tangent = gp_Pnt(), gp_Vec()
        curve.D1(mid, point, tangent)
        normals = []
        for f in (face, neighbour):
            uv = ShapeAnalysis_Surface(BRep_Tool.Surface_s(f)).ValueOfUV(point, 1e-7)
            normals.append(outward_normal(f, uv.X(), uv.Y()))
        n_face, n_next = normals
        if n_face is None or n_next is None or tangent.Magnitude() < 1e-12:
            return False
        grow = tangent.Crossed(gp_Vec(*n_next))
        if grow.Magnitude() < 1e-9:
            return False
        grow.Normalize()
        # A point a little way back from the edge must be on the neighbour; ahead of it
        # may be off the end of its surface, where a projection comes back to the edge.
        step = 1e-3 * max(1.0, curve.LastParameter() - curve.FirstParameter())
        behind = point.Translated(grow.Multiplied(-step))
        uv = ShapeAnalysis_Surface(BRep_Tool.Surface_s(neighbour)).ValueOfUV(behind, 1e-7)
        inside = BRepClass_FaceClassifier(neighbour, gp_Pnt2d(uv.X(), uv.Y()), 1e-7)
        if inside.State() != TopAbs_IN:
            grow.Reverse()  # that way was into the neighbour, not out across the edge
        if grow.Dot(gp_Vec(*n_face)) < STRAIGHT_ON:
            return False
        seen += 1
    return seen > 0


def _patch_part(
    body: NamedShape, faces: Sequence[TopoDS_Face], fid: str, owner: str, labels: Sequence[str]
) -> NamedShape:
    if slow_for_kernel(body.shape) and grows_straight_on(body.shape, faces):
        # Only where the kernel takes minutes to fail (D2608): on plain faces it
        # answers at once, and a boss top alone can still go (it takes the boss with
        # it), which face patterns of a boss top rely on (D2613).
        raise _cannot_close(owner, labels)
    # The kernel's defeaturing has no safe mode in this build (D1067), so it is given a
    # copy of the body, as Heal Edges is (D1066): the body shares its faces, edges and
    # corners with the results kept for earlier features, and the tool may write into
    # what it is given (D2642).
    copy = _Copied(body)
    faces = [copy.face(f) for f in faces]
    body = copy.body
    op = BRepAlgoAPI_Defeaturing()
    op.SetShape(body.shape)
    for face in faces:
        op.AddFaceToRemove(face)
    op.SetRunParallel(True)
    op.SetToFillHistory(True)
    try:
        op.Build()
        ok = op.IsDone()
        shape = result_shape(op) if ok else None
    except Exception:  # kernel failure: report it as a feature error
        ok, shape = False, None
    if ok and shape is not None:
        # The kernel may hand back the part unchanged with a warning: every picked
        # face must really be gone.
        ok = not any(_contains(shape, f) for f in faces) and not _any_still_there(shape, faces)
    if not ok or shape is None or not valid_solid(shape):
        raise _cannot_close(owner, labels)
    if _same_volume(body.shape, shape):
        # The picked faces are gone, but another face of the same hole or boss grew
        # back into their place, so no material came or went (D1104): a hole whose wall
        # was in two faces, one picked, stayed open and the feature said it was done.
        listed = ", ".join(short_name(n) for n in labels)
        raise FeatureError(
            f"{owner} changed nothing: removing {listed} let the faces next to them grow "
            "back into their place. Pick every face of the hole or boss.",
            highlight=list(labels),
        )
    history = op.History()
    named = carry(body.faces, history)
    return _finish(fid, named, shape)


class _Copied:
    """A body copied with its geometry, its faces under their own names (D2642)."""

    def __init__(self, body: NamedShape) -> None:
        self.copier = BRepBuilderAPI_Copy(body.shape, True, False)
        named = [(n, self.face(f)) for n, f in body.faces]
        self.body = NamedShape(self.copier.Shape(), named)

    def face(self, face: TopoDS_Face) -> TopoDS_Face:
        """The copy of ``face``, turned the same way.

        The copier hands back each face turned forward; a reversed face kept that
        way would measure its normal the wrong way round, and the check that a
        removed face did not come back would miss it.
        """
        copied = self.copier.ModifiedShape(face.Oriented(TopAbs_FORWARD))
        return TopoDS.Face(copied.Oriented(face.Orientation()))


def _same_volume(before: TopoDS_Shape, after: TopoDS_Shape) -> bool:
    """True when the two shapes hold the same material, to a part in a billion."""
    a, b = volume_of(before), volume_of(after)
    return abs(a - b) <= 1e-9 * max(abs(a), abs(b), 1.0)


def _any_still_there(shape: TopoDS_Shape, faces: Sequence[TopoDS_Face]) -> bool:
    """True when ``shape`` has a face in the same place as one of ``faces`` (the kernel
    rebuilt it).

    A face matches only when its centre of area is within 1e-3 mm of the stored one,
    and that centre lies inside the face's bounding box. So a face whose box misses
    the stored centre is skipped, and each face left is measured once (D1090): on a
    bike frame of lofted tubes, measuring every face once per removed face took 1.4 s.
    """
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    from fdcad.core.naming.resolve import _POINT_TOL, _matches, face_snapshot

    candidates = faces_of(shape)
    boxes: list[Bnd_Box] = []
    for face in candidates:
        box = Bnd_Box()
        BRepBndLib.Add_s(face, box, False)  # from the geometry: never smaller than the face
        box.Enlarge(2 * _POINT_TOL)
        boxes.append(box)
    measured: dict[int, dict[str, Any]] = {}
    for gone in faces:
        stored = face_snapshot(gone)
        centre = gp_Pnt(*stored["point"])
        for i, (face, box) in enumerate(zip(candidates, boxes, strict=True)):
            if box.IsOut(centre):
                continue
            if i not in measured:
                measured[i] = face_snapshot(face)
            if _matches(stored, measured[i]):
                return True
    return False


def _cannot_close(owner: str, labels: Sequence[str]) -> FeatureError:
    listed = ", ".join(short_name(n) for n in labels)
    return FeatureError(
        f"{owner} failed: the faces around {listed} cannot grow to close the gap. "
        "Pick the whole feature (for example every face of a boss or hole) or pick "
        "fewer faces.",
        highlight=list(labels),
    )


def patch_each(
    body: NamedShape,
    faces: Sequence[TopoDS_Face],
    labels: Sequence[str],
    fid: str,
    owner: str,
) -> list[str]:
    """Labels of the faces that cannot be patched on their own (to pinpoint a failure)."""
    failed: list[str] = []
    for face, label in zip(faces, labels, strict=True):
        try:
            patch(body, [face], fid, owner, [label])
        except FeatureError:
            failed.append(label)
    return failed


# Offset -----------------------------------------------------------------------------


def offset_faces(
    body: NamedShape,
    offsets: Sequence[tuple[TopoDS_Face, float]],
    fid: str,
    owner: str,
    labels: Sequence[str],
) -> NamedShape:
    """Move each face along its outward normal by its distance; the neighbours stretch.

    A positive distance moves a face out of the material (a hole wall offset
    outwards makes the hole smaller). Raises FeatureError when the kernel
    cannot rejoin the faces.
    """
    from OCP.BRepOffset import BRepOffset_MakeOffset, BRepOffset_Skin

    moving = [(f, d) for f, d in offsets if abs(d) > 1e-9]
    if not moving:
        return body
    for (face, distance), label in zip(offsets, labels, strict=False):
        left = radius_after(face, distance)
        if left is not None and left <= 1e-6:
            raise FeatureError(
                f"{owner} failed: {short_name(label)} would shrink to nothing (its radius would "
                f"be {left:.3g} mm). Use a smaller value.",
                highlight=[label],
            )
    if slow_for_kernel(body.shape) and all(_slab_fits(body.shape, f) for f, _d in moving):
        # A slab on each face first on a large body (D1105): the kernel's offset works on
        # every face of the body to move one, which took over three minutes on a part
        # of 5000 faces; where the neighbours meet a face square, a slab added or cut is
        # the same shape. Smaller bodies keep the offset, whose face names rounds made
        # again after the move (Reapply Fillets) rely on, unless they hold free form
        # faces: the offset works on those too, 37 s for the thread of the nut and bolt
        # to move one side of its head (D2612).
        slabbed = _offset_by_slabs(body, moving, fid, owner)
        if slabbed is not None:
            return slabbed
    op = BRepOffset_MakeOffset()
    try:
        op.Initialize(
            body.shape,
            0.0,
            1e-7,
            BRepOffset_Skin,
            False,
            False,
            GeomAbs_Intersection,
            False,
            False,
        )
        for face, distance in moving:
            op.SetOffsetOnFace(face, distance)
        op.MakeOffsetShape()
        ok = op.IsDone()
        raw = result_shape(op) if ok else None
        shape = _as_solid(raw) if raw is not None else None
    except Exception:
        ok, shape = False, None
    if not ok or shape is None or not valid_solid(shape):
        slabbed = _offset_by_slabs(body, moving, fid, owner)
        if slabbed is not None:
            return slabbed
        listed = ", ".join(short_name(n) for n in labels)
        raise FeatureError(
            f"{owner} failed: {listed} cannot move that far, because a neighbouring face "
            "would have to cross another face or leave the body. Use a smaller value.",
            highlight=list(labels),
        )
    if not _same_solid_count(body.shape, shape):
        raise FeatureError(
            f"{owner} failed: moving the faces splits or joins bodies. Use a smaller value.",
            highlight=list(labels),
        )
    named = _carry_by_history(body, op, shape)
    return _finish(fid, named, shape)


def slow_for_kernel(shape: TopoDS_Shape) -> bool:
    """True when the kernel's offset or defeaturing of a few faces of ``shape`` is slow:
    a large body (D1105) or one with free form faces (D2612, D2613)."""
    faces = faces_of(shape)
    if len(faces) > SLAB_FIRST_FACES:
        return True
    from OCP.GeomAbs import (
        GeomAbs_BezierSurface,
        GeomAbs_BSplineSurface,
        GeomAbs_OffsetSurface,
        GeomAbs_OtherSurface,
        GeomAbs_SurfaceOfExtrusion,
        GeomAbs_SurfaceOfRevolution,
    )

    slow = {
        GeomAbs_BezierSurface,
        GeomAbs_BSplineSurface,
        GeomAbs_OffsetSurface,
        GeomAbs_OtherSurface,
        GeomAbs_SurfaceOfExtrusion,
        GeomAbs_SurfaceOfRevolution,
    }
    return any(BRepAdaptor_Surface(f).GetType() in slow for f in faces)


def _slab_fits(body: TopoDS_Shape, face: TopoDS_Face) -> bool:
    """True when a slab gives the moved face exactly: square neighbours (D1105), or a
    flat face whose neighbours are all flat (D2612)."""
    from fdcad.core.features import tapered_slab

    return _square_neighbours(body, face) or tapered_slab.plan(body, face) is not None


def _square_neighbours(body: TopoDS_Shape, face: TopoDS_Face) -> bool:
    """True when every face next to ``face`` meets it at a right angle along their edge."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer

    edge_faces = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(body, TopAbs_EDGE, TopAbs_FACE, edge_faces)

    def normal_at(f: TopoDS_Face, point: gp_Pnt) -> Any:
        from OCP.BRep import BRep_Tool

        projector = GeomAPI_ProjectPointOnSurf(point, BRep_Tool.Surface_s(f))
        if projector.NbPoints() < 1:
            return None
        u, v = projector.LowerDistanceParameters()
        props = BRepLProp_SLProps(BRepAdaptor_Surface(f), u, v, 1, 1e-7)
        return props.Normal() if props.IsNormalDefined() else None

    explorer = TopExp_Explorer(face, TopAbs_EDGE)
    while explorer.More():
        edge = explorer.Current()
        explorer.Next()
        curve = BRepAdaptor_Curve(TopoDS.Edge(edge))
        mid = curve.Value((curve.FirstParameter() + curve.LastParameter()) / 2)
        index = edge_faces.FindIndex(edge)
        if not index:
            return False
        for other in shape_list(edge_faces.FindFromIndex(index)):
            if other.IsSame(face):
                continue
            a, b = normal_at(face, mid), normal_at(TopoDS.Face(other), mid)
            if a is None or b is None or abs(a.Dot(b)) > 1e-6:
                return False
    return True


def _offset_by_slabs(
    body: NamedShape, moving: Sequence[tuple[TopoDS_Face, float]], fid: str, owner: str
) -> NamedShape | None:
    """Offset faces whose neighbours all meet them square, by adding or cutting a thin
    slab on each face (the slab's sides continue the neighbours exactly).

    None when a face does not qualify or the kernel fails, so the caller reports it.
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.BRepOffset import BRepOffset_MakeOffset, BRepOffset_Skin

    from fdcad.core.features import tapered_slab
    from fdcad.core.naming.names import centroid

    current = body
    for face, distance in moving:
        image = face if current is body else _find_image(current, body, face)
        if not _square_neighbours(current.shape, image):
            # A flat face with flat neighbours: the slab from their planes (D2612).
            planned = tapered_slab.plan(current.shape, image)
            built = tapered_slab.slab(planned, distance) if planned is not None else None
            if built is None:
                return None
            slab_shape, far_face = built
            try:
                current = _add_slab(current, image, slab_shape, far_face, distance, fid, owner)
            except FeatureError:
                return None
            continue
        op = BRepOffset_MakeOffset()
        try:
            # A slab grown from the face along its outward normal (out of the material
            # for positive distances), or into the material for negative ones.
            op.Initialize(
                image,
                distance,
                1e-7,
                BRepOffset_Skin,
                False,
                False,
                GeomAbs_Intersection,
                True,
                False,
            )
            op.MakeOffsetShape()
            slab = result_shape(op) if op.IsDone() else None
        except Exception:
            return None
        if slab is None:
            return None
        slab = _as_solid(slab)
        if not solids(slab):
            return None
        far = None
        c = centroid(image)
        # The slab's far face is the one the face's centre reaches when moved by the distance.
        from OCP.BRepLProp import BRepLProp_SLProps
        from OCP.BRepTools import BRepTools as Tools

        umin, umax, vmin, vmax = Tools.UVBounds_s(image)
        props = BRepLProp_SLProps(
            BRepAdaptor_Surface(image), (umin + umax) / 2, (vmin + vmax) / 2, 1, 1e-7
        )
        if not props.IsNormalDefined():
            return None
        n = props.Normal()
        if image.Orientation() == TopAbs_REVERSED:
            n.Reverse()
        p = props.Value()
        target = gp_Pnt(
            p.X() + n.X() * distance, p.Y() + n.Y() * distance, p.Z() + n.Z() * distance
        )
        vertex = BRepBuilderAPI_MakeVertex(target).Vertex()
        for f in faces_of(slab):
            dist = BRepExtrema_DistShapeShape(vertex, f)
            if dist.IsDone() and dist.Value() < 1e-6:
                far = f
                break
        _ = c
        try:
            current = _add_slab(current, image, slab, far, distance, fid, owner)
        except FeatureError:
            return None
    if not valid_solid(current.shape) or not _same_solid_count(body.shape, current.shape):
        return None
    return current


def _add_slab(
    current: NamedShape,
    image: TopoDS_Face,
    slab: TopoDS_Shape,
    far: TopoDS_Face | None,
    distance: float,
    fid: str,
    owner: str,
) -> NamedShape:
    """Add the slab (a positive distance) or cut it; its far face takes the face's names."""
    from fdcad.core.features.booleans import boolean_named

    names = [(n_, far) for n_ in current.names_of(image)] if far is not None else []
    tool = NamedShape(slab, names)
    kept = NamedShape(current.shape, [(n_, f) for n_, f in current.faces if not f.IsSame(image)])
    return boolean_named("fuse" if distance > 0 else "cut", kept, tool, fid, owner)


def radius_after(face: TopoDS_Face, distance: float) -> float | None:
    """The radius a round face has after an offset of ``distance`` along its outward normal.

    None for faces without a radius (flat or free form). For a cone the radius
    at its reference circle is used. A torus reports its tube radius.
    """
    from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Sphere, GeomAbs_Torus

    surface = BRepAdaptor_Surface(face)
    kind = surface.GetType()
    if kind == GeomAbs_Cylinder:
        radius, direct = surface.Cylinder().Radius(), surface.Cylinder().Position().Direct()
    elif kind == GeomAbs_Sphere:
        radius, direct = surface.Sphere().Radius(), surface.Sphere().Position().Direct()
    elif kind == GeomAbs_Torus:
        radius, direct = surface.Torus().MinorRadius(), surface.Torus().Position().Direct()
    elif kind == GeomAbs_Cone:
        radius, direct = surface.Cone().RefRadius(), surface.Cone().Position().Direct()
        if radius <= 1e-9:
            return None
    else:
        return None
    # On a right handed frame the surface normal points away from the axis; a
    # reversed face has its material outside, so its outward normal points at the
    # axis. A mirror copy makes the frame left handed, which turns the normal round
    # (D721).
    toward_axis = (face.Orientation() == TopAbs_REVERSED) == direct
    return float(radius - distance if toward_axis else radius + distance)


def _as_solid(shape: TopoDS_Shape) -> TopoDS_Shape:
    """The offset result as solids: the kernel returns closed shells in skin mode."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid
    from OCP.ShapeFix import ShapeFix_Solid
    from OCP.TopAbs import TopAbs_SHELL
    from OCP.TopExp import TopExp_Explorer

    found = solids(shape)
    if not found:
        explorer = TopExp_Explorer(shape, TopAbs_SHELL)
        while explorer.More():
            maker = BRepBuilderAPI_MakeSolid(TopoDS.Shell(explorer.Current()))
            fixer = ShapeFix_Solid(maker.Solid())
            fixer.Perform()
            found.extend(solids(fixer.Solid()))
            explorer.Next()
    if len(found) == 1:
        return found[0]
    return compound(found) if found else shape


def _carry_by_history(body: NamedShape, op: Any, shape: TopoDS_Shape) -> list[NamedFace]:
    """Carry names through an offset: the kernel's image of each face, else its own face."""
    fmap = ShapeMap()
    TopExp.MapShapes_s(shape, TopAbs_FACE, fmap)

    def modified(face: TopoDS_Shape) -> ShapeList:
        out = ShapeList()
        try:
            images = shape_list(op.Modified(face)) + shape_list(op.Generated(face))
        except Exception:
            images = []
        for image in images:
            if image.ShapeType() == TopAbs_FACE and fmap.Contains(image):
                out.Append(image)
        return out

    def deleted(face: TopoDS_Shape) -> bool:
        return not fmap.Contains(face) and modified(face).Size() == 0

    return carry(body.faces, _History(modified, deleted))


def outward_normal(face: TopoDS_Face) -> Vec3 | None:
    """Outward unit normal of a flat face, or None for a curved face."""
    return plane_normal(face)


# Tilt -------------------------------------------------------------------------------


def tilt_faces(
    body: NamedShape,
    faces: Sequence[TopoDS_Face],
    trsf: gp_Trsf,
    fid: str,
    owner: str,
    labels: Sequence[str],
) -> NamedShape:
    """Turn flat faces to the planes ``trsf`` takes them to; the neighbours stretch.

    Each face turns about the line where its old and new planes meet. A face
    whose new plane is parallel to the old one is offset instead.
    """
    from OCP.BRepOffsetAPI import BRepOffsetAPI_DraftAngle

    drafts: list[tuple[TopoDS_Face, gp_Dir, float, gp_Pln]] = []
    offsets: list[tuple[TopoDS_Face, float]] = []
    for face, label in zip(faces, labels, strict=True):
        plan = _tilt_plan(face, trsf)
        if plan is None:
            raise FeatureError(
                f"{owner}: {short_name(label)} is curved and cannot be turned on its own. "
                "Pick the whole feature it belongs to.",
                highlight=[label],
            )
        if isinstance(plan, float):
            offsets.append((face, plan))
        else:
            drafts.append((face, *plan))
    current = body
    if drafts:
        op = BRepOffsetAPI_DraftAngle(body.shape)
        try:
            for face, direction, angle, neutral in drafts:
                op.Add(face, direction, angle, neutral, True)
                if not op.AddDone():
                    raise FeatureError(
                        f"{owner} failed: {short_name(_label_of(face, faces, labels))} cannot "
                        "turn that far. Use a smaller angle.",
                        highlight=list(labels),
                    )
            op.Build()
            ok = op.IsDone()
            shape = result_shape(op) if ok else None
        except FeatureError:
            raise
        except Exception:
            ok, shape = False, None
        if not ok or shape is None or not valid_solid(shape):
            listed = ", ".join(short_name(n) for n in labels)
            raise FeatureError(
                f"{owner} failed: the faces next to {listed} cannot follow the turn. "
                "Use a smaller angle or pick the whole feature.",
                highlight=list(labels),
            )
        named = carry(body.faces, _image_history(op, shape))
        current = _finish(fid, named, shape)
    if offsets:
        moved = [_find_image(current, body, f) for f, _d in offsets]
        current = offset_faces(
            current,
            [(m, d) for m, (_f, d) in zip(moved, offsets, strict=True)],
            fid,
            owner,
            labels,
        )
    return current


def _label_of(face: TopoDS_Face, faces: Sequence[TopoDS_Face], labels: Sequence[str]) -> str:
    for f, label in zip(faces, labels, strict=True):
        if f.IsSame(face):
            return label
    return ""


def _image_history(op: Any, shape: TopoDS_Shape) -> _History:
    """A history from ``ModifiedShape``: the kernel's image of each face in ``shape``."""
    fmap = ShapeMap()
    TopExp.MapShapes_s(shape, TopAbs_FACE, fmap)

    def modified(face: TopoDS_Shape) -> ShapeList:
        out = ShapeList()
        try:
            image = op.ModifiedShape(face)
        except Exception:
            return out
        if not image.IsNull() and fmap.Contains(image) and not image.IsSame(face):
            out.Append(image)
        return out

    def deleted(face: TopoDS_Shape) -> bool:
        return not fmap.Contains(face) and modified(face).Size() == 0

    return _History(modified, deleted)


def _find_image(after: NamedShape, before: NamedShape, face: TopoDS_Face) -> TopoDS_Face:
    """The face of ``after`` that carries the first name of ``face`` in ``before``."""
    name = before.primary_name(face)
    found = after.face(name) if name is not None else None
    if found is None:
        raise FeatureError("A picked face was lost while moving. Pick the faces again.")
    return found


def _tilt_plan(face: TopoDS_Face, trsf: gp_Trsf) -> tuple[gp_Dir, float, gp_Pln] | float | None:
    """How to bring a flat face to its moved plane: a draft, an offset, or None (curved)."""
    normal = outward_normal(face)
    if normal is None:
        return None
    surface = BRepAdaptor_Surface(face)
    origin = surface.Plane().Location()
    n_old = gp_Dir(*normal)
    n_new = n_old.Transformed(trsf)
    p_new = origin.Transformed(trsf)
    cross = n_old.Crossed(n_new) if not n_old.IsParallel(n_new, _ANGLE_TOL) else None
    if cross is None:
        # Parallel planes: an offset along the old normal (a half turn flips it).
        d = gp_Pnt(origin.XYZ()).Distance(p_new)
        if d < 1e-12:
            return 0.0
        v = p_new.XYZ() - origin.XYZ()
        return float(v.Dot(n_old.XYZ()))
    # The pivot line lies in both planes: solve for one point on it.
    line_dir = cross
    pln_old = gp_Pln(origin, n_old)
    pln_new = gp_Pln(p_new, n_new)
    point = _planes_point(pln_old, pln_new, line_dir)
    # Draft: direction lies in the old face, square to the pivot line, so the
    # face starts parallel to it (angle 0) and the draft turns it about the line.
    direction = line_dir.Crossed(n_old)
    angle = n_old.AngleWithRef(n_new, line_dir)
    neutral = gp_Pln(point, direction)
    return direction, angle, neutral


def _planes_point(a: gp_Pln, b: gp_Pln, along: gp_Dir) -> gp_Pnt:
    """A point on the line where planes ``a`` and ``b`` meet (``along`` is its direction)."""
    na, nb = a.Axis().Direction().XYZ(), b.Axis().Direction().XYZ()
    da = na.Dot(a.Location().XYZ())
    db = nb.Dot(b.Location().XYZ())
    u = along.XYZ()
    # Point = (da * (nb x u) + db * (u x na)) / (na . (nb x u))
    nb_u = nb.Crossed(u)
    u_na = u.Crossed(na)
    denom = na.Dot(nb_u)
    p = (nb_u.Multiplied(da) + u_na.Multiplied(db)).Divided(denom)
    return gp_Pnt(p)


# Volumes ----------------------------------------------------------------------------


def _corners(box: Any) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """The low and high corners of a bounding box."""
    a, b = box.CornerMin(), box.CornerMax()
    return (a.X(), a.Y(), a.Z()), (b.X(), b.Y(), b.Z())


def _near_difference(
    before: TopoDS_Shape, after: TopoDS_Shape, faces: Sequence[TopoDS_Face]
) -> tuple[TopoDS_Shape | None, TopoDS_Shape | None] | None:
    """``before`` cut by ``after`` and the reverse, worked out only in a box round the
    removed ``faces`` (D1090), or None to work them out on the whole part.

    The two shapes share every face away from the patch, and the kernel is slowest on
    such a pair: on a bike frame the two whole cuts took 4.7 s. Patching changes the part
    only where the faces were, and the change is in one piece, so when no piece of the
    difference reaches a wall of the box, the box held all of it.
    """
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    from fdcad.core.features.booleans import boolean_shape

    around = Bnd_Box()
    for face in faces:
        BRepBndLib.Add_s(face, around, False)
    if around.IsVoid():
        return None
    (x0, y0, z0), (x1, y1, z1) = _corners(around)
    margin = max(1.0, 0.1 * math.dist((x0, y0, z0), (x1, y1, z1)))
    lo = (x0 - margin, y0 - margin, z0 - margin)
    hi = (x1 + margin, y1 + margin, z1 + margin)
    room = BRepPrimAPI_MakeBox(gp_Pnt(*lo), gp_Pnt(*hi)).Shape()
    near_before = boolean_shape("common", before, room)
    near_after = boolean_shape("common", after, room)
    if near_before is None or near_after is None:
        return None
    added = boolean_shape("cut", near_before, near_after)
    removed = boolean_shape("cut", near_after, near_before)
    if added is None or removed is None:
        return None
    wall = 1e-3 * margin
    found = False
    for piece in (added, removed):
        for solid in solids(piece):
            if volume_of(solid) <= _TINY_VOLUME:
                continue
            found = True
            box = Bnd_Box()
            BRepBndLib.AddOptimal_s(solid, box, False, False)
            low, high = _corners(box)
            if any(v <= w + wall for v, w in zip(low, lo, strict=True)) or any(
                v >= w - wall for v, w in zip(high, hi, strict=True)
            ):
                return None  # the change reaches past the box
    if not found:
        return None  # patching always changes something: it must lie outside the box
    return added, removed


def feature_volumes(
    body: NamedShape, faces: Sequence[TopoDS_Face], fid: str, owner: str, labels: Sequence[str]
) -> tuple[NamedShape, TopoDS_Shape | None, TopoDS_Shape | None]:
    """The part with the face group patched away, plus the material the group adds
    (a boss) and the material it removes (a hole or pocket), each None when empty."""
    from fdcad.core.features.booleans import boolean_shape

    patched = patch(body, faces, fid, owner, labels)
    near = _near_difference(body.shape, patched.shape, faces)
    if near is not None:
        added, removed = near
    else:
        added = boolean_shape("cut", body.shape, patched.shape)
        removed = boolean_shape("cut", patched.shape, body.shape)
    return (
        patched,
        added if added is not None and volume_of(added) > _TINY_VOLUME else None,
        removed if removed is not None and volume_of(removed) > _TINY_VOLUME else None,
    )


def move_volumes(
    base: NamedShape,
    added: TopoDS_Shape | None,
    removed: TopoDS_Shape | None,
    trsfs: Sequence[gp_Trsf],
    fid: str,
    owner: str,
    role: str,
    faces_of_added: list[NamedFace] | None = None,
) -> NamedShape:
    """Add every moved copy of ``added`` to ``base`` and cut every moved ``removed``.

    All copies go into one compound and one boolean each (PLAN 11.3 item 4).
    New faces are called ``<fid>/<role><k>/face#j``.
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform

    from fdcad.core.features.booleans import boolean_named

    current = base
    for volume, op in ((removed, "cut"), (added, "fuse")):
        if volume is None:
            continue
        pieces: list[TopoDS_Shape] = []
        names: list[NamedFace] = []
        for k, trsf in enumerate(trsfs, start=1):
            moved = BRepBuilderAPI_Transform(volume, trsf, True).Shape()
            pieces.append(moved)
            for j, face in enumerate(faces_of(moved), start=1):
                names.append((f"{fid}/{role}{k}/face#{j}", face))
        tool = NamedShape(compound(pieces), names)
        current = boolean_named(op, current, tool, fid, owner)
    return current


def rotation(axis_point: Vec3, axis_dir: Vec3, angle: float) -> gp_Trsf:
    """A turn of ``angle`` radians about an axis (right hand rule)."""
    from OCP.gp import gp_Ax1

    trsf = gp_Trsf()
    trsf.SetRotation(gp_Ax1(gp_Pnt(*axis_point), gp_Dir(*axis_dir)), angle)
    return trsf


def translation(delta: Vec3) -> gp_Trsf:
    """A move by ``delta`` mm."""
    from OCP.gp import gp_Vec

    trsf = gp_Trsf()
    trsf.SetTranslation(gp_Vec(*delta))
    return trsf


def degrees(value: float) -> str:
    """An angle in degrees for messages."""
    return f"{math.degrees(value):g} degrees"


__all__ = [
    "FUZZY_TOLERANCE",
    "face_refs",
    "feature_volumes",
    "move_volumes",
    "offset_faces",
    "outward_normal",
    "patch",
    "patch_each",
    "resolve_faces",
    "rotation",
    "tilt_faces",
    "translation",
    "valid_solid",
]


def _moved_face(face: TopoDS_Face, trsf: gp_Trsf) -> TopoDS_Face:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform

    return TopoDS.Face(BRepBuilderAPI_Transform(face, trsf, True).Shape())


def rename_moved(
    result: NamedShape,
    before: NamedShape,
    faces: Sequence[TopoDS_Face],
    trsf: gp_Trsf,
    prefix: str = "",
) -> NamedShape:
    """Give the moved copies of ``faces`` the names of the faces they came from.

    A face of ``result`` that lies exactly where a picked face moves to takes
    that face's names (with ``prefix`` for copies), first in its name list.
    """
    from fdcad.core.naming.resolve import _matches, face_snapshot

    extra: list[NamedFace] = []
    current = faces_of(result.shape)
    for face in faces:
        target = face_snapshot(_moved_face(face, trsf))
        found = [f for f in current if _matches(target, face_snapshot(f))]
        if len(found) != 1:
            continue
        for name in before.names_of(face):
            extra.append((prefix + name, found[0]))
    if not extra:
        return result
    kept = [(n, f) for n, f in result.faces if not any(n == e for e, _ in extra)]
    ordered = extra + kept
    return NamedShape(result.shape, restrict(ordered, result.shape, "moved"))


def on_target(
    result: NamedShape, before: NamedShape, faces: Sequence[TopoDS_Face], trsf: gp_Trsf
) -> bool:
    """True when every flat picked face now lies on the plane ``trsf`` takes it to."""
    for face in faces:
        normal = outward_normal(face)
        if normal is None:
            continue
        name = before.primary_name(face)
        image = result.face(name) if name is not None else None
        if image is None:
            return False
        moved = outward_normal(_moved_face(face, trsf))
        got = outward_normal(image)
        if moved is None or got is None:
            return False
        if sum(a * b for a, b in zip(moved, got, strict=True)) < 1 - 1e-7:
            return False
        p = BRepAdaptor_Surface(image).Plane()
        q = BRepAdaptor_Surface(_moved_face(face, trsf)).Plane()
        if p.Distance(q.Location()) > 1e-6:
            return False
    return True


# Fill -------------------------------------------------------------------------------


def fill(
    body: NamedShape,
    faces: Sequence[TopoDS_Face],
    tangent: bool,
    fid: str,
    owner: str,
    labels: Sequence[str],
) -> NamedShape:
    """Remove ``faces`` and close each opening with one new smooth face (Delete and Fill).

    With ``tangent`` the new face meets its neighbours smoothly (G1), else it
    only touches them (G0). New faces are called ``<fid>/fill`` (``#k`` for
    several openings).
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid, BRepBuilderAPI_Sewing
    from OCP.BRepFill import BRepFill_Filling
    from OCP.GeomAbs import GeomAbs_C0, GeomAbs_G1
    from OCP.ShapeAnalysis import ShapeAnalysis_FreeBounds
    from OCP.ShapeFix import ShapeFix_Solid
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_SHELL, TopAbs_WIRE
    from OCP.TopExp import TopExp_Explorer

    listed = ", ".join(short_name(n) for n in labels)

    def failed(reason: str) -> FeatureError:
        return FeatureError(
            f"{owner} failed: the opening left by {listed} {reason}. "
            "Try Delete and Patch, untick Tangent fill, or pick fewer faces.",
            highlight=list(labels),
        )

    owners = [s for s in solids(body.shape) if any(_contains(s, f) for f in faces)]
    if len(owners) != 1:
        raise FeatureError(f"{owner}: pick faces of one body at a time.", highlight=list(labels))
    target = owners[0]
    removed = ShapeMap()
    for f in faces:
        removed.Add(f)
    kept = [f for f in faces_of(target) if not removed.Contains(f)]
    if not kept:
        raise FeatureError(f"{owner}: that would delete every face of the body. Pick fewer faces.")
    try:
        sewing = BRepBuilderAPI_Sewing(1e-6)
        for f in kept:
            sewing.Add(f)
        sewing.Perform()
        shell = sewing.SewedShape()
        bounds = ShapeAnalysis_FreeBounds(shell, 1e-6, False, False)
        wires = bounds.GetClosedWires()
    except Exception as exc:
        raise failed("could not be found") from exc
    edge_faces = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(shell, TopAbs_EDGE, TopAbs_FACE, edge_faces)
    patches: list[TopoDS_Face] = []
    explorer = TopExp_Explorer(wires, TopAbs_WIRE)
    while explorer.More():
        wire = explorer.Current()
        explorer.Next()
        filling = BRepFill_Filling()
        edges = TopExp_Explorer(wire, TopAbs_EDGE)
        while edges.More():
            edge = TopoDS.Edge(edges.Current())
            edges.Next()
            index = edge_faces.FindIndex(edge)
            neighbour = None
            if index:
                around = shape_list(edge_faces.FindFromIndex(index))
                neighbour = TopoDS.Face(around[0]) if around else None
            if tangent and neighbour is not None:
                filling.Add(edge, neighbour, GeomAbs_G1, True)
            else:
                filling.Add(edge, GeomAbs_C0, True)
        try:
            filling.Build()
            ok = filling.IsDone()
        except Exception:
            ok = False
        if not ok:
            raise failed("could not be filled with one smooth face")
        patches.append(filling.Face())
    if not patches:
        raise failed("is not a closed loop of edges")
    try:
        sewing = BRepBuilderAPI_Sewing(1e-4)
        sewing.Add(shell)
        for p in patches:
            sewing.Add(p)
        sewing.Perform()
        sewed = sewing.SewedShape()
        shells = TopExp_Explorer(sewed, TopAbs_SHELL)
        if not shells.More():
            raise failed("could not be closed")
        maker = BRepBuilderAPI_MakeSolid(TopoDS.Shell(shells.Current()))
        fixer = ShapeFix_Solid(maker.Solid())
        fixer.Perform()
        solid = fixer.Solid()
    except FeatureError:
        raise
    except Exception as exc:
        raise failed("could not be closed") from exc
    if not valid_solid(solid):
        raise failed("could not be closed into a valid solid")
    # Carry names: sewing keeps or copies the kept faces.
    names: list[NamedFace] = []
    for name, face in body.faces:
        if removed.Contains(face):
            continue
        if not _contains(target, face):
            names.append((name, face))
            continue
        image = sewing.Modified(face)
        if not image.IsNull() and image.ShapeType() == TopAbs_FACE:
            names.append((name, TopoDS.Face(image)))
    fmap = ShapeMap()
    TopExp.MapShapes_s(solid, TopAbs_FACE, fmap)
    for k, p in enumerate(patches, start=1):
        image = sewing.Modified(p)
        label = f"{fid}/fill" if len(patches) == 1 else f"{fid}/fill#{k}"
        if not image.IsNull() and image.ShapeType() == TopAbs_FACE:
            names.append((label, TopoDS.Face(image)))
    others = [s for s in solids(body.shape) if not s.IsSame(target)]
    shape = compound([solid, *others]) if others else solid
    return NamedShape(shape, restrict(names, shape, fid))


def _contains(shape: TopoDS_Shape, sub: TopoDS_Shape) -> bool:
    fmap = ShapeMap()
    TopExp.MapShapes_s(shape, sub.ShapeType(), fmap)
    return bool(fmap.Contains(sub))
