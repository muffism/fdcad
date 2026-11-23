"""Instance markers of a pattern in the view (TR59 item 4, D2400).

While a pattern of numbered copies is open in the property panel, the view shows
a small numbered marker on each copy, the seed left out. Clicking a marker starts
an entry for that copy in Copy values (D1900). This module finds where the markers
sit: the middle of the seed (the faces its seed features made, or the picked seed
faces or bodies) moved by each copy's transform. No Qt; runs on the preview worker.
"""

from __future__ import annotations

from typing import Any

from OCP.BRep import BRep_Builder
from OCP.gp import gp_Pnt
from OCP.TopoDS import TopoDS_Compound

from fdcad.core.document.model import Feature
from fdcad.core.features.base import BuildContext
from fdcad.core.features.pattern_explode import EXPLODE_TYPES, only
from fdcad.core.features.preview_anchor import box_centre

Vec3 = tuple[float, float, float]
#: More copies than this show no markers: they would only cover the part.
MAX_MARKERS = 200


def instance_label(index: tuple[int, int]) -> str:
    """The instance number as the user types it: ``3`` or ``2.2``."""
    return str(index[0]) if index[1] == 1 else f"{index[0]}.{index[1]}"


def parse_label(text: str) -> tuple[int, int] | None:
    """The instance index of a label such as ``3`` or ``2.2``, or None."""
    head, _dot, tail = text.partition(".")
    if not head.isdigit() or (tail and not tail.isdigit()):
        return None
    return int(head), int(tail or 1)


def _seed_names(feature: Feature) -> tuple[list[str], list[str]]:
    """Face name prefixes of the seed features, and the picked face or body names."""
    prefixes: list[str] = []
    names: list[str] = []
    for key in ("features", "faces", "bodies"):
        items = feature.refs.get(key)
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            if key == "features" and isinstance(item.get("feature"), str):
                prefixes.append(f"{item['feature']}/")
            elif isinstance(item.get("name"), str):
                names.append(item["name"])
    return prefixes, names


def seed_point(feature: Feature, ctx: BuildContext) -> Vec3 | None:
    """The middle of the pattern's seed in the part before the pattern, or None."""
    body = ctx.body
    if body is None:
        return None
    prefixes, names = _seed_names(feature)
    shapes: list[Any] = [
        f for n, f in body.faces if any(n.startswith(p) for p in prefixes) or n in names
    ]
    if feature.refs.get("bodies"):
        from fdcad.core.features.bodies import body_indices
        from fdcad.core.features.solids import solids

        every = solids(body.shape)
        indices, _issues = body_indices(ctx, feature.refs["bodies"], feature.name)
        shapes += [every[i] for i in indices if 0 <= i < len(every)]
    if not shapes:
        return None
    builder = BRep_Builder()
    comp = TopoDS_Compound()
    builder.MakeCompound(comp)
    for shape in shapes:
        builder.Add(comp, shape)
    return box_centre(comp)


def instance_markers(feature: Feature, ctx: BuildContext) -> list[tuple[str, Vec3]]:
    """Each copy's instance number and marker point, skipped copies included, the seed
    left out. Empty for features that are not patterns of numbered copies, for an
    exploded copy, or when the seed cannot be found. Never raises."""
    if feature.type not in EXPLODE_TYPES or only(feature) is not None:
        return []
    from fdcad.core.features import REGISTRY

    ftype: Any = REGISTRY.get(feature.type)
    if ftype is None or not hasattr(ftype, "placements"):
        return []
    try:
        point = seed_point(feature, ctx)
        if point is None:
            return []
        placements, _issues = ftype.placements(feature, ctx)
    except Exception:  # a failing pattern simply shows no markers
        return []
    if len(placements) > MAX_MARKERS:
        return []
    out: list[tuple[str, Vec3]] = []
    for placement in placements:
        moved = gp_Pnt(*point).Transformed(placement.trsf)
        out.append((instance_label(placement.index), (moved.X(), moved.Y(), moved.Z())))
    return out
