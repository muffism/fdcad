"""Multi colour inlay (TUTORIAL_REVIEW_SPEC_2 TR184, DECISIONS D867).

Type ``inlay``. A sketch on a face of the part (text or shapes, ``refs.sketch``,
optionally ``refs.regions``) is cut ``depth`` into the part, and the material it
removes becomes a separate body of the same shape: the inlay, printed in a second
colour. Its faces are named ``<fid>/inlay/...``; the pocket faces use the usual
extrude names. Exports keep the inlay as its own body, so a 3MF holds both.
"""

from __future__ import annotations

import copy

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    register,
)
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind


def _tool(feature: Feature, ctx: BuildContext, reverse: bool) -> NamedShape:
    from fdcad.core.features.base import REGISTRY

    sub = copy.deepcopy(feature)
    sub.type = "extrude"
    sub.params = {
        "operation": "cut",
        "end_condition": "blind",
        "depth": feature.params["depth"],
        "reverse": reverse,
        "normal_cut": False,
    }
    made = REGISTRY["extrude"].tool(sub, ctx)
    if made is None:
        raise FeatureError(f"{feature.name}: the sketch makes no shape. Close its outline.")
    return made


@register
class Inlay(FeatureType):
    """Cuts a sketch into the part and keeps the cut material as a second body."""

    type_name = "inlay"
    makes_solid = True
    params = (ParamSpec("depth", kind=Kind.LENGTH),)

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Pocket and inlay."""
        from fdcad.core.document.model import Param
        from fdcad.core.features.bodies import join
        from fdcad.core.features.booleans import boolean_named
        from fdcad.core.features.solids import check_result, solids, volume_of

        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part is empty. Add a body first.")
        depth = feature.params.get("depth")
        if not isinstance(depth, Param) or depth.value <= 0:
            raise FeatureError(f"{name}: the depth must be greater than zero. Enter a depth.")
        inlay = None
        for reverse in (False, True):  # into the material, whichever side that is
            tool = _tool(feature, ctx, reverse)
            try:
                inside = boolean_named("common", ctx.body, tool, feature.id, name)
            except FeatureError:
                continue
            if solids(inside.shape) and volume_of(inside.shape) > 1e-9:
                inlay = inside
                break
        if inlay is None:
            raise FeatureError(
                f"{name}: the sketch does not reach into the part. Move the sketch onto a face "
                "of the part."
            )
        pocket = boolean_named("cut", ctx.body, inlay, feature.id, name)
        prefix = f"{feature.id}/"
        piece = NamedShape(
            inlay.shape,
            [
                (
                    n.replace(prefix, f"{prefix}inlay/", 1)
                    if n.startswith(prefix)
                    else f"{prefix}inlay/{n}",
                    f,
                )
                for n, f in inlay.faces
            ],
        )
        body = join([pocket, piece], feature.id)
        assert body is not None
        issues = [
            i
            for i in check_result(feature.id, name, ctx.body, body, None)
            if i.code != "separate_body"
        ]
        return FeatureResult(body=body, issues=issues)
