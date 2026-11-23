"""Indent (TR68, DECISIONS D1026): reshape a target body round a tool body.

Type ``indent``. Pick the target body, then the tool body (``refs.bodies``, in that
order). The tool stays as it is. ``indent_mode``:

- ``indent`` (default): the target gets a wall ``indent_thickness`` thick round the tool,
  ``indent_clearance`` away from it, where the tool presses into or stands beside the target;
  the space the tool takes, grown by the clearance, is taken out. Only the part of
  that wall within one thickness of the target is added, so the wall follows the
  target rather than wrapping the whole tool.
- ``cut``: only the space the tool takes, grown by the clearance, is taken out of the
  target: a pocket that follows an inserted part.

New faces are ``<fid>/indent/<k>``, numbered by position (D1068).
"""

from __future__ import annotations

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
from fdcad.core.units import Kind

MODES = ("indent", "cut")


def _value(feature: Feature, key: str, default: float) -> float:
    found = feature.params.get(key)
    return found.value if isinstance(found, Param) else default


def grown(solid: Any, by: float, owner: str) -> Any:
    """``solid`` grown by ``by`` mm on every side (unchanged for 0)."""
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeOffsetShape

    if abs(by) < 1e-9:
        return solid
    maker = BRepOffsetAPI_MakeOffsetShape()
    try:
        maker.PerformByJoin(solid, by, 1e-6)
    except Exception as exc:  # kernel failure becomes a feature error
        raise FeatureError(
            f"{owner}: the tool body could not be grown by {by:.4g} mm. Use a smaller "
            "clearance or thickness."
        ) from exc
    if not maker.IsDone():
        raise FeatureError(
            f"{owner}: the tool body could not be grown by {by:.4g} mm. Use a smaller "
            "clearance or thickness."
        )
    return maker.Shape()


@register
class Indent(FeatureType):
    """A wall or pocket in one body that follows the shape of another."""

    type_name = "indent"
    makes_solid = True
    params = (
        ParamSpec("indent_mode", choices=MODES, default="indent", optional=True),
        ParamSpec("indent_thickness", kind=Kind.LENGTH, optional=True),
        ParamSpec("indent_clearance", kind=Kind.LENGTH, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Reshape the target round the tool."""
        from fdcad.core.features.bodies import body_indices, join, rest_of, sub_body
        from fdcad.core.features.booleans import boolean_named
        from fdcad.core.features.solids import check_result, solids, volume_of
        from fdcad.core.naming.names import NamedShape, in_order
        from fdcad.core.occ import BRepAlgoAPI_Common, BRepAlgoAPI_Cut

        name, fid = feature.name, feature.id
        if ctx.body is None:
            raise FeatureError(f"{name}: the part is empty. Add the two bodies first.")
        indices, issues = body_indices(ctx, feature.refs.get("bodies"), name)
        if len(indices) != 2:
            raise FeatureError(f"{name}: pick the target body, then the tool body.")
        target_index, tool_index = indices
        all_solids = solids(ctx.body.shape)
        target, tool = all_solids[target_index], all_solids[tool_index]
        mode = str(feature.params.get("indent_mode", "indent"))
        if mode not in MODES:
            raise FeatureError(f"{name}: unknown mode '{mode}'. Choose Indent or Cut.")
        clearance = _value(feature, "indent_clearance", 0.0)
        thickness = _value(feature, "indent_thickness", 1.0)
        if clearance < 0:
            raise FeatureError(f"{name}: the clearance cannot be below 0. Enter 0 or more.")
        if mode == "indent" and not thickness > 0:
            raise FeatureError(f"{name}: the thickness must be more than 0. Enter a thickness.")
        hollow = grown(tool, clearance, name)
        reach = volume_of(
            BRepAlgoAPI_Common(target, grown(tool, clearance + thickness, name)).Shape()
        )
        if reach < 1e-9:
            raise FeatureError(
                f"{name}: the tool does not reach the target. Move the tool against the target "
                "or into it."
            )
        new_target = sub_body(ctx.body, [target_index], fid)
        if mode == "indent":
            wall = BRepAlgoAPI_Cut(grown(tool, clearance + thickness, name), hollow).Shape()
            near = BRepAlgoAPI_Common(wall, grown(target, thickness, name)).Shape()
            if solids(near):
                add = NamedShape(
                    near, [(f"{fid}/indent/w{k}", f) for k, f in enumerate(in_order(near), 1)]
                )
                new_target = boolean_named("fuse", new_target, add, fid, name)
        cut = NamedShape(
            hollow, [(f"{fid}/indent/{k}", f) for k, f in enumerate(in_order(hollow), 1)]
        )
        new_target = boolean_named("cut", new_target, cut, fid, name)
        parts: list[NamedShape | None] = [rest_of(ctx.body, [target_index], fid), new_target]
        result = join(parts, fid)
        assert result is not None
        found = [
            i for i in check_result(fid, name, ctx.body, result, None) if i.code != "separate_body"
        ]
        return FeatureResult(body=result, issues=[*issues, *found])
