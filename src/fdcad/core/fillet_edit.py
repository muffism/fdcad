"""Change existing fillets and drafts without opening them (TR132, DECISIONS D1404).

Pure functions on features: each returns an edited copy for one undoable command
(CLAUDE.md rule 3). No Qt.

1. One edge of a multi edge fillet: give it its own radius (``multiple_radius``
   with ``radius_<k>``), or take it out of the feature (later per edge values move
   up one place).
2. The part's constant fillets with their radius, filtered by a range, and a new
   radius for several at once.
3. The part's drafts with their angle and pull direction; a new angle.
"""

from __future__ import annotations

import copy
import math
import re
from dataclasses import dataclass

from fdcad.core.document.model import Document, Feature, Param


class EditError(ValueError):
    """The change cannot be made; the message says why and what to do."""


def fillet_face_owner(doc: Document, names: list[str]) -> tuple[str, str] | None:
    """``(fillet id, edge name)`` of a face named ``<fid>/fillet/<edge name>``, or None."""
    for name in names:
        match = re.fullmatch(r"(f\d+)/fillet/(.+?)(#\d+)?", name)
        if match is None:
            continue
        fid = match.group(1)
        try:
            feature = doc.feature(fid)
        except KeyError:
            continue
        if feature.type == "fillet":
            return fid, match.group(2)
    return None


def edge_index(feature: Feature, edge_name: str) -> int:
    """1 based place of ``edge_name`` in the fillet's picked edges, or 0."""
    from fdcad.core.features.modify import piece_base

    base = piece_base(edge_name)
    edges = feature.refs.get("edges", [])
    if not isinstance(edges, list):
        return 0
    for k, ref in enumerate(edges, start=1):
        if isinstance(ref, dict) and str(ref.get("name", "")) in (edge_name, base):
            return k
    return 0


def _picked(feature: Feature, edge_name: str) -> int:
    if feature.type != "fillet":
        raise EditError(f"{feature.name} is not a fillet. Pick a fillet face.")
    if feature.params.get("fillet_type", "constant") != "constant":
        raise EditError(
            f"{feature.name} is not a constant size fillet. Edit the feature to change it."
        )
    k = edge_index(feature, edge_name)
    if k == 0:
        raise EditError(
            f"This round comes from a face or feature picked in {feature.name}, not from a "
            "picked edge. Edit the feature to change it."
        )
    return k


def with_edge_radius(feature: Feature, edge_name: str, radius: Param) -> Feature:
    """The fillet with its own radius for one picked edge."""
    k = _picked(feature, edge_name)
    if radius.value <= 0:
        raise EditError("The radius must be above zero. Enter a larger radius.")
    out = copy.deepcopy(feature)
    out.params["multiple_radius"] = True
    out.params[f"radius_{k}"] = copy.deepcopy(radius)
    return out


def without_edge(feature: Feature, edge_name: str) -> Feature:
    """The fillet without one picked edge; later per edge values move up one place."""
    k = _picked(feature, edge_name)
    edges = list(feature.refs["edges"])
    others = [key for key in ("faces", "features", "auto_edges") if feature.refs.get(key)]
    if len(edges) == 1 and not others:
        raise EditError(
            f"{edge_name} is the only edge of {feature.name}. Delete the feature instead."
        )
    out = copy.deepcopy(feature)
    del out.refs["edges"][k - 1]
    if not out.refs["edges"]:
        del out.refs["edges"]
    moved: dict[str, object] = {}
    for name, value in list(out.params.items()):
        match = re.fullmatch(r"(radius|vr)_(\d+)(_.+)?", name)
        if match is None:
            continue
        index = int(match.group(2))
        del out.params[name]
        if index == k:
            continue
        new = index - 1 if index > k else index
        moved[f"{match.group(1)}_{new}{match.group(3) or ''}"] = value
    out.params.update(moved)  # type: ignore[arg-type]
    return out


@dataclass
class FilletRow:
    """One constant size fillet, for the Change Fillets list."""

    fid: str
    name: str
    radius: float  # mm
    text: str
    edges: int


def fillet_rows(
    doc: Document, low: float | None = None, high: float | None = None
) -> list[FilletRow]:
    """The part's constant size fillets, optionally only radii from ``low`` to ``high`` mm."""
    out: list[FilletRow] = []
    for feature in doc.features:
        if feature.type != "fillet" or feature.params.get("fillet_type", "constant") != "constant":
            continue
        radius = feature.params.get("radius")
        if not isinstance(radius, Param):
            continue
        if low is not None and radius.value < low - 1e-9:
            continue
        if high is not None and radius.value > high + 1e-9:
            continue
        edges = feature.refs.get("edges", [])
        count = len(edges) if isinstance(edges, list) else 0
        out.append(FilletRow(feature.id, feature.name, radius.value, radius.expr, count))
    return out


def with_radius(feature: Feature, radius: Param) -> Feature:
    """The fillet with a new main radius (per edge radii stay)."""
    if radius.value <= 0:
        raise EditError("The radius must be above zero. Enter a larger radius.")
    out = copy.deepcopy(feature)
    out.params["radius"] = copy.deepcopy(radius)
    return out


@dataclass
class DraftRow:
    """One draft, for the Change Drafts list."""

    fid: str
    name: str
    angle: float  # radians
    text: str
    pull: str  # the neutral plane or face, and "reversed"


def _pull(doc: Document, feature: Feature) -> str:
    ref = feature.refs.get("neutral")
    words = "none"
    if isinstance(ref, dict):
        if "feature" in ref:
            try:
                words = doc.feature(str(ref["feature"])).name
            except KeyError:
                words = str(ref["feature"])
        else:
            words = str(ref.get("name", "face"))
    if feature.params.get("reverse") is True:
        words += ", reversed"
    return words


def draft_rows(doc: Document) -> list[DraftRow]:
    """The part's draft features, sorted by pull direction and then angle."""
    out: list[DraftRow] = []
    for feature in doc.features:
        if feature.type != "draft":
            continue
        angle = feature.params.get("angle")
        if not isinstance(angle, Param):
            continue
        out.append(DraftRow(feature.id, feature.name, angle.value, angle.expr, _pull(doc, feature)))
    out.sort(key=lambda r: (r.pull, r.angle))
    return out


def with_angle(feature: Feature, angle: Param) -> Feature:
    """The draft with a new angle."""
    if not 0 < angle.value < math.pi / 2:
        raise EditError("The draft angle must be between 0 and 90 degrees. Enter another angle.")
    out = copy.deepcopy(feature)
    out.params["angle"] = copy.deepcopy(angle)
    return out
