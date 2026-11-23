"""Roof: an equal slope roof over a closed outline (TR258 item 1, DECISIONS D2414).

Type ``roof``. Refs: ``sketch`` (``{"feature": id}``: a sketch whose regions are the
outlines; holes make courtyards). Params:

- ``slope``: angle of every roof face from the sketch plane (default 30 degrees).
- ``max_height``: optional length: the roof is cut flat at this height above the
  sketch (0 or empty: up to the ridges).
- ``operation``: ``boss`` (default) or ``cut``.

Every point of the roof's top is ``tan(slope)`` times its distance to the nearest
outline edge above the sketch plane, so all faces have the same slope and meet in
hips, valleys and ridges for any outline, also one with inside corners. It is built
as the region's prism less, for every outline edge, the space above the sloped
"tent" over that edge (two cones at its ends and a wedge along it). Curved edges
are followed as short straight pieces. Faces: ``roof/base``, ``roof/top`` (a
Max height cut) and ``roof/slope``. No Qt.
"""

from __future__ import annotations

import math
from itertools import pairwise
from typing import Any

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone, BRepPrimAPI_MakePrism
from OCP.GeomAbs import GeomAbs_Line
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Shape

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    register,
)
from fdcad.core.features.solids import FUZZY_TOLERANCE, check_result, combine, expected_issues
from fdcad.core.naming.names import NamedShape, faces_of, restrict
from fdcad.core.occ import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse, ShapeList
from fdcad.core.units import Kind

DEFAULT_SLOPE = math.radians(30.0)
#: Straight pieces a curved outline edge is followed with.
CURVE_PIECES = 16
MOST_EDGES = 400


def _segments(face: Any) -> list[tuple[gp_Pnt, gp_Pnt]]:
    """Every outline edge of ``face`` as straight pieces (3D points)."""
    out: list[tuple[gp_Pnt, gp_Pnt]] = []
    explorer = TopExp_Explorer(face, TopAbs_EDGE)
    while explorer.More():
        curve = BRepAdaptor_Curve(TopoDS.Edge(explorer.Current()))
        explorer.Next()
        t0, t1 = curve.FirstParameter(), curve.LastParameter()
        steps = 1 if curve.GetType() == GeomAbs_Line else CURVE_PIECES
        points = [curve.Value(t0 + (t1 - t0) * k / steps) for k in range(steps + 1)]
        out.extend(pairwise(points))
    return out


def _tent(a: gp_Pnt, b: gp_Pnt, up: gp_Dir, rise: float, height: float) -> list[TopoDS_Shape]:
    """The space above the slope over the piece from ``a`` to ``b`` (up to ``height``):
    a cone at each end and a wedge along it. ``rise`` is tan(slope)."""
    reach = height / rise
    out = [BRepPrimAPI_MakeCone(gp_Ax2(p, up), 0.0, reach, height).Shape() for p in (a, b)]
    along = gp_Vec(a, b)
    if along.Magnitude() < 1e-9:
        return out[:1]
    side = gp_Vec(up).Crossed(along).Normalized().Multiplied(reach)
    top = gp_Vec(up).Multiplied(height)
    poly = BRepBuilderAPI_MakePolygon()
    for p in (a, a.Translated(top + side), a.Translated(top - side)):
        poly.Add(p)
    poly.Close()
    wedge = BRepBuilderAPI_MakeFace(poly.Wire(), True).Face()
    out.append(BRepPrimAPI_MakePrism(wedge, along).Shape())
    return out


