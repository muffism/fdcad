"""Patterns of reference geometry (TR142 item 1, D2402).

A Linear or Circular Pattern whose one seed is a reference plane, axis, point or
coordinate system copies that datum to every placement instead of adding material.
The part is left as it is. The copies are listed in the result's ``extras["datums"]``
as ``(instance label, Datum)`` pairs and drawn in the view. Explode Pattern (D1902)
turns each copy into its own feature whose result carries that one datum (and plane),
so later features can pick it like any reference feature. No Qt.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from OCP.gp import gp_Dir, gp_Pnt, gp_Trsf

from fdcad.core.document.model import Feature
from fdcad.core.features.base import BuildContext, Datum, FeatureError, FeatureResult, Issue
from fdcad.core.features.datum import REFERENCE_TYPES, plane_at
from fdcad.core.features.pattern_markers import instance_label
from fdcad.core.features.patterns import Placement, skipped

Vec3 = tuple[float, float, float]
#: Pattern types that copy reference geometry.
DATUM_PATTERN_TYPES = ("linear_pattern", "circular_pattern")


def _seed_ids(feature: Feature) -> list[str]:
    refs = feature.refs.get("features")
    items = refs if isinstance(refs, list) else []
    return [
        r["feature"] for r in items if isinstance(r, dict) and isinstance(r.get("feature"), str)
    ]


def datum_seed(feature: Feature, ctx: BuildContext) -> Datum | None:
    """The datum the pattern copies, or None when its seeds are not reference geometry.
    Raises FeatureError when a reference feature is mixed with other seeds."""
    if feature.type not in DATUM_PATTERN_TYPES:
        return None
    ids = _seed_ids(feature)
    kinds = []
    for fid in ids:
        try:
            kinds.append(ctx.document.feature(fid).type in REFERENCE_TYPES)
        except KeyError:
            kinds.append(False)
    if not any(kinds):
        return None
    if len(ids) > 1 or feature.refs.get("faces") or feature.refs.get("bodies"):
        raise FeatureError(
            f"{feature.name}: a pattern copies one plane, axis, point or coordinate system "
            "on its own. Remove the other items to copy, or make a second pattern."
        )
    result = ctx.result(ids[0])
    if result.datum is not None:
        return result.datum
    plane = result.plane
    if plane is None:
        raise FeatureError(f"{feature.name}: the reference has no geometry yet. Fix it first.")
    return Datum("plane", plane.origin, plane.normal, plane.x_dir)


def _point(p: Vec3, trsf: gp_Trsf) -> Vec3:
    q = gp_Pnt(*p).Transformed(trsf)
    return q.X(), q.Y(), q.Z()


def _dir(d: Vec3 | None, trsf: gp_Trsf) -> Vec3 | None:
    if d is None:
        return None
    q = gp_Dir(*d).Transformed(trsf)
    return q.X(), q.Y(), q.Z()


def moved_datum(datum: Datum, trsf: gp_Trsf) -> Datum:
    """``datum`` moved by ``trsf``."""
    return Datum(
        datum.kind,
        _point(datum.origin, trsf),
        _dir(datum.direction, trsf),
        _dir(datum.x_dir, trsf),
        datum.size,
    )


def datum_result(
    feature: Feature, ctx: BuildContext, seed: Datum, placements: Sequence[Placement]
) -> FeatureResult:
    """The result of a pattern of ``seed``: the part unchanged and one datum per copy
    (skipped copies left out). An exploded copy carries its datum as its own."""
    from fdcad.core.features.pattern_explode import only

    skip = skipped(feature)
    copies = [(p.index, moved_datum(seed, p.trsf)) for p in placements if p.index not in skip]
    kept = only(feature)
    issues: list[Issue] = []
    if kept is not None:
        copies = [c for c in copies if c[0] == kept]
        if not copies:
            from fdcad.core.features.base import FeatureState

            why = (
                f"{feature.name}: the pattern values no longer make copy "
                f"{instance_label(kept)}. Raise the count, or delete this copy."
            )
            return FeatureResult(ctx.body, [Issue(FeatureState.WARNING, why, code="copy_gone")])
    extras = {"datums": [(instance_label(i), d) for i, d in copies]}
    if kept is None:
        return FeatureResult(ctx.body, issues, extras=extras)
    datum = copies[0][1]
    plane = None
    if datum.kind == "plane" and datum.direction is not None:
        plane = plane_at(datum.origin, datum.direction, datum.x_dir)
    return FeatureResult(ctx.body, issues, plane=plane, datum=datum, extras=extras)


def copy_shape(datum: Datum, half: float) -> Any:
    """Edges that draw one copied datum: a square outline for a plane (planes have no
    edges in ``datum_shape``), else the datum's own lines."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon

    from fdcad.core.features.datum import datum_shape

    if datum.kind != "plane" or datum.direction is None:
        return datum_shape(datum, half)
    plane = plane_at(datum.origin, datum.direction, datum.x_dir)
    poly = BRepBuilderAPI_MakePolygon()
    for u, v in ((-half, -half), (half, -half), (half, half), (-half, half)):
        poly.Add(plane.to_3d(u, v))
    poly.Close()
    return poly.Wire()


def datum_preview(
    feature: Feature, ctx: BuildContext, seed: Datum, placements: Sequence[Placement]
) -> Any:
    """The live preview of a pattern of reference geometry: the copies' outlines."""
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    from fdcad.core.features.solids import bounding_size

    result = datum_result(feature, ctx, seed, placements)
    half = 0.5 * bounding_size(ctx.body.shape) if ctx.body is not None else 20.0
    builder = BRep_Builder()
    comp = TopoDS_Compound()
    builder.MakeCompound(comp)
    for _label, datum in result.extras.get("datums", []):
        builder.Add(comp, copy_shape(datum, max(half, 5.0)))
    return comp
