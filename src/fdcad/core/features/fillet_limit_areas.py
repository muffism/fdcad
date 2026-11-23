"""Limit Failing Areas (TR271 item 1, D1802): round what works, leave the failing
stretch of an edge sharp.

When a picked edge cannot be rounded whole at its radius, the longest stretch of
it that can is looked for: stretches that keep one end of the edge (the failure
is often where the edge meets a short or steep neighbour) and stretches in the
middle, from long to short. Each trial rounds that stretch alone with the partial
edge routine (D519). The answer is offered as a fix button with action
``limit_failing`` (``data["parts"]``: ``[name, start percent, end percent]`` per
edge); clicking it keeps the other edges in the fillet and makes one Partial
Edges fillet for each failing edge after it, as one undo step (``limit_failing``).
Nothing changes until then (CLAUDE.md rule 12).
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import TYPE_CHECKING

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureError, Fix
from fdcad.core.naming.names import NamedShape

if TYPE_CHECKING:
    from fdcad.core.features.fillet import Item, RadiusLaw

ACTION = "limit_failing"
#: More failing edges than this are not searched: each trial is a kernel call.
MAX_FAILING = 4
#: Stretch lengths tried, in percent of the edge, longest first.
_LENGTHS = (95.0, 90.0, 80.0, 70.0, 60.0, 50.0, 35.0, 20.0)


def _stretches(length: float) -> list[tuple[float, float]]:
    """Ranges of ``length`` percent: keep the start, keep the end, centred."""
    middle = (100.0 - length) / 2
    return [(0.0, length), (100.0 - length, 100.0), (middle, 100.0 - middle)]


def _builds(
    feature: Feature, body: NamedShape, item: Item, radius: float, span: tuple[float, float]
) -> bool:
    from fdcad.core.features.fillet_partial import partial_fillet

    trial = copy.deepcopy(feature)
    trial.params["partial"] = "percent"
    trial.params["start_percent"] = Param(f"{span[0]:g}", span[0])
    trial.params["end_percent"] = Param(f"{span[1]:g}", span[1])
    trial.params.pop("partial_flip", None)
    try:
        partial_fillet(trial, body, [(item.name, item.edge)], lambda _n: radius)
    except (FeatureError, ValueError, RuntimeError):
        return False
    except Exception:  # kernel failure: this stretch does not build
        return False
    return True


def longest_stretch(
    feature: Feature, body: NamedShape, item: Item, radius: float
) -> tuple[float, float] | None:
    """The longest stretch (start and end percent) of ``item`` that rounds alone."""
    for size in _LENGTHS:
        for span in _stretches(size):
            if _builds(feature, body, item, radius, span):
                return span
    return None


def allowed(feature: Feature) -> bool:
    """True for fillets the partial routine can make: one constant radius law per edge,
    Radius method, circular profile, whole edges, tangent propagation on."""
    from fdcad.core.features.fillet_profile import built_here, method_of

    p = feature.params
    return (
        p.get("fillet_type", "constant") == "constant"
        and not p.get("partial")
        and not feature.refs.get("limit_plane")
        and p.get("tangent_propagation") is not False
        and method_of(feature) == "radius"
        and not built_here(feature)
    )


def limit_fix(
    feature: Feature,
    body: NamedShape,
    failing: list[Item],
    law_of: Callable[[Item], RadiusLaw],
) -> Fix | None:
    """The Limit Failing Areas button, or None when no failing edge has a stretch
    that builds (or the fillet is not one the partial routine can make)."""
    from fdcad.core.features.solids import solids

    if not failing or len(failing) > MAX_FAILING or not allowed(feature):
        return None
    if any(i.index == 0 for i in failing) or len(solids(body.shape)) != 1:
        return None
    picked = [r.get("name") for r in feature.refs.get("edges", []) if isinstance(r, dict)]
    if len(set(picked)) != len(picked):  # the new fillets pick edges by name (D1043)
        return None
    parts: list[list[object]] = []
    for item in failing:
        span = longest_stretch(feature, body, item, max(r for _u, r in law_of(item)))
        if span is None:
            return None
        parts.append([item.name, span[0], span[1]])
    count = len(parts)
    label = f"Limit failing areas (round {count} edge{'s' if count != 1 else ''} in part)"
    return Fix(label, ACTION, {"feature": feature.id, "parts": parts})


def limit_failing(doc: Document, fid: str, parts: list[list[object]]) -> list[Feature]:
    """The fillet without the failing edges, then one Partial Edges fillet per failing
    edge (percent ``start`` to ``end``). New fillets get new ids and the next free
    names, as for ``split_fillet``; the document is not changed. When every edge
    fails, the first edge's partial fillet takes the original's place."""
    from fdcad.core.features.fillet_help import split_fillet
    from fdcad.core.features.modify import piece_base

    original = doc.feature(fid)
    failing = [str(p[0]) for p in parts]
    picked = [str(r.get("name", "")) for r in original.refs.get("edges", []) if isinstance(r, dict)]
    rest = [n for n in picked if n not in failing and piece_base(n) not in failing]
    groups = ([rest] if rest else []) + [[n] for n in failing]
    made = split_fillet(doc, fid, groups)
    spans = {str(p[0]): (float(str(p[1])), float(str(p[2]))) for p in parts}
    for feature in made[1 if rest else 0 :]:
        name = str(feature.refs["edges"][0].get("name", ""))
        start, end = spans.get(name) or spans[piece_base(name)]
        feature.params["partial"] = "percent"
        feature.params["start_percent"] = Param(f"{start:g}", start)
        feature.params["end_percent"] = Param(f"{end:g}", end)
        feature.params.pop("partial_flip", None)
    return made
