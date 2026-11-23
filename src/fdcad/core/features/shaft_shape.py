"""Shaft and bore shapes (TUTORIAL_REVIEW_SPEC_2 TR247, DECISIONS D841).

Type ``shaft_shape``. Pick a round face (``refs.face``): the outside of a shaft
or the inside of a bore. Over a length from one end of that face, the round is
changed to a hex, a D flat, a double D or a keyway, sized from its diameter D
by FDCAD's rules:

- ``hex``: across flats D * sqrt(3) / 2 (the corners on the round).
- ``d_flat``: one flat 0.1 D deep. ``double_d``: two opposite flats 0.1 D deep.
- ``keyway``: a slot D / 4 wide and D / 8 deep, or a standard key's keyseat (shaft)
  or keyway (bore) when ``key_standard`` is ``metric``, ``inch`` or ``woodruff``
  (TR248, D871, sizes in ``keys.py``). A half moon keyseat is the key's circle,
  centred along the length.

On a shaft the shape is cut from it. In a bore the hole takes the matching
shape grown by ``clearance`` on every side, so a shaft of the same size slides
in. Params: ``shaft_form``, ``length`` (optional: the whole face), ``from_end``
("start" or "end" of the face along its axis), ``angle`` (turns the flats or
key about the axis), ``clearance`` (bores). New faces are ``<fid>/shape``.
"""

from __future__ import annotations

import math
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
from fdcad.core.features.keys import STANDARDS
from fdcad.core.units import Kind

KINDS = ("hex", "d_flat", "double_d", "keyway")


