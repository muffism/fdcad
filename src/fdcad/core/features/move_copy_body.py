"""Move or copy bodies (PHASE3_SPEC P3.4 item 4, P3.7 item 3, DECISIONS D233).

Params:
- ``mode``: "translate" or "rotate".
- ``copy``: boolean; ``count``: number of copies (each moved once more than the last).
- ``translate_by``: "delta" (``dx``, ``dy``, ``dz``), "edge" (along ``refs.edge``
  by ``distance``) or "vertices" (from ``refs.from`` to ``refs.to``).
- ``reverse``: boolean, flips the move along an edge or the turn about an edge.
- ``rotate_by``: "edge" (``refs.axis`` by ``angle``), "origin" (``ox``, ``oy``,
  ``oz`` and ``rx``, ``ry``, ``rz``: turns about X, then Y, then Z) or "centroid"
  (the same turns about the centre of the picked bodies, DECISIONS D411).

- ``mode`` "relations" (TR268 item 1, D2415): ``refs.rel_from`` and ``refs.rel_to``
  pairs with the ``relations`` text, solved together, see ``body_relations``.
- ``mode`` "frame" (TR268, D1815): ``refs.from_frame`` onto ``refs.to_frame`` (origin,
  Z and optional X picks each), see ``orient_body``.

Refs: ``bodies`` (face references to faces of the bodies) and the picks above.

Face roles: moved bodies keep their names; copies are ``copy<k>/<name>``.
This is also the feature the transform handles write (PLAN Phase 3, D411): while
nothing is moved yet, the body shows both the move arrows and the turn rings.
"""

from __future__ import annotations

from OCP.gp import gp_Trsf

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    ANGLE_RULER_STEP,
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    PreviewHandle,
    register,
    ruler_step,
)
from fdcad.core.features.bodies import body_indices, join, rest_of, sub_body
from fdcad.core.features.direct import rotation, translation
from fdcad.core.features.geometry_refs import minus, resolve_placement, scaled
from fdcad.core.features.linear_pattern import count_of
from fdcad.core.features.patterns import _moved_named
from fdcad.core.features.solids import bounding_size
from fdcad.core.naming.names import NamedShape, centroid
from fdcad.core.units import Kind

Vec3 = tuple[float, float, float]

_AXES = (("x", (1.0, 0.0, 0.0)), ("y", (0.0, 1.0, 0.0)), ("z", (0.0, 0.0, 1.0)))


def value(feature: Feature, name: str) -> float:
    """A typed parameter's value, 0 when it is not set."""
    found = feature.params.get(name)
    return found.value if isinstance(found, Param) else 0.0


def origin_rotation(
    feature: Feature, origin: Vec3 | None = None, axes: tuple[Vec3, Vec3, Vec3] | None = None
) -> gp_Trsf:
    """Turns about X, Y and Z through ``origin`` (default: the origin fields), in that order;
    ``axes`` are the handle axes (TR268 item 3, D2416), the model's by default."""
    if origin is None:
        origin = (value(feature, "ox"), value(feature, "oy"), value(feature, "oz"))
    trsf = gp_Trsf()
    for (axis, direction), along in zip(_AXES, axes or [d for _a, d in _AXES], strict=True):
        angle = value(feature, f"r{axis}")
        if angle:
            trsf = rotation(origin, along, angle).Multiplied(trsf)
        _ = direction
    return trsf


#: Where the transform handles sit, and which way their axes point (TR268 item 3, D2416).
PIVOTS = ("body_centre", "picked")
HANDLE_AXES = ("model", "plane_axes")


def handle_axes(feature: Feature, ctx: BuildContext) -> tuple[Vec3, Vec3, Vec3]:
    """The X, Y and Z of the handles: the model's, or a picked plane's (its X, Y and normal)."""
    if feature.params.get("handle_axes", "model") != "plane_axes":
        return (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)
    from fdcad.core.features.datum import cross, unit, x_hint

    found = resolve_placement(ctx, feature.refs.get("handle_plane"), feature.name, "plane")
    z = found.direction
    x = x_hint(z)
    try:
        from fdcad.core.features.sketch import plane_of

        ref = feature.refs.get("handle_plane")
        if isinstance(ref, dict):
            plane, _issues = plane_of(ref, ctx, feature.name)
            x = plane.x_dir
    except FeatureError:
        pass
    y = unit(cross(z, x))
    assert y is not None
    return x, y, z


