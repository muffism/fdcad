"""Half lap joints between crossing plates (TUTORIAL_REVIEW_SPEC_2 TR364, DECISIONS D882).

Type ``half_lap``. Pick two plate bodies that cross (``refs.bodies``). Each plate's
thickness direction is the normal of its largest flat face; the joint runs along
the line where the plates meet (the cross product of the two normals). Where they
cross, the first plate is notched from one side and the second from the other, so
they slot together: the first loses the part of the crossing above the split, the
second the part below. ``depth`` is the split as a percent of the crossing's height
(50 is half and half). Each notch is the other plate grown by half the
``clearance`` on each side and shrunk by half the ``kerf`` (a laser's cut width),
so the cut parts fit. New faces are ``<fid>/lap/...``.
"""

from __future__ import annotations

from typing import Any

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    register,
)
from fdcad.core.units import Kind


def _value(feature: Feature, key: str, default: float) -> float:
    found = feature.params.get(key)
    return found.value if isinstance(found, Param) else default


def thickness_normal(solid: Any) -> tuple[float, float, float] | None:
    """The normal of the solid's largest flat face: a plate's thickness direction."""
    from fdcad.core.features.solids import face_area
    from fdcad.core.naming.names import faces_of
    from fdcad.core.plane_normal import plane_normal

    best: tuple[float, tuple[float, float, float]] | None = None
    for face in faces_of(solid):
        n = plane_normal(face)
        if n is None:
            continue
        area = face_area([face])
        if best is None or area > best[0]:
            best = (area, n)
    return best[1] if best is not None else None


def _corners(shape: Any) -> list[tuple[float, float, float]]:
    from OCP.BRep import BRep_Tool
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    out = []
    exp = TopExp_Explorer(shape, TopAbs_VERTEX)
    while exp.More():
        p = BRep_Tool.Pnt_s(TopoDS.Vertex(exp.Current()))
        out.append((p.X(), p.Y(), p.Z()))
        exp.Next()
    return out


def _grown(solid: Any, by: float) -> Any:
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeOffsetShape

    if abs(by) < 1e-9:
        return solid
    maker = BRepOffsetAPI_MakeOffsetShape()
    maker.PerformByJoin(solid, by, 1e-6)
    if not maker.IsDone():
        raise FeatureError("The plate could not be grown by the clearance. Use a smaller value.")
    return maker.Shape()


def _half(origin: Any, up: tuple[float, float, float], size: float, above: bool) -> Any:
    """A big box on one side of the plane through ``origin`` square to ``up``."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec

    z = gp_Dir(*up) if above else gp_Dir(-up[0], -up[1], -up[2])
    frame = gp_Ax2(gp_Pnt(*origin), z)
    shift = gp_Vec(frame.XDirection()).Multiplied(-size) + gp_Vec(frame.YDirection()).Multiplied(
        -size
    )
    corner = gp_Pnt(*origin).Translated(shift)
    box_frame = gp_Ax2(corner, z, frame.XDirection())
    return BRepPrimAPI_MakeBox(box_frame, 2 * size, 2 * size, size).Shape()


@register
class HalfLap(FeatureType):
    """Matching notches so two crossing plates slot together."""

    type_name = "half_lap"
    makes_solid = True
    params = (
        ParamSpec("depth_percent", kind=Kind.NUMBER, optional=True),
        ParamSpec("clearance", kind=Kind.LENGTH, optional=True),
        ParamSpec("kerf", kind=Kind.LENGTH, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Notch both plates."""
        import math

        from fdcad.core.features.bodies import body_indices, join, rest_of, sub_body
        from fdcad.core.features.booleans import boolean_named
        from fdcad.core.features.solids import check_result, reach_from, solids, volume_of
        from fdcad.core.naming.names import NamedShape, in_order
        from fdcad.core.occ import BRepAlgoAPI_Common

        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part is empty. Add the plates first.")
        indices, issues = body_indices(ctx, feature.refs.get("bodies"), name)
        if len(indices) != 2:
            raise FeatureError(f"{name}: pick exactly two plate bodies that cross.")
        all_solids = solids(ctx.body.shape)
        a, b = all_solids[indices[0]], all_solids[indices[1]]
        na, nb = thickness_normal(a), thickness_normal(b)
        if na is None or nb is None:
            raise FeatureError(f"{name}: a picked body has no flat face. Pick flat plates.")
        up = (
            na[1] * nb[2] - na[2] * nb[1],
            na[2] * nb[0] - na[0] * nb[2],
            na[0] * nb[1] - na[1] * nb[0],
        )
        size = math.sqrt(sum(c * c for c in up))
        if size < 0.1:
            raise FeatureError(f"{name}: the plates are parallel. Pick two plates that cross.")
        up = (up[0] / size, up[1] / size, up[2] / size)
        crossing = BRepAlgoAPI_Common(a, b).Shape()
        if not solids(crossing) or volume_of(crossing) < 1e-9:
            raise FeatureError(f"{name}: the plates do not cross. Move them so they overlap.")
        heights = [sum(p[k] * up[k] for k in range(3)) for p in _corners(crossing)]
        low, high = min(heights), max(heights)
        percent = _value(feature, "depth_percent", 50.0)
        if not 0 < percent < 100:
            raise FeatureError(
                f"{name}: the depth is out of range. Enter a depth between 0 and 100 percent."
            )
        split = low + (high - low) * (1 - percent / 100)
        origin = (up[0] * split, up[1] * split, up[2] * split)
        reach = reach_from(origin, a, b)  # the halves are centred on the axis (D1087)
        grow = _value(feature, "clearance", 0.1) / 2 - _value(feature, "kerf", 0.0) / 2
        notch_a = BRepAlgoAPI_Common(_grown(b, grow), _half(origin, up, reach, True)).Shape()
        notch_b = BRepAlgoAPI_Common(_grown(a, grow), _half(origin, up, reach, False)).Shape()
        fid = feature.id
        parts: list[NamedShape | None] = [rest_of(ctx.body, indices, fid)]
        for index, notch in ((indices[0], notch_a), (indices[1], notch_b)):
            plate = sub_body(ctx.body, [index], fid)
            tool = NamedShape(
                notch, [(f"{fid}/lap/{k}", f) for k, f in enumerate(in_order(notch), 1)]
            )
            parts.append(boolean_named("cut", plate, tool, fid, name))
        result = join(parts, fid)
        assert result is not None
        found = [
            i for i in check_result(fid, name, ctx.body, result, None) if i.code != "separate_body"
        ]
        return FeatureResult(body=result, issues=[*issues, *found])
