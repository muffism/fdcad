"""Joint helpers between two touching bodies (TR401, DECISIONS D2014).

Type ``joint_helper``. Refs: ``bodies``: two body picks (a face of each): the
first is the part cut into, the second the part that goes in. They must touch on
a flat face. Params:

- ``joint``: ``groove`` (default: the second body's whole end goes into a groove,
  a dado; at the first body's edge it is a rabbet), ``rabbet`` (the same cut,
  named for a joint at an edge), ``mortise`` (a tenon on the second body, smaller
  than its end by the ``shoulder`` on every side, into a mortise) or ``dowels``
  (two dowel holes across the joint, ``dowel_diameter`` wide, ``depth`` into
  each body).
- ``depth``: length, how far the joint goes into the first body.
- ``joint_clearance``: optional length, the gap round the part that goes in.
- ``shoulder``: optional length (mortise), ``dowel_diameter`` (dowels).

Faces of the cuts and of the added piece are ``<fid>/joint#k``.
"""

from __future__ import annotations

from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
from OCP.gp import gp_Ax2, gp_Dir, gp_Vec
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
from fdcad.core.features.solids import FUZZY_TOLERANCE, compound, face_area, solids
from fdcad.core.naming.names import NamedShape, carry, faces_of, restrict
from fdcad.core.occ import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse, ShapeMap
from fdcad.core.plane_normal import plane_normal
from fdcad.core.units import Kind

JOINTS = ("groove", "rabbet", "mortise", "dowels")


def _value(feature: Feature, name: str, default: float = 0.0) -> float:
    value = feature.params.get(name)
    return value.value if isinstance(value, Param) else default


def contact(first: TopoDS_Shape, second: TopoDS_Shape) -> tuple[TopoDS_Face, gp_Vec] | None:
    """The largest flat patch where ``second`` lies on ``first``, and the direction from
    it into ``first``; None when they do not touch on a flat face."""
    best: tuple[float, TopoDS_Face, gp_Vec] | None = None
    for fb in faces_of(second):
        nb = plane_normal(fb)
        if nb is None:
            continue
        for fa in faces_of(first):
            na = plane_normal(fa)
            if na is None or sum(a * b for a, b in zip(na, nb, strict=True)) > -1 + 1e-7:
                continue
            if _plane_gap(fa, fb, na) > 1e-6:
                continue
            common = BRepAlgoAPI_Common(fa, fb)
            common.Build()
            if not common.IsDone():
                continue
            patches = faces_of(common.Shape())
            area = face_area(patches) if patches else 0.0
            if patches and area > 1e-9 and (best is None or area > best[0]):
                patches.sort(key=lambda f: -face_area([f]))
                best = (area, patches[0], gp_Vec(*nb))
    return None if best is None else (best[1], best[2])


