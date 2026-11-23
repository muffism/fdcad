"""Knurl: straight or diamond knurling on a cylinder face (TR163 item 1, D2015).

Type ``knurl``. Refs: ``round_face`` (a cylindrical face). Params:

- ``knurl_pattern``: ``straight`` (default: V grooves along the axis) or ``diamond``
  (two sets of V grooves on 30 degree helices, one each way).
- ``knurl_pitch``: length, the groove spacing round the cylinder.
- ``knurl_depth``: length, how deep the V grooves go.

The grooves run past both ends of the face. The count round the cylinder is
the circumference over the pitch, rounded. Groove faces are ``<fid>/knurl#k``.
"""

from __future__ import annotations

import math

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.gp import gp_Vec
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    register,
)
from fdcad.core.features.solids import FUZZY_TOLERANCE, compound, polygon_face, solids
from fdcad.core.naming.names import NamedShape, carry, faces_of, restrict
from fdcad.core.occ import BRepAlgoAPI_Cut, ShapeMap
from fdcad.core.units import Kind

#: Most grooves round the cylinder, in one direction.
MOST_GROOVES = 180
#: Helix angle of diamond grooves, from the axis.
DIAMOND_ANGLE = math.radians(30)
#: How far the grooves start outside the cylinder and run past its ends (mm).
_PAST = 0.2


def _rotate(v: tuple[float, float, float], axis: tuple[float, float, float], a: float):  # type: ignore[no-untyped-def]
    """``v`` turned by ``a`` about the unit ``axis`` (Rodrigues)."""
    c, s = math.cos(a), math.sin(a)
    k = axis
    cross = (k[1] * v[2] - k[2] * v[1], k[2] * v[0] - k[0] * v[2], k[0] * v[1] - k[1] * v[0])
    dot = k[0] * v[0] + k[1] * v[1] + k[2] * v[2]
    return tuple(v[i] * c + cross[i] * s + k[i] * dot * (1 - c) for i in range(3))


def grooves(
    origin: tuple[float, float, float],
    axis: tuple[float, float, float],
    x_dir: tuple[float, float, float],
    radius: float,
    length: float,
    count: int,
    depth: float,
    pattern: str,
    past_start: float = _PAST,
    past_end: float = _PAST,
) -> list[list[TopoDS_Shape]]:
    """The groove solids, one list per direction (grooves of one list never overlap).
    They run ``past_start`` and ``past_end`` beyond the two ends of the face."""
    from fdcad.core.features.modeled_thread import helical_solid

    outer, inner = radius + _PAST, radius - depth
    start = tuple(origin[i] - axis[i] * past_start for i in range(3))
    run = length + past_start + past_end
    sets: list[list[TopoDS_Shape]] = []
    if pattern == "straight":
        half = math.pi / count * (outer / radius)
        out = []
        for k in range(count):
            a = 2 * math.pi * k / count
            x = _rotate(x_dir, axis, a)
            y = _rotate(x_dir, axis, a + math.pi / 2)
            pts = []
            for r, t in ((outer, -half), (inner, 0.0), (outer, half)):
                pts.append(
                    tuple(
                        start[i] + r * (x[i] * math.cos(t) + y[i] * math.sin(t)) for i in range(3)
                    )
                )
            face = polygon_face(pts)
            out.append(BRepPrimAPI_MakePrism(face, gp_Vec(*axis).Multiplied(run)).Shape())
        sets.append(out)
        return sets
    lead = 2 * math.pi * radius / math.tan(DIAMOND_ANGLE)
    spacing = lead / count  # between neighbouring grooves of one set, along the axis
    profile = [(outer, -spacing / 2), (inner, 0.0), (outer, spacing / 2)]
    for left in (False, True):
        out = []
        for k in range(count):
            x = _rotate(x_dir, axis, 2 * math.pi * k / count)
            out.append(helical_solid(start, axis, x, profile, radius, lead, run, left))  # type: ignore[arg-type]
        sets.append(out)
    return sets


def _goes_on(
    solid: TopoDS_Shape,
    origin: tuple[float, ...],
    axis: tuple[float, float, float],
    x_dir: tuple[float, float, float],
    radius: float,
    along: float,
) -> bool:
    """True when ``solid`` has material at ``radius`` from the axis, ``along`` the axis
    from ``origin``: asked at three places round the axis, two of three decide."""
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN

    inside = 0
    for k in range(3):
        x = _rotate(x_dir, axis, 2 * math.pi * k / 3 + 0.3)
        point = tuple(origin[i] + axis[i] * along + x[i] * radius for i in range(3))
        state = BRepClass3d_SolidClassifier(solid, gp_Pnt(*point), 1e-7).State()
        inside += 1 if state == TopAbs_IN else 0
    return inside >= 2