@register
class Roof(FeatureType):
    """A roof of one slope over every edge of a sketch outline."""

    type_name = "roof"
    makes_solid = True
    params = (
        ParamSpec("slope", kind=Kind.ANGLE, optional=True),
        ParamSpec("max_height", kind=Kind.LENGTH, optional=True),
        ParamSpec("operation", choices=("boss", "cut"), default="boss", optional=True),
    )

    def _solid(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        from fdcad.core.features.solids import bounding_size, compound
        from fdcad.core.features.sweep import _sketch_output

        owner, fid = feature.name, feature.id
        out = _sketch_output(feature, ctx, "sketch", "outline")
        if out.profile is None or not out.profile.faces:
            raise FeatureError(f"{owner}: the sketch has no closed outline. Close the sketch.")
        value = feature.params.get("slope")
        slope = value.value if isinstance(value, Param) else DEFAULT_SLOPE
        if not math.radians(1) <= slope <= math.radians(85):
            raise FeatureError(f"{owner}: the slope must be 1 to 85 degrees. Enter another slope.")
        rise = math.tan(slope)
        cap = feature.params.get("max_height")
        limit = cap.value if isinstance(cap, Param) and cap.value > 0 else None
        up = gp_Dir(*out.plane.normal)
        size = bounding_size(*out.profile.faces)
        height = rise * size / 2 + 1.0
        if limit is not None:
            height = min(height, limit)
        shapes = []
        for face in out.profile.faces:
            segments = _segments(face)
            if len(segments) > MOST_EDGES:
                raise FeatureError(
                    f"{owner}: the outline has more than {MOST_EDGES} edges. Use a sketch "
                    "with fewer edges."
                )
            block = BRepPrimAPI_MakePrism(face, gp_Vec(up).Multiplied(height)).Shape()
            tents = ShapeList()
            for a, b in segments:
                for piece in _tent(a, b, up, rise, rise * size / 2 + 1.0):
                    tents.Append(piece)
            args = ShapeList()
            args.Append(block)
            cut = BRepAlgoAPI_Cut()
            cut.SetArguments(args)
            cut.SetTools(tents)
            cut.SetFuzzyValue(FUZZY_TOLERANCE)
            cut.Build()
            if not cut.IsDone():
                raise FeatureError(
                    f"{owner}: the roof could not be made. Change the slope or simplify the "
                    "outline."
                )
            shapes.append(cut.Shape())
        shape = (
            shapes[0]
            if len(shapes) == 1
            else BRepAlgoAPI_Fuse(shapes[0], compound(shapes[1:])).Shape()
        )
        names = [(f"{fid}/roof/{_role(f, up, out.plane.origin)}", f) for f in faces_of(shape)]
        return NamedShape(shape, restrict(names, shape, fid))

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Add or cut the roof."""
        tool = self._solid(feature, ctx)
        operation = str(feature.params.get("operation", "boss"))
        if ctx.body is None:
            if operation == "cut":
                raise FeatureError(f"{feature.name}: there is nothing to cut. Choose Add.")
            return FeatureResult(body=tool)
        # A roof drawn on a face is added to (or cut from) that face's body only (IDEAS 52,
        # D2641); it was combined with the whole part, which joined to it any other body
        # the roof touched. A roof drawn on a plane still meets every body.
        from fdcad.core.features.bodies import in_body_of, sketch_face

        def run(part: NamedShape) -> NamedShape:
            return combine(feature.id, feature.name, part, tool, operation)

        drawn_on = sketch_face(feature, ctx)
        body = (
            run(ctx.body) if drawn_on is None else in_body_of(ctx.body, drawn_on, feature.id, run)
        )
        found = check_result(feature.id, feature.name, ctx.body, body, None)
        return FeatureResult(body=body, issues=expected_issues(feature, found))

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The roof solid, for the preview."""
        return self._solid(feature, ctx)


def _role(face: Any, up: gp_Dir, origin: tuple[float, float, float]) -> str:
    """``base`` for the flat face on the sketch plane, ``top`` for a flat cut at Max
    height, else ``slope``."""
    from fdcad.core.features.sketch import face_plane

    plane = face_plane(face)
    n = up.Coord()
    if plane is None or abs(sum(a * b for a, b in zip(plane.normal, n, strict=True))) < 1 - 1e-9:
        return "slope"
    lift = sum((p - o) * c for p, o, c in zip(plane.origin, origin, n, strict=True))
    return "base" if abs(lift) < 1e-6 else "top"
