"""Move a feature to another body (TR155, D2107).

In a part with several bodies, a feature that has the Bodies box (TR33, D697) can
be moved so it acts on one other body: its ``bodies_scope`` becomes "selected" and
``refs.bodies`` names one face of the chosen body, found in the part as it is just
before the feature. Its sketch stays where it is, so the feature keeps its place and
shape and only the body it cuts or joins changes. No Qt; kernel calls are small
topology queries.
"""

from __future__ import annotations

import copy
from typing import Any

from fdcad.core.document.model import Document, Feature

#: Feature types with a Bodies box (the property panel's list).
TYPES = ("extrude", "revolve", "sweep", "loft", "hole")


class MoveToBodyError(ValueError):
    """The feature cannot be moved. The message says what to do."""


def bodies_before(doc: Document, feature: Feature, results: Any) -> Any:
    """The part just before ``feature`` (a NamedShape), or None."""
    from fdcad.core.features.preview import body_before

    return body_before(doc, feature, results) if results is not None else None


def current_body(doc: Document, feature: Feature, results: Any) -> int | None:
    """The body the feature acts on now, when it acts on exactly one picked body."""
    from fdcad.core.features.base import BuildContext, FeatureError
    from fdcad.core.features.bodies import body_indices

    if feature.params.get("bodies_scope") != "selected":
        return None
    body = bodies_before(doc, feature, results)
    if body is None:
        return None
    ctx = BuildContext(doc, body, dict(results or {}))
    try:
        indices, _issues = body_indices(ctx, feature.refs.get("bodies"), feature.name)
    except FeatureError:
        return None
    return indices[0] if len(indices) == 1 else None


def moved(doc: Document, feature: Feature, results: Any, index: int) -> Feature:
    """A copy of ``feature`` that acts on body ``index`` (from 0) only. Raises
    MoveToBodyError."""
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer

    from fdcad.core.features.solids import solids
    from fdcad.core.naming.select import reference_for

    if feature.type not in TYPES:
        raise MoveToBodyError(
            f"{feature.name} does not choose bodies. Use it on a cut, boss or hole instead."
        )
    body = bodies_before(doc, feature, results)
    pieces = solids(body.shape) if body is not None else []
    if len(pieces) < 2:
        raise MoveToBodyError(
            f"The part has one body before {feature.name}. Add another body first."
        )
    if not 0 <= index < len(pieces):
        raise MoveToBodyError(f"There is no body {index + 1}. Pick one of the bodies listed.")
    ref = reference_for(body, TopExp_Explorer(pieces[index], TopAbs_FACE).Current())
    if ref is None:
        raise MoveToBodyError(
            f"Body {index + 1} has no lasting face name to keep. Rebuild the part and try again."
        )
    out = copy.deepcopy(feature)
    out.params["bodies_scope"] = "selected"
    out.refs["bodies"] = [ref]
    return out