def pivot_point(feature: Feature, ctx: BuildContext, centre: Vec3) -> Vec3:
    """Where the handles sit and turns about the centre go: the bodies' centre, or a
    picked point, which moves only the handle (TR268 item 3, D2416)."""
    if feature.params.get("pivot", "body_centre") != "picked":
        return centre
    ref = feature.refs.get("pivot_point")
    ref = ref[0] if isinstance(ref, list) and ref else ref
    if isinstance(ref, dict) and isinstance(ref.get("feature"), str) and len(ref) == 1:
        datum = ctx.result(ref["feature"]).datum
        if datum is not None and datum.kind == "point":
            return datum.origin
    return resolve_placement(ctx, ref, feature.name, "point").point


@register
class MoveCopyBody(FeatureType):
    """Moves, turns or copies whole bodies."""

    type_name = "move_copy_body"
    makes_solid = True
    params = (
        ParamSpec(
            "mode", choices=("translate", "rotate", "frame", "relations"), default="translate"
        ),
        ParamSpec("copy", default=False, optional=True),
        ParamSpec("count", kind=Kind.NUMBER, optional=True),
        ParamSpec("translate_by", choices=("delta", "edge", "vertices"), optional=True),
        ParamSpec("rotate_by", choices=("edge", "origin", "centroid"), optional=True),
        ParamSpec("reverse", default=False, optional=True),
        ParamSpec("distance", kind=Kind.LENGTH, optional=True),
        ParamSpec("angle", kind=Kind.ANGLE, optional=True),
        *(
            ParamSpec(k, kind=Kind.LENGTH, optional=True)
            for k in ("dx", "dy", "dz", "ox", "oy", "oz")
        ),
        *(ParamSpec(k, kind=Kind.ANGLE, optional=True) for k in ("rx", "ry", "rz")),
        ParamSpec("pivot", choices=PIVOTS, optional=True),  # TR268 item 3 (D2416)
        ParamSpec("handle_axes", choices=HANDLE_AXES, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Move or copy the bodies."""
        body, issues = self._build(feature, ctx)
        return FeatureResult(body=body, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The part after the move, for the live preview."""
        return self._build(feature, ctx)[0]

    def trsf(
        self, feature: Feature, ctx: BuildContext, centre: Vec3 = (0.0, 0.0, 0.0)
    ) -> tuple[gp_Trsf, list[Issue]]:
        """The move of one step. ``centre`` is the centre of the picked bodies."""
        name = feature.name
        sign = -1.0 if feature.params.get("reverse") is True else 1.0
        if feature.params.get("mode") == "relations":  # TR268 item 1 (D2415)
            from fdcad.core.features.body_relations import relation_move

            text = str(feature.params.get("relations", "") or "")
            return relation_move(ctx, feature.refs, text, name, centre)
        if feature.params.get("mode") == "frame":  # TR268 item 2 (D1815)
            from fdcad.core.features.orient_body import frame_move

            return frame_move(ctx, feature.refs, name, sign < 0)
        axes = handle_axes(feature, ctx)  # TR268 item 3 (D2416)
        if feature.params.get("mode", "translate") == "rotate":
            how = feature.params.get("rotate_by", "edge")
            if how == "origin":
                return origin_rotation(feature, None, axes), []
            if how == "centroid":
                return origin_rotation(feature, pivot_point(feature, ctx, centre), axes), []
            axis = resolve_placement(ctx, feature.refs.get("axis"), name, "axis")
            return rotation(
                axis.point, axis.direction, self.number(feature, "angle") * sign
            ), axis.issues
        how = feature.params.get("translate_by", "delta")
        if how == "edge":
            edge = resolve_placement(ctx, feature.refs.get("edge"), name, "direction")
            distance = self.number(feature, "distance") * sign
            return translation(scaled(edge.direction, distance)), edge.issues
        if how == "vertices":
            a = resolve_placement(ctx, feature.refs.get("from"), name, "point")
            b = resolve_placement(ctx, feature.refs.get("to"), name, "point")
            return translation(minus(b.point, a.point)), a.issues + b.issues
        d = (value(feature, "dx"), value(feature, "dy"), value(feature, "dz"))
        delta = tuple(sum(d[k] * axes[k][i] for k in range(3)) for i in range(3))
        return translation(delta), []  # type: ignore[arg-type]

    def _build(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part has no bodies. Add a body first.")
        indices, issues = body_indices(ctx, feature.refs.get("bodies"), name)
        picked = sub_body(ctx.body, indices, feature.id)
        step, found = self.trsf(feature, ctx, centroid(picked.shape))
        issues += found
        if feature.params.get("copy") is True:
            count = count_of(feature, "count") if "count" in feature.params else 1
            copies = []
            current = gp_Trsf()
            for k in range(1, count + 1):
                current = step.Multiplied(current)
                copies.append(_moved_named(picked, current, f"{feature.id}/copy{k}"))
            result = join([ctx.body, *copies], feature.id)
        else:
            moved = _moved_named(picked, step, "")
            # Moved bodies keep their names: drop the empty prefix again.
            moved.faces = [(n.removeprefix("/"), f) for n, f in moved.faces]
            result = join([rest_of(ctx.body, indices, feature.id), moved], feature.id)
        assert result is not None
        return result, issues

    def preview_handles(self, feature: Feature, ctx: BuildContext) -> list[PreviewHandle]:
        """Transform handles on the picked bodies: arrows for X, Y, Z and rings for turns.

        Moving by Delta X, Y, Z shows the arrows, turning about the origin or the
        bodies' centre shows the rings. While the current move is still zero, the
        other kind shows too, so a new move can start with either (D411).
        """
        if ctx.body is None:
            return []
        try:
            indices, _ = body_indices(ctx, feature.refs.get("bodies"), feature.name)
        except FeatureError:
            return []
        picked = sub_body(ctx.body, indices, feature.id)
        try:  # TR268 item 3 (D2416): the pivot and the handle axes
            base = pivot_point(feature, ctx, centroid(picked.shape))
            axes = handle_axes(feature, ctx)
        except FeatureError:
            return []
        size = bounding_size(picked.shape) * 0.5
        step = ruler_step(bounding_size(picked.shape))
        mode = feature.params.get("mode", "translate")
        how = feature.params.get("rotate_by", "edge")
        moving = mode == "translate" and feature.params.get("translate_by", "delta") == "delta"
        turning = mode == "rotate" and how in ("origin", "centroid")
        if not moving and not turning:
            return []
        arrows = _arrows(feature, base, step, axes)
        if turning and how == "origin":
            centre = (value(feature, "ox"), value(feature, "oy"), value(feature, "oz"))
        else:
            centre = base
        rings = _rings(feature, centre, size, axes)
        if moving:
            idle = all(value(feature, f"d{a}") == 0 for a, _d in _AXES)
            return arrows + (rings if idle else [])
        idle = all(value(feature, f"r{a}") == 0 for a, _d in _AXES)
        return rings + (arrows if idle else [])


def _arrows(
    feature: Feature, base: Vec3, step: float, axes: tuple[Vec3, Vec3, Vec3] | None = None
) -> list[PreviewHandle]:
    """Move arrows along X, Y and Z (the handle axes) from ``base``."""
    out = []
    for (axis, _model), direction in zip(_AXES, axes or [d for _a, d in _AXES], strict=True):
        v = value(feature, f"d{axis}")
        out.append(
            PreviewHandle(
                f"d{axis}",
                base,
                scaled(direction, -1.0 if v < 0 else 1.0),
                abs(v),
                step=step,
                flips=True,
            )
        )
    return out


def _rings(
    feature: Feature, centre: Vec3, size: float, axes: tuple[Vec3, Vec3, Vec3] | None = None
) -> list[PreviewHandle]:
    """Turn rings about X, Y and Z (the handle axes) through ``centre``."""
    out = []
    dirs = list(axes or [d for _a, d in _AXES])
    for i, (axis, _model) in enumerate(_AXES):
        direction = dirs[i]
        v = value(feature, f"r{axis}")
        other = dirs[(i + 1) % 3]
        ring = (
            centre[0] + other[0] * size,
            centre[1] + other[1] * size,
            centre[2] + other[2] * size,
        )
        out.append(
            PreviewHandle(
                f"r{axis}",
                ring,
                scaled(direction, -1.0 if v < 0 else 1.0),
                abs(v),
                centre=centre,
                step=ANGLE_RULER_STEP,
                flips=True,
            )
        )
    return out
