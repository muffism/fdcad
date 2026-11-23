"""Two edges that share a name are two picks (D1051).

Found on a bike frame (2026-11-12): where a stay crosses a dropout plate it meets one
face of the plate in two edges. Both are named by the same two faces. The pick list
keyed its items by name, so a click on the second edge added nothing and said nothing.
"""

from typing import Any

from fdcad.core.document.model import new_document
from fdcad.ui.property_panel.forms.base import PickList


def _edge(name: str, y: float) -> dict[str, Any]:
    return {
        "kind": "edge",
        "name": name,
        "snapshot": {"curve": "line", "length": 30.0, "midpoint": [25.0, y, 10.0]},
    }


def test_a_second_edge_with_the_same_name_is_added(qtbot: Any) -> None:
    picks = PickList(new_document(), "")
    qtbot.addWidget(picks)
    name = "edge(f6/cap/end|f9/side/e2)"
    assert picks.add(_edge(name, 41.0))
    assert picks.add(_edge(name, 49.0))  # another edge between the same two faces
    assert not picks.add(_edge(name, 49.0))  # the same edge again is still refused
    assert [r["snapshot"]["midpoint"][1] for r in picks.refs()] == [41.0, 49.0]
    # A reference with no place is the same pick as one of that name, as before.
    assert not picks.add({"kind": "edge", "name": name})


def test_edges_are_removed_by_their_place_among_the_edges(qtbot: Any) -> None:
    picks = PickList(new_document(), "")
    qtbot.addWidget(picks)
    name = "edge(f6/cap/end|f9/side/e2)"
    picks.add({"kind": "face", "name": "f6/cap/end"})
    picks.add(_edge(name, 41.0))
    picks.add(_edge(name, 49.0))
    seen = []
    picks.changed.connect(lambda: seen.append(1))
    picks.remove_edges_at([2])  # the second edge, not the second row
    kept = picks.refs()
    assert [r["kind"] for r in kept] == ["face", "edge"]
    assert kept[1]["snapshot"]["midpoint"][1] == 41.0 and seen == [1]


def test_fillet_the_rest_removes_the_failing_edge_only(qtbot: Any) -> None:
    """The form's own handling of the button: by place when the fix gives places."""
    from fdcad.core.features.base import Fix
    from fdcad.ui.property_panel.forms import fillet_form

    picks = PickList(new_document(), "")
    qtbot.addWidget(picks)
    name = "edge(f6/cap/end|f9/side/e2)"
    picks.add(_edge(name, 41.0))
    picks.add(_edge(name, 49.0))

    class Form:
        items = picks
        apply_fix = fillet_form.FilletForm.apply_fix

    fix = Fix("Fillet the rest (skip 1 edge)", "skip_items",
              {"feature": "f10", "items": [name], "keys": ["edges"], "positions": [2]})  # fmt: skip
    Form().apply_fix(fix)
    assert [r["snapshot"]["midpoint"][1] for r in picks.refs()] == [41.0]
