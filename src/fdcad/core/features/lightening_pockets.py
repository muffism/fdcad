"""Lightening Pockets: a plate face pocketed as triangles between ribs (TR245, D2012).

Type ``lightening_pockets``. Refs: ``plate_face`` (a flat face of a plate).
Params:

- ``border``: length kept solid along the face's outer edge and round its holes.
- ``web``: length, the width of the ribs between pockets.
- ``cell``: length, the size of the triangles (the rib spacing).
- ``corner_radius``: optional length, rounding of the pockets' corners.
- ``pocket_depth``: optional length: the pockets' depth; 0 or left out cuts
  right through.

The face less its border is crossed by ribs in three directions 60 degrees apart;
what is left between them are the pockets. Each pocket is shrunk by the corner
radius and grown back, which rounds its corners; pockets too small for that are
left solid. Pocket faces are ``<fid>/pocket#k``.
"""

from __future__ import annotations

import math

from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeOffset
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.GeomAbs import GeomAbs_Arc
from OCP.gp import gp_Vec
from OCP.TopoDS import TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    register,
)
from fdcad.core.features.solids import (
    FUZZY_TOLERANCE,
    compound,
    face_area,
    polygon_face,
    solids,
)
from fdcad.core.naming.names import NamedShape, carry, faces_of, restrict
from fdcad.core.occ import BRepAlgoAPI_Cut, ShapeMap
from fdcad.core.plane_normal import plane_normal
from fdcad.core.units import Kind

#: Most ribs in one direction.
MOST_RIBS = 400


def _value(feature: Feature, name: str) -> float:
    value = feature.params.get(name)
    return value.value if isinstance(value, Param) else 0.0


def offset_face(face: TopoDS_Face, distance: float) -> list[TopoDS_Face]:
    """The face grown (or shrunk, when negative) by ``distance`` with round corners; its
    holes move the other way. Empty when it shrinks away."""
    maker = BRepOffsetAPI_MakeOffset(face, GeomAbs_Arc)
    try:
        maker.Perform(distance)
    except Exception:
        return []
    if not maker.IsDone():
        return []
    from OCP.TopAbs import TopAbs_WIRE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    from fdcad.core.naming.names import faces_of as faces

    wires = []
    explorer = TopExp_Explorer(maker.Shape(), TopAbs_WIRE)
    while explorer.More():
        wires.append(TopoDS.Wire(explorer.Current()))
        explorer.Next()
    if not wires:
        return []
    made = []
    for wire in wires:
        builder = BRepBuilderAPI_MakeFace(wire, True)
        if builder.IsDone():
            made.append(builder.Face())
    if not made:
        return []
    # The largest is the outline; the rest are holes cut out of it.
    made.sort(key=lambda f: -face_area([f]))
    outline, holes = made[0], made[1:]
    if not holes:
        return [outline]
    cut = BRepAlgoAPI_Cut(outline, compound(holes))
    cut.Build()
    return faces(cut.Shape()) if cut.IsDone() else [outline]


def cut_each(shape: TopoDS_Shape, tools: list[TopoDS_Shape]) -> TopoDS_Shape | None:
    """``shape`` less every one of ``tools``, each given to the kernel as its own tool
    (D1054). The rib strips cross each other, and the kernel does not sort out the
    pieces of one compound against each other: with the strips in one compound a
    large face came back as a few big overlapping pieces, some of them inside out,
    and the pockets cut from those took five times the material and left a solid
    that was not valid. None when the kernel fails."""
    from fdcad.core.occ import ShapeList

    op = BRepAlgoAPI_Cut()
    args, cutters = ShapeList(), ShapeList()
    args.Append(shape)
    for tool in tools:
        cutters.Append(tool)
    op.SetArguments(args)
    op.SetTools(cutters)
    op.SetFuzzyValue(FUZZY_TOLERANCE)
    op.Build()
    return op.Shape() if op.IsDone() else None


