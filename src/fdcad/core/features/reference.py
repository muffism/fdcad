"""Built in reference features: the origin and the three default planes (FDEF_SPEC 5.2).

Params: ``plane`` has ``basis`` ("xy", "xz" or "yz"). Neither changes the part.

The part origin can be moved and turned (TR343, D2419): ``origin`` takes optional
``ox``, ``oy``, ``oz`` (lengths) and ``rx``, ``ry``, ``rz`` (angles, turned about X,
then Y, then Z). The main planes go with it, so new sketches on them sit at the new
origin and features built on them follow; geometry not built on them stays where it
is. The origin's result carries its frame as a datum.
"""

from __future__ import annotations

from typing import Any

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    Datum,
    FeatureResult,
    FeatureType,
    ParamSpec,
    register,
)
from fdcad.core.sketch.profiles import BASIS_PLANES, SketchPlane
from fdcad.core.units import Kind

#: The placement values of a moved origin (TR343, D2419).
ORIGIN_KEYS = ("ox", "oy", "oz", "rx", "ry", "rz")


def origin_trsf(doc: Document) -> Any:
    """The move from the model's own origin to the part origin, or None when it has not
    been moved (TR343, D2419)."""
    feature = next((f for f in doc.features if f.type == "origin"), None)
    if feature is None or not any(isinstance(feature.params.get(k), Param) for k in ORIGIN_KEYS):
        return None
    from OCP.gp import gp_Trsf, gp_Vec

    from fdcad.core.features.move_copy_body import origin_rotation, value

    turn = origin_rotation(feature, (0.0, 0.0, 0.0))
    shift = gp_Trsf()
    shift.SetTranslation(gp_Vec(value(feature, "ox"), value(feature, "oy"), value(feature, "oz")))
    out: Any = shift.Multiplied(turn)
    return out


def moved_plane(plane: SketchPlane, trsf: Any) -> SketchPlane:
    """``plane`` moved by ``trsf``."""
    from OCP.gp import gp_Dir, gp_Pnt

    o = gp_Pnt(*plane.origin).Transformed(trsf)
    n = gp_Dir(*plane.normal).Transformed(trsf)
    x = gp_Dir(*plane.x_dir).Transformed(trsf)
    return SketchPlane((o.X(), o.Y(), o.Z()), (n.X(), n.Y(), n.Z()), (x.X(), x.Y(), x.Z()))


@register
class Origin(FeatureType):
    """The model origin. Passes the part through unchanged."""

    type_name = "origin"
    params = (
        *(ParamSpec(k, kind=Kind.LENGTH, optional=True) for k in ("ox", "oy", "oz")),
        *(ParamSpec(k, kind=Kind.ANGLE, optional=True) for k in ("rx", "ry", "rz")),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Return the incoming part; a moved origin carries its frame (D2419)."""
        trsf = origin_trsf(ctx.document)
        if trsf is None:
            return FeatureResult(body=ctx.body)
        frame = moved_plane(BASIS_PLANES["xy"], trsf)
        datum = Datum("frame", frame.origin, frame.normal, frame.x_dir)
        return FeatureResult(body=ctx.body, datum=datum)


@register
class Plane(FeatureType):
    """A default plane through the origin."""

    type_name = "plane"
    params = (ParamSpec("basis", choices=("xy", "xz", "yz")),)

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Return the incoming part and the plane placement."""
        basis = str(self.setting(feature, "basis", ""))
        plane = BASIS_PLANES[basis]
        trsf = origin_trsf(ctx.document)  # the main planes go with a moved origin (D2419)
        if trsf is not None:
            plane = moved_plane(plane, trsf)
        return FeatureResult(body=ctx.body, plane=plane)
