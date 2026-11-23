"""Extrude end conditions Up to Next and Up to Body (TOOL_SPEC T16 item 1, DECISIONS D460).

Both directions are swept as a long prism from the start (as far as Through All
reaches for a cut) and then clipped:

- Up to Next, boss: the prism less the part, keeping only the pieces that touch
  the start. Each part of the profile so stops at its own first face. A piece
  that still reaches the far end met nothing, which is an error.
- Up to Next, cut: the prism inside the part, keeping only the pieces that touch
  the start: the cut goes through the material until it first comes out.
- Up to Body, boss: as Up to Next, but against the picked body only.
- Up to Body, cut: a depth to the far side of the picked body, worked out in the
  plan (``body_reach``), so no clipping is needed.

Faces the clip takes from the part are renamed ``cap/end`` (``#k`` when there
are several), so a separate boss body never shares face names with the part.
"""

from __future__ import annotations

from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.gp import gp_Trsf, gp_Vec
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.document.model import Feature
from fdcad.core.features.base import BuildContext, FeatureError, SketchOutput, Vec3
from fdcad.core.features.extrude_start import Start
from fdcad.core.features.solids import combine, common, compound, extent_along, solids
from fdcad.core.naming.names import NamedShape, order_by_position, restrict

CLIP_CONDITIONS = ("up_to_next", "up_to_body")
_GAP_TOL = 1e-4  # mm: a piece this close to the start touches it
_FAR_TOL = 1e-3  # mm


def _label(which: str) -> str:
    return "Direction 2" if which == "2" else "Direction 1"


def no_next(owner: str, which: str) -> FeatureError:
    """The error for Up to Next when part of the profile meets no face."""
    return FeatureError(
        f"{owner}: Up to Next finds no face for the whole profile in {_label(which)}. "
        "Choose Blind or Through All."
    )


def needs_body(owner: str, condition: str) -> FeatureError:
    """The error for Up to Next or Up to Body in an empty part."""
    label = "Up to Next" if condition == "up_to_next" else "Up to Body"
    return FeatureError(f"{owner}: {label} needs a body to end at. Choose Blind, or add a body.")


def picked_body(feature: Feature, ctx: BuildContext, which: str) -> TopoDS_Shape:
    """The solid an Up to Body direction ends at (``refs.end`` or ``refs.end2``)."""
    from fdcad.core.features.bodies import body_of_ref

    owner = feature.name
    if ctx.body is None:
        raise needs_body(owner, "up_to_body")
    ref = feature.refs.get(f"end{which}")
    if not isinstance(ref, dict):
        raise FeatureError(f"{owner}: {_label(which)} needs a body to end at. Pick a body.")
    try:
        body, _issues = body_of_ref(ctx, ref, owner)
    except FeatureError as exc:
        raise FeatureError(
            f"{owner}: the {_label(which)} end body was lost. Pick the body again or choose Blind."
        ) from exc
    return body


def body_reach(feature: Feature, ctx: BuildContext, unit: Vec3, level: float, which: str) -> float:
    """Up to Body for a cut: the depth from ``level`` to the far side of the body."""
    span = extent_along(picked_body(feature, ctx, which), unit)
    far = span[1] - level if span is not None else 0.0
    if far <= 1e-6:
        raise FeatureError(
            f"{feature.name}: the {_label(which)} end body is behind the start. "
            "Reverse the direction or pick another body."
        )
    return far


def start_shape(
    sketch: SketchOutput, start: Start, face: TopoDS_Shape | None = None
) -> TopoDS_Shape:
    """Where the sweep starts: the start face, or the profile (or ``face``) moved to it."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform

    if start.surface is not None:
        return start.surface
    assert sketch.profile is not None
    shape: TopoDS_Shape = face if face is not None else compound(list(sketch.profile.faces))
    if start.shift:
        n = sketch.plane.normal
        trsf = gp_Trsf()
        trsf.SetTranslation(gp_Vec(n[0] * start.shift, n[1] * start.shift, n[2] * start.shift))
        shape = BRepBuilderAPI_Transform(shape, trsf, True).Shape()
    return shape


def touches(solid: TopoDS_Shape, start: TopoDS_Shape) -> bool:
    """True when ``solid`` touches ``start`` (within 0.0001 mm)."""
    dist = BRepExtrema_DistShapeShape(solid, start)
    return bool(dist.IsDone()) and float(dist.Value()) < _GAP_TOL


def _keep(named: NamedShape, keep: list[TopoDS_Shape], fid: str) -> NamedShape:
    shape = keep[0] if len(keep) == 1 else compound(keep)
    return NamedShape(shape, restrict(named.faces, shape, f"{fid}/limit"))


def own_names(named: NamedShape, fid: str) -> NamedShape:
    """Rename faces that came from the part to ``cap/end`` (``#k`` when several)."""
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp
    from OCP.TopoDS import TopoDS

    from fdcad.core.occ import ShapeMap

    fmap = ShapeMap()
    TopExp.MapShapes_s(named.shape, TopAbs_FACE, fmap)
    own = [(n, f) for n, f in named.faces if n.startswith(f"{fid}/")]
    taken = {fmap.FindIndex(f) for _n, f in own}
    others = [TopoDS.Face(fmap.FindKey(i)) for i in range(1, fmap.Extent() + 1) if i not in taken]
    ordered = order_by_position(others)
    if len(ordered) == 1:
        own.append((f"{fid}/cap/end", ordered[0]))
    else:
        own += [(f"{fid}/cap/end#{k}", f) for k, f in enumerate(ordered, start=1)]
    return NamedShape(named.shape, restrict(own, named.shape, f"{fid}/limit"))


def clip(
    feature: Feature,
    ctx: BuildContext,
    piece: NamedShape,
    condition: str,
    operation: str,
    unit: Vec3,
    begin: TopoDS_Shape,
    which: str,
) -> NamedShape:
    """Clip one direction's long prism ``piece`` for Up to Next or Up to Body (boss)."""
    fid, owner = feature.id, feature.name
    if ctx.body is None:
        raise needs_body(owner, condition)
    if condition == "up_to_body":
        target = NamedShape(picked_body(feature, ctx, which), [])
    else:
        from fdcad.core.features.bodies import scope_body

        target = scope_body(feature, ctx) or ctx.body
    span = extent_along(piece.shape, unit)
    try:
        if operation == "cut" and condition == "up_to_next":
            rest = common(fid, owner, piece, target)
        else:
            rest = combine(fid, owner, piece, target, "cut")
    except FeatureError as exc:
        raise FeatureError(
            f"{owner} failed: the {_label(which)} end could not be found. "
            "Choose Blind or Through All."
        ) from exc
    keep = [s for s in solids(rest.shape) if touches(s, begin)]
    if not keep:
        raise no_next(owner, which) if condition == "up_to_next" else _misses(owner, which)
    if operation != "cut" and span is not None:
        for s in keep:
            reach = extent_along(s, unit)
            if reach is not None and reach[1] > span[1] - _FAR_TOL:
                if condition == "up_to_next":
                    raise no_next(owner, which)
                raise _misses(owner, which)
    return own_names(_keep(rest, keep, fid), fid)


def _misses(owner: str, which: str) -> FeatureError:
    return FeatureError(
        f"{owner}: the profile does not fully meet the {_label(which)} end body. "
        "Pick another body, or choose Blind or Through All."
    )
