"""Sprue Tree: casting sprues, or a kit frame of parts on a runner (TR408 item 3, D2411).

Type ``sprue_tree``. Refs: ``feed_points``, the spots where the parts are fed (vertices,
sketch points or reference points, at least one), and for a tree ``cup`` (a point:
the middle of the pouring cup's open end). Params, lengths unless noted:

- ``layout``: ``tree`` (default) or ``kit_frame``.
- Tree: a pouring cup ``cup_diameter`` wide and ``cup_height`` deep narrows to the
  trunk, ``sprue_diameter`` thick, which runs from the cup straight toward the
  points as far as the farthest of them; a gate ``gate_diameter`` thick runs square
  from the trunk to each point, with a ball at each joint.
- Frame: a rectangular runner ``sprue_diameter`` thick round all the points, in the
  plane through their middle square to their least spread, ``margin`` outside them;
  a gate runs from each point straight to the nearest side of the frame. The frame's
  sides follow model X, or Y, laid in that plane.

Everything is joined to the part, so the parts and their feeds make one body, as a
casting master or a model kit sprue. Faces: ``cup``, ``trunk``, ``gate<k>``,
``frame``. No Qt.
"""

from __future__ import annotations

import numpy as np
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.solids import check_result, compound
from fdcad.core.naming.names import NamedShape, faces_of
from fdcad.core.units import Kind

LAYOUTS = ("tree", "kit_frame")
MOST_POINTS = 200
_TINY = 1e-6


def _value(feature: Feature, name: str, default: float) -> float:
    v = feature.params.get(name)
    return v.value if isinstance(v, Param) else default


def _rod(a: np.ndarray, b: np.ndarray, diameter: float) -> TopoDS_Shape | None:
    """A round rod from ``a`` to ``b``, or None when they meet."""
    v = b - a
    n = float(np.linalg.norm(v))
    if n < _TINY:
        return None
    axis = gp_Ax2(gp_Pnt(*a), gp_Dir(*(v / n)))
    return BRepPrimAPI_MakeCylinder(axis, diameter / 2, n).Shape()


def _ball(p: np.ndarray, diameter: float) -> TopoDS_Shape:
    return BRepPrimAPI_MakeSphere(gp_Pnt(*p), diameter / 2).Shape()


def _points(feature: Feature, ctx: BuildContext, key: str) -> tuple[np.ndarray, list[Issue]]:
    from fdcad.core.features.geometry_refs import resolve_placement

    refs = feature.refs.get(key)
    items = refs if isinstance(refs, list) else ([refs] if isinstance(refs, dict) else [])
    out, issues = [], []
    for ref in items:
        datum = ctx.result(ref["feature"]).datum if _is_feature(ref) else None
        if datum is not None and datum.kind == "point":  # a reference point
            out.append(datum.origin)
            continue
        place = resolve_placement(ctx, ref, feature.name, "point")
        issues += place.issues
        out.append(place.point)
    return np.array(out, dtype=float).reshape(-1, 3), issues


def _is_feature(ref: object) -> bool:
    return isinstance(ref, dict) and isinstance(ref.get("feature"), str) and len(ref) == 1


def tree_pieces(
    cup: np.ndarray, points: np.ndarray, sizes: dict[str, float]
) -> list[tuple[str, TopoDS_Shape]]:
    """The cup, trunk, gates and joint balls of a sprue tree."""
    middle = points.mean(axis=0)
    run = middle - cup
    if float(np.linalg.norm(run)) < _TINY:
        raise ValueError("the cup sits on the middle of the points. Move the cup away.")
    axis = run / np.linalg.norm(run)
    cup_h, cup_d, trunk_d, gate_d = (
        sizes["cup_height"], sizes["cup_diameter"], sizes["sprue_diameter"], sizes["gate_diameter"],
    )  # fmt: skip
    neck = cup + axis * cup_h
    reach = max(float(np.dot(p - cup, axis)) for p in points)
    if reach <= cup_h:
        raise ValueError("the points are inside the cup's depth. Move the cup farther away.")
    out: list[tuple[str, TopoDS_Shape]] = []
    frame = gp_Ax2(gp_Pnt(*cup), gp_Dir(*axis))
    out.append(("cup", BRepPrimAPI_MakeCone(frame, cup_d / 2, trunk_d / 2, cup_h).Shape()))
    end = cup + axis * reach
    trunk = _rod(neck, end, trunk_d)
    if trunk is not None:
        out.append(("trunk", trunk))
    out.append(("trunk", _ball(end, trunk_d)))
    for k, p in enumerate(points, start=1):
        foot = cup + axis * max(float(np.dot(p - cup, axis)), cup_h)
        gate = _rod(foot, p, gate_d)
        if gate is not None:
            out.append((f"gate{k}", gate))
            out.append((f"gate{k}", _ball(foot, max(gate_d, trunk_d))))
    return out