@register
class Knurl(FeatureType):
    """Straight or diamond knurling cut into a cylinder face."""

    type_name = "knurl"
    makes_solid = True
    params = (
        ParamSpec("knurl_pattern", choices=("straight", "diamond"), default="straight"),
        ParamSpec("knurl_pitch", kind=Kind.LENGTH),
        ParamSpec("knurl_depth", kind=Kind.LENGTH),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Cut the grooves."""
        from fdcad.core.features.lookup import resolve_face
        from fdcad.core.features.solids import extent_along

        owner, fid = feature.name, feature.id
        body = ctx.body
        if body is None:
            raise FeatureError(f"{owner}: the part is empty. Add a cylinder first.")
        ref = feature.refs.get("round_face")
        if isinstance(ref, list):
            ref = ref[0] if ref else None
        if not isinstance(ref, dict):
            raise FeatureError(f"{owner}: pick the round face to knurl.")
        face, issues = resolve_face(body, ref, owner)
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Cylinder:
            raise FeatureError(f"{owner}: the face is not a cylinder. Pick a cylinder face.")
        cyl = surface.Cylinder()
        radius = cyl.Radius()
        pos = cyl.Position()
        loc, d, xd = pos.Location(), pos.Direction(), pos.XDirection()
        axis = (d.X(), d.Y(), d.Z())
        values = {}
        for name in ("knurl_pitch", "knurl_depth"):
            value = feature.params.get(name)
            values[name] = value.value if isinstance(value, Param) else 0.0
        pitch, depth = values["knurl_pitch"], values["knurl_depth"]
        if pitch <= 0 or depth <= 0 or depth >= radius / 2:
            raise FeatureError(
                f"{owner}: enter a pitch above zero and a depth above zero and under half the "
                "radius."
            )
        count = round(2 * math.pi * radius / pitch)
        if not 3 <= count <= MOST_GROOVES:
            raise FeatureError(
                f"{owner}: the pitch gives {count} grooves round the cylinder. Enter a pitch "
                f"for 3 to {MOST_GROOVES} grooves."
            )
        span = extent_along(face, axis)
        assert span is not None
        here = loc.X() * axis[0] + loc.Y() * axis[1] + loc.Z() * axis[2]
        origin = tuple(
            c + axis[i] * (span[0] - here) for i, c in enumerate((loc.X(), loc.Y(), loc.Z()))
        )
        pattern = str(feature.params.get("knurl_pattern", "straight"))
        # The grooves run a little past a free end of the face, so they cut clean
        # through it. Where the body goes on past the end (a shoulder, a wider part the
        # round stands on) they stop at the end (D1060): they used to notch the
        # shoulder 0.2 mm deep, and the notches met each other along edges only.
        from fdcad.core.features.bodies import solid_of_face

        pieces = solids(body.shape)
        index = solid_of_face(body.shape, face)
        own = pieces[index] if index >= 0 else body.shape
        length = span[1] - span[0]
        past = []
        for at, sign in ((0.0, -1.0), (length, 1.0)):
            beyond = at + sign * _PAST / 2
            past.append(
                0.0 if _goes_on(own, origin, axis, (xd.X(), xd.Y(), xd.Z()), radius - depth / 2,
                                beyond) else _PAST
            )  # fmt: skip
        try:
            sets = grooves(
                origin,
                axis,
                (xd.X(), xd.Y(), xd.Z()),
                radius,
                length,
                count,
                depth,
                pattern,
                past[0],
                past[1],
            )
        except FeatureError as exc:
            raise FeatureError(f"{owner} failed: {exc} Use a larger pitch.") from exc
        # Only the body of the picked face is cut; the others are put back as they are.
        own_faces = ShapeMap()
        from OCP.TopAbs import TopAbs_FACE
        from OCP.TopExp import TopExp

        TopExp.MapShapes_s(own, TopAbs_FACE, own_faces)
        shape = own
        names = [(n, f) for n, f in body.faces if own_faces.Contains(f)]
        others = [(n, f) for n, f in body.faces if not own_faces.Contains(f)]
        from fdcad.core.occ import ShapeList

        for tools in sets:
            # Every groove is its own tool (D1060). Neighbouring grooves touch along
            # their outer edges, and the kernel does not sort out the pieces of one
            # compound against each other: on a stem under a wider body the cut with
            # all grooves in one compound removed nothing and left 110 edges with more
            # than two faces.
            cut = BRepAlgoAPI_Cut()
            args, cutters = ShapeList(), ShapeList()
            args.Append(shape)
            for tool in tools:
                cutters.Append(tool)
            cut.SetArguments(args)
            cut.SetTools(cutters)
            cut.SetFuzzyValue(FUZZY_TOLERANCE)
            cut.SetToFillHistory(True)
            cut.Build()
            if not cut.IsDone():
                raise FeatureError(
                    f"{owner} failed: the grooves could not be cut. Use a larger pitch."
                )
            shape = cut.Shape()
            names = carry(names, cut.History())
        rest = [p for i, p in enumerate(pieces) if i != index] if index >= 0 else []
        shape = compound([*rest[:index], *solids(shape), *rest[index:]] if index >= 0
                         else solids(shape))  # fmt: skip
        names = names + others
        named = ShapeMap()
        for _n, f in names:
            named.Add(f)
        k = 0
        for f in faces_of(shape):
            if not named.Contains(f):
                k += 1
                names.append((f"{fid}/knurl#{k}", f))
        result = NamedShape(shape, restrict(names, shape, fid))
        from fdcad.core.features.solids import check_result

        issues = issues + check_result(fid, owner, body, result, None)
        return FeatureResult(body=result, issues=issues)
