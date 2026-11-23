"""Cross Break (PHASE5_SPEC P5.6, DECISIONS D539): cosmetic X lines across a wall.

Type ``cross_break``. Params: ``reverse`` (titles the break "down" instead of "up"),
``break_angle`` and ``break_radius`` (optional; written into each line's title, so the
flat pattern export carries them, TR174 item 3, D1107).
Refs: ``face`` (a flat face of a wall), ``sheet_metal``. No geometry changes.
"""

from __future__ import annotations

from OCP.TopoDS import TopoDS_Shape

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    register,
)
from fdcad.core.features.lookup import resolve_face
from fdcad.core.features.sheetmetal.common import own_body, require_sheet
from fdcad.core.features.sheetmetal.locate import bounds, wall_face
from fdcad.core.features.sheetmetal.model import SheetResult
from fdcad.core.units import Kind


@register
class CrossBreak(FeatureType):
    """Marks a wall with two cosmetic diagonal lines."""

    type_name = "cross_break"
    makes_solid = True
    params = (
        ParamSpec("reverse", default=False, optional=True),
        ParamSpec("break_angle", kind=Kind.ANGLE, optional=True),
        ParamSpec("break_radius", kind=Kind.LENGTH, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Add the lines to the sheet model; the part is unchanged."""
        name = feature.name
        model = require_sheet(feature, ctx)
        ref = feature.refs.get("face")
        if not isinstance(ref, dict):
            raise FeatureError(f"{name}: pick a flat face of a wall.")
        face, issues = resolve_face(ctx.body, ref, name)
        spot = wall_face(model, face, name)
        piece = model.piece(spot.wid)
        lo, hi = bounds(piece)
        title = "Cross break down" if feature.params.get("reverse") is True else "Cross break up"
        title += _values(feature)
        mid = (lo[2] + hi[2]) / 2
        for a, b in (((lo[0], lo[1]), (hi[0], hi[1])), ((lo[0], hi[1]), (hi[0], lo[1]))):
            for p, q in _inside(piece.shape, a, b, mid):
                model.marks.append((spot.wid, p, q, title))
        return SheetResult(body=own_body(feature, ctx), issues=issues, sheet=model)


def _values(feature: Feature) -> str:
    """The typed break angle and radius as title text, such as " 3 degrees, radius 50 mm"."""
    import math

    from fdcad.core.document.model import Param

    parts = []
    angle = feature.params.get("break_angle")
    if isinstance(angle, Param):
        if not 0 < angle.value < math.pi:
            raise FeatureError(
                f"{feature.name}: the break angle must be between 0 and 180 degrees. "
                "Enter another angle."
            )
        parts.append(f"{math.degrees(angle.value):g} degrees")
    radius = feature.params.get("break_radius")
    if isinstance(radius, Param):
        if radius.value <= 0:
            raise FeatureError(
                f"{feature.name}: the break radius must be greater than zero. Enter a radius."
            )
        parts.append(f"radius {radius.value:g} mm")
    return (" " + ", ".join(parts)) if parts else ""


def _inside(
    wall: TopoDS_Shape, a: tuple[float, float], b: tuple[float, float], z: float
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """The parts of the line from ``a`` to ``b`` that lie on the wall, so an L shaped or
    notched wall keeps its marks on the sheet (audit A item 4, D727)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.gp import gp_Pnt

    from fdcad.core.features.modify import edges_of
    from fdcad.core.features.solids import line_ends
    from fdcad.core.occ import BRepAlgoAPI_Common

    edge = BRepBuilderAPI_MakeEdge(gp_Pnt(a[0], a[1], z), gp_Pnt(b[0], b[1], z)).Edge()
    common = BRepAlgoAPI_Common(edge, wall)
    common.Build()
    if not common.IsDone():
        return [(a, b)]
    out = []
    for piece in edges_of(common.Shape()):
        ends = line_ends(piece)
        if ends is not None:
            (x0, y0, _z0), (x1, y1, _z1) = ends
            out.append(((x0, y0), (x1, y1)))
    return out or [(a, b)]
