"""Explain a relation in words (TUTORIAL_REVIEW_SPEC_2 TR237, DECISIONS D920). No Qt."""

from __future__ import annotations

from fdcad.core.sketch.model import (
    Arc,
    Circle,
    Ellipse,
    EllipseArc,
    Line,
    Point,
    Relation,
    Sketch,
    Spline,
)

_KINDS = (
    (Point, "point"),
    (Line, "line"),
    (Circle, "circle"),
    (Arc, "arc"),
    (EllipseArc, "elliptical arc"),
    (Ellipse, "ellipse"),
    (Spline, "spline"),
)


def item_name(sketch: Sketch, eid: str) -> str:
    """ "line e4", or "missing item e4" for one that is gone."""
    entity = sketch.entities.get(eid)
    for kind, word in _KINDS:
        if isinstance(entity, kind):
            return f"{word} {eid}"
    return f"missing item {eid}"


def _join(names: list[str]) -> str:
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def explain(sketch: Sketch, relation: Relation) -> str:
    """One or two sentences saying what ``relation`` holds and which items it links."""
    names = [item_name(sketch, e) for e in relation.entities]
    a = names[0] if names else "the item"
    b = names[1] if len(names) > 1 else "the other item"
    both = _join(names)
    t = relation.type
    value = relation.value
    text = {
        "horizontal": f"Keeps {both} level with the sketch X axis"
        + (" (the points at the same height)." if len(names) > 1 else "."),
        "vertical": f"Keeps {both} upright along the sketch Y axis"
        + (" (the points one above the other)." if len(names) > 1 else "."),
        "coincident": f"Holds {a} on {b}: they stay at the same place.",
        "collinear": f"Keeps {both} on one straight line.",
        "parallel": f"Keeps {both} pointing the same way.",
        "perpendicular": f"Keeps {a} at a right angle to {b}.",
        "tangent": f"Keeps {a} touching {b} smoothly, without a corner where they meet.",
        "concentric": f"Keeps {both} on the same centre.",
        "equal": f"Keeps {both} the same size: equal lengths for lines, equal radii for "
        "circles and arcs.",
        "midpoint": f"Holds {a} at the middle of {b}.",
        "on_segment": f"Keeps {a} on {b}, between its two ends.",  # TR342
        "symmetric": f"Keeps {_join(names[:2])} mirror images of each other about "
        f"{names[2] if len(names) > 2 else 'the line'}.",
        "coradial": f"Keeps {both} on the same centre with the same radius.",
        "intersection": f"Holds {a} where {_join(names[1:])} cross.",
        "fixed": f"Fixes {both} where it is now, so dragging and other relations cannot move it.",
        "offset": f"Keeps {b} a set distance from {a}"
        + (f" ({value:g} mm)." if value is not None else ", set by a dimension."),
        "length_ratio": f"Keeps the length of {a} at {value:g} times the length of {b}."
        if value is not None
        else f"Keeps the lengths of {a} and {b} in a set ratio.",
        "length_difference": f"Keeps {a} {value:g} mm longer than {b}."
        if value is not None
        else f"Keeps a set difference between the lengths of {a} and {b}.",
        "equal_angle": f"Keeps the angle between {_join(names[:2])} equal to the angle "
        f"between {_join(names[2:4])}.",
        "equal_distance": f"Keeps the distance between {_join(names[:2])} equal to the "
        f"distance between {_join(names[2:4])}.",
    }.get(t, f"A {t.replace('_', ' ')} relation between {both}.")
    if any(e not in sketch.entities for e in relation.entities):
        text += " An item it links is gone, so it holds nothing; delete it or pick a new item."
    if relation.off:
        text += " It is switched off, so it does nothing until you turn it on."
    return text
