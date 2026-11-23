"""Projected curve (PHASE3_SPEC P3.6 item 2, DECISIONS D291).

Params:

- ``mode``: ``"faces"`` (sketch onto faces, default) or ``"sketches"`` (the 3D
  curve where two sketches on crossing planes meet).
- ``reverse``: project the other way. ``both``: project both ways.

Refs:

- ``sketch``: the sketch to project (both modes).
- ``faces``: face references to project onto (``"faces"``).
- ``direction``: optional, a plane or axis feature, a flat face or a straight edge;
  the sketch's normal when left out (``"faces"``).
- ``sketch2``: the second sketch (``"sketches"``).
"""

from __future__ import annotations

import math
from typing import Any

from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepGProp import BRepGProp
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.BRepProj import BRepProj_Projection
from OCP.gp import gp_Dir, gp_Trsf, gp_Vec
from OCP.GProp import GProp_GProps
from OCP.TopoDS import TopoDS_Edge, TopoDS_Shape, TopoDS_Wire

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    SketchOutput,
    Vec3,
    register,
)
from fdcad.core.features.curves import (
    connect,
    curve_result,
    edges_in,
    group,
    sketch_curve_edges,
)
from fdcad.core.features.solids import bounding_size
from fdcad.core.occ import BRepAlgoAPI_Section


def _sketch(feature: Feature, ctx: BuildContext, key: str, label: str) -> SketchOutput:
    ref = feature.refs.get(key)
    if not isinstance(ref, dict) or "feature" not in ref:
        raise FeatureError(f"{feature.name} has no {label}. Choose a sketch.")
    out = ctx.result(str(ref["feature"])).sketch
    if out is None:
        raise FeatureError(f"{feature.name}: the {label} is not a sketch. Choose a sketch.")
    return out


def pick_direction(feature: Feature, ctx: BuildContext, key: str) -> Vec3 | None:
    """A direction from a plane or axis feature, a flat face or a straight edge; None when
    unset."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Plane

    from fdcad.core.features.solids import line_ends
    from fdcad.core.naming.resolve import resolve_edge, resolve_face

    owner = feature.name
    ref: Any = feature.refs.get(key)
    if not isinstance(ref, dict):
        return None
    if "feature" in ref and "kind" not in ref:
        fid = str(ref["feature"])
        res = ctx.results.get(fid)
        if res is None:
            raise FeatureError(f"{owner}: the direction pick was lost. Pick it again.")
        if res.plane is not None:
            return res.plane.normal
        datum = res.datum
        if datum is not None and datum.kind == "axis" and datum.direction is not None:
            return datum.direction
        raise FeatureError(
            f"{owner}: {ctx._name(fid)} is not a plane or an axis. "
            "Pick a plane, an axis, a flat face or a straight edge."
        )
    if ref.get("kind") == "edge":
        edge, _issues = resolve_edge(ctx.body, ref, owner)
        ends = line_ends(edge)
        if ends is None:
            raise FeatureError(
                f"{owner}: the direction edge is not straight. Pick a straight edge."
            )
        a, b = ends
        d = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        n = math.sqrt(sum(c * c for c in d))
        return (d[0] / n, d[1] / n, d[2] / n)
    face, _issues = resolve_face(ctx.body, ref, owner)
    surface = BRepAdaptor_Surface(face)
    if surface.GetType() != GeomAbs_Plane:
        raise FeatureError(f"{owner}: the direction face is not flat. Pick a flat face.")
    d = surface.Plane().Axis().Direction()
    return (d.X(), d.Y(), d.Z())


def _side(wire: TopoDS_Wire, origin: Vec3, direction: Vec3) -> float:
    """Signed distance of the wire's centre from the sketch plane along ``direction``."""
    props = GProp_GProps()
    BRepGProp.LinearProperties_s(wire, props)
    p = props.CentreOfMass()
    c = (p.X(), p.Y(), p.Z())
    return float(sum((c[i] - origin[i]) * direction[i] for i in range(3)))


