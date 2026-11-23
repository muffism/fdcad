"""Copied reference geometry is drawn in the view (TR142 item 1, D2402)."""

from __future__ import annotations

from fdcad.ui.main_window.window import pattern_datum_shapes
from tests.core.features.test_patterns import Y, centred, count, length, pattern


def test_copies_are_drawn_and_exploded_planes_are_left_to_the_plane_faces() -> None:
    doc, _plate, _boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(10), "count1": count(3)},
        {"direction1": Y, "features": [{"feature": "f3"}]},
    )
    assert len(pattern_datum_shapes(doc, results, 30.0)) == 2
    doc.feature(fid).suppressed = True
    assert pattern_datum_shapes(doc, results, 30.0) == []
    doc.feature(fid).suppressed = False
    doc.feature(fid).data["only"] = [2, 1]
    from fdcad.core.rebuild.runner import rebuild

    results = rebuild(doc)
    assert results[fid].plane is not None
    assert pattern_datum_shapes(doc, results, 30.0) == []
