"""Section sizes along a sweep (TR396 item 1, D1910).

``section_values`` is text such as ``d1 = 10 + 10 * t; d2 = 4``: profile sketch
dimensions (by id, ``d1``, or by the user's name) and formulas of ``t``, the position
along the path from 0 at the start to 1 at the end, in the units of the dimension
(mm or degrees; variables of the part may be used too). The profile sketch is solved
again at each of ``STEPS`` stations with those values, carried along the path with
the least turning, and the sections are joined with a smooth loft.
"""

from __future__ import annotations

import copy
import re
from typing import Any

from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
from OCP.gp import gp_Vec
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Wire

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import BuildContext, FeatureError, SketchOutput
from fdcad.core.naming.names import NamedFace, NamedShape, restrict
from fdcad.core.occ import shape_list
from fdcad.core.units import Kind

#: How many sections the sweep is built through.
STEPS = 9


def parse_values(feature: Feature) -> list[tuple[str, str]]:
    """``section_values`` as (dimension, formula) pairs. Raises FeatureError."""
    text = str(feature.params.get("section_values", "") or "").strip()
    out: list[tuple[str, str]] = []
    for part in text.split(";"):
        part = part.strip()
        if not part:
            continue
        found = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)", part)
        if found is None:
            raise FeatureError(
                f"{feature.name}: section values must read like d1 = 10 + 10 * t. Fix '{part}'."
            )
        out.append((found.group(1), found.group(2).strip()))
    return out


def _dimension(sketch: Any, key: str) -> Any:
    for dim in sketch.dimensions:
        if dim.id == key or dim.name == key:
            return dim
    return None


def _profile_at(
    feature: Feature, ctx: BuildContext, out: SketchOutput, values: list[tuple[str, str]], t: float
) -> TopoDS_Wire:
    """The profile's outline with the dimensions set for position ``t``."""
    from fdcad.core.sketch.profiles import build_profile
    from fdcad.core.sketch.solver import solve
    from fdcad.core.units.errors import ExpressionError
    from fdcad.core.units.expressions import evaluate

    sketch = copy.deepcopy(out.model)
    names = {**ctx.variables, "t": (Kind.NUMBER, t)}
    for key, formula in values:
        dim = _dimension(sketch, key)
        if dim is None:
            raise FeatureError(
                f"{feature.name}: the profile sketch has no dimension {key}. Enter a dimension "
                "of the profile, such as d1."
            )
        kind = Kind.ANGLE if dim.type == "angle" else Kind.LENGTH
        try:
            value = evaluate(f"={formula}", kind, ctx.document.units, names)
        except ExpressionError as exc:
            raise FeatureError(f"{feature.name}: the formula for {key}: {exc}") from None
        dim.param = Param(f"={formula}", value)
    solved = solve(sketch)
    if not solved.solved:
        raise FeatureError(
            f"{feature.name}: the profile cannot be solved at {t:.0%} along the path with its "
            "section values. Change the formulas."
        )
    from fdcad.core.features.sweep import _wires

    profile = build_profile(sketch, out.plane)
    if len(profile.faces) != 1:
        raise FeatureError(
            f"{feature.name}: section values need a profile of one closed region. Edit the sketch."
        )
    outer, holes = _wires(profile.faces[0])
    if holes:
        raise FeatureError(
            f"{feature.name}: section values work with profiles without holes. Remove the "
            "holes, or clear the section values."
        )
    return outer


def valued_sweep(
    feature: Feature, ctx: BuildContext, out: SketchOutput, path: TopoDS_Wire, up: gp_Vec
) -> NamedShape:
    """The sweep through the profile solved at each station (TR396 item 1, D1910)."""
    from fdcad.core.features.sweep import _faces
    from fdcad.core.features.sweep_guides import _carried, _rigid, _stations

    fid, owner = feature.id, feature.name
    values = parse_values(feature)
    stations = _stations(path)
    p0, t0 = stations[0]
    x0 = up.Subtracted(t0.Multiplied(up.Dot(t0)))
    if x0.Magnitude() < 1e-9:
        x0 = t0.Crossed(gp_Vec(0, 0, 1))
    frames = _carried(stations, x0.Normalized())
    loft = BRepOffsetAPI_ThruSections(True, False, 1e-6)
    loft.CheckCompatibility(False)
    first: tuple[TopoDS_Wire, Any] | None = None
    for i in range(STEPS):
        t = i / (STEPS - 1)
        index = round(t * (len(stations) - 1))
        p, tangent = stations[index]
        wire = _profile_at(feature, ctx, out, values, t)
        moved = BRepBuilderAPI_Transform(wire, _rigid(p0, t0, frames[0], p, tangent, frames[index]))
        moved.Build()
        if first is None:
            first = (wire, moved)
        loft.AddWire(TopoDS.Wire(moved.Shape()))
    try:
        loft.Build()
        ok = loft.IsDone()
    except Exception:  # kernel failure
        ok = False
    if not ok or first is None:
        raise FeatureError(
            f"{owner}: the sweep with section values could not be made. Use gentler formulas "
            "or a gentler path."
        )
    names: list[NamedFace] = []
    wire, maker = first
    profile = out.profile
    ex = TopExp_Explorer(wire, TopAbs_EDGE)
    while ex.More():
        edge = TopoDS.Edge(ex.Current())
        ex.Next()
        image = maker.ModifiedShape(edge)
        entity = profile.entity_of(edge) if profile is not None else None
        if image.IsNull():
            continue
        for k, side in enumerate(shape_list(loft.Generated(image)), start=1):
            if side.ShapeType() == TopAbs_FACE:
                label = entity or f"edge{k}"
                names.append((f"{fid}/side/{label}", TopoDS.Face(side)))
    for role, shape in (("cap/start", loft.FirstShape()), ("cap/end", loft.LastShape())):
        for f in _faces(shape):
            names.append((f"{fid}/{role}", f))
    solid = loft.Shape()
    return NamedShape(solid, restrict(names, solid, fid))


__all__ = ["STEPS", "parse_values", "valued_sweep"]
