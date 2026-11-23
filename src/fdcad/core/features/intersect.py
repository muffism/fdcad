"""Intersect: regions where bodies and planes overlap (PHASE3_SPEC P3.4 item 2, DECISIONS D233).

Params:
- ``regions``: "overlap" (default), "internal" or "both". Overlap regions lie
  inside two or more picked bodies (inside one when it is cut only by planes);
  internal regions are closed spaces inside none of them.
- ``merge``: boolean (default true): touching kept regions become one body.
- ``cap``: optional boolean (Cap flat openings). Kept for open surface bodies;
  every body is a closed solid so far, so it changes nothing yet.

Refs: ``bodies`` (face references to faces of the bodies) and optional
``planes`` (planes or flat faces, treated as endless).

Key ``exclude``: region numbers (from 1, ordered by centre X, then Y, then Z)
the user excluded in the region list.

The picked bodies are replaced by the kept regions; other bodies stay.
Face roles: ``region<k>/face#j``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from OCP.BOPAlgo import BOPAlgo_MakerVolume
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.bodies import body_indices, join, rest_of
from fdcad.core.features.booleans import boolean_shape, result_shape
from fdcad.core.features.geometry_refs import resolve_placement
from fdcad.core.features.solids import (
    FUZZY_TOLERANCE,
    _unify,
    bounding_size,
    compound,
    solids,
    volume_of,
)
from fdcad.core.naming.names import NamedShape, centroid, faces_of, order_by_position, restrict
from fdcad.core.occ import ShapeList

_TINY = 1e-6


def endless_plane(
    point: tuple[float, float, float],
    normal: tuple[float, float, float],
    size: float,
    over: Sequence[TopoDS_Shape] = (),
) -> TopoDS_Shape:
    """A square face on the plane, ``size`` mm across, to stand for the whole plane.

    It is centred on ``point``, or with ``over`` on the point of the plane nearest
    the middle of those shapes (D1062). A reference plane keeps its origin where it
    was made, often near the part's origin; a body 280 mm from there was not reached
    by a sheet sized for the body and centred on the plane's origin, and Split said
    "the tools do not cut through any body".
    """
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.gp import gp_Dir, gp_Pln, gp_Pnt

    centre = point
    if over:
        box = Bnd_Box()
        for shape in over:
            BRepBndLib.Add_s(shape, box)
        if not box.IsVoid():
            lo, hi = box.CornerMin(), box.CornerMax()
            mid = ((lo.X() + hi.X()) / 2, (lo.Y() + hi.Y()) / 2, (lo.Z() + hi.Z()) / 2)
            length = sum(n * n for n in normal) ** 0.5 or 1.0
            n = tuple(v / length for v in normal)
            off = sum((m - p) * v for m, p, v in zip(mid, point, n, strict=True))
            centre = (mid[0] - off * n[0], mid[1] - off * n[1], mid[2] - off * n[2])
    half = size / 2
    return BRepBuilderAPI_MakeFace(
        gp_Pln(gp_Pnt(*centre), gp_Dir(*normal)), -half, half, -half, half
    ).Face()


def regions_of(
    feature: Feature, ctx: BuildContext
) -> tuple[list[TopoDS_Shape], list[int], list[int], list[Any]]:
    """Every region ordered by position, with how many picked bodies hold each,
    the picked body indices and warnings."""
    name = feature.name
    assert ctx.body is not None
    indices, issues = body_indices(ctx, feature.refs.get("bodies"), name)
    picked = [solids(ctx.body.shape)[i] for i in indices]
    size = bounding_size(*picked) * 4 + 10
    args = ShapeList()
    for s in picked:
        args.Append(s)
    planes = feature.refs.get("planes") or []
    for ref in planes:
        place = resolve_placement(ctx, ref, name, "plane")
        issues += place.issues
        args.Append(endless_plane(place.point, place.direction, size, picked))
    if len(picked) < 2 and not planes:
        raise FeatureError(f"{name}: pick two or more bodies, or a body and a plane.")
    maker = BOPAlgo_MakerVolume()
    maker.SetArguments(args)
    maker.SetFuzzyValue(FUZZY_TOLERANCE)
    maker.SetRunParallel(True)
    maker.SetNonDestructive(True)  # the bodies are not changed (D1067)
    maker.SetIntersect(True)
    try:
        maker.Perform()
        ok = not maker.HasErrors()
    except Exception:
        ok = False
    if not ok:
        raise FeatureError(
            f"{name} failed: the kernel could not find the regions. "
            "Move a body slightly so faces do not almost touch."
        )
    made = result_shape(maker)
    if made is None:
        raise FeatureError(f"{name} failed: the kernel found no regions. Move a body slightly.")
    found = [r for r in solids(made) if volume_of(r) > _TINY]
    ordered = _order(found)
    depth = []
    for region in ordered:
        size_r = volume_of(region)
        inside = 0
        for s in picked:
            common = boolean_shape("common", region, s)
            if common is not None and volume_of(common) > size_r * 0.5:
                inside += 1
        depth.append(inside)
    return ordered, depth, indices, issues


def _order(shapes: list[TopoDS_Shape]) -> list[TopoDS_Shape]:
    keyed = sorted(shapes, key=lambda s: tuple(round(v, 6) for v in centroid(s)))
    return keyed


def wanted(feature: Feature, depth: list[int], single: bool) -> list[int]:
    """Region numbers (from 0) of the kind the feature keeps, before exclusions."""
    kind = feature.params.get("regions", "overlap")
    need = 1 if single else 2
    out = []
    for k, d in enumerate(depth):
        overlap = d >= need
        internal = d == 0
        if (kind in ("overlap", "both") and overlap) or (kind in ("internal", "both") and internal):
            out.append(k)
    return out


@register
class Intersect(FeatureType):
    """Makes bodies from the regions where bodies and planes overlap or enclose space."""

    type_name = "intersect"
    makes_solid = True
    params = (
        ParamSpec("regions", choices=("overlap", "internal", "both"), default="overlap"),
        ParamSpec("merge", default=True, optional=True),
        ParamSpec("cap", default=False, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Build the kept regions."""
        body, issues = self._build(feature, ctx)
        return FeatureResult(body=body, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The part with the kept regions, for the live preview."""
        return self._build(feature, ctx)[0]

    def _build(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part has no bodies. Add a body first.")
        regions, depth, indices, issues = regions_of(feature, ctx)
        single = len(indices) == 1
        exclude = {k - 1 for k in feature.data.get("exclude", []) if isinstance(k, int)}
        found = wanted(feature, depth, single)
        if not found:
            kind = str(feature.params.get("regions", "overlap"))
            raise FeatureError(f"{name}: {_NONE_FOUND.get(kind, _NONE_FOUND['overlap'])}")
        keep = [k for k in found if k not in exclude]
        if not keep:
            raise FeatureError(
                f"{name}: no region is left. Include a region in the list or choose other regions."
            )
        names = []
        shapes = []
        for k in keep:
            region = regions[k]
            shapes.append(region)
            for j, face in enumerate(order_by_position(faces_of(region)), start=1):
                names.append((f"{feature.id}/region{k + 1}/face#{j}", face))
        shape = shapes[0] if len(shapes) == 1 else compound(shapes)
        kept = NamedShape(shape, restrict(names, shape, feature.id))
        if feature.params.get("merge", True) is not False and len(shapes) > 1:
            from fdcad.core.features.booleans import boolean_named

            merged = NamedShape(shapes[0], [(n, f) for n, f in names if _on(shapes[0], f)])
            for region in shapes[1:]:
                part = NamedShape(region, [(n, f) for n, f in names if _on(region, f)])
                merged = boolean_named("fuse", merged, part, feature.id, name, unify=False)
            kept = _unify(merged, feature.id)
        result = join([rest_of(ctx.body, indices, feature.id), kept], feature.id)
        assert result is not None
        return result, issues


#: What to say when no region of the chosen kind exists, before any is excluded.
_NONE_FOUND = {
    "overlap": "the picked bodies do not overlap. Pick bodies that overlap, or a body and a "
    "plane that cuts it.",
    "internal": "the picked bodies enclose no closed space. Choose Overlap regions or "
    "pick bodies that close a space.",
    "both": "the picked bodies neither overlap nor enclose a closed space. Pick bodies "
    "that overlap, or a body and a plane that cuts it.",
}


def _on(shape: TopoDS_Shape, face: TopoDS_Shape) -> bool:
    from fdcad.core.features.bodies import solid_of_face

    return solid_of_face(shape, face) >= 0