def _round_face(feature: Feature, ctx: BuildContext) -> tuple[Any, Any, float, float, float, bool]:
    """The picked face's axis (gp_Ax1), its radius, the axial range and True for a shaft."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.BRepTools import BRepTools
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.gp import gp_Vec
    from OCP.TopAbs import TopAbs_REVERSED

    from fdcad.core.naming.resolve import resolve_face

    name = feature.name
    refs = feature.refs.get("face")
    ref = refs[0] if isinstance(refs, list) and refs else refs
    if not isinstance(ref, dict):
        raise FeatureError(f"{name}: pick the round face of a shaft or a bore.")
    face = resolve_face(ctx.body, ref, name)[0]
    surface = BRepAdaptor_Surface(face)
    if surface.GetType() != GeomAbs_Cylinder:
        raise FeatureError(f"{name}: the picked face is not round. Pick a shaft or a bore face.")
    cylinder = surface.Cylinder()
    axis = cylinder.Axis()
    radius = cylinder.Radius()
    u0, u1, v0, v1 = BRepTools.UVBounds_s(face)
    props = BRepLProp_SLProps(surface, (u0 + u1) / 2, (v0 + v1) / 2, 1, 1e-7)
    normal = props.Normal()
    if face.Orientation() == TopAbs_REVERSED:
        normal.Reverse()
    point = props.Value()
    foot = axis.Location().Translated(
        gp_Vec(axis.Direction()).Multiplied(
            gp_Vec(axis.Location(), point).Dot(gp_Vec(axis.Direction()))
        )
    )
    radial = gp_Vec(foot, point)
    shaft = radial.Dot(gp_Vec(normal.XYZ())) > 0
    return axis, face, radius, v0, v1, shaft


def _value(feature: Feature, key: str, default: float) -> float:
    found = feature.params.get(key)
    return found.value if isinstance(found, Param) else default


def _profile_solid(
    kind: str, r: float, grow: float, length: float, frame: Any, key: Any = None
) -> Any:
    """The new cross section (grown by ``grow`` on every side) swept ``length`` along the
    frame's Z, as a solid."""
    from OCP.BRepBuilderAPI import (
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_MakePolygon,
    )
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec

    from fdcad.core.occ import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse

    d = 2 * r
    big = 4 * r + 10.0
    round_ = BRepPrimAPI_MakeCylinder(
        gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), r + grow, length
    ).Shape()
    if kind == "hex":
        flats = d * math.sqrt(3) / 2 + 2 * grow
        corner = flats / math.sqrt(3)
        poly = BRepBuilderAPI_MakePolygon()
        for i in range(6):
            a = math.radians(60 * i)
            poly.Add(gp_Pnt(corner * math.cos(a), corner * math.sin(a), 0))
        poly.Close()
        face = BRepBuilderAPI_MakeFace(poly.Wire(), True).Face()
        shape = BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, length)).Shape()
    elif kind in ("d_flat", "double_d"):
        level = r - 0.1 * d + grow
        keep = BRepPrimAPI_MakeBox(gp_Pnt(-big, -big, 0), gp_Pnt(big, level, length)).Shape()
        if kind == "double_d":
            low = BRepPrimAPI_MakeBox(gp_Pnt(-big, -level, 0), gp_Pnt(big, big, length)).Shape()
            keep = BRepAlgoAPI_Common(keep, low).Shape()
        shape = BRepAlgoAPI_Common(round_, keep).Shape()
    else:  # keyway: D / 4 wide, D / 8 deep, or a standard key (TR248)
        from fdcad.core.features.keys import Key

        if not isinstance(key, Key):
            key = Key("D/4", d / 4, d / 8, d / 8)
        half = key.width / 2 + grow
        if grow == 0 and key.seat_diameter > 0:  # a half moon keyseat
            seat = key.seat_diameter / 2
            disc = BRepPrimAPI_MakeCylinder(
                gp_Ax2(gp_Pnt(-half, r - key.shaft_depth + seat, length / 2), gp_Dir(1, 0, 0)),
                seat,
                2 * half,
            ).Shape()
            shape = BRepAlgoAPI_Cut(round_, disc).Shape()
        elif grow == 0:  # a shaft: the keyseat is cut from the round
            slot = BRepPrimAPI_MakeBox(
                gp_Pnt(-half, r - key.shaft_depth, 0), gp_Pnt(half, big, length)
            )
            shape = BRepAlgoAPI_Cut(round_, slot.Shape()).Shape()
        else:  # a bore: the hub keyway reaches out past the round
            slot = BRepPrimAPI_MakeBox(
                gp_Pnt(-half, 0, 0), gp_Pnt(half, r + key.hub_depth + grow, length)
            )
            shape = BRepAlgoAPI_Fuse(round_, slot.Shape()).Shape()
    return _placed(shape, frame)


