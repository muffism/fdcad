"""Snap hook groove (PHASE4_SPEC P4.4 item 3, DECISIONS D317).

The pocket a snap hook's head catches in, cut into another body. Its outline
follows the hook's head (so it follows the hook's lead in draft), grown by the
clearances.

Params (FDEF_SPEC 5.3.26), all lengths:

- ``offset_height``: how far the groove's ledge sits below the hook's catch.
- ``hook_height``: height of the head pocket above the catch (the hook's own
  hook height when left out).
- ``gap_height``: extra room above the head.
- ``groove_clearance``: room in front of the head. ``gap_clearance``: room behind.
- ``offset_width``: extra width on each side.

Refs: ``hook`` (``{"feature": <snap hook id>}``) and ``body`` (one face of the
body to cut; the hook's own body is never cut).

Face roles: ``groove/face/<k>`` (outline sides from the ledge round to the back),
``groove/face/start`` and ``groove/face/end``.
"""

from __future__ import annotations

from OCP.TopoDS import TopoDS_Shape

from fdcad.core.document.model import Feature
from fdcad.core.features import fastening as fx
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.modify import require_body
from fdcad.core.features.snap_hook import HookShape, hook_shape, value
from fdcad.core.features.solids import FUZZY_TOLERANCE, check_result, compound, solids
from fdcad.core.naming.names import NamedShape, carry, restrict
from fdcad.core.occ import BRepAlgoAPI_Cut
from fdcad.core.units import Kind

_LENGTHS = (
    "offset_height",
    "hook_height",
    "gap_height",
    "groove_clearance",
    "gap_clearance",
    "offset_width",
)


def groove_solid(fid: str, hook: HookShape, feature: Feature) -> NamedShape:
    """The groove pocket in the hook's frame."""
    off = value(feature, "offset_height", 0.0)
    head = value(feature, "hook_height", hook.hook_height)
    gap = value(feature, "gap_height", 0.0)
    front = value(feature, "groove_clearance", 0.0)
    back = value(feature, "gap_clearance", 0.0)
    side = value(feature, "offset_width", 0.0)
    if min(off, gap, front, back, side) < 0 or head <= 0:
        raise FeatureError(
            f"{feature.name}: groove values cannot be negative and the hook height must be "
            "above zero. Enter other values."
        )
    f, h = hook.frame, hook.height
    reach_x = hook.top + hook.overhang + front
    tip_x = hook.tip_x + front

    def at(x: float, y: float) -> fx.Vec3:
        return fx.add(fx.add(f.origin, f.x, x), fx.add((0, 0, 0), f.up, y))

    outline = [
        at(-back, h - off),
        at(reach_x, h - off),
        at(reach_x, h + min(hook.lip_height, head)),
        at(tip_x, h + head),
        at(tip_x, h + head + gap),
        at(-back, h + head + gap),
    ]
    # A zero gap height (or a lip as tall as the head) makes two corners the same
    # point; the kernel cannot build a side of zero length.
    outline = [p for i, p in enumerate(outline) if i == 0 or _apart(p, outline[i - 1])]
    if len(outline) > 1 and not _apart(outline[-1], outline[0]):
        outline.pop()
    width = hook.width + 2 * side
    outline = [fx.add(p, f.y, -width / 2) for p in outline]
    return fx.named_prism(f"{fid}/groove", "face", outline, fx.add((0, 0, 0), f.y, width))


def _holds_hook(feature: Feature, ctx: BuildContext, target: TopoDS_Shape) -> bool:
    """True when ``target`` is the hook's own body: the body of the face it stands on."""
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp

    from fdcad.core.occ import ShapeMap

    hook_feature = ctx.document.feature(str(feature.refs["hook"]["feature"]))
    try:
        face, _issues = fx.face_of(hook_feature, ctx)
    except FeatureError:
        return False
    fmap = ShapeMap()
    TopExp.MapShapes_s(target, TopAbs_FACE, fmap)
    return bool(fmap.Contains(face))


def _apart(a: fx.Vec3, b: fx.Vec3) -> bool:
    return sum((x - y) ** 2 for x, y in zip(a, b, strict=True)) > 1e-12


@register
class SnapGroove(FeatureType):
    """The groove for a snap hook, cut into the mating body."""

    type_name = "snap_groove"
    makes_solid = True
    params = (ParamSpec("groove_clearance", kind=Kind.LENGTH, optional=True),)

    def kind_of(self, name: str) -> Kind | None:
        """Every value is a length."""
        if name in _LENGTHS:
            return Kind.LENGTH
        return super().kind_of(name)

    def _groove(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        ref = feature.refs.get("hook")
        if not isinstance(ref, dict) or "feature" not in ref:
            raise FeatureError(f"{feature.name}: pick the snap hook the groove is for.")
        hid = str(ref["feature"])
        ctx.result(hid)  # the hook must have built
        hook_feature = ctx.document.feature(hid)
        if hook_feature.type != "snap_hook":
            raise FeatureError(
                f"{feature.name}: the picked feature is not a snap hook. Pick a snap hook."
            )
        hook, issues = hook_shape(hook_feature, ctx)
        return groove_solid(feature.id, hook, feature), issues

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Cut the groove from the picked body only."""
        body = require_body(feature, ctx)
        groove, issues = self._groove(feature, ctx)
        if not feature.refs.get("body"):
            raise FeatureError(f"{feature.name}: pick a face of the body to cut the groove in.")
        face, found = fx.face_of(feature, ctx, "body")
        issues += found
        target = fx.solid_with_face(body.shape, face)
        if target is None:
            raise FeatureError(f"{feature.name}: the picked face is not on a body. Pick again.")
        if _holds_hook(feature, ctx, target):
            raise FeatureError(
                f"{feature.name}: the picked body holds the snap hook, so the groove would "
                "cut the hook. Pick a face of the body the hook catches in, or split the part "
                "first."
            )
        others = [s for s in solids(body.shape) if not s.IsSame(target)]
        op = BRepAlgoAPI_Cut(target, groove.shape)
        op.SetFuzzyValue(FUZZY_TOLERANCE)
        op.Build()
        if not op.IsDone():
            raise FeatureError(
                f"{feature.name} failed: the groove could not be cut. Change its values slightly."
            )
        cut = op.Shape()
        # Bodies keep their order: colours and hidden bodies go by body number.
        pieces = [solids(cut) if s.IsSame(target) else [s] for s in solids(body.shape)]
        shape = compound([p for group in pieces for p in group]) if others else cut
        names = carry(body.faces + groove.faces, op.History())
        result = NamedShape(shape, restrict(names, shape, feature.id))
        issues = issues + check_result(feature.id, feature.name, ctx.body, result, None)
        return FeatureResult(body=result, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The groove pocket, for the preview."""
        groove, _issues = self._groove(feature, ctx)
        return groove
