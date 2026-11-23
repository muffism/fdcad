"""Extruded Cut from an open sketch (TR157, DECISIONS D1023).

When a cut's sketch is one open chain (no closed region) and Thin Feature is off, the
chain is made into a closed profile that covers one side of it: each end is carried
on along its end direction to well past the part, and the two far ends are joined
round the chosen side. Cutting with that profile, Through All or by a distance,
removes the material on that side. ``flip_side`` picks the other side. The faces the
chain makes are named after its sketch curves, as for any cut; the carried on parts
are named ``<curve>/extend_start`` and ``<curve>/extend_end``.
"""

from __future__ import annotations

from dataclasses import replace

from OCP.Bnd import Bnd_Box
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_CompCurve
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeVertex
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.gp import gp_Pnt, gp_Vec
from OCP.TopoDS import TopoDS_Edge, TopoDS_Shape, TopoDS_Vertex, TopoDS_Wire

from fdcad.core.document.model import Feature
from fdcad.core.features.base import BuildContext, FeatureError, SketchOutput
from fdcad.core.features.extrude_thin import (
    _edges,
    _ends,
    _midpoint,
    _nearest_entity,
    _plane_face,
    join_edges,
    thin_on,
)
from fdcad.core.features.sketch_paths import sketch_chain
from fdcad.core.naming.names import NamedShape
from fdcad.core.sketch.profiles import Profile, SketchPlane

#: How close (mm) a profile edge must lie to a chain edge to take its name.
_ON = 1e-5


def wants_open_cut(feature: Feature, sketch: SketchOutput) -> bool:
    """True for a cut (Thin Feature off) whose sketch has no closed region but has curves."""
    if feature.params.get("operation") != "cut":
        return False
    if thin_on(feature):
        return False
    if sketch.profile is not None and sketch.profile.faces:
        return False
    return bool(sketch.model.curves())


def _size(shapes: list[TopoDS_Shape]) -> float:
    box = Bnd_Box()
    for s in shapes:
        BRepBndLib.Add_s(s, box)
    if box.IsVoid():
        return 100.0
    return float(box.CornerMin().Distance(box.CornerMax()))


def _end_directions(wire: TopoDS_Wire, first: gp_Pnt) -> tuple[gp_Vec, gp_Vec]:
    """Unit directions pointing out of the chain at its first and at its last vertex."""
    curve = BRepAdaptor_CompCurve(wire)
    p0, d0, p1, d1 = gp_Pnt(), gp_Vec(), gp_Pnt(), gp_Vec()
    curve.D1(curve.FirstParameter(), p0, d0)
    curve.D1(curve.LastParameter(), p1, d1)
    if p0.Distance(first) <= p1.Distance(first):
        out_first, out_last = d0.Reversed(), d1
    else:  # the curve runs from the last vertex to the first
        out_first, out_last = d1, d0.Reversed()
    if out_first.Magnitude() < 1e-12 or out_last.Magnitude() < 1e-12:
        raise ValueError("the chain has no direction at an end")
    return out_first.Normalized(), out_last.Normalized()


def open_cut_profile(
    owner: str,
    wire: TopoDS_Wire,
    sources: list[tuple[TopoDS_Edge, str]],
    plane: SketchPlane,
    reach: float,
    flip: bool,
) -> Profile:
    """A closed profile covering one side of the open ``wire``. ``reach`` is how far past
    the chain the profile goes (more than the part's size)."""
    v_first, v_last = _ends(wire)
    a, b = BRep_Tool.Pnt_s(v_first), BRep_Tool.Pnt_s(v_last)
    try:
        out_a, out_b = _end_directions(wire, a)
    except ValueError as exc:
        raise FeatureError(
            f"{owner}: the open line has no direction at an end. Draw its end segments again."
        ) from exc
    far_a = a.Translated(out_a.Multiplied(reach))
    far_b = b.Translated(out_b.Multiplied(reach))
    chord = gp_Vec(far_a, far_b)
    if chord.Magnitude() < 1e-9:
        raise FeatureError(
            f"{owner}: the open line closes on itself. Close it, or use Thin Feature."
        )
    normal = gp_Vec(*plane.normal)
    side = normal.Crossed(chord).Normalized()
    if flip:
        side.Reverse()
    corner_b = far_b.Translated(side.Multiplied(2 * reach))
    corner_a = far_a.Translated(side.Multiplied(2 * reach))

    def vertex(p: gp_Pnt) -> TopoDS_Vertex:
        return BRepBuilderAPI_MakeVertex(p).Vertex()

    vf_a, vf_b, vc_b, vc_a = vertex(far_a), vertex(far_b), vertex(corner_b), vertex(corner_a)
    ext_a = BRepBuilderAPI_MakeEdge(vf_a, v_first).Edge()
    ext_b = BRepBuilderAPI_MakeEdge(v_last, vf_b).Edge()
    closing = [
        BRepBuilderAPI_MakeEdge(vf_b, vc_b).Edge(),
        BRepBuilderAPI_MakeEdge(vc_b, vc_a).Edge(),
        BRepBuilderAPI_MakeEdge(vc_a, vf_a).Edge(),
    ]
    joined = join_edges([ext_a, *_edges(wire), ext_b, *closing])
    if joined is None:
        raise FeatureError(
            f"{owner}: the open line could not be closed round one side. Use Thin Feature."
        )
    face = _plane_face(plane, joined)
    if not BRepCheck_Analyzer(face).IsValid():
        raise FeatureError(
            f"{owner}: the open line crosses itself or the lines carried on from its ends. "
            "Draw a simpler line, or use Thin Feature."
        )
    first_id = _nearest_entity(a, sources)[0] or "open"
    last_id = _nearest_entity(b, sources)[0] or "open"
    mid_a, mid_b = _midpoint(ext_a), _midpoint(ext_b)
    names: list[tuple[TopoDS_Edge, str]] = []
    for edge in _edges(face):
        mid = _midpoint(edge)
        if mid.Distance(mid_a) < _ON:
            names.append((edge, f"{first_id}/extend_start"))
            continue
        if mid.Distance(mid_b) < _ON:
            names.append((edge, f"{last_id}/extend_end"))
            continue
        eid, dist = _nearest_entity(mid, sources)
        if eid is not None and dist < _ON:
            names.append((edge, eid))
    return Profile([face], names)