def _placed(shape: Any, frame: Any) -> Any:
    """``shape`` built about the origin and Z, moved onto ``frame``."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Ax3, gp_Trsf

    move = gp_Trsf()
    move.SetTransformation(frame, gp_Ax3())
    return BRepBuilderAPI_Transform(shape, move, True).Shape()


@register
class ShaftShape(FeatureType):
    """Hex, D flat, double D or keyway on a shaft or in a bore."""

    type_name = "shaft_shape"
    makes_solid = True
    params = (
        ParamSpec("shaft_form", choices=KINDS, default="d_flat"),
        ParamSpec("length", kind=Kind.LENGTH, optional=True),
        ParamSpec("from_end", choices=("start", "end"), optional=True),
        ParamSpec("angle", kind=Kind.ANGLE, optional=True),
        ParamSpec("clearance", kind=Kind.LENGTH, optional=True),
        ParamSpec("key_standard", choices=STANDARDS, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Change the round over the length."""
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
        from OCP.gp import gp_Ax2, gp_Ax3, gp_Dir, gp_Pnt, gp_Vec

        from fdcad.core.features.solids import check_result, solids
        from fdcad.core.naming.names import NamedShape, carry, restrict
        from fdcad.core.occ import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse

        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part is empty. Add a body first.")
        kind = str(feature.params.get("shaft_form", "d_flat"))
        if kind not in KINDS:
            raise FeatureError(f"{name}: unknown shape '{kind}'. Choose a shape in the panel.")
        axis, face, r, v0, v1, shaft = _round_face(feature, ctx)
        full = v1 - v0
        length = _value(feature, "length", full)
        if length <= 0:
            raise FeatureError(f"{name}: the length must be greater than zero. Enter a length.")
        length = min(length, full)
        clearance = 0.0 if shaft else max(_value(feature, "clearance", 0.1), 0.0)
        start = v0 if feature.params.get("from_end", "start") == "start" else v1 - length
        direction = gp_Dir(axis.Direction().XYZ())
        origin = axis.Location().Translated(gp_Vec(direction).Multiplied(start))
        frame = gp_Ax3(origin, direction)
        turn = _value(feature, "angle", 0.0)
        if abs(turn) > 1e-12:
            frame.Rotate(axis, turn)
        tol = 1e-4
        key = None
        if kind == "keyway":
            from fdcad.core.features.keys import KeySizeError, key_for

            try:
                key = key_for(str(feature.params.get("key_standard", "rule")), 2 * r)
            except KeySizeError as exc:
                raise FeatureError(f"{name}: {exc}") from exc
        new = _profile_solid(kind, r, clearance, length, frame, key)
        if shaft:
            # What is cut away is a sleeve round the shaft less the new shape. The sleeve
            # used to be a hair (0.0001 mm) longer than the shape at each end, so at each
            # end it was a whole disc: on a stepped shaft, with the shape on a middle step,
            # those two discs sliced the shaft into three bodies (D1059). Now the sleeve
            # is as long as the shape, and the shape it is cut by is the longer one.
            sleeve = BRepPrimAPI_MakeCylinder(
                gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 2 * r + 10.0, length
            ).Shape()
            sleeve = _placed(sleeve, frame)
            longer = gp_Ax3(origin.Translated(gp_Vec(direction).Multiplied(-tol)), direction)
            if abs(turn) > 1e-12:
                longer.Rotate(axis, turn)
            core = _profile_solid(kind, r, clearance, length + 2 * tol, longer, key)
            tool = BRepAlgoAPI_Cut(sleeve, core).Shape()

            def run(part: NamedShape) -> NamedShape:
                op: Any = BRepAlgoAPI_Cut(part.shape, tool)
                op.Build()
                if not op.IsDone() or not solids(op.Shape()):
                    raise FeatureError(
                        f"{name}: the shape could not be made. Use a shorter length."
                    )
                shape = op.Shape()
                return NamedShape(
                    shape, restrict(carry(part.faces, op.History()), shape, f"{feature.id}/shape")
                )

        else:
            round_ = BRepPrimAPI_MakeCylinder(
                gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), r, length
            ).Shape()
            round_ = _placed(round_, frame)
            fill = BRepAlgoAPI_Cut(round_, new).Shape()  # inside the bore, outside the shape

            def run(part: NamedShape) -> NamedShape:
                grown = BRepAlgoAPI_Fuse(part.shape, fill)
                grown.Build()
                if not grown.IsDone():
                    raise FeatureError(
                        f"{name}: the shape could not be made. Use a shorter length."
                    )
                op = BRepAlgoAPI_Cut(grown.Shape(), new)  # the keyway reaches past the round
                names = carry(part.faces, grown.History())
                op.Build()
                if not op.IsDone():
                    raise FeatureError(
                        f"{name}: the shape could not be made. Use a shorter length."
                    )
                shape = op.Shape()
                return NamedShape(
                    shape, restrict(carry(names, op.History()), shape, f"{feature.id}/shape")
                )

        # The shape is made on the body of the picked face only (D2622). It was made on
        # the whole part: the sleeve cut from a shaft reaches 2 D plus 10 mm out and
        # took a hub on the shaft with it, and the fill of a bore joined a pin in it.
        from fdcad.core.features.bodies import in_body_of

        result = in_body_of(ctx.body, face, feature.id, run)
        issues = check_result(feature.id, name, ctx.body, result, None)
        return FeatureResult(body=result, issues=issues)
