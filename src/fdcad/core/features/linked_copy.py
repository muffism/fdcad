"""Linked Body Copy: a copy that follows the original (TR154, DECISIONS D2417).

Type ``linked_copy``. Refs: ``bodies`` (a face of each body to copy). The copy is
made from the bodies as they are at the end of the part, so features added to the
original after the copy (also further down the tree) show on the copy too: the
rebuild builds linked copies, and the features that use their faces, after every
other feature (``deferred_order``). Params:

- ``place``: ``offset`` (default: ``dx``, ``dy``, ``dz`` and turns ``rx``, ``ry``,
  ``rz`` about the bodies' centre, turned before the shift) or ``on_frame`` (the copy
  sits on ``refs.frame``, a coordinate system or plane, as the original sits on the
  model origin).

Break Link (``break_link``) turns the link off (``data["link"]`` false) and puts the
features in the order they are built, so the copy is built in its place from then on
and no longer follows later changes. Copy faces are
``<fid>/copy/<name>``. No Qt.
"""

from __future__ import annotations

import copy
from typing import Any

from OCP.gp import gp_Ax3, gp_Dir, gp_Pnt, gp_Trsf

from fdcad.core.document.model import Document, Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.units import Kind

PLACES = ("offset", "on_frame")
TYPE = "linked_copy"


def _value(feature: Feature, name: str) -> float:
    from fdcad.core.features.move_copy_body import value

    return value(feature, name)


def _frame_trsf(feature: Feature, ctx: BuildContext) -> tuple[gp_Trsf, list[Issue]]:
    ref = feature.refs.get("frame")
    ref = ref[0] if isinstance(ref, list) and ref else ref
    if not isinstance(ref, dict):
        raise FeatureError(f"{feature.name}: pick the coordinate system the copy sits on.")
    if isinstance(ref.get("feature"), str):
        result = ctx.result(ref["feature"])
        datum = result.datum
        if datum is not None and datum.direction is not None:
            x = datum.x_dir
            target = (
                gp_Ax3(gp_Pnt(*datum.origin), gp_Dir(*datum.direction), gp_Dir(*x))
                if x is not None
                else gp_Ax3(gp_Pnt(*datum.origin), gp_Dir(*datum.direction))
            )
        elif result.plane is not None:
            target = result.plane.ax3()
        else:
            raise FeatureError(
                f"{feature.name}: the frame is not a coordinate system or plane. Pick one."
            )
    else:
        from fdcad.core.features.sketch import plane_of

        plane, issues = plane_of(ref, ctx, feature.name)
        target = plane.ax3()
        trsf = gp_Trsf()
        trsf.SetDisplacement(gp_Ax3(), target)
        return trsf, issues
    trsf = gp_Trsf()
    trsf.SetDisplacement(gp_Ax3(), target)
    return trsf, []


def placement(
    feature: Feature, ctx: BuildContext, centre: tuple[float, float, float]
) -> tuple[gp_Trsf, list[Issue]]:
    """The move from the original to the copy."""
    from fdcad.core.features.direct import translation
    from fdcad.core.features.move_copy_body import origin_rotation

    if feature.params.get("place", "offset") == "on_frame":
        return _frame_trsf(feature, ctx)
    turn = origin_rotation(feature, centre)
    shift = translation((_value(feature, "dx"), _value(feature, "dy"), _value(feature, "dz")))
    return shift.Multiplied(turn), []


@register
class LinkedCopy(FeatureType):
    """A copy of bodies that follows every change of the original."""

    type_name = TYPE
    makes_solid = True
    params = (
        ParamSpec("place", choices=PLACES, default="offset", optional=True),
        *(ParamSpec(k, kind=Kind.LENGTH, optional=True) for k in ("dx", "dy", "dz")),
        *(ParamSpec(k, kind=Kind.ANGLE, optional=True) for k in ("rx", "ry", "rz")),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Add the copy of the bodies as they are now."""
        from fdcad.core.features.bodies import body_indices, join, sub_body
        from fdcad.core.features.patterns import _moved_named
        from fdcad.core.naming.names import centroid

        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part has no bodies. Add a body first.")
        indices, issues = body_indices(ctx, feature.refs.get("bodies"), name)
        picked = sub_body(ctx.body, indices, feature.id)
        trsf, found = placement(feature, ctx, centroid(picked.shape))
        copied = _moved_named(picked, trsf, f"{feature.id}/copy")
        result = join([ctx.body, copied], feature.id)
        assert result is not None
        return FeatureResult(body=result, issues=issues + found)

    def tool(self, feature: Feature, ctx: BuildContext) -> Any:
        """The part with the copy, for the preview."""
        return self.execute(feature, ctx).body


def deferred_order(features: list[Feature]) -> list[Feature]:
    """``features`` with every linked copy, and every later feature that uses one's faces
    or another deferred feature, moved after the rest (each group keeps its order)."""
    from fdcad.core.io.fdef import feature_to_json_data

    if not any(linked(f) for f in features):
        return features
    deferred: list[Feature] = []
    held: set[str] = set()
    rest: list[Feature] = []
    for feature in features:
        if linked(feature):
            deferred.append(feature)
            held.add(feature.id)
            continue
        text = str(feature_to_json_data(feature).get("refs", {}))
        if any(f"'{fid}/" in text or f"'{fid}'" in text for fid in held):
            deferred.append(feature)
            held.add(feature.id)
        else:
            rest.append(feature)
    return rest + deferred


def linked(feature: Feature) -> bool:
    """True for a linked copy whose link is kept (Break Link sets ``data["link"]`` off)."""
    return feature.type == TYPE and feature.data.get("link", True) is not False


def break_link(doc: Document, fid: str) -> list[Feature]:
    """The document's features with linked copy ``fid`` made independent: its link is off
    and the features are put in the order they are built now (linked copies and the
    features on them last), so the copy stays as it is at the end of the part and no
    longer follows later changes. The document is not changed. Raises FeatureError."""
    found = doc.feature(fid)
    if not linked(found):
        raise FeatureError(f"{found.name} is not a linked copy. Pick a linked copy.")
    out = [copy.deepcopy(f) for f in deferred_order(list(doc.features))]
    for feature in out:
        if feature.id == fid:
            feature.data["link"] = False
    return out