def open_cut_sketch(feature: Feature, ctx: BuildContext, sketch: SketchOutput) -> SketchOutput:
    """``sketch`` with a profile covering the chosen side of its open chain."""
    owner = feature.name
    chain = sketch_chain(sketch.model, sketch.plane, owner)
    if chain.closed:
        raise FeatureError(f"{owner}: {sketch.profile_error}")
    shapes: list[TopoDS_Shape] = [chain.wire]
    if ctx.body is not None:
        shapes.append(ctx.body.shape)
    reach = 2 * _size(shapes) + 10.0
    flip = feature.params.get("flip_side", False) is True
    profile = open_cut_profile(owner, chain.wire, chain.edges, sketch.plane, reach, flip)
    return replace(sketch, profile=profile)


# Thin walls joined at their ends (TR272, D1025) ---------------------------------------


def merge_ends_on(feature: Feature) -> bool:
    """True for an open Thin Feature boss with Merge Ends ticked."""
    return (
        thin_on(feature)
        and feature.params.get("thin_merge_ends", False) is True
        and feature.params.get("operation", "boss") != "cut"
    )


def extended_wire(wire: TopoDS_Wire, reach: float) -> TopoDS_Wire:
    """``wire`` with each end carried on straight along its end direction by ``reach``."""
    v_first, v_last = _ends(wire)
    a, b = BRep_Tool.Pnt_s(v_first), BRep_Tool.Pnt_s(v_last)
    out_a, out_b = _end_directions(wire, a)
    far_a = BRepBuilderAPI_MakeVertex(a.Translated(out_a.Multiplied(reach))).Vertex()
    far_b = BRepBuilderAPI_MakeVertex(b.Translated(out_b.Multiplied(reach))).Vertex()
    joined = join_edges(
        [
            BRepBuilderAPI_MakeEdge(far_a, v_first).Edge(),
            *_edges(wire),
            BRepBuilderAPI_MakeEdge(v_last, far_b).Edge(),
        ]
    )
    if joined is None:
        raise ValueError("the carried on ends could not be joined")
    return joined


def merged_ends_tool(
    fid: str, owner: str, body: NamedShape, extended: NamedShape, plain: NamedShape
) -> NamedShape:
    """The wall carried on at both ends (``extended``) trimmed to the part: the material
    already there is taken out, only the piece holding most of the wall as drawn
    (``plain``) is kept, so ends that ran past a wall lose what stuck out, and a carried on
    end that meets nothing is taken off again."""
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape

    from fdcad.core.features.booleans import boolean_named
    from fdcad.core.features.solids import compound, solids, volume_of
    from fdcad.core.naming.names import restrict
    from fdcad.core.occ import BRepAlgoAPI_Common, BRepAlgoAPI_Cut

    trimmed = boolean_named("cut", extended, body, fid, owner)
    pieces = solids(trimmed.shape)
    if not pieces:
        raise FeatureError(f"{owner}: the wall is inside the part. Turn off Merge Ends.")

    def overlap(piece: TopoDS_Shape) -> float:
        return float(volume_of(BRepAlgoAPI_Common(piece, plain.shape).Shape()))

    keep = max(pieces, key=overlap)
    stubs = solids(BRepAlgoAPI_Cut(keep, plain.shape).Shape())
    for stub in stubs:
        dist = BRepExtrema_DistShapeShape(stub, body.shape)
        if dist.IsDone() and dist.Value() > 1e-6:  # an end carried on into empty space
            keep = BRepAlgoAPI_Cut(keep, stub).Shape()
    shape = compound(solids(keep))
    return NamedShape(shape, restrict(trimmed.faces, shape, fid))
