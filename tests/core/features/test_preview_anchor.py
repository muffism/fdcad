"""Where value labels sit for features without drag handles (TOOL_SPEC T15.2, D440)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature
from fdcad.core.features.preview import build_preview
from fdcad.core.features.preview_anchor import edge_middle, named_edge, pick_anchor
from fdcad.core.naming.names import centroid
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, plate
from tests.core.features.test_fillet import _plate_and_refs, add_fillet, top_edges
from tests.core.features.test_shell import add_shell


def test_fillet_labels_sit_in_the_middle_of_the_first_edge() -> None:
    doc, ext, b, refs = _plate_and_refs(2)
    fid = add_fillet(doc, 2.0, edges=refs)
    geometry = build_preview(doc, doc.feature(fid), rebuild(doc))
    assert geometry.anchor is not None
    expected = edge_middle(top_edges(b, ext)[0])
    assert geometry.anchor == pytest.approx(expected)


def test_named_edge_finds_the_shared_edge() -> None:
    _doc, ext, b, refs = _plate_and_refs(1)
    edge = named_edge(b, refs[0]["name"])
    assert edge is not None and edge.IsSame(top_edges(b, ext)[0])
    assert named_edge(b, "edge(nothing|here)") is None
    assert named_edge(b, "not an edge") is None


def test_shell_labels_go_on_the_first_face() -> None:
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    top = b.face(f"{ext}/cap/end")
    assert top is not None
    fid = add_shell(doc, 1.0, faces=[reference_for(b, top)])
    geometry = build_preview(doc, doc.feature(fid), rebuild(doc))
    assert geometry.anchor == pytest.approx(centroid(top))


def test_shell_without_picks_uses_the_middle_of_the_part() -> None:
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    feature = Feature("fx", "shell", "Shell", params={}, refs={})
    anchor = pick_anchor(feature, b, None)
    assert anchor == pytest.approx((25.0, 25.0, 5.0), abs=1e-6)


def test_draft_prefers_the_neutral_face() -> None:
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    top, bottom = b.face(f"{ext}/cap/end"), b.face(f"{ext}/cap/start")
    assert top is not None and bottom is not None
    feature = Feature(
        "fx",
        "draft",
        "Draft",
        refs={"faces": [reference_for(b, top)], "neutral": reference_for(b, bottom)},
    )
    assert pick_anchor(feature, b, None) == pytest.approx(centroid(bottom))


def test_no_body_and_no_tool_gives_no_anchor() -> None:
    assert pick_anchor(Feature("fx", "shell", "Shell"), None, None) is None
