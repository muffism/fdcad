"""Landing Pad: a flat pad on a sloped or curved wall (TR325, DECISIONS D2013).

Type ``landing_pad``. Refs: ``wall_face`` (the sloped or curved wall) and
``sketch`` (a closed outline; the sketch plane is the pad's flat face, its normal
pointing out of the wall). Params:

- ``pad_mode``: ``raise`` (default: the pad is built out from the wall up to the
  sketch plane) or ``press`` (the pad is sunk into the wall down to the sketch
  plane).
- ``cup_wall``: optional length: for ``press`` on a thin walled housing, a cup this
  thick is kept behind and round the sunk pad so the wall stays closed.

Used for screw bosses and labels on curved housings. New faces are
``<fid>/pad#k``.
"""

from __future__ import annotations

from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.gp import gp_Trsf, gp_Vec
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    register,
)
from fdcad.core.features.solids import FUZZY_TOLERANCE, bounding_size, compound, solids
from fdcad.core.naming.names import NamedShape, carry, faces_of, restrict
from fdcad.core.occ import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse, ShapeMap
from fdcad.core.units import Kind


def _run(kind: str, a: TopoDS_Shape, b: TopoDS_Shape) -> tuple[TopoDS_Shape, object]:
    maker = {"common": BRepAlgoAPI_Common, "cut": BRepAlgoAPI_Cut, "fuse": BRepAlgoAPI_Fuse}[kind](
        a, b
    )
    maker.SetFuzzyValue(FUZZY_TOLERANCE)
    maker.Build()
    if not maker.IsDone():
        raise ValueError(f"the pad {kind} failed")
    return maker.Shape(), maker


def _moved(shape: TopoDS_Shape, step: gp_Vec) -> TopoDS_Shape:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform

    trsf = gp_Trsf()
    trsf.SetTranslation(step)
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()


@register
class LandingPad(FeatureType):
    """A flat pad raised from or pressed into a sloped wall."""

    type_name = "landing_pad"
    makes_solid = True
    params = (
        ParamSpec("pad_mode", choices=("raise", "press"), default="raise"),
        ParamSpec("cup_wall", kind=Kind.LENGTH, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Build the pad."""
        from fdcad.core.features.lookup import resolve_face

        owner, fid = feature.name, feature.id
        body = ctx.body
        if body is None:
            raise FeatureError(f"{owner}: the part is empty. Add a body first.")
        ref = feature.refs.get("wall_face")
        if isinstance(ref, list):
            ref = ref[0] if ref else None
        if not isinstance(ref, dict):
            raise FeatureError(f"{owner}: pick the sloped or curved wall.")
        wall_face, issues = resolve_face(body, ref, owner)
        sref = feature.refs.get("sketch")
        sid = sref.get("feature") if isinstance(sref, dict) else None
        out = ctx.result(sid).sketch if isinstance(sid, str) and sid in ctx.results else None
        if out is None or out.profile is None or not out.profile.faces:
            raise FeatureError(f"{owner}: pick a sketch with a closed outline for the pad.")
        profile = compound(list(out.profile.faces))
        n = gp_Vec(*out.plane.normal)
        # The pad is built on the body of the picked wall (D1077). It was fused with the
        # whole part, and that joined other bodies of the part that only touched each
        # other (D1055).
        from fdcad.core.features.bodies import in_body_of

        def build(body: NamedShape) -> NamedShape:
            big = 4.0 * max(bounding_size(body.shape), 1.0)
            value = feature.params.get("cup_wall")
            wall = value.value if isinstance(value, Param) else 0.0
            if wall < 0:
                raise FeatureError(f"{owner}: the wall cannot be negative. Enter zero or more.")
            mode = str(feature.params.get("pad_mode", "raise"))
            level = sum(a * b for a, b in zip(out.plane.origin, out.plane.normal, strict=True))
            normal = tuple(out.plane.normal)
            try:
                if mode == "raise":
                    tool = BRepPrimAPI_MakePrism(profile, n.Reversed().Multiplied(big)).Shape()
                    air, _m = _run("cut", tool, body.shape)
                    # Only the air between the wall and the sketch plane, not past the part.
                    pads = [
                        p
                        for p in solids(air)
                        if _reaches(p, normal, level, top=True) and _touches(p, wall_face)
                    ]
                    if not pads:
                        raise ValueError("the sketch plane does not stand off the wall")
                    shape, maker = _run("fuse", body.shape, compound(pads))
                    makers = [maker]
                else:
                    recess = BRepPrimAPI_MakePrism(profile, n.Multiplied(big)).Shape()
                    makers = []
                    shape = body.shape
                    if wall > 0:
                        grown = _grown(out, wall)
                        start = _moved(grown, n.Reversed().Multiplied(wall))
                        behind = BRepPrimAPI_MakePrism(start, n.Multiplied(big)).Shape()
                        air, _m = _run("cut", behind, body.shape)
                        top = level - wall + big
                        outer = [p for p in solids(air) if _reaches(p, normal, top, top=True)]
                        cup, _m = _run("cut", behind, compound(outer)) if outer else (behind, None)
                        shape, maker = _run("fuse", shape, cup)
                        makers.append(maker)
                    shape, maker = _run("cut", shape, recess)
                    makers.append(maker)
            except ValueError as exc:
                raise FeatureError(
                    f"{owner} failed: {exc}. Move the sketch plane so the pad meets the wall."
                ) from exc
            pieces = solids(shape)
            if not pieces:
                raise FeatureError(f"{owner} failed: nothing is left of the part. Move the sketch.")
            shape = compound(pieces)
            names = list(body.faces)
            for maker in makers:
                names = carry(names, maker.History())  # type: ignore[attr-defined]
            named = ShapeMap()
            for _n, f in names:
                named.Add(f)
            k = 0
            for f in faces_of(shape):
                if not named.Contains(f):
                    k += 1
                    names.append((f"{fid}/pad#{k}", f))
            return NamedShape(shape, restrict(names, shape, fid))

        return FeatureResult(body=in_body_of(body, wall_face, fid, build), issues=issues)


def _reaches(shape: TopoDS_Shape, normal: tuple[float, ...], level: float, top: bool) -> bool:
    """True when ``shape`` reaches ``level`` along ``normal`` (its top, or its bottom)."""
    from fdcad.core.features.solids import extent_along

    span = extent_along(shape, (normal[0], normal[1], normal[2]))
    if span is None:
        return False
    return abs((span[1] if top else span[0]) - level) < 1e-4


def _touches(shape: TopoDS_Shape, face: TopoDS_Shape) -> bool:
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape

    dist = BRepExtrema_DistShapeShape(shape, face)
    return bool(dist.IsDone() and dist.Value() < 1e-4)


def _grown(out: object, distance: float) -> TopoDS_Shape:
    """The sketch's outline grown by ``distance`` on every side, as faces."""
    from fdcad.core.features.lightening_pockets import offset_face

    grown = []
    for face in out.profile.faces:  # type: ignore[attr-defined]
        grown += offset_face(face, distance)
    if not grown:
        raise ValueError("the pad outline could not be grown by the wall")
    return compound(grown)
