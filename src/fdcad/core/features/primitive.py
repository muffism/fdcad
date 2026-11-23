"""Primitive solids (TUTORIAL_REVIEW_SPEC_2 TR127, DECISIONS D813).

Type ``primitive``. A box, cylinder, sphere, cone, torus, wedge, prism or tube
made from typed sizes, with no sketch, added or cut like any boss or cut.

Params:

- ``kind``: ``box``, ``cylinder``, ``sphere``, ``cone``, ``torus``, ``wedge``,
  ``prism`` or ``tube``. ``operation``: ``boss`` (default) or ``cut``;
  ``merge`` as for other bosses.
- Sizes (lengths): ``length``, ``width``, ``height`` (box; wedge, which slopes
  from ``height`` at the start to ``top`` (length) at the end), ``diameter``
  (cylinder, sphere, prism across corners, tube outside), ``diameter2`` (cone
  top; 0 for a point), ``inner`` (tube inside diameter), ``ring`` and ``tube``
  (torus: the diameter of the ring through the tube's middle and of the tube),
  ``sides`` (number, prism).
- ``centred``: optional boolean: the shape is centred on the frame's origin
  (else it stands on the frame's XY plane, starting at the origin).

Refs: ``frame``: a plane, flat face or coordinate system (else the part's own
axes). The shape's Z is the frame's normal.

Face roles: ``<fid>/face#k`` (by position).
"""

from __future__ import annotations

import math
from typing import Any

from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakePolygon,
    BRepBuilderAPI_Transform,
)
from OCP.BRepPrimAPI import (
    BRepPrimAPI_MakeBox,
    BRepPrimAPI_MakeCone,
    BRepPrimAPI_MakeCylinder,
    BRepPrimAPI_MakePrism,
    BRepPrimAPI_MakeSphere,
    BRepPrimAPI_MakeTorus,
)
from OCP.gp import gp_Ax2, gp_Ax3, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    register,
)
from fdcad.core.features.solids import check_result, combine_or_keep, expected_issues
from fdcad.core.naming.names import NamedShape, restrict
from fdcad.core.units import Kind

KINDS = (
    "box",
    "cylinder",
    "sphere",
    "cone",
    "torus",
    "wedge",
    "prism",
    "tube",
    "geodesic_sphere",  # TR371 item 4 (D936)
    "geodesic_dome",
)
#: The sizes each kind needs.
NEEDS: dict[str, tuple[str, ...]] = {
    "box": ("length", "width", "height"),
    "cylinder": ("diameter", "height"),
    "sphere": ("diameter",),
    "cone": ("diameter", "diameter2", "height"),
    "torus": ("ring", "tube"),
    "wedge": ("length", "width", "height", "top"),
    "prism": ("diameter", "height", "sides"),
    "tube": ("diameter", "inner", "height"),
    "geodesic_sphere": ("diameter", "frequency"),
    "geodesic_dome": ("diameter", "frequency"),
}
#: The finest geodesic frequency (20 times its square triangles).
MAX_FREQUENCY = 8


def _size(feature: Feature, name: str) -> float:
    value = feature.params.get(name)
    if not isinstance(value, Param):
        raise FeatureError(f"{feature.name}: the {name} is missing. Type it.")
    return float(value.value)


