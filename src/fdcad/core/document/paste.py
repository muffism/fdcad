"""Copy a sketch, or a feature with its sketch, and paste it onto another plane or
face (TUTORIAL_REVIEW_SPEC TR3.2, TR9, DECISIONS D685).

A copied sketch becomes a new sketch on the picked plane or face, with the same
entity ids, so references into it (a revolve axis, hole points) still work in
the pasted feature. Part geometry links cannot carry over (``unlink_model``).
Pure Python, no Qt: the caller pushes the features as one undo step.
"""

from __future__ import annotations

import copy as _copy
import math
from dataclasses import dataclass, field
from typing import Any

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.names import default_name
from fdcad.core.sketch.model import sketch_from_data
from fdcad.core.sketch.ops.clipboard import model_links, unlink_model
from fdcad.core.units import Kind

#: Keys of a sketch feature's data that hold the sketch itself.
SKETCH_KEYS = (
    "next_entity",
    "entities",
    "relations",
    "dimensions",
    "pictures",
    "texts",
    "layers",
    "layer_of",
    "keep_sides",
)


class PasteError(ValueError):
    """The copied item cannot be pasted; the message says why and what to do."""


@dataclass
class Pasted:
    """The new features, in tree order (sketch first), and what was dropped."""

    features: list[Feature] = field(default_factory=list)
    #: Relations and dimensions to part geometry that were removed.
    removed: int = 0
    #: Face, edge and feature picks cleared because the copy came from another part.
    cleared: list[str] = field(default_factory=list)
    #: Formulas turned into their values for the same reason.
    frozen: int = 0


def sketch_of(doc: Document, feature: Feature) -> Feature | None:
    """The sketch a feature is made from (its ``sketch`` reference), or None."""
    ref = feature.refs.get("sketch")
    if isinstance(ref, dict) and isinstance(ref.get("feature"), str):
        try:
            sketch = doc.feature(ref["feature"])
        except KeyError:
            return None
        return sketch if sketch.type == "sketch" else None
    return None


def link_count(sketch: Feature) -> int:
    """How many part geometry copies a sketch has (TR9.2 asks what to do with them)."""
    try:
        return len(model_links(sketch_from_data(sketch.data)))
    except ValueError:
        return 0


def _new_sketch(
    doc: Document, source: Feature, plane: dict[str, Any], keep: bool
) -> tuple[Feature, int]:
    try:
        unlinked = unlink_model(source.data, keep=keep)
    except (ValueError, KeyError, TypeError) as exc:
        raise PasteError("The copied sketch is damaged. Copy it again.") from exc
    data = {k: _copy.deepcopy(v) for k, v in source.data.items() if k not in SKETCH_KEYS}
    data.update(unlinked.data)
    sketch = Feature(
        doc.new_feature_id(),
        "sketch",
        default_name(doc, "sketch"),
        refs={"plane": _copy.deepcopy(plane)},
        data=data,
    )
    return sketch, unlinked.removed


def paste_sketch(
    doc: Document,
    source: Feature,
    plane: dict[str, Any],
    keep_links: bool = False,
    other_part: bool = False,
) -> Pasted:
    """A new sketch on ``plane`` (a plane feature or a face reference) with the
    entities and dimensions of ``source``. From ``other_part`` its formulas become
    their values and part links are not kept (D708)."""
    if source.type != "sketch":
        raise PasteError("Only a sketch can be pasted onto a plane. Copy a sketch first.")
    sketch, removed = _new_sketch(doc, source, plane, keep_links and not other_part)
    frozen = freeze_formulas(sketch) if other_part else 0
    return Pasted([sketch], removed, frozen=frozen)


def centre_on(sketch: Feature, at: tuple[float, float]) -> int:
    """Move a pasted sketch so the middle of its geometry is at ``at`` (sketch mm).

    The origin stays; relations and dimensions to it are removed, since they would
    pull the geometry back. Returns how many were removed.
    """
    from fdcad.core.sketch.model import Point, sketch_to_data
    from fdcad.core.sketch.ops.pieces import _origin

    sk = sketch_from_data(sketch.data)
    origins = {e for e in sk.entities if _origin(sk, e)}
    points = [e for e in sk.entities.values() if isinstance(e, Point) and e.id not in origins]
    if not points:
        return 0
    xs, ys = [p.x for p in points], [p.y for p in points]
    dx = at[0] - (min(xs) + max(xs)) / 2
    dy = at[1] - (min(ys) + max(ys)) / 2
    for p in points:
        p.x, p.y = p.x + dx, p.y + dy
    before = len(sk.relations) + len(sk.dimensions)
    sk.relations = [
        r for r in sk.relations if not (set(r.entities) & origins) or set(r.entities) <= origins
    ]
    sk.dimensions = [d for d in sk.dimensions if not set(d.entities) & origins]
    removed = before - len(sk.relations) - len(sk.dimensions)
    sketch.data.update(sketch_to_data(sk))
    return removed


