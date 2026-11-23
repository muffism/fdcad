"""Change a fillet to a chamfer and back (TR134, D994)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature, Param
from fdcad.core.fillet_chamfer import SwapError, can_swap, swapped


def test_round_trip_keeps_edges_and_size() -> None:
    fillet = Feature(
        "f9",
        "fillet",
        "Fillet 2",
        params={"fillet_type": "constant", "radius": Param("3mm", 3.0)},
        refs={"edges": [{"kind": "edge", "name": "a"}]},
    )
    chamfer = swapped(fillet)
    assert chamfer.type == "chamfer" and chamfer.name == "Chamfer 2"
    assert chamfer.params["distance"] == Param("3mm", 3.0)
    assert chamfer.refs == fillet.refs and chamfer.id == "f9"
    back = swapped(chamfer)
    assert back.type == "fillet" and back.params["radius"] == Param("3mm", 3.0)
    assert back.name == "Fillet 2"


def test_other_kinds_are_refused() -> None:
    variable = Feature(
        "f9", "fillet", "Edge round", params={"fillet_type": "variable"}, refs={"edges": []}
    )
    assert not can_swap(variable)
    angled = Feature(
        "f9",
        "chamfer",
        "Chamfer 1",
        params={"chamfer_type": "angle_distance", "distance": Param("1", 1.0)},
        refs={"edges": [{"name": "a"}]},
    )
    with pytest.raises(SwapError, match="equal distance"):
        swapped(angled)