def frame_pieces(points: np.ndarray, sizes: dict[str, float]) -> list[tuple[str, TopoDS_Shape]]:
    """A rectangular runner round the points with a gate from each to its nearest side."""
    middle = points.mean(axis=0)
    spread = points - middle
    normal = np.array([0.0, 0.0, 1.0])
    if len(points) >= 3:
        _u, sing, vt = np.linalg.svd(spread)
        if sing[1] > _TINY:  # the points span a plane: square to their least spread
            normal = vt[2]
    # The frame's sides follow model X (or Y) laid in that plane, so a frame round parts
    # on the Front plane is square to the model.
    x = np.array([1.0, 0.0, 0.0]) - normal * normal[0]
    if float(np.linalg.norm(x)) < 1e-3:
        x = np.array([0.0, 1.0, 0.0]) - normal * normal[1]
    x = x / np.linalg.norm(x)
    y = np.cross(normal, x)
    u, v = spread @ x, spread @ y
    m = sizes["margin"]
    lo_u, hi_u, lo_v, hi_v = u.min() - m, u.max() + m, v.min() - m, v.max() + m

    def at(a: float, b: float) -> np.ndarray:
        out: np.ndarray = middle + x * a + y * b
        return out

    d = sizes["sprue_diameter"]
    corners = [at(lo_u, lo_v), at(hi_u, lo_v), at(hi_u, hi_v), at(lo_u, hi_v)]
    out: list[tuple[str, TopoDS_Shape]] = []
    for a, b in zip(corners, corners[1:] + corners[:1], strict=True):
        rod = _rod(a, b, d)
        if rod is not None:
            out.append(("frame", rod))
        out.append(("frame", _ball(a, d)))
    for k, (p, pu, pv) in enumerate(zip(points, u, v, strict=True), start=1):
        gaps = {(lo_u, pv): pu - lo_u, (hi_u, pv): hi_u - pu, (pu, lo_v): pv - lo_v}
        gaps[(pu, hi_v)] = hi_v - pv
        side = min(gaps, key=lambda key: gaps[key])
        gate = _rod(p, at(*side), sizes["gate_diameter"])  # to the side, in the frame's plane
        if gate is not None:
            out.append((f"gate{k}", gate))
    return out


@register
class SprueTree(FeatureType):
    """Sprues from a pouring cup, or a kit frame, joined to the parts."""

    type_name = "sprue_tree"
    makes_solid = True
    params = (
        ParamSpec("layout", choices=LAYOUTS, default="tree", optional=True),
        ParamSpec("cup_diameter", kind=Kind.LENGTH, optional=True),
        ParamSpec("cup_height", kind=Kind.LENGTH, optional=True),
        ParamSpec("sprue_diameter", kind=Kind.LENGTH, optional=True),
        ParamSpec("gate_diameter", kind=Kind.LENGTH, optional=True),
        ParamSpec("margin", kind=Kind.LENGTH, optional=True),
    )

    def _pieces(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[list[tuple[str, TopoDS_Shape]], list[Issue]]:
        owner = feature.name
        points, issues = _points(feature, ctx, "feed_points")
        if not len(points):
            raise FeatureError(f"{owner}: pick the points where the parts are fed.")
        if len(points) > MOST_POINTS:
            raise FeatureError(f"{owner}: use at most {MOST_POINTS} points. Pick fewer.")
        sizes = {
            "cup_diameter": _value(feature, "cup_diameter", 12.0),
            "cup_height": _value(feature, "cup_height", 10.0),
            "sprue_diameter": _value(feature, "sprue_diameter", 4.0),
            "gate_diameter": _value(feature, "gate_diameter", 2.0),
            "margin": _value(feature, "margin", 5.0),
        }
        if any(v <= 0 for v in sizes.values()):
            raise FeatureError(f"{owner}: every size must be above zero. Enter larger values.")
        if sizes["cup_diameter"] <= sizes["sprue_diameter"]:
            raise FeatureError(
                f"{owner}: the cup must be wider than the sprue. Enter a larger cup diameter."
            )
        try:
            if feature.params.get("layout", "tree") == "kit_frame":
                return frame_pieces(points, sizes), issues
            cup, more = _points(feature, ctx, "cup")
            issues += more
            if not len(cup):
                raise FeatureError(f"{owner}: pick the point for the pouring cup.")
            return tree_pieces(cup[0], points, sizes), issues
        except ValueError as exc:
            raise FeatureError(f"{owner}: {exc}") from None

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Join the sprues to the part."""
        body = ctx.body
        if body is None:
            raise FeatureError(f"{feature.name}: the part is empty. Add the parts first.")
        pieces, issues = self._pieces(feature, ctx)
        # Through ``combine`` (D1055): the sprues join the bodies they reach, and those
        # only. A plain fuse with the whole part also joined bodies elsewhere that
        # shared a face (the two halves of a bar split for printing).
        from fdcad.core.features.solids import combine

        named = [(f"{feature.id}/{role}", f) for role, s in pieces for f in faces_of(s)]
        tool = NamedShape(compound([s for _role, s in pieces]), named)
        try:
            result = combine(feature.id, feature.name, body, tool, "boss", pieces=True)
        except FeatureError:
            raise FeatureError(
                f"{feature.name}: the sprues could not be joined. Use thinner sprues or move "
                "the points."
            ) from None
        issues += check_result(feature.id, feature.name, ctx.body, result, None)
        return FeatureResult(body=result, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The sprues, for the preview."""
        pieces, _issues = self._pieces(feature, ctx)
        return NamedShape(compound([s for _n, s in pieces]), [])