def face_centre(plane_ref: dict[str, Any]) -> tuple[float, float, float] | None:
    """The middle of a face reference (its stored centre of mass), or None for a plane."""
    snap = plane_ref.get("snapshot") if plane_ref.get("kind") == "face" else None
    point = snap.get("point") if isinstance(snap, dict) else None
    if isinstance(point, list) and len(point) == 3:
        return float(point[0]), float(point[1]), float(point[2])
    return None


def _value_text(value: float, kind: Kind | None) -> str:
    if kind is Kind.LENGTH:
        return f"{value:.12g}mm"
    if kind is Kind.ANGLE:
        return f"{math.degrees(value):.12g}deg"
    return f"{value:.12g}"


def _freeze(param: Any, kind: Kind | None) -> Any | None:
    """A formula Param (or stored ``{"expr", "value"}``) as its value, else None."""
    if isinstance(param, Param) and param.expr.strip().startswith("="):
        return Param(_value_text(param.value, kind), param.value)
    if isinstance(param, dict) and str(param.get("expr", "")).strip().startswith("="):
        value = float(param.get("value", 0.0))
        return {**param, "expr": _value_text(value, kind)}
    return None


def freeze_formulas(feature: Feature) -> int:
    """Turn every formula of ``feature`` (values, sketch dimensions, suppression) into
    its value, so names in it cannot pick up other things in another part (D708).
    Returns how many were changed."""
    from fdcad.core.equations.engine import _param_kind, dimension_kind

    count = 0
    for name, value in list(feature.params.items()):
        frozen = _freeze(value, _param_kind(feature, name))
        if frozen is not None:
            feature.params[name] = frozen
            count += 1
    dims = feature.data.get("dimensions", []) if feature.type == "sketch" else []
    for dim in dims:
        if isinstance(dim, dict):
            frozen = _freeze(dim.get("param"), dimension_kind(str(dim.get("type"))))
            if frozen is not None:
                dim["param"] = frozen
                count += 1
    rule = feature.data.get("suppression")
    if isinstance(rule, str) and rule.strip():
        del feature.data["suppression"]
        count += 1
    return count


def _follow_sketch(value: Any, old: str, new: str, keep_others: bool) -> tuple[Any, bool]:
    """``value`` (a reference, or a list of them) with references into sketch ``old``
    moved to ``new``. Without ``keep_others`` other references are dropped; the flag
    says whether anything was dropped."""
    if isinstance(value, list):
        out, dropped = [], False
        for item in value:
            kept, gone = _follow_sketch(item, old, new, keep_others)
            dropped = dropped or gone
            if kept is not None:
                out.append(kept)
        return out, dropped
    if isinstance(value, dict) and value.get("feature") == old:
        return {**value, "feature": new}, False
    if keep_others:
        return value, False
    return None, True


def paste_feature(
    doc: Document,
    source: Feature,
    source_sketch: Feature,
    plane: dict[str, Any],
    keep_links: bool = False,
    centre: tuple[float, float] | None = None,
    other_part: bool = False,
) -> Pasted:
    """A copy of ``source`` with the same values, made from a copy of its sketch on
    ``plane``. References into its sketch (an axis line, hole points) follow the new
    sketch. Its other references (faces, edges) are kept when pasting into the same
    part.

    From ``other_part`` they would name unrelated faces of this part, so they are
    cleared, part links are not kept, and formulas become their values (D708).

    With ``centre`` (sketch mm, the middle of the picked face) and part links not
    kept, the copy is centred there, so it lands on the face (D685).
    """
    if source.type == "sketch":
        return paste_sketch(doc, source, plane, keep_links, other_part)
    keep_links = keep_links and not other_part
    sketch, removed = _new_sketch(doc, source_sketch, plane, keep_links)
    if centre is not None and not keep_links:
        removed += centre_on(sketch, centre)
    feature = _copy.deepcopy(source)
    feature.id = doc.new_feature_id()
    operation = feature.params.get("operation", "boss")
    feature.name = default_name(doc, feature.type, str(operation))
    feature.suppressed = False
    cleared: list[str] = []
    for key in list(feature.refs):
        if key == "sketch":
            continue
        kept, dropped = _follow_sketch(
            feature.refs[key], source_sketch.id, sketch.id, not other_part
        )
        if dropped:
            cleared.append(key)
        if kept is None or kept == []:
            del feature.refs[key]
        else:
            feature.refs[key] = kept
    feature.refs["sketch"] = {"feature": sketch.id}
    frozen = 0
    if other_part:
        frozen = freeze_formulas(feature) + freeze_formulas(sketch)
    return Pasted([sketch, feature], removed, cleared, frozen)


__all__ = [
    "PasteError",
    "Pasted",
    "centre_on",
    "face_centre",
    "freeze_formulas",
    "link_count",
    "paste_feature",
    "paste_sketch",
    "sketch_of",
]