def _shape(feature: Feature) -> Any:
    """The shape in its own frame: standing on XY at the origin, Z up."""
    name = feature.name
    kind = str(feature.params.get("kind", "box"))
    if kind not in KINDS:
        raise FeatureError(f"{name}: choose a shape from the list.")
    v = {key: _size(feature, key) for key in NEEDS[kind]}
    for key, size in v.items():
        least = 0.0 if key in ("diameter2", "top") else 1e-6
        if size < least:
            raise FeatureError(f"{name}: the {key} must be more than 0. Type a larger value.")
    axis = gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))
    try:
        if kind == "box":
            return BRepPrimAPI_MakeBox(v["length"], v["width"], v["height"]).Shape()
        if kind == "cylinder":
            return BRepPrimAPI_MakeCylinder(axis, v["diameter"] / 2, v["height"]).Shape()
        if kind == "sphere":
            r = v["diameter"] / 2
            return BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, r), r).Shape()
        if kind == "cone":
            return BRepPrimAPI_MakeCone(
                axis, v["diameter"] / 2, v["diameter2"] / 2, v["height"]
            ).Shape()
        if kind == "torus":
            if v["tube"] >= v["ring"]:
                raise FeatureError(
                    f"{name}: the tube must be thinner than the ring. Make the ring larger."
                )
            r = v["tube"] / 2
            return BRepPrimAPI_MakeTorus(
                gp_Ax2(gp_Pnt(0, 0, r), gp_Dir(0, 0, 1)), v["ring"] / 2, r
            ).Shape()
        if kind == "wedge":
            return _wedge(v["length"], v["width"], v["height"], v["top"])
        if kind in ("geodesic_sphere", "geodesic_dome"):
            frequency = round(v["frequency"])
            if not 1 <= frequency <= MAX_FREQUENCY:
                raise FeatureError(
                    f"{name}: the frequency must be 1 to {MAX_FREQUENCY}. Type another number."
                )
            return geodesic(v["diameter"] / 2, frequency, kind == "geodesic_dome")
        if kind == "prism":
            sides = round(v["sides"])
            if not 3 <= sides <= 64:
                raise FeatureError(f"{name}: a prism has 3 to 64 sides. Type another number.")
            poly = BRepBuilderAPI_MakePolygon()
            r = v["diameter"] / 2
            for k in range(sides):
                a = 2 * math.pi * k / sides
                poly.Add(gp_Pnt(r * math.cos(a), r * math.sin(a), 0))
            poly.Close()
            face = BRepBuilderAPI_MakeFace(poly.Wire(), True).Face()
            return BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, v["height"])).Shape()
        # tube
        if v["inner"] >= v["diameter"]:
            raise FeatureError(
                f"{name}: the inside diameter must be smaller than the outside. Make it smaller."
            )
        from fdcad.core.occ import BRepAlgoAPI_Cut

        outer = BRepPrimAPI_MakeCylinder(axis, v["diameter"] / 2, v["height"]).Shape()
        hole = BRepPrimAPI_MakeCylinder(axis, v["inner"] / 2, v["height"]).Shape()
        return BRepAlgoAPI_Cut(outer, hole).Shape()
    except FeatureError:
        raise
    except Exception as exc:  # kernel failure
        raise FeatureError(
            f"{name}: the {kind} could not be made ({type(exc).__name__}). Change its sizes."
        ) from exc


Vec3 = tuple[float, float, float]


