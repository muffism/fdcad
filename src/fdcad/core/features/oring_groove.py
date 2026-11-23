"""O ring grooves (TUTORIAL_REVIEW_SPEC_2 TR250, DECISIONS D886).

Type ``oring_groove``. ``cross_section`` is the O ring's cord diameter (the
standard inch dash series and metric cords are offered in the panel). Two ways:

- Pick the round face of a shaft or a bore (``refs.face``): a groove for a piston
  seal (on a shaft) or a rod seal (in a bore) is cut ``position`` from one end.
- Pick a sketch on a flat face (``refs.sketch``): a face seal groove follows the
  sketch's closed curve as the ring's centre line.

Groove depth and width follow the usual design rules for the ``use``: ``static``
squeezes the cord about 20 percent, ``moving`` about 15 percent, ``face`` about 25
percent; the width leaves room for the ring to swell. The feature checks the
squeeze (10 to 30 percent) and how full the groove is (at most 85 percent) and
warns outside those, and reports both in ``extras["oring"]``. New faces are
``<fid>/oring``.
"""

from __future__ import annotations

from typing import Any

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureState,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.units import Kind

USES = ("static", "moving", "face")
#: Groove depth and width as fractions of the cord, by use.
RULES: dict[str, tuple[float, float]] = {
    "static": (0.80, 1.40),
    "moving": (0.85, 1.30),
    "face": (0.75, 1.50),
}
#: Standard cords: the inch dash series (-0xx to -4xx) and common metric cords, mm.
CORDS: dict[str, float] = {
    "1/16 in (-0xx)": 1.78,
    "3/32 in (-1xx)": 2.62,
    "1/8 in (-2xx)": 3.53,
    "3/16 in (-3xx)": 5.33,
    "1/4 in (-4xx)": 6.99,
    "1.0 mm": 1.0,
    "1.5 mm": 1.5,
    "2.0 mm": 2.0,
    "2.5 mm": 2.5,
    "3.0 mm": 3.0,
    "4.0 mm": 4.0,
    "5.0 mm": 5.0,
}


def groove_size(cord: float, use: str) -> tuple[float, float]:
    """(depth, width) of the groove for a cord of ``cord`` mm."""
    depth, width = RULES[use]
    return cord * depth, cord * width


def checks(cord: float, depth: float, width: float) -> tuple[float, float]:
    """(squeeze, fill) as fractions: how much the cord is pressed, and how much of the
    groove's section the ring fills."""
    import math

    squeeze = (cord - depth) / cord
    fill = (math.pi * cord * cord / 4) / (depth * width)
    return squeeze, fill


def _value(feature: Feature, key: str, default: float) -> float:
    found = feature.params.get(key)
    return found.value if isinstance(found, Param) else default


