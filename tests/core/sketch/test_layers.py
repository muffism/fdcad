"""Sketch layers (TR389, D982)."""

from __future__ import annotations

import pytest

from fdcad.core.sketch.layers import (
    LayerError,
    add_layer,
    hidden,
    layer_style,
    put_on,
    remove_layer,
)
from fdcad.core.sketch.model import Sketch, sketch_from_data, sketch_to_data


def test_layers_round_trip_and_hide() -> None:
    sk = Sketch()
    a = sk.add_line(0, 0, 10, 0)
    b = sk.add_line(0, 5, 10, 5)
    assert "layers" not in sketch_to_data(sk)  # no layers: saved as before
    add_layer(sk, "Guide", "#FF0000", "dashed")
    assert put_on(sk, [a, sk.entities[a].p1], "Guide") == 1  # type: ignore[union-attr]
    assert layer_style(sk, a) == {
        "name": "Guide",
        "colour": "#FF0000",
        "style": "dashed",
        "visible": True,
    }
    sk.layers[0]["visible"] = False
    assert hidden(sk, a) and not hidden(sk, b)
    again = sketch_from_data(sketch_to_data(sk))
    assert again.layers == sk.layers and again.layer_of == {a: "Guide"}
    remove_layer(sk, "Guide")
    assert sk.layer_of == {} and not hidden(sk, a)


def test_layer_names_are_checked() -> None:
    sk = Sketch()
    add_layer(sk, "One")
    with pytest.raises(LayerError, match="already"):
        add_layer(sk, "One")
    with pytest.raises(LayerError, match="needs a name"):
        add_layer(sk, " ")
    with pytest.raises(LayerError, match="no layer called"):
        put_on(sk, [], "Two")
