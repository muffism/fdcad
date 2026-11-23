"""Sketch layers (TR389, D982).

Named sets of a sketch's curves, each with its own colour, line style and
visibility. The layers are display and picking only: the sketch is still solved
as one, and a hidden layer's curves still count in profiles. No Qt.
"""

from __future__ import annotations

from typing import Any

from fdcad.core.sketch.model import Point, Sketch

STYLES = ("solid", "dashed")


class LayerError(ValueError):
    """The layer change cannot be made; the message says what to do."""


def find(sketch: Sketch, name: str) -> dict[str, Any] | None:
    """The layer called ``name``, or None."""
    return next((layer for layer in sketch.layers if layer.get("name") == name), None)


def add_layer(sketch: Sketch, name: str, colour: str = "", style: str = "solid") -> dict[str, Any]:
    """A new layer, shown. Raises when the name is empty or taken."""
    name = name.strip()
    if not name:
        raise LayerError("A layer needs a name. Type a name.")
    if find(sketch, name) is not None:
        raise LayerError(f"There is a layer called {name} already. Type another name.")
    layer = {
        "name": name,
        "colour": colour,
        "style": style if style in STYLES else "solid",
        "visible": True,
    }
    sketch.layers.append(layer)
    return layer


def put_on(sketch: Sketch, ids: list[str], name: str | None) -> int:
    """Put the curves among ``ids`` on layer ``name`` (None takes them off any layer).
    Points follow their curves and are not put on layers. Returns how many moved."""
    if name is not None and find(sketch, name) is None:
        raise LayerError(f"There is no layer called {name}. Make it first.")
    count = 0
    for eid in ids:
        ent = sketch.entities.get(eid)
        if ent is None or isinstance(ent, Point):
            continue
        if name is None:
            count += sketch.layer_of.pop(eid, None) is not None
        else:
            sketch.layer_of[eid] = name
            count += 1
    return count


def remove_layer(sketch: Sketch, name: str) -> None:
    """Delete a layer; its curves go back to no layer."""
    sketch.layers = [layer for layer in sketch.layers if layer.get("name") != name]
    sketch.layer_of = {k: v for k, v in sketch.layer_of.items() if v != name}


def layer_style(sketch: Sketch, eid: str) -> dict[str, Any] | None:
    """The layer of curve ``eid``, or None."""
    name = sketch.layer_of.get(eid)
    return find(sketch, name) if name else None


def hidden(sketch: Sketch, eid: str) -> bool:
    """True when the curve is on a layer that is hidden."""
    layer = layer_style(sketch, eid)
    return layer is not None and layer.get("visible") is False