def ribs(
    face: TopoDS_Face, normal: tuple[float, float, float], cell: float, web: float
) -> list[TopoDS_Shape]:
    """Rib strips ``web`` wide every ``cell`` in three directions 60 degrees apart,
    covering the face, in its plane. The strips cross; see ``cut_each``."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    from fdcad.core.features.solids import bounding_size

    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    centre = props.CentreOfMass()
    n = gp_Vec(*normal)
    helper = gp_Vec(1, 0, 0) if abs(n.X()) < 0.9 else gp_Vec(0, 1, 0)
    x = n.Crossed(helper).Normalized()
    y = n.Crossed(x).Normalized()
    reach = bounding_size(face) + cell
    count = math.ceil(reach / cell)
    if count > MOST_RIBS:
        raise ValueError("the cells are too small for this face")
    strips = []
    pitch = cell * math.sqrt(3) / 2  # rows of equilateral triangles of side ``cell``
    for k in range(3):
        a = math.radians(60 * k)
        along = x.Multiplied(math.cos(a)).Added(y.Multiplied(math.sin(a)))
        across = n.Crossed(along).Normalized()
        for i in range(-count, count + 1):
            mid = centre.Translated(across.Multiplied(i * pitch))
            corners = []
            for s, t in (
                (-reach, -web / 2),
                (reach, -web / 2),
                (reach, web / 2),
                (-reach, web / 2),
            ):
                p = mid.Translated(along.Multiplied(s)).Translated(across.Multiplied(t))
                corners.append((p.X(), p.Y(), p.Z()))
            strips.append(polygon_face(corners))
    return strips


@register
class LighteningPockets(FeatureType):
    """Triangular pockets between ribs on a plate face."""

    type_name = "lightening_pockets"
    makes_solid = True
    params = (
        ParamSpec("border", kind=Kind.LENGTH),
        ParamSpec("web", kind=Kind.LENGTH),
        ParamSpec("cell", kind=Kind.LENGTH),
        ParamSpec("corner_radius", kind=Kind.LENGTH, optional=True),
        ParamSpec("pocket_depth", kind=Kind.LENGTH, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Cut the pockets."""
        from fdcad.core.features.lookup import resolve_face
        from fdcad.core.features.solids import bounding_size

        owner, fid = feature.name, feature.id
        body = ctx.body
        if body is None:
            raise FeatureError(f"{owner}: the part is empty. Add a plate first.")
        ref = feature.refs.get("plate_face")
        if isinstance(ref, list):
            ref = ref[0] if ref else None
        if not isinstance(ref, dict):
            raise FeatureError(f"{owner}: pick the flat face of the plate to pocket.")
        face, issues = resolve_face(body, ref, owner)
        normal = plane_normal(face)
        if normal is None:
            raise FeatureError(f"{owner}: the face is not flat. Pick a flat face.")
        border, web, cell = (_value(feature, n) for n in ("border", "web", "cell"))
        radius, depth = _value(feature, "corner_radius"), _value(feature, "pocket_depth")
        if border < 0 or web <= 0 or cell <= 2 * web or radius < 0 or depth < 0:
            raise FeatureError(
                f"{owner}: enter a web above zero, a cell more than twice the web, and a "
                "border, corner radius and depth of zero or more."
            )
        try:
            inside = offset_face(face, -border) if border > 0 else [face]
            if not inside:
                raise ValueError("the border leaves no room for pockets")
            grid = ribs(face, normal, cell, web)
            between = cut_each(compound(inside), grid)
            if between is None:
                raise ValueError("the ribs could not be laid out")
            pockets = []
            for piece in faces_of(between):
                if radius > 0:
                    shrunk = offset_face(piece, -radius)
                    pockets += [g for s in shrunk for g in offset_face(s, radius)]
                else:
                    pockets.append(piece)
            pockets = [p for p in pockets if face_area([p]) > web * web]
            if not pockets:
                raise ValueError("no pocket is left between the ribs")
            reach = depth if depth > 0 else 2 * bounding_size(body.shape)
            step = gp_Vec(*normal).Reversed().Multiplied(reach)
            lift = gp_Vec(*normal).Multiplied(0.01)
            tools = []
            for p in pockets:
                from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
                from OCP.gp import gp_Trsf

                move = gp_Trsf()
                move.SetTranslation(lift)
                raised = BRepBuilderAPI_Transform(p, move, True).Shape()
                tools.append(BRepPrimAPI_MakePrism(raised, step.Added(lift.Reversed())).Shape())
        except ValueError as exc:
            raise FeatureError(
                f"{owner} failed: {exc}. Use a larger cell, a thinner web or a smaller border."
            ) from exc
        # The pockets are cut from the plate that was picked (D1077). They were cut from
        # the whole part: pockets through a plate went on through a body lying on it.
        from fdcad.core.features.bodies import in_body_of

        def cut(body: NamedShape) -> NamedShape:
            from fdcad.core.features.solids import right_side_out
            from fdcad.core.occ import ShapeList

            maker = BRepAlgoAPI_Cut()
            args, cutters = ShapeList(), ShapeList()
            args.Append(body.shape)
            for tool in tools:
                cutters.Append(right_side_out(tool))
            maker.SetArguments(args)
            maker.SetTools(cutters)
            maker.SetFuzzyValue(FUZZY_TOLERANCE)
            maker.SetToFillHistory(True)
            maker.Build()
            if not maker.IsDone() or not solids(maker.Shape()):
                raise FeatureError(
                    f"{owner} failed: the pockets could not be cut. Use a larger cell."
                )
            shape = compound(solids(maker.Shape()))
            from OCP.BRepCheck import BRepCheck_Analyzer

            if (
                not BRepCheck_Analyzer(shape, True, True).IsValid()
                and BRepCheck_Analyzer(body.shape, True, True).IsValid()
            ):  # never hand on a broken solid as if it were fine (D1054)
                raise FeatureError(
                    f"{owner} failed: the pockets did not leave a valid solid. Use a larger "
                    "cell, a wider web or a larger border."
                )
            names = carry(body.faces, maker.History())
            named = ShapeMap()
            for _n, f in names:
                named.Add(f)
            k = 0
            for f in faces_of(shape):
                if not named.Contains(f):
                    k += 1
                    names.append((f"{fid}/pocket#{k}", f))
            return NamedShape(shape, restrict(names, shape, fid))

        return FeatureResult(body=in_body_of(body, face, fid, cut), issues=issues)