def _icosahedron() -> tuple[list[Vec3], list[tuple[int, int, int]]]:
    """Unit icosahedron with a vertex straight up, faces counter clockwise outside."""
    t = (1 + math.sqrt(5)) / 2
    raw = [
        (-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0),
        (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
        (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1),
    ]  # fmt: skip
    faces = [
        (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
        (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
        (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
        (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
    ]  # fmt: skip
    # Turn so vertex 0 points along +Z.
    n = math.sqrt(1 + t * t)
    a = (-1 / n, t / n, 0.0)
    angle = math.acos(a[2])
    axis = (a[1], -a[0], 0.0)  # a x z
    length = math.hypot(axis[0], axis[1])
    ux, uy = axis[0] / length, axis[1] / length
    c, s = math.cos(angle), math.sin(angle)

    def turn(p: tuple[float, float, float]) -> tuple[float, float, float]:
        x, y, z = (q / n for q in p)
        dot = ux * x + uy * y
        cx, cy, cz = uy * z, -ux * z, ux * y - uy * x  # (u x p)
        return (
            x * c + cx * s + ux * dot * (1 - c),
            y * c + cy * s + uy * dot * (1 - c),
            z * c + cz * s,
        )

    return [turn(p) for p in raw], faces


def geodesic(radius: float, frequency: int, dome: bool) -> Any:
    """A geodesic sphere of flat triangles (an icosahedron with each face split
    ``frequency`` times and pushed onto the sphere), standing on XY; ``dome`` keeps
    the top half, cut flat at the sphere's middle (TR371, D936)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid, BRepBuilderAPI_Sewing
    from OCP.TopoDS import TopoDS

    from fdcad.core.occ import BRepAlgoAPI_Common

    verts, faces = _icosahedron()

    def on_sphere(p: tuple[float, float, float]) -> gp_Pnt:
        k = radius / math.sqrt(p[0] ** 2 + p[1] ** 2 + p[2] ** 2)
        return gp_Pnt(p[0] * k, p[1] * k, p[2] * k + radius)

    sewing = BRepBuilderAPI_Sewing(1e-6 * max(radius, 1.0))

    def point(a: Vec3, b: Vec3, c: Vec3, i: int, j: int) -> gp_Pnt:
        # i steps from a toward b, j from a toward c (i + j <= frequency).
        f = frequency
        w = (f - i - j) / f
        return on_sphere(
            (
                w * a[0] + i / f * b[0] + j / f * c[0],
                w * a[1] + i / f * b[1] + j / f * c[1],
                w * a[2] + i / f * b[2] + j / f * c[2],
            )
        )

    f = frequency
    for ia, ib, ic in faces:
        a, b, c = verts[ia], verts[ib], verts[ic]

        for i in range(f):
            for j in range(f - i):
                tris = [(point(a, b, c, i, j), point(a, b, c, i + 1, j), point(a, b, c, i, j + 1))]
                if i + j < f - 1:
                    tris.append(
                        (
                            point(a, b, c, i + 1, j),
                            point(a, b, c, i + 1, j + 1),
                            point(a, b, c, i, j + 1),
                        )
                    )
                for p1, p2, p3 in tris:
                    poly = BRepBuilderAPI_MakePolygon(p1, p2, p3, True)
                    sewing.Add(BRepBuilderAPI_MakeFace(poly.Wire(), True).Face())
    sewing.Perform()
    shell = TopoDS.Shell(sewing.SewedShape())
    solid = BRepBuilderAPI_MakeSolid(shell).Solid()
    if not dome:
        return solid
    cut = BRepPrimAPI_MakeBox(
        gp_Pnt(-2 * radius, -2 * radius, radius), 4 * radius, 4 * radius, 2 * radius
    ).Shape()
    top = BRepAlgoAPI_Common(solid, cut).Shape()
    move = gp_Trsf()
    move.SetTranslation(gp_Vec(0, 0, -radius))  # the flat base on XY
    return BRepBuilderAPI_Transform(top, move, True).Shape()


def _wedge(length: float, width: float, height: float, top: float) -> Any:
    """A block whose top slopes along X from ``height`` to ``top``."""
    pts = [(0.0, 0.0), (length, 0.0), (length, top), (0.0, height)]
    poly = BRepBuilderAPI_MakePolygon()
    for x, z in pts:
        if top <= 0 and (x, z) == (length, top):
            continue  # a point at the end: a triangle
        poly.Add(gp_Pnt(x, 0.0, z))
    poly.Close()
    face = BRepBuilderAPI_MakeFace(poly.Wire(), True).Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(0, width, 0)).Shape()


def _centre_shift(feature: Feature) -> gp_Vec:
    """Where to move the shape so it is centred on the origin."""
    kind = str(feature.params.get("kind", "box"))
    if kind in ("box", "wedge"):
        return gp_Vec(-_size(feature, "length") / 2, -_size(feature, "width") / 2,
                      -_size(feature, "height") / 2)  # fmt: skip
    if kind in ("sphere", "geodesic_sphere"):
        return gp_Vec(0, 0, -_size(feature, "diameter") / 2)
    if kind == "geodesic_dome":
        return gp_Vec(0, 0, 0)  # centred on its base circle
    if kind == "torus":
        return gp_Vec(0, 0, -_size(feature, "tube") / 2)
    return gp_Vec(0, 0, -_size(feature, "height") / 2)


@register
class Primitive(FeatureType):
    """A box, cylinder, sphere, cone, torus, wedge, prism or tube from typed sizes."""

    type_name = "primitive"
    makes_solid = True
    params = (
        ParamSpec("kind", choices=KINDS, default="box"),
        ParamSpec("operation", choices=("boss", "cut"), default="boss"),
        ParamSpec("merge", default=True, optional=True),
        ParamSpec("centred", default=False, optional=True),
        *(
            ParamSpec(n, kind=Kind.LENGTH, optional=True)
            for n in ("length", "width", "height", "top", "diameter", "diameter2", "inner")
        ),
        ParamSpec("ring", kind=Kind.LENGTH, optional=True),
        ParamSpec("tube", kind=Kind.LENGTH, optional=True),
        ParamSpec("sides", kind=Kind.NUMBER, optional=True),
        ParamSpec("frequency", kind=Kind.NUMBER, optional=True),
    )

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The shape, placed on its frame."""
        from fdcad.core.features.bounding_box import frame_from_ref

        shape = _shape(feature)
        move = gp_Trsf()
        if feature.params.get("centred") is True:
            move.SetTranslation(_centre_shift(feature))
        frame = (
            frame_from_ref(ctx, feature.refs["frame"], feature.name)
            if feature.refs.get("frame")
            else gp_Ax3()
        )
        place = gp_Trsf()
        place.SetTransformation(frame, gp_Ax3())
        placed = BRepBuilderAPI_Transform(shape, place.Multiplied(move), True).Shape()
        return NamedShape(placed, restrict([], placed, feature.id))

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Make the shape and add or cut it."""
        operation = str(feature.params.get("operation", "boss"))
        tool = self.tool(feature, ctx)
        issues: list[Any] = []
        body = combine_or_keep(feature, ctx.body, tool, operation, ctx, issues)
        issues += check_result(feature.id, feature.name, ctx.body, body, None)
        # With Merge result off the separate body is what was asked for (D1061).
        return FeatureResult(body=body, issues=expected_issues(feature, issues))
