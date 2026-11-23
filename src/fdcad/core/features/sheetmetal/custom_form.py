"""Own forming tools (TR279, DECISIONS D2313): a Forming Tool shaped by a body of the part.

A Forming Tool with ``tool`` "custom" takes its shape from a solid body of the part:
``refs.tool_face`` is the tool's stop face (a flat face; the side that sits on the sheet),
``refs.remove_faces`` lists faces of the tool that become holes in the formed sheet,
and ``refs.insert`` (optional vertex) is the insert point (the stop face's centre when
missing). On each sketch line the tool is placed with the insert point on the line's
middle and its X axis along the line, turned by ``tool_angle`` and mirrored across
the line with ``mirror``. The sheet takes the tool's shape with its thickness measured
along the press, as the built in forms do (D545), and the tool body leaves the part.
"""

from __future__ import annotations

import math
from typing import Any

from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Feature
from fdcad.core.features.base import BuildContext, FeatureError
from fdcad.core.naming.names import NamedShape, centroid


def _faces(feature: Feature, ctx: BuildContext, key: str) -> list[TopoDS_Face]:
    from fdcad.core.naming.resolve import resolve_face

    refs = feature.refs.get(key)
    if isinstance(refs, dict):
        refs = [refs]
    out = []
    for ref in refs if isinstance(refs, list) else []:
        face, _issues = resolve_face(ctx.body, ref, feature.name)
        out.append(face)
    return out


def tool_solid_index(feature: Feature, ctx: BuildContext) -> int | None:
    """Index of the solid holding the tool's stop face, or None (D2313)."""
    from fdcad.core.features.bodies import solid_of_face

    if ctx.body is None or not feature.refs.get("tool_face"):
        return None
    try:
        stops = _faces(feature, ctx, "tool_face")
    except FeatureError:
        return None
    if not stops:
        return None
    index = solid_of_face(ctx.body.shape, stops[0])
    return index if index >= 0 else None


def custom_tool(
    feature: Feature, ctx: BuildContext, angle: float, mirror: bool
) -> tuple[TopoDS_Shape, list[TopoDS_Shape]]:
    """The tool solid and the hole solids in the form frame: the stop face on z = 0 with
    the tool above it, the insert point at the origin."""
    from fdcad.core.features.bodies import solid_of_face
    from fdcad.core.features.sheetmetal.model import frame
    from fdcad.core.features.solids import solids
    from fdcad.core.plane_normal import plane_normal

    name = feature.name
    if ctx.body is None:
        raise FeatureError(f"{name}: there is no tool body. Add the tool as a body first.")
    stops = _faces(feature, ctx, "tool_face")
    if not stops:
        raise FeatureError(
            f"{name}: pick the stop face of the tool body: the flat face that sits on the sheet."
        )
    stop = stops[0]
    normal = plane_normal(stop)
    if normal is None:
        raise FeatureError(f"{name}: the stop face is curved. Pick a flat stop face.")
    solid = solids(ctx.body.shape)[solid_of_face(ctx.body.shape, stop)]
    insert = centroid(stop)
    pick = feature.refs.get("insert")
    if isinstance(pick, list):
        pick = pick[0] if pick else None
    if isinstance(pick, dict):
        from fdcad.core.features.geometry_refs import resolve_placement

        insert = resolve_placement(ctx, pick, name, "point").point
    up = (-normal[0], -normal[1], -normal[2])
    x = (1.0, 0.0, 0.0) if abs(normal[0]) < 0.9 else (0.0, 1.0, 0.0)
    d = sum(x[i] * up[i] for i in range(3))
    x = (x[0] - d * up[0], x[1] - d * up[1], x[2] - d * up[2])
    size = math.sqrt(sum(c * c for c in x))
    x = (x[0] / size, x[1] / size, x[2] / size)
    trsf = frame(insert, x, up).Inverted()
    if mirror:
        flip = gp_Trsf()
        flip.SetMirror(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0)))
        trsf = flip.Multiplied(trsf)
    if abs(angle) > 1e-12:
        turn = gp_Trsf()
        turn.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), angle)
        trsf = turn.Multiplied(trsf)
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform

    def moved(shape: TopoDS_Shape) -> TopoDS_Shape:
        return BRepBuilderAPI_Transform(shape, trsf, True).Shape()

    tool = moved(solid)
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(tool, box, False, False)
    if box.CornerMin().Z() < -1e-6:
        raise FeatureError(
            f"{name}: the tool body reaches past its stop face. Pick the face the whole "
            "tool stands on."
        )
    holes = []
    for face in _faces(feature, ctx, "remove_faces"):
        flat = plane_normal(face)
        if flat is None:
            raise FeatureError(
                f"{name}: a face to remove is curved. Pick flat faces to leave holes."
            )
        local = TopoDS.Face(moved(face))
        n = plane_normal(local)
        assert n is not None
        holes.append(_through(local, n))
    return tool, holes


def _through(face: TopoDS_Face, n: tuple[float, float, float]) -> TopoDS_Shape:
    """A block through the formed sheet under ``face``: from well inside along the face's
    normal to just outside."""
    reach = 50.0
    back = gp_Trsf()
    back.SetTranslation(gp_Vec(-n[0] * reach, -n[1] * reach, -n[2] * reach))
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform

    start = BRepBuilderAPI_Transform(face, back, True).Shape()
    return BRepPrimAPI_MakePrism(start, gp_Vec(n[0] * (reach + 1), n[1] * (reach + 1),
                                                 n[2] * (reach + 1))).Shape()  # fmt: skip


def foot_box(tool: TopoDS_Shape) -> tuple[float, float, float, float]:
    """The tool's footprint on the sheet: x and y range in the form frame."""
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(tool, box, False, False)
    lo, hi = box.CornerMin(), box.CornerMax()
    return lo.X(), lo.Y(), hi.X(), hi.Y()


def named(prefix: str, shape: Any) -> NamedShape:
    """The shape with every face called ``<prefix>/form``."""
    from fdcad.core.naming.names import faces_of

    return NamedShape(shape, [(f"{prefix}/form", f) for f in faces_of(shape)])
