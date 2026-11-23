"""Edge names come from maps made once per body (D1058).

Found on a gearbox (2026-11-12): rounding the four corners of the cover took 30
seconds, all of it spent finding four edges by name. Naming one edge mapped every
edge of the part to its faces again, and finding an edge by name named every edge.
"""

from __future__ import annotations

from typing import Any

import pytest
from tests.core.features.test_features import body, plate

from fdcad.core.features.modify import edges_of
from fdcad.core.naming import names
from fdcad.core.naming.names import NamedShape
from fdcad.core.rebuild.runner import rebuild


def test_naming_and_finding_edges_maps_the_body_once(monkeypatch: pytest.MonkeyPatch) -> None:
    doc, ext = plate()
    built = body(rebuild(doc), ext)
    fresh = NamedShape(built.shape, list(built.faces))
    real = names.TopExp
    calls = 0

    class Counting:
        MapShapes_s = staticmethod(real.MapShapes_s)

        @staticmethod
        def MapShapesAndAncestors_s(*args: Any) -> Any:  # noqa: N802
            nonlocal calls
            calls += 1
            return real.MapShapesAndAncestors_s(*args)

    monkeypatch.setattr(names, "TopExp", Counting)
    labels = [fresh.edge_name(edge) for edge in edges_of(fresh.shape)]
    assert len(labels) == 12 and all(labels)
    for label in labels:
        assert len(fresh.edges(label)) == 1  # type: ignore[arg-type]
        assert fresh.edge(label) is not None  # type: ignore[arg-type]
    assert calls == 1, calls  # it was once per edge named: several hundred here


def test_names_added_later_are_seen() -> None:
    """The kept maps are made again when a name is added."""
    doc, ext = plate()
    built = body(rebuild(doc), ext)
    top = built.face(f"{ext}/cap/end")
    assert top is not None
    partial = NamedShape(built.shape, [(n, f) for n, f in built.faces if not f.IsSame(top)])
    edge = edges_of(top)[0]
    before = partial.edge_name(edge)
    partial.faces.append((f"{ext}/cap/end", top))
    after = partial.edge_name(edge)
    assert before != after and after is not None and f"{ext}/cap/end" in after
    assert partial.edges(after) and not partial.edges(str(before))
