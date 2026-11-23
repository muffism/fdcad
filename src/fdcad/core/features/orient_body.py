"""Orient Body: map a picked frame of a body onto another frame (TR268 item 2, D1815).

Move and Copy Body with ``mode`` "frame". ``refs.from_frame`` and ``refs.to_frame``
each hold up to three picks, in order: the origin (a vertex, or a round edge or
cylinder for its centre on the axis), the Z direction (a flat face's normal, a
straight edge or an axis) and, optional, the X direction (a straight edge or a flat
face's normal, made square to Z). The body moves so its frame lands on the target
frame. ``reverse`` turns the target Z round (the body flips over).
"""

from __future__ import annotations

import math
from typing import Any

from OCP.gp import gp_Ax3, gp_Dir, gp_Pnt, gp_Trsf

from fdcad.core.features.base import BuildContext, FeatureError, Issue, Vec3
from fdcad.core.features.geometry_refs import resolve_placement


def _origin(ctx: BuildContext, ref: Any, owner: str) -> tuple[Vec3, list[Issue]]:
    if isinstance(ref, dict) and ref.get("kind") == "vertex":
        found = resolve_placement(ctx, ref, owner, "point")
        return found.point, found.issues
    try:
        found = resolve_placement(ctx, ref, owner, "axis")
    except FeatureError as exc:
        raise FeatureError(
            f"{owner}: a frame origin must be a vertex, a round edge or a cylinder. "
            "Pick one of those first."
        ) from exc
    return found.point, found.issues


def frame(ctx: BuildContext, picks: Any, owner: str, which: str) -> tuple[gp_Ax3, list[Issue]]:
    """The frame of ``picks`` (origin, Z, optional X)."""
    if not isinstance(picks, list) or len(picks) < 2:
        raise FeatureError(
            f"{owner}: the {which} frame needs an origin and a Z direction. "
            "Pick a vertex or round edge, then a face or edge for Z."
        )
    point, issues = _origin(ctx, picks[0], owner)
    z = resolve_placement(ctx, picks[1], owner, "direction")
    issues = issues + z.issues
    zd = gp_Dir(*z.direction)
    if len(picks) > 2:
        x = resolve_placement(ctx, picks[2], owner, "direction")
        issues = issues + x.issues
        xv = x.direction
        along = sum(xv[i] * z.direction[i] for i in range(3))
        rest = [xv[i] - along * z.direction[i] for i in range(3)]
        if math.sqrt(sum(c * c for c in rest)) < 1e-6:
            raise FeatureError(
                f"{owner}: the {which} frame's X runs along its Z. Pick an X edge across Z."
            )
        return gp_Ax3(gp_Pnt(*point), zd, gp_Dir(*rest)), issues
    return gp_Ax3(gp_Pnt(*point), zd), issues


def frame_move(
    ctx: BuildContext, refs: dict[str, Any], owner: str, flip: bool
) -> tuple[gp_Trsf, list[Issue]]:
    """The move that takes the from frame onto the to frame."""
    start, issues = frame(ctx, refs.get("from_frame"), owner, "body")
    end, more = frame(ctx, refs.get("to_frame"), owner, "target")
    if flip:
        end.ZReverse()
    trsf = gp_Trsf()
    trsf.SetDisplacement(start, end)
    return trsf, issues + more