def _onto_faces(
    feature: Feature, ctx: BuildContext, out: SketchOutput
) -> tuple[TopoDS_Shape, list[Issue]]:
    from fdcad.core.features.modify import resolve_faces

    owner = feature.name
    if not feature.refs.get("faces"):
        raise FeatureError(f"{owner}: pick the faces to project onto.")
    found, issues = resolve_faces(feature, ctx, "faces")
    target = group([f for _n, f in found])
    direction = pick_direction(feature, ctx, "direction") or out.plane.normal
    if feature.params.get("reverse") is True:
        direction = (-direction[0], -direction[1], -direction[2])
    both = feature.params.get("both") is True
    edges = sketch_curve_edges(out)
    if not edges:
        raise FeatureError(
            f"{owner}: the sketch has no curves to project. Draw curves in it first."
        )
    wires = connect(edges)
    kept: list[TopoDS_Shape] = []
    for wire in wires:
        projection = BRepProj_Projection(wire, target, gp_Dir(*direction))
        while projection.More():
            piece = projection.Current()
            projection.Next()
            if both or _side(piece, out.plane.origin, direction) > -1e-7:
                kept.append(piece)
    if not kept:
        raise FeatureError(
            f"{owner}: the sketch does not land on the picked faces. "
            "Pick other faces, or turn on Reverse or Both directions."
        )
    return (kept[0] if len(kept) == 1 else group(kept)), issues


def _sheet(out: SketchOutput, size: float) -> TopoDS_Shape:
    """The sketch's curves pulled both ways along its normal into surfaces."""
    n = out.plane.normal
    edges = sketch_curve_edges(out)
    if not edges:
        raise FeatureError("The sketch has no curves. Draw curves in it first.")
    trsf = gp_Trsf()
    trsf.SetTranslation(gp_Vec(-n[0] * size, -n[1] * size, -n[2] * size))
    moved = BRepBuilderAPI_Transform(group(list(edges)), trsf, True).Shape()
    vec = gp_Vec(n[0] * 2 * size, n[1] * 2 * size, n[2] * 2 * size)
    return BRepPrimAPI_MakePrism(moved, vec).Shape()


def _sketch_sketch(feature: Feature, ctx: BuildContext, out: SketchOutput) -> TopoDS_Shape:
    owner = feature.name
    other = _sketch(feature, ctx, "sketch2", "second sketch")
    n1, n2 = out.plane.normal, other.plane.normal
    if abs(sum(a * b for a, b in zip(n1, n2, strict=True))) > 1 - 1e-9:
        raise FeatureError(
            f"{owner}: the two sketches are on parallel planes. Move one to a crossing plane."
        )
    first, second = sketch_curve_edges(out), sketch_curve_edges(other)
    if not first or not second:
        raise FeatureError(f"{owner}: both sketches need curves. Draw curves in each sketch.")
    size = 2.0 * max(bounding_size(group(list(first)), group(list(second))), 1.0)
    try:
        sheet1, sheet2 = _sheet(out, size), _sheet(other, size)
        section = BRepAlgoAPI_Section(sheet1, sheet2)
        section.Build()
    except FeatureError:
        raise
    except Exception as exc:
        raise FeatureError(
            f"{owner}: the sketches could not be intersected. Change the curves so they cross."
        ) from exc
    edges: list[TopoDS_Edge] = edges_in(section.Shape()) if section.IsDone() else []
    if not edges:
        raise FeatureError(
            f"{owner}: the two sketches do not meet. Change them so their curves "
            "cross when seen along each other's planes."
        )
    wires = connect(edges)
    return wires[0] if len(wires) == 1 else group(list(wires))


@register
class ProjectedCurve(FeatureType):
    """A sketch projected onto faces, or the curve where two sketches meet."""

    type_name = "projected_curve"
    params = (
        ParamSpec("mode", choices=("faces", "sketches"), default="faces"),
        ParamSpec("reverse", default=False, optional=True),
        ParamSpec("both", default=False, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Project; the part is unchanged."""
        out = _sketch(feature, ctx, "sketch", "sketch")
        issues: list[Issue] = []
        if feature.params.get("mode", "faces") == "sketches":
            curve = _sketch_sketch(feature, ctx, out)
        else:
            curve, issues = _onto_faces(feature, ctx, out)
        result = curve_result(ctx, curve)
        result.issues.extend(issues)
        return result
