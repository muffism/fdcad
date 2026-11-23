"""Resolve model reference nodes against the part at the graph's position."""

from __future__ import annotations

from typing import Any

from fdcad.core.graph.nodes.base import NodeContext, NodeError
from fdcad.core.graph.types import make_plane


def _issues_to_warnings(issues: list[Any], ctx: NodeContext) -> None:
    for issue in issues:
        ctx.warnings.append(str(getattr(issue, "message", issue)))


def resolve(kind: str, ref: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
    """Outputs of a model reference node. Raises NodeError."""
    from fdcad.core.features.base import FeatureError
    from fdcad.core.features.lookup import resolve_edge, resolve_face

    owner = "Model Reference"
    out: dict[str, Any] = {"curve": None, "body": None, "plane": None}
    named = ref.get("named")
    if isinstance(named, str):  # a named face or edge (TR152, D2105)
        found = ctx.env.named.get(named.casefold())
        if found is None:
            raise NodeError(
                f'There is no item named "{named}". Pick the face or edge again in the view.'
            )
        ref = found
    try:
        if kind == "curve":
            out["curve"] = _curve_feature(ref, ctx)
            return out
        body = ctx.env.body
        if body is None:
            raise NodeError("The part has no body above the graph's position. Move the graph down.")
        if kind == "edge":
            edge, issues = resolve_edge(body, ref, owner)
            _issues_to_warnings(issues, ctx)
            from fdcad.core.graph.geometry import wire_of

            out["curve"] = wire_of(edge)
            return out
        face, issues = resolve_face(body, ref, owner)
        _issues_to_warnings(issues, ctx)
        if kind == "body":
            out["body"] = _solid_with(body.shape, face)
            return out
        from OCP.BRepTools import BRepTools

        out["curve"] = BRepTools.OuterWire_s(face)
        out["plane"] = _face_plane(face)
        return out
    except FeatureError as exc:
        raise NodeError(str(exc)) from exc


def _curve_feature(ref: dict[str, Any], ctx: NodeContext) -> Any:
    from fdcad.core.features.curves import connect, edges_in, sketch_curve_edges
    from fdcad.core.graph.geometry import group

    fid = ref.get("feature")
    if not isinstance(fid, str):
        raise NodeError("Pick a sketch or a curve feature.")
    res = ctx.env.results.get(fid)
    if res is None:
        raise NodeError(
            f"Feature {fid} is missing or below the graph's position. "
            "A graph reads only features above it. Pick a feature above the graph."
        )
    curve = res.extras.get("curve")
    edges = edges_in(curve) if curve is not None else []
    if not edges and res.sketch is not None:
        from fdcad.core.features.base import FeatureError

        try:
            edges = sketch_curve_edges(res.sketch)
        except FeatureError as exc:
            raise NodeError(str(exc)) from exc
    if not edges:
        raise NodeError(f"Feature {fid} is not a sketch or a curve. Pick another one.")
    wires = connect(edges)
    return wires[0] if len(wires) == 1 else group(wires)


def _solid_with(shape: Any, face: Any) -> Any:
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer

    from fdcad.core.graph.geometry import solids_of

    for solid in solids_of(shape):
        explorer = TopExp_Explorer(solid, TopAbs_FACE)
        while explorer.More():
            if explorer.Current().IsSame(face):
                return solid
            explorer.Next()
    return shape


def _face_plane(face: Any) -> Any:
    from OCP.BRep import BRep_Tool
    from OCP.BRepGProp import BRepGProp
    from OCP.GeomAbs import GeomAbs_Plane
    from OCP.GeomAdaptor import GeomAdaptor_Surface
    from OCP.GProp import GProp_GProps

    from fdcad.core.plane_normal import plane_normal

    surf = GeomAdaptor_Surface(BRep_Tool.Surface_s(face))
    if surf.GetType() != GeomAbs_Plane:
        return None
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    c = props.CentreOfMass()
    normal = plane_normal(face)
    assert normal is not None  # the surface was checked to be a plane above
    return make_plane((c.X(), c.Y(), c.Z()), normal)
