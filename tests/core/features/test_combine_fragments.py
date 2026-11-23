"""Combine: Fragments and Inside at least (TR371 items 1 and 2, D999)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.solids import solids, volume_of
from tests.core.features.phase3_parts import add_feature, ok_body, rebuild
from tests.core.features.test_multibody import BLOCK, SHARED, body_a, body_b, two_blocks


def test_fragments_keep_every_piece() -> None:
    doc, first, second, body = two_blocks()
    refs = {"bodies": [body_a(body, first), body_b(body, second)]}
    fid = add_feature(doc, "combine", {"operation": "fragments"}, refs)
    out = ok_body(rebuild(doc), fid)
    assert len(solids(out.shape)) == 3  # each block's own part and the shared part
    assert volume_of(out.shape) == pytest.approx(2 * BLOCK - SHARED, rel=1e-9)


def test_inside_at_least_two_is_the_overlap() -> None:
    doc, first, second, body = two_blocks()
    refs = {"bodies": [body_a(body, first), body_b(body, second)]}
    fid = add_feature(
        doc, "combine", {"operation": "at_least", "min_bodies": Param("2", 2.0)}, refs
    )
    out = ok_body(rebuild(doc), fid)
    assert volume_of(out.shape) == pytest.approx(SHARED, rel=1e-9)
    doc, first, second, body = two_blocks()
    fid = add_feature(
        doc, "combine", {"operation": "at_least", "min_bodies": Param("3", 3.0)}, refs
    )
    result = rebuild(doc)[fid]
    assert "Enter a smaller number" in result.issues[0].message
