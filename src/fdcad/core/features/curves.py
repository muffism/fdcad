"""Shared helpers for curve features (PHASE3_SPEC P3.6, DECISIONS D291).

A curve feature leaves the part as it is and returns its curve in
``FeatureResult.extras``: ``curve`` (a wire, or a compound of wires) for later
features and ``reference`` (the same shape) for display. Other features use a
curve by a feature reference ``{"feature": "f9"}``, like a sketch.
"""

from __future__ import annotations

from typing import Any

from OCP.BRep import BRep_Builder
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeWire
from OCP.ShapeAnalysis import ShapeAnalysis_FreeBounds
from OCP.TopAbs import TopAbs_EDGE, TopAbs_WIRE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Compound, TopoDS_Edge, TopoDS_Shape, TopoDS_Wire

from fdcad.core.features.base import BuildContext, FeatureError, FeatureResult, SketchOutput
from fdcad.core.sketch.model import Point
from fdcad.core.sketch.profiles import ProfileError, _EdgeMaker

#: How far apart two curve ends may be and still join, in mm.
JOIN_TOLERANCE = 1e-4


def edges_in(shape: TopoDS_Shape) -> list[TopoDS_Edge]:
    """Every edge of ``shape`` in order (a wire's edges in wire order)."""
    out = []
    explorer = TopExp_Explorer(shape, TopAbs_EDGE)
    while explorer.More():
        out.append(TopoDS.Edge(explorer.Current()))
        explorer.Next()
    return out


def wires_in(shape: TopoDS_Shape) -> list[TopoDS_Wire]:
    """Every wire of ``shape``."""
    out = []
    explorer = TopExp_Explorer(shape, TopAbs_WIRE)
    while explorer.More():
        out.append(TopoDS.Wire(explorer.Current()))
        explorer.Next()
    return out


def group(shapes: list[TopoDS_Shape]) -> TopoDS_Compound:
    """Shapes in one compound."""
    comp = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(comp)
    for s in shapes:
        builder.Add(comp, s)
    return comp


def connect(edges: list[TopoDS_Edge], tolerance: float = JOIN_TOLERANCE) -> list[TopoDS_Wire]:
    """Join edges end to end into as few wires as possible, in any order or direction."""
    if not edges:
        return []
    from OCP.collections import HSequence_TopoDS_Shape

    hedges = HSequence_TopoDS_Shape()
    for edge in edges:
        hedges.Append(edge)
    hwires = HSequence_TopoDS_Shape()
    ShapeAnalysis_FreeBounds.ConnectEdgesToWires_s(hedges, tolerance, False, hwires)
    out = []
    for i in range(1, hwires.Length() + 1):
        out.append(TopoDS.Wire(hwires.Value(i)))
    return out


def one_wire(edges: list[TopoDS_Edge], owner: str, what: str = "curves") -> TopoDS_Wire:
    """``edges`` joined into exactly one wire. Raises FeatureError naming the gap."""
    wires = connect(edges)
    if not wires:
        raise FeatureError(f"{owner}: there are no {what}. Pick at least one.")
    if len(wires) > 1:
        raise FeatureError(
            f"{owner}: the {what} do not join end to end ({len(wires)} separate pieces). "
            "Pick curves that touch, in one chain."
        )
    # Rebuild through MakeWire so edge order and orientation follow the chain.
    maker = BRepBuilderAPI_MakeWire()
    for edge in edges_in(wires[0]):
        maker.Add(edge)
    return maker.Wire() if maker.IsDone() else wires[0]


def sketch_curve_edges(out: SketchOutput, owner: str = "The sketch") -> list[TopoDS_Edge]:
    """The sketch's curves as 3D edges, construction geometry left out.

    A curve that cannot become an edge raises FeatureError naming it, instead of
    being left out of the curve (audit A item 8, D706).
    """
    maker = _EdgeMaker(out.model, out.plane)
    edges = []
    for ent in out.model.entities.values():
        if isinstance(ent, Point) or getattr(ent, "construction", False):
            continue
        try:
            edges.append(maker.edge(ent.id))
        except (ProfileError, KeyError, ValueError) as exc:
            raise FeatureError(f"{owner}: curve {ent.id} could not be used. {exc}") from exc
    return edges


def curve_result(ctx: BuildContext, curve: TopoDS_Shape) -> FeatureResult:
    """A result that keeps the part and carries ``curve``."""
    result = FeatureResult(body=ctx.body)
    result.extras["curve"] = curve
    result.extras["reference"] = curve
    return result


def feature_edges(ctx: BuildContext, ref: Any, owner: str) -> list[TopoDS_Edge]:
    """Edges of a referenced sketch or curve feature. Raises FeatureError."""
    if not isinstance(ref, dict) or "feature" not in ref:
        raise FeatureError(f"{owner}: pick a sketch or a curve.")
    result = ctx.result(str(ref["feature"]))
    curve = result.extras.get("curve")
    if curve is not None:
        return edges_in(curve)
    if result.sketch is not None:
        return sketch_curve_edges(result.sketch, owner)
    raise FeatureError(
        f"{owner}: {ctx._name(str(ref['feature']))} is not a sketch or a curve. "
        "Pick a sketch or a curve feature."
    )


def curve_of(ctx: BuildContext, ref: Any, owner: str) -> TopoDS_Wire | None:
    """The one wire of a referenced curve feature, or None when ``ref`` is not a curve."""
    if not isinstance(ref, dict) or "feature" not in ref:
        return None
    result = ctx.results.get(str(ref["feature"]))
    if result is None or "curve" not in result.extras:
        return None
    result = ctx.result(str(ref["feature"]))
    curve = result.extras["curve"]
    if curve.ShapeType() == TopAbs_WIRE:
        return TopoDS.Wire(curve)
    return one_wire(edges_in(curve), owner, "curve pieces")