def _plane_gap(fa: TopoDS_Face, fb: TopoDS_Face, na: tuple[float, float, float]) -> float:
    """How far ``fb``'s plane is from ``fa``'s, along ``fa``'s normal."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface

    pa = BRepAdaptor_Surface(fa).Plane().Location()
    pb = BRepAdaptor_Surface(fb).Plane().Location()
    return float(
        abs((pb.X() - pa.X()) * na[0] + (pb.Y() - pa.Y()) * na[1] + (pb.Z() - pa.Z()) * na[2])
    )


def _run(kind: str, a: TopoDS_Shape, b: TopoDS_Shape) -> tuple[TopoDS_Shape, object]:
    maker = {"common": BRepAlgoAPI_Common, "cut": BRepAlgoAPI_Cut, "fuse": BRepAlgoAPI_Fuse}[kind](
        a, b
    )
    maker.SetFuzzyValue(FUZZY_TOLERANCE)
    maker.Build()
    if not maker.IsDone():
        raise ValueError(f"the joint {kind} failed")
    return maker.Shape(), maker


def _grown(shape: TopoDS_Shape, distance: float) -> TopoDS_Shape:
    """Every face of ``shape`` grown (or shrunk) by ``distance`` in its plane."""
    from fdcad.core.features.lightening_pockets import offset_face

    if abs(distance) < 1e-12:
        return shape
    made = [g for f in faces_of(shape) for g in offset_face(f, distance)]
    if not made:
        raise ValueError("the joint outline could not be offset")
    return compound(made)


@register
class JointHelper(FeatureType):
    """A groove, rabbet, mortise and tenon or dowels between two touching bodies."""

    type_name = "joint_helper"
    makes_solid = True
    params = (
        ParamSpec("joint", choices=JOINTS, default="groove"),
        ParamSpec("depth", kind=Kind.LENGTH),
        ParamSpec("joint_clearance", kind=Kind.LENGTH, optional=True),
        ParamSpec("shoulder", kind=Kind.LENGTH, optional=True),
        ParamSpec("dowel_diameter", kind=Kind.LENGTH, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Cut the joint into the first body and shape the second."""
        from fdcad.core.features.bodies import body_indices

        owner, fid = feature.name, feature.id
        body = ctx.body
        if body is None:
            raise FeatureError(f"{owner}: the part is empty. Add two bodies first.")
        indices, issues = body_indices(ctx, feature.refs.get("bodies"), owner)
        if len(indices) != 2:
            raise FeatureError(f"{owner}: pick exactly two bodies, the one to cut first.")
        pieces = solids(body.shape)
        first, second = pieces[indices[0]], pieces[indices[1]]
        found = contact(first, second)
        if found is None:
            raise FeatureError(
                f"{owner}: the bodies do not touch on a flat face. Move them together."
            )
        patch, into = found
        depth = _value(feature, "depth")
        gap = _value(feature, "joint_clearance", 0.2)
        if depth <= 0 or gap < 0:
            raise FeatureError(f"{owner}: enter a depth above zero and a clearance of 0 or more.")
        kind = str(feature.params.get("joint", "groove"))
        try:
            makers_a: list[object] = []
            makers_b: list[object] = []
            a, b = first, second
            if kind in ("groove", "rabbet", "mortise"):
                if kind == "mortise":
                    shoulder = _value(feature, "shoulder", 0.0)
                    if shoulder <= 0:
                        raise ValueError("a mortise needs a shoulder above zero")
                    tenon_face = _grown(patch, -shoulder)
                else:
                    tenon_face = patch
                tenon = BRepPrimAPI_MakePrism(tenon_face, into.Multiplied(depth)).Shape()
                room_face = _grown(tenon_face if kind == "mortise" else patch, gap)
                room = BRepPrimAPI_MakePrism(room_face, into.Multiplied(depth + gap)).Shape()
                a, m = _run("cut", a, room)
                makers_a.append(m)
                b, m = _run("fuse", b, tenon)
                makers_b.append(m)
            else:
                diameter = _value(feature, "dowel_diameter", 0.0)
                if diameter <= 0:
                    raise ValueError("enter the dowel diameter")
                holes = _dowel_holes(patch, into, diameter + 2 * gap, depth + gap)
                a, m = _run("cut", a, holes)
                makers_a.append(m)
                b, m = _run("cut", b, holes)
                makers_b.append(m)
        except ValueError as exc:
            raise FeatureError(
                f"{owner} failed: {exc}. Change the depth, shoulder or dowel size."
            ) from exc
        rest = [s for i, s in enumerate(pieces) if i not in indices]
        shape = compound([*solids(a), *solids(b), *rest])
        names: list[tuple[str, TopoDS_Face]] = []
        for old, makers in ((first, makers_a), (second, makers_b)):
            own = ShapeMap()
            for f in faces_of(old):
                own.Add(f)
            kept = [(n, f) for n, f in body.faces if own.Contains(f)]
            for maker in makers:
                kept = carry(kept, maker.History())  # type: ignore[attr-defined]
            names += kept
        others = ShapeMap()
        for s in rest:
            for f in faces_of(s):
                others.Add(f)
        names += [(n, f) for n, f in body.faces if others.Contains(f)]
        named = ShapeMap()
        for _n, f in names:
            named.Add(f)
        k = 0
        for f in faces_of(shape):
            if not named.Contains(f):
                k += 1
                names.append((f"{fid}/joint#{k}", f))
        return FeatureResult(body=NamedShape(shape, restrict(names, shape, fid)), issues=issues)


def _dowel_holes(patch: TopoDS_Face, into: gp_Vec, diameter: float, depth: float) -> TopoDS_Shape:
    """Two holes ``depth`` deep each way across the patch, along its long direction."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    from fdcad.core.features.solids import extent_along

    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(patch, props)
    centre = props.CentreOfMass()
    axis = props.PrincipalProperties().ThirdAxisOfInertia()
    along = gp_Vec(axis.X(), axis.Y(), axis.Z())
    along = along.Subtracted(into.Multiplied(along.Dot(into)))
    if along.Magnitude() < 1e-9:
        along = gp_Vec(gp_Ax2(centre, gp_Dir(into)).XDirection())
    along.Normalize()
    span = extent_along(patch, (along.X(), along.Y(), along.Z()))
    length = 0.0 if span is None else span[1] - span[0]
    if length < 3 * diameter:
        raise ValueError("the joint is too short for two dowels")
    holes = []
    for sign in (-1.0, 1.0):
        spot = centre.Translated(along.Multiplied(sign * length / 4))
        start = spot.Translated(into.Reversed().Multiplied(depth))
        holes.append(
            BRepPrimAPI_MakeCylinder(gp_Ax2(start, gp_Dir(into)), diameter / 2, 2 * depth).Shape()
        )
    return compound(holes)