@register
class ORingGroove(FeatureType):
    """An O ring groove on a shaft, in a bore, or as a face seal along a sketch."""

    type_name = "oring_groove"
    makes_solid = True
    params = (
        ParamSpec("cross_section", kind=Kind.LENGTH),
        ParamSpec("use", choices=USES, default="static"),
        ParamSpec("position", kind=Kind.LENGTH, optional=True),
        ParamSpec("from_end", choices=("start", "end"), optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Cut the groove."""
        from fdcad.core.features.solids import check_result, solids
        from fdcad.core.naming.names import NamedShape, carry, restrict

        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part is empty. Add a body first.")
        cord = _value(feature, "cross_section", 0.0)
        if cord <= 0:
            raise FeatureError(f"{name}: the cross section must be greater than zero. Pick a cord.")
        use = str(feature.params.get("use", "static"))
        if use not in USES:
            raise FeatureError(f"{name}: unknown use '{use}'. Choose one in the panel.")
        if feature.refs.get("sketch"):
            use = "face"
        depth, width = groove_size(cord, use)
        from fdcad.core.features.bodies import in_body_of, sketch_face
        from fdcad.core.occ import BRepAlgoAPI_Cut

        if feature.refs.get("sketch"):
            tool = _face_seal(feature, ctx, depth, width)
            on = sketch_face(feature, ctx)
        else:
            tool, on = _radial(feature, ctx, depth, width)

        # The groove is cut from the body of the picked face, or of the face the sketch
        # was drawn on (D2622). It was cut from the whole part: a groove on a shaft cut
        # into a hub on it too. A sketch on a plane still cuts every body it meets.
        def run(part: NamedShape) -> NamedShape:
            op = BRepAlgoAPI_Cut(part.shape, tool)
            op.Build()
            if not op.IsDone() or not solids(op.Shape()):
                raise FeatureError(f"{name}: the groove could not be cut. Move it on the part.")
            shape = op.Shape()
            return NamedShape(
                shape, restrict(carry(part.faces, op.History()), shape, f"{feature.id}/oring")
            )

        result = run(ctx.body) if on is None else in_body_of(ctx.body, on, feature.id, run)
        squeeze, fill = checks(cord, depth, width)
        issues = check_result(feature.id, name, ctx.body, result, None)
        if not 0.10 <= squeeze <= 0.30 or fill > 0.85:
            issues.append(
                Issue(
                    FeatureState.WARNING,
                    f"{name}: the ring is squeezed {squeeze:.0%} and fills {fill:.0%} of the "
                    "groove. Pick another cord or use so the squeeze is 10 to 30 percent and "
                    "the fill at most 85 percent.",
                    code="oring_check",
                )
            )
        out = FeatureResult(body=result, issues=issues)
        out.extras["oring"] = {"squeeze": squeeze, "fill": fill, "depth": depth, "width": width}
        return out


def _radial(feature: Feature, ctx: BuildContext, depth: float, width: float) -> tuple[Any, Any]:
    """A ring cut into a shaft (piston seal) or out of a bore (rod seal), and the
    picked round face."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Ax3, gp_Dir, gp_Pnt, gp_Vec

    from fdcad.core.features.shaft_shape import _placed, _round_face
    from fdcad.core.occ import BRepAlgoAPI_Cut

    name = feature.name
    if not feature.refs.get("face"):
        raise FeatureError(f"{name}: pick the round face of a shaft or bore, or a sketch.")
    axis, face, r, v0, v1, shaft = _round_face(feature, ctx)
    position = _value(feature, "position", 2.0)
    if position < 0 or position + width > v1 - v0 + 1e-9:
        raise FeatureError(
            f"{name}: the groove does not fit on the face there. "
            f"Enter a position from 0 to {v1 - v0 - width:.4g} mm."
        )
    if shaft and depth >= r:
        raise FeatureError(f"{name}: the groove is deeper than the shaft. Pick a smaller cord.")
    start = (
        v0 + position
        if feature.params.get("from_end", "start") == "start"
        else v1 - position - width
    )
    direction = gp_Dir(axis.Direction().XYZ())
    frame = gp_Ax3(axis.Location().Translated(gp_Vec(direction).Multiplied(start)), direction)
    outer, inner = (r + 1.0, r - depth) if shaft else (r + depth, max(r - 1.0, 0.01))
    base = gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))
    ring = BRepAlgoAPI_Cut(
        BRepPrimAPI_MakeCylinder(base, outer, width).Shape(),
        BRepPrimAPI_MakeCylinder(base, inner, width).Shape(),
    ).Shape()
    return _placed(ring, frame), face


def _face_seal(feature: Feature, ctx: BuildContext, depth: float, width: float) -> Any:
    """A groove ``width`` wide centred on the sketch's closed curve, ``depth`` into the
    face the sketch is on."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Vec

    from fdcad.core.features.profile_offset import offset_face
    from fdcad.core.features.sketch import sketch_input
    from fdcad.core.features.solids import compound
    from fdcad.core.occ import BRepAlgoAPI_Cut

    name = feature.name
    sketch = sketch_input(feature, ctx)
    if sketch.profile is None or not sketch.profile.faces:
        raise FeatureError(f"{name}: the sketch has no closed curve. Close the ring's path.")
    n = sketch.plane.normal
    pieces = []
    for face in sketch.profile.faces:
        try:
            outer, _p = offset_face(face, width / 2)
            inner, _q = offset_face(face, -width / 2)
            band = BRepAlgoAPI_Cut(outer, inner).Shape()
        except Exception as exc:
            raise FeatureError(
                f"{name}: the path is too tight for this groove. Pick a smaller cord or a "
                "larger path."
            ) from exc
        pieces.append(band)
    # The sketch sits on the face, with its normal pointing out of the part.
    lift = gp_Vec(*n).Multiplied(0.1)
    cuts = [BRepPrimAPI_MakePrism(p, gp_Vec(*n).Multiplied(-(depth + 0.1))).Shape() for p in pieces]
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Trsf

    move = gp_Trsf()
    move.SetTranslation(lift)
    return BRepBuilderAPI_Transform(compound(cuts), move, True).Shape()
