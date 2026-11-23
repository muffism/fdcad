"""Split for printing: cut the part into pieces that fit the printer, with optional
alignment pins or dovetail keys (PLAN Phase 3, PHASE3_SPEC P3.9, DECISIONS D293).

Params:

- ``mode``: ``"auto"`` (default: even cuts along X, Y and Z so every piece fits
  ``build_x`` by ``build_y`` by ``build_z``), ``"planes"`` (cut at
  ``refs.planes``: plane features or flat faces) or ``"sketch"`` (TR181, D2002:
  cut along the curves of the sketch in ``refs.path``, swept through the part
  along the sketch normal, for a stepped or shaped seam; connectors go on its
  flat cut faces).
- ``connector``: ``"none"`` (default), ``"pins"`` or ``"dovetail"``.
- Pins: ``pin_diameter``, ``pin_length`` (lengths). Each pin is its own body,
  half in each piece; both pieces get a hole ``clearance`` wider all round and
  ``clearance`` deeper.
- Dovetail keys: ``key_width`` (at the seam) and ``key_depth`` (into each
  piece). A key is a separate body shaped like two dovetails back to back that
  slides in from the side; its pocket is ``clearance`` larger. ``key_draft``
  (optional angle, TR181, D2002) tapers the key and its pocket along the slide,
  so the key wedges tight as it goes in from the wide end.
- Magnets (TR181, D1211): ``magnet_diameter`` and ``magnet_depth``. A round pocket
  ``magnet_depth`` plus ``clearance`` deep goes into each piece; no body is added.
- Screws (TR181, D1211): ``screw_diameter`` (a hole ``clearance`` wider, right
  through the part along the cut's normal), and a hexagon nut pocket ``nut_size``
  across flats and ``nut_height`` deep where the hole leaves the part on the
  normal's side, both ``clearance`` larger.
- ``clearance`` (length) for all of them.
- ``glue_gap`` (optional length, TR181): each piece on the normal's side of a cut
  is trimmed back this far from the seam, so the joint has room for glue.

Refs: ``planes`` (planes mode) and ``bodies``: optional body references (a face
of each body); without any, every body is cut (D621).

Face roles: ``cut<j>`` for the new faces on cut plane ``j`` (``#k`` when there
are several), ``pin<k>/face<i>`` and ``key<k>/...`` for connector bodies. Faces of
the part keep their names; split faces get ``#1``, ``#2``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from OCP.Bnd import Bnd_Box
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeVertex
from OCP.BRepClass import BRepClass_FaceClassifier
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
from OCP.GeomAbs import GeomAbs_Plane
from OCP.gp import gp_Ax2, gp_Dir, gp_Pln, gp_Pnt, gp_Vec
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_FACE, TopAbs_IN
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureState,
    FeatureType,
    Issue,
    ParamSpec,
    Vec3,
    register,
)
from fdcad.core.features.solids import (
    FUZZY_TOLERANCE,
    bounding_size,
    compound,
    polygon_face,
    solids,
    volume_of,
)
from fdcad.core.naming.names import (
    NamedFace,
    NamedShape,
    carry,
    faces_of,
    order_by_position,
    restrict,
)
from fdcad.core.occ import (
    BRepAlgoAPI_Common,
    BRepAlgoAPI_Cut,
    BRepAlgoAPI_Splitter,
    ShapeList,
    ShapeMap,
)
from fdcad.core.plane_normal import plane_normal
from fdcad.core.units import Kind

CONNECTORS = ("none", "pins", "dovetail", "magnets", "screws")
#: Steepest key draft (TR181, D2002).
MAX_KEY_DRAFT = math.radians(10)
#: Dovetail flank angle from the key's centre line.
DOVETAIL_ANGLE = math.radians(15)
#: Most cut planes one feature may make.
MAX_PLANES = 64
_ON_PLANE = 1e-6


@dataclass
class CutPlane:
    """A cut plane: a point on it and its unit normal."""

    origin: Vec3
    normal: Vec3


@dataclass
class _Sizes:
    """The connector's kind and sizes, as the panel's values give them."""

    kind: str
    width: float
    room: float
    clearance: float
    draft: float
    reach: float
    diameter: float
    half: float
    nut: float
    nut_height: float
    depth: float


def _groups(named: NamedShape, origin: list[int], fid: str) -> list[tuple[int, NamedShape, bool]]:
    """The pieces of ``named`` by the body they came from (``origin`` gives each piece's
    body), in order: the body's index, its pieces with their names, and whether the body
    was cut into more than one piece (D2641). A part of one body is one group, ``named``
    itself, so the kernel calls on it stay as they were."""
    from fdcad.core.features.bodies import sub_body

    order = list(dict.fromkeys(origin))
    if len(order) == 1:
        return [(order[0], named, True)]
    out = []
    for index in order:
        mine = [i for i, o in enumerate(origin) if o == index]
        out.append((index, sub_body(named, mine, fid), len(mine) > 1))
    return out


def _length(feature: Feature, name: str, label: str) -> float:
    value = feature.params.get(name)
    if not isinstance(value, Param) or not value.value > 0:
        raise FeatureError(f"{feature.name}: enter a {label} greater than zero.")
    return value.value


def _box(shape: TopoDS_Shape) -> tuple[Vec3, Vec3]:
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    lo, hi = box.CornerMin(), box.CornerMax()
    return (lo.X(), lo.Y(), lo.Z()), (hi.X(), hi.Y(), hi.Z())


def auto_planes(shape: TopoDS_Shape, build: Vec3) -> list[CutPlane]:
    """Even cuts so each piece's box fits ``build`` in the part's own orientation."""
    lo, hi = _box(shape)
    out = []
    for axis in range(3):
        size = hi[axis] - lo[axis]
        count = max(1, math.ceil(size / build[axis] - 1e-9))
        normal = tuple(1.0 if i == axis else 0.0 for i in range(3))
        for k in range(1, count):
            origin = tuple(lo[i] + (size * k / count if i == axis else 0.0) for i in range(3))
            out.append(CutPlane(origin, normal))  # type: ignore[arg-type]
    return out


def _picked_planes(feature: Feature, ctx: BuildContext) -> list[CutPlane]:
    from fdcad.core.naming.resolve import resolve_face

    owner = feature.name
    refs = feature.refs.get("planes")
    if not isinstance(refs, list) or not refs:
        raise FeatureError(f"{owner}: pick planes or flat faces to cut at.")
    out = []
    for ref in refs:
        if isinstance(ref, dict) and "feature" in ref and "kind" not in ref:
            res = ctx.results.get(str(ref["feature"]))
            if res is None or res.plane is None:
                raise FeatureError(f"{owner}: a cut plane was lost. Pick it again.")
            out.append(CutPlane(res.plane.origin, res.plane.normal))
            continue
        face, _issues = resolve_face(ctx.body, ref, owner)
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Plane:
            raise FeatureError(f"{owner}: a cut face is not flat. Pick flat faces or planes.")
        pln = surface.Plane()
        p, d = pln.Location(), pln.Axis().Direction()
        out.append(CutPlane((p.X(), p.Y(), p.Z()), (d.X(), d.Y(), d.Z())))
    return out


def _tool_face(plane: CutPlane, size: float, over: TopoDS_Shape | None = None) -> TopoDS_Face:
    """A square sheet on ``plane``, ``size`` to each side, standing for the whole plane.
    With ``over`` it is centred on the point of the plane nearest the middle of that
    shape, not on the plane's own origin (D1062): a bar 510 mm from the origin was not
    reached, and the feature said "the cut planes miss the part"."""
    origin = plane.origin
    if over is not None:
        box = Bnd_Box()
        BRepBndLib.Add_s(over, box)
        if not box.IsVoid():
            lo, hi = box.CornerMin(), box.CornerMax()
            mid = ((lo.X() + hi.X()) / 2, (lo.Y() + hi.Y()) / 2, (lo.Z() + hi.Z()) / 2)
            off = sum((m - o) * n for m, o, n in zip(mid, origin, plane.normal, strict=True))
            n = plane.normal
            origin = (mid[0] - off * n[0], mid[1] - off * n[1], mid[2] - off * n[2])
    pln = gp_Pln(gp_Pnt(*origin), gp_Dir(*plane.normal))
    return BRepBuilderAPI_MakeFace(pln, -size, size, -size, size).Face()


def _on_plane(face: TopoDS_Face, plane: CutPlane) -> int:
    """+1 when ``face`` lies on ``plane`` looking along its normal, -1 against, else 0."""
    outward = plane_normal(face)
    if outward is None:
        return 0
    n = plane.normal
    dot = outward[0] * n[0] + outward[1] * n[1] + outward[2] * n[2]
    if abs(abs(dot) - 1) > 1e-7:
        return 0
    loc = BRepAdaptor_Surface(face).Plane().Location()
    gap = sum(
        (c - o) * k for c, o, k in zip((loc.X(), loc.Y(), loc.Z()), plane.origin, n, strict=True)
    )
    if abs(gap) > _ON_PLANE:
        return 0
    return 1 if dot > 0 else -1


def _major_axis(face: TopoDS_Face, normal: Vec3) -> tuple[gp_Pnt, gp_Vec]:
    """Area centre of the face and its longest direction (in the plane)."""
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    centre = props.CentreOfMass()
    axis = props.PrincipalProperties().ThirdAxisOfInertia()
    first = props.PrincipalProperties().FirstAxisOfInertia()
    v = gp_Vec(axis.X(), axis.Y(), axis.Z())
    n = gp_Vec(*normal)
    v = v.Subtracted(n.Multiplied(v.Dot(n)))
    if v.Magnitude() < 1e-9:
        v = gp_Vec(first.X(), first.Y(), first.Z())
        v = v.Subtracted(n.Multiplied(v.Dot(n)))
    if v.Magnitude() < 1e-9:
        v = gp_Vec(gp_Ax2(centre, gp_Dir(n)).XDirection())
    return centre, v.Normalized()


def _extent(face: TopoDS_Face, direction: gp_Vec) -> float:
    from fdcad.core.features.solids import extent_along

    span = extent_along(face, (direction.X(), direction.Y(), direction.Z()))
    return 0.0 if span is None else span[1] - span[0]


def _room(face: TopoDS_Face, point: gp_Pnt) -> float:
    """How far ``point`` is from the edge of ``face``; 0 when it is outside."""
    from OCP.BRep import BRep_Tool
    from OCP.ShapeAnalysis import ShapeAnalysis_Surface
    from OCP.TopAbs import TopAbs_WIRE
    from OCP.TopExp import TopExp_Explorer

    uv = ShapeAnalysis_Surface(BRep_Tool.Surface_s(face)).ValueOfUV(point, 1e-7)
    if BRepClass_FaceClassifier(face, uv, 1e-7).State() != TopAbs_IN:
        return 0.0
    vertex = BRepBuilderAPI_MakeVertex(point).Vertex()
    best = math.inf
    explorer = TopExp_Explorer(face, TopAbs_WIRE)
    while explorer.More():
        dist = BRepExtrema_DistShapeShape(vertex, explorer.Current())
        if dist.IsDone():
            best = min(best, dist.Value())
        explorer.Next()
    return best


def spots(face: TopoDS_Face, normal: Vec3, size: float, room: float) -> list[tuple[gp_Pnt, gp_Vec]]:
    """Connector places on a cut face: its centre, or two along a long face.

    ``size`` is the connector's width; a place needs ``room`` mm to the face's edge.
    Returns (point, long direction) pairs.
    """
    centre, along = _major_axis(face, normal)
    length = _extent(face, along)
    if length > 6 * size:
        offset = along.Multiplied(length / 4)
        candidates = [centre.Translated(offset.Reversed()), centre.Translated(offset)]
    else:
        candidates = [centre]
    return [(p, along) for p in candidates if _room(face, p) >= room]


def _cylinder(point: gp_Pnt, normal: Vec3, diameter: float, half: float) -> TopoDS_Shape:
    n = gp_Vec(*normal)
    start = point.Translated(n.Multiplied(-half))
    return BRepPrimAPI_MakeCylinder(gp_Ax2(start, gp_Dir(n)), diameter / 2, 2 * half).Shape()


def _bowtie(
    point: gp_Pnt,
    normal: Vec3,
    along: gp_Vec,
    width: float,
    depth: float,
    reach: float,
    taper: tuple[float, float, float] | None = None,
) -> TopoDS_Shape:
    """Two dovetails back to back across the plane, pulled ``reach`` both ways across.

    ``taper`` (TR181, D2002) is (start, end, tan of the draft angle): the key runs from
    ``start`` to ``end`` along the slide direction (as distances from ``point``), full
    size at the start and narrower by the draft on every side toward the end."""
    n = gp_Vec(*normal)
    u = along
    slide = n.Crossed(u).Normalized()
    end = width + 2 * depth * math.tan(DOVETAIL_ANGLE)
    corners2d = [
        (-end / 2, -depth), (end / 2, -depth), (width / 2, 0.0),
        (end / 2, depth), (-end / 2, depth), (-width / 2, 0.0),
    ]  # fmt: skip

    def section(at: float, scale: float) -> list[Vec3]:
        base = point.Translated(slide.Multiplied(at))
        return [
            (
                base.X() + scale * (a * u.X() + b * n.X()),
                base.Y() + scale * (a * u.Y() + b * n.Y()),
                base.Z() + scale * (a * u.Z() + b * n.Z()),
            )
            for a, b in corners2d
        ]

    if taper is None:
        face = polygon_face(section(-reach, 1.0))
        return BRepPrimAPI_MakePrism(face, slide.Multiplied(2 * reach)).Shape()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon
    from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections

    start, stop, slope = taper
    scale = 1.0 - (stop - start) * slope / (end / 2)
    if scale < 0.2:
        raise ValueError("the key draft narrows the key to nothing across the part")
    loft = BRepOffsetAPI_ThruSections(True, True)
    for at, k in ((start, 1.0), (stop, scale)):
        poly = BRepBuilderAPI_MakePolygon()
        for q in section(at, k):
            poly.Add(gp_Pnt(*q))
        poly.Close()
        loft.AddWire(poly.Wire())
    loft.Build()
    if not loft.IsDone():
        raise ValueError("the tapered key could not be made")
    return loft.Shape()


def _taper(
    body: TopoDS_Shape, point: gp_Pnt, normal: Vec3, along: gp_Vec, slope: float
) -> tuple[float, float, float] | None:
    """The key's run along its slide direction, 1 mm past the part each way, for a
    draft of ``slope`` (tan of the angle); None without a draft."""
    if slope <= 0:
        return None
    from fdcad.core.features.solids import extent_along

    slide = gp_Vec(*normal).Crossed(along).Normalized()
    direction = (slide.X(), slide.Y(), slide.Z())
    span = extent_along(body, direction)
    if span is None:
        return None
    here = point.X() * direction[0] + point.Y() * direction[1] + point.Z() * direction[2]
    return span[0] - here - 1.0, span[1] - here + 1.0, slope


def _inside(tool: TopoDS_Shape, body: TopoDS_Shape) -> bool:
    """True when ``tool`` lies in the part (its volume is all material)."""
    common = BRepAlgoAPI_Common(tool, body)
    common.SetFuzzyValue(FUZZY_TOLERANCE)
    common.Build()
    return common.IsDone() and abs(volume_of(common.Shape()) - volume_of(tool)) <= 1e-6 * max(
        volume_of(tool), 1.0
    )


def _nut_trap(
    body: TopoDS_Shape, point: gp_Pnt, normal: Vec3, along: gp_Vec, flats: float, height: float
) -> TopoDS_Shape | None:
    """A hexagon pocket ``flats`` across and ``height`` deep, in from where the line
    through ``point`` along ``normal`` last leaves ``body``; None when it never does."""
    from OCP.BRepIntCurveSurface import BRepIntCurveSurface_Inter
    from OCP.gp import gp_Lin

    hits = BRepIntCurveSurface_Inter()
    hits.Init(body, gp_Lin(point, gp_Dir(*normal)), 1e-7)
    far = None
    while hits.More():
        if hits.W() > 1e-6 and (far is None or hits.W() > far):
            far = hits.W()
        hits.Next()
    if far is None:
        return None
    n = gp_Vec(*normal)
    u = gp_Vec(along.X(), along.Y(), along.Z()).Normalized()
    v = n.Crossed(u).Normalized()
    outer = flats / math.sqrt(3)  # corner distance of a hexagon with these flats
    base = point.Translated(n.Multiplied(far - height))
    pts = []
    for k in range(6):
        a = math.radians(60 * k)
        off = u.Multiplied(outer * math.cos(a)).Added(v.Multiplied(outer * math.sin(a)))
        q = base.Translated(off)
        pts.append((q.X(), q.Y(), q.Z()))
    return BRepPrimAPI_MakePrism(polygon_face(pts), n.Multiplied(height + 1.0)).Shape()


@register
class SplitForPrint(FeatureType):
    """Cuts the part into printable pieces with optional connectors."""

    type_name = "split_for_print"
    makes_solid = True
    params = (
        ParamSpec("mode", choices=("auto", "planes", "sketch"), default="auto"),
        ParamSpec("build_x", kind=Kind.LENGTH, optional=True),
        ParamSpec("build_y", kind=Kind.LENGTH, optional=True),
        ParamSpec("build_z", kind=Kind.LENGTH, optional=True),
        ParamSpec("connector", choices=CONNECTORS, default="none"),
        ParamSpec("pin_diameter", kind=Kind.LENGTH, optional=True),
        ParamSpec("pin_length", kind=Kind.LENGTH, optional=True),
        ParamSpec("key_width", kind=Kind.LENGTH, optional=True),
        ParamSpec("key_depth", kind=Kind.LENGTH, optional=True),
        ParamSpec("clearance", kind=Kind.LENGTH, optional=True),
        ParamSpec("magnet_diameter", kind=Kind.LENGTH, optional=True),  # TR181 (D1211)
        ParamSpec("magnet_depth", kind=Kind.LENGTH, optional=True),
        ParamSpec("screw_diameter", kind=Kind.LENGTH, optional=True),
        ParamSpec("nut_size", kind=Kind.LENGTH, optional=True),
        ParamSpec("nut_height", kind=Kind.LENGTH, optional=True),
        ParamSpec("glue_gap", kind=Kind.LENGTH, optional=True),
        ParamSpec("key_draft", kind=Kind.ANGLE, optional=True),  # TR181 (D2002)
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Split, add connectors and check the pieces fit."""
        owner = feature.name
        body = ctx.body
        if body is None:
            raise FeatureError(f"{owner}: the part is empty. Add a body to split first.")
        issues: list[Issue] = []
        whole = body
        indices = list(range(len(solids(body.shape))))
        if feature.refs.get("bodies"):
            from fdcad.core.features.bodies import body_indices, sub_body

            indices, issues = body_indices(ctx, feature.refs["bodies"], owner)
            body = sub_body(whole, indices, feature.id)
        mode = feature.params.get("mode", "auto")
        auto = mode == "auto"
        build: Vec3 | None = None
        if mode == "sketch":  # TR181 (D2002): a stepped or shaped seam along a sketch
            named, planes, origin = self._split_sketch(feature, ctx, body)
            named, extra = self._connectors(feature, body, named, planes, origin)
            issues += extra
            if len(indices) < len(solids(whole.shape)):
                from fdcad.core.features.bodies import join, rest_of

                joined = join([rest_of(whole, indices, feature.id), named], feature.id)
                assert joined is not None
                named = joined
            return FeatureResult(body=named, issues=issues)
        if auto:
            build = (
                _length(feature, "build_x", "build volume width"),
                _length(feature, "build_y", "build volume depth"),
                _length(feature, "build_z", "build volume height"),
            )
            planes = auto_planes(body.shape, build)
        else:
            planes = _picked_planes(feature, ctx)
        if len(planes) > MAX_PLANES:
            raise FeatureError(f"{owner}: more than {MAX_PLANES} cuts. Use a larger build volume.")
        if not planes:
            issues.append(
                Issue(
                    FeatureState.WARNING,
                    f"{owner}: the part already fits the build volume, so nothing was cut. "
                    "Delete this feature if it is not needed.",
                    code="fits",
                )
            )
            return FeatureResult(body=whole, issues=issues)
        named, origin = self._split(feature, body, planes)
        named, origin = self._glue(feature, named, planes, origin)
        named, extra = self._connectors(feature, body, named, planes, origin)
        issues += extra
        if build is not None:
            issues += self._fit(owner, named.shape, build)
        if len(indices) < len(solids(whole.shape)):
            from fdcad.core.features.bodies import join, rest_of

            joined = join([rest_of(whole, indices, feature.id), named], feature.id)
            assert joined is not None
            named = joined
        return FeatureResult(body=named, issues=issues)

    def _split(
        self, feature: Feature, body: NamedShape, planes: list[CutPlane]
    ) -> tuple[NamedShape, list[int]]:
        """The pieces, and for each piece the index of the body it was cut from."""
        owner, fid = feature.name, feature.id
        size = 2.0 * max(bounding_size(body.shape), 1.0)
        tools = ShapeList()
        for plane in planes:
            tools.Append(_tool_face(plane, size, body.shape))
        # Each body is cut on its own, so overlapping bodies never cut each other.
        pieces: list[TopoDS_Shape] = []
        names: list[NamedFace] = []
        origin: list[int] = []
        for index, target in enumerate(solids(body.shape)):
            args = ShapeList()
            args.Append(target)
            splitter = BRepAlgoAPI_Splitter()
            splitter.SetArguments(args)
            splitter.SetTools(tools)
            splitter.SetFuzzyValue(FUZZY_TOLERANCE)
            splitter.Build()
            if not splitter.IsDone():
                raise FeatureError(
                    f"{owner}: the part could not be cut. Move the cut planes a little."
                )
            made = solids(splitter.Shape())
            pieces.extend(made)
            origin.extend([index] * len(made))
            fmap = ShapeMap()
            TopExp.MapShapes_s(target, TopAbs_FACE, fmap)
            own = [(n, f) for n, f in body.faces if fmap.Contains(f)]
            names.extend(carry(own, splitter.History()))
        if len(pieces) <= len(solids(body.shape)):
            raise FeatureError(f"{owner}: the cut planes miss the part. Pick planes through it.")
        shape = compound(pieces)
        named_faces = [f for _n, f in names]
        for j, plane in enumerate(planes, start=1):
            new = [
                f
                for f in faces_of(shape)
                if _on_plane(f, plane) != 0 and not any(f.IsSame(g) for g in named_faces)
            ]
            ordered = order_by_position(new)
            for k, face in enumerate(ordered, start=1):
                suffix = "" if len(ordered) == 1 else f"#{k}"
                names.append((f"{fid}/cut{j}{suffix}", face))
        return NamedShape(shape, restrict(names, shape, fid)), origin

    def _split_sketch(
        self, feature: Feature, ctx: BuildContext, body: NamedShape
    ) -> tuple[NamedShape, list[CutPlane], list[int]]:
        """Cut along the path sketch's curves; the planes of its flat cut faces carry
        the connectors (TR181, D2002). Also the index of the body each piece came from."""
        from fdcad.core.features.split import _sketch_tool

        owner, fid = feature.name, feature.id
        refs = feature.refs.get("path")
        ref = refs[0] if isinstance(refs, list) and refs else None
        sketch_id = ref.get("feature") if isinstance(ref, dict) else None
        if not isinstance(sketch_id, str) or ctx.results.get(sketch_id) is None:
            raise FeatureError(f"{owner}: pick a sketch to cut along.")
        if ctx.result(sketch_id).sketch is None:
            raise FeatureError(f"{owner}: the cut path is not a sketch. Pick a sketch.")
        value = feature.params.get("glue_gap")
        if isinstance(value, Param) and value.value > 1e-9:
            raise FeatureError(
                f"{owner}: a glue gap needs plane cuts. Enter 0 for the glue gap, or use At Planes."
            )
        size = 2.0 * max(bounding_size(body.shape), 1.0)
        tools = ShapeList()
        tools.Append(_sketch_tool(ctx, sketch_id, size, owner))
        pieces: list[TopoDS_Shape] = []
        names: list[NamedFace] = []
        origin: list[int] = []
        for index, target in enumerate(solids(body.shape)):
            args = ShapeList()
            args.Append(target)
            splitter = BRepAlgoAPI_Splitter()
            splitter.SetArguments(args)
            splitter.SetTools(tools)
            splitter.SetFuzzyValue(FUZZY_TOLERANCE)
            splitter.Build()
            if not splitter.IsDone():
                raise FeatureError(f"{owner}: the part could not be cut. Move the path a little.")
            made = solids(splitter.Shape())
            pieces.extend(made)
            origin.extend([index] * len(made))
            fmap = ShapeMap()
            TopExp.MapShapes_s(target, TopAbs_FACE, fmap)
            own = [(n, f) for n, f in body.faces if fmap.Contains(f)]
            names.extend(carry(own, splitter.History()))
        if len(pieces) <= len(solids(body.shape)):
            raise FeatureError(
                f"{owner}: the path does not cut the part in two. Draw it right across the part."
            )
        shape = compound(pieces)
        named_faces = [f for _n, f in names]
        new = [f for f in faces_of(shape) if not any(f.IsSame(g) for g in named_faces)]
        for k, face in enumerate(order_by_position(new), start=1):
            names.append((f"{fid}/cut1#{k}", face))
        planes: list[CutPlane] = []
        for face in new:
            if BRepAdaptor_Surface(face).GetType() != GeomAbs_Plane:
                continue
            normal = plane_normal(face)
            if normal is None:
                continue
            loc = BRepAdaptor_Surface(face).Plane().Location()
            plane = CutPlane((loc.X(), loc.Y(), loc.Z()), normal)
            if not any(_on_plane(face, p) != 0 for p in planes):
                planes.append(plane)
        return NamedShape(shape, restrict(names, shape, fid)), planes, origin

    @staticmethod
    def _glue(
        feature: Feature, named: NamedShape, planes: list[CutPlane], origin: list[int]
    ) -> tuple[NamedShape, list[int]]:
        """Trim the pieces on each cut's normal side back by ``glue_gap`` (TR181).

        Only the pieces of a body that was cut are trimmed, each body's pieces on their
        own (D2641). ``origin`` gives the body each piece came from, as the result does."""
        value = feature.params.get("glue_gap")
        gap = value.value if isinstance(value, Param) else 0.0
        if gap < 0:
            raise FeatureError(
                f"{feature.name}: the glue gap cannot be negative. Enter zero or more."
            )
        if gap <= 1e-9:
            return named, origin
        size = 2.0 * max(bounding_size(named.shape), 1.0)
        slabs = []
        for plane in planes:
            face = _tool_face(plane, size, named.shape)
            slabs.append(BRepPrimAPI_MakePrism(face, gp_Vec(*plane.normal).Multiplied(gap)).Shape())
        pieces: list[TopoDS_Shape] = []
        names: list[NamedFace] = []
        made: list[int] = []
        for index, group, was_cut in _groups(named, origin, feature.id):
            kept = solids(group.shape)
            if was_cut:
                cut = BRepAlgoAPI_Cut(group.shape, compound(slabs))
                cut.SetFuzzyValue(FUZZY_TOLERANCE)
                cut.Build()
                if not cut.IsDone() or not solids(cut.Shape()):
                    raise FeatureError(
                        f"{feature.name}: the glue gap could not be cut. Enter a smaller gap."
                    )
                kept = solids(cut.Shape())
                names.extend(carry(group.faces, cut.History()))
            else:
                names.extend(group.faces)
            pieces.extend(kept)
            made.extend([index] * len(kept))
        shape = compound(pieces)
        return NamedShape(shape, restrict(names, shape, feature.id)), made

    def _connectors(
        self,
        feature: Feature,
        body: NamedShape,
        named: NamedShape,
        planes: list[CutPlane],
        origin: list[int],
    ) -> tuple[NamedShape, list[Issue]]:
        """Pins, keys, magnet pockets or screw holes on the cut faces; ``origin`` is the
        index of the body of ``body`` each piece of ``named`` came from."""
        owner, fid = feature.name, feature.id
        kind = str(feature.params.get("connector", "none"))
        if kind == "none":
            return named, []
        clearance_value = feature.params.get("clearance")
        clearance = clearance_value.value if isinstance(clearance_value, Param) else 0.2
        if clearance < 0:
            raise FeatureError(f"{owner}: the clearance cannot be negative. Enter zero or more.")
        diameter = half = nut = nut_height = depth = 0.0
        if kind == "pins":
            diameter = _length(feature, "pin_diameter", "pin diameter")
            half = _length(feature, "pin_length", "pin length") / 2
            width, room = diameter, diameter / 2 + clearance + 1.0
        elif kind == "magnets":
            diameter = _length(feature, "magnet_diameter", "magnet diameter")
            half = _length(feature, "magnet_depth", "magnet depth")
            width, room = diameter, diameter / 2 + clearance + 1.0
        elif kind == "screws":
            diameter = _length(feature, "screw_diameter", "screw diameter")
            nut = _length(feature, "nut_size", "nut size across flats")
            nut_height = _length(feature, "nut_height", "nut height")
            width, room = diameter, nut / math.sqrt(3) + clearance + 1.0
        else:
            width = _length(feature, "key_width", "key width")
            depth = _length(feature, "key_depth", "key depth")
            end = width + 2 * depth * math.tan(DOVETAIL_ANGLE)
            room = end / 2 + clearance + 1.0
        draft_value = feature.params.get("key_draft")
        draft = draft_value.value if isinstance(draft_value, Param) else 0.0
        if draft < 0 or draft > MAX_KEY_DRAFT + 1e-12:
            raise FeatureError(
                f"{owner}: the key draft must be 0 to 10 degrees. Enter a smaller angle."
            )
        reach = 2.0 * max(bounding_size(body.shape), 1.0)
        # Each body's pieces get the connectors of their own cut faces, sized to that body
        # and cut from its pieces alone (IDEAS 52, D2641). They were cut from every body
        # in one call: a screw hole went on into a body touching the end of the split
        # bar, and its nut trap was put where the line left that other body.
        sizes = _Sizes(kind, width, room, clearance, draft, reach, diameter, half, nut,
                       nut_height, depth)  # fmt: skip
        groups = _groups(named, origin, fid)
        bodies = solids(body.shape)
        parts: list[tuple[str, TopoDS_Shape]] = []
        missed = 0
        holed: list[tuple[NamedShape, list[TopoDS_Shape]]] = []
        for index, group, was_cut in groups:
            pockets: list[TopoDS_Shape] = []
            holed.append((group, pockets))
            if not was_cut:
                continue
            own = body.shape if len(groups) == 1 else bodies[index]
            for plane in planes:
                missed += self._place(owner, own, group, plane, sizes, pockets, parts)
        issues: list[Issue] = []
        if missed:
            issues.append(
                Issue(
                    FeatureState.WARNING,
                    f"{owner}: {missed} cut {'face has' if missed == 1 else 'faces have'} no "
                    "room for a connector. Use a smaller connector or move the cut.",
                    code="connector_room",
                )
            )
        if not any(pockets for _g, pockets in holed):
            return named, issues
        pieces: list[TopoDS_Shape] = []
        names: list[NamedFace] = []
        for group, pockets in holed:
            if not pockets:
                pieces.extend(solids(group.shape))
                names.extend(group.faces)
                continue
            cut = BRepAlgoAPI_Cut(group.shape, compound(pockets))
            cut.SetFuzzyValue(FUZZY_TOLERANCE)
            cut.Build()
            if not cut.IsDone():
                raise FeatureError(
                    f"{owner}: the connector holes could not be cut. Change the connector size."
                )
            pieces.extend(solids(cut.Shape()))
            names.extend(carry(group.faces, cut.History()))
        connector_faces: list[NamedFace] = []
        counts = {"pin": 0, "key": 0}
        for label, part in parts:
            counts[label] += 1
            for i, face in enumerate(faces_of(part), start=1):
                connector_faces.append((f"{fid}/{label}{counts[label]}/face{i}", face))
        shape = compound([*pieces, *[p for _l, p in parts]])
        return NamedShape(shape, restrict(names + connector_faces, shape, fid)), issues

    @staticmethod
    def _place(
        owner: str,
        own: TopoDS_Shape,
        named: NamedShape,
        plane: CutPlane,
        z: _Sizes,
        pockets: list[TopoDS_Shape],
        parts: list[tuple[str, TopoDS_Shape]],
    ) -> int:
        """Connectors on the faces of ``named`` that lie on ``plane``: their pockets go
        into ``pockets`` and pins and keys into ``parts``. ``named`` holds the pieces of
        the body ``own``, which the connectors are measured in. Gives the number of cut
        faces with no room for one."""
        kind, width, room = z.kind, z.width, z.room
        clearance, draft, reach = z.clearance, z.draft, z.reach
        diameter, half, nut, nut_height, depth = z.diameter, z.half, z.nut, z.nut_height, z.depth
        missed = 0
        placed: list[gp_Pnt] = []
        for face in faces_of(named.shape):
            if _on_plane(face, plane) == 0:
                continue
            places = spots(face, plane.normal, width, room)
            # Pieces share their cut face, or have two equal ones: one set per spot.
            places = [(p, a) for p, a in places if all(p.Distance(q) > 1e-6 for q in placed)]
            if not places and not any(_room(face, q) > 0 for q in placed):
                missed += 1
            placed.extend(p for p, _a in places)
            for point, along in places:
                if kind == "magnets":
                    pocket = _cylinder(
                        point, plane.normal, diameter + 2 * clearance, half + clearance
                    )
                    if not _inside(pocket, own):
                        missed += 1
                        continue
                    pockets.append(pocket)
                elif kind == "screws":
                    hole = _cylinder(point, plane.normal, diameter + 2 * clearance, reach)
                    pockets.append(hole)
                    trap = _nut_trap(
                        own, point, plane.normal, along, nut + 2 * clearance,
                        nut_height + clearance,
                    )  # fmt: skip
                    if trap is not None:  # one solid: overlapping tools are not cut twice
                        from fdcad.core.occ import BRepAlgoAPI_Fuse

                        pockets[-1] = BRepAlgoAPI_Fuse(hole, trap).Shape()
                elif kind == "pins":
                    hole = _cylinder(
                        point, plane.normal, diameter + 2 * clearance, half + clearance
                    )
                    if not _inside(hole, own):
                        missed += 1
                        continue
                    pockets.append(hole)
                    parts.append(("pin", _cylinder(point, plane.normal, diameter, half)))
                else:
                    taper = _taper(own, point, plane.normal, along, math.tan(draft))
                    try:
                        pocket = _bowtie(
                            point, plane.normal, along, width + 2 * clearance,
                            depth + clearance, reach, taper,
                        )  # fmt: skip
                        exact = _bowtie(point, plane.normal, along, width, depth, reach, taper)
                    except ValueError as exc:
                        raise FeatureError(
                            f"{owner}: {exc}. Enter a smaller key draft or a wider key."
                        ) from exc
                    common = BRepAlgoAPI_Common(exact, own)
                    common.SetFuzzyValue(FUZZY_TOLERANCE)
                    common.Build()
                    if not common.IsDone() or not solids(common.Shape()):
                        missed += 1
                        continue
                    pockets.append(pocket)
                    parts.extend(("key", s) for s in solids(common.Shape()))
        return missed

    @staticmethod
    def _fit(owner: str, shape: TopoDS_Shape, build: Vec3) -> list[Issue]:
        too_big = 0
        for piece in solids(shape):
            lo, hi = _box(piece)
            if any(hi[i] - lo[i] > build[i] + 1e-6 for i in range(3)):
                too_big += 1
        if not too_big:
            return []
        return [
            Issue(
                FeatureState.WARNING,
                f"{owner}: {too_big} {'piece is' if too_big == 1 else 'pieces are'} larger than "
                "the build volume. Use smaller connectors or a larger build volume.",
                code="too_big",
            )
        ]
