"""Delete Face fills small holes by size (TR388, D990)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from tests.core.features.phase3_parts import (
    add_feature,
    block_with_hole_and_boss,
    ok_body,
    rebuild,
    volume_of,
)


def test_holes_up_to_a_size_are_filled_without_picks() -> None:
    doc, _ids = block_with_hole_and_boss()
    before = volume_of(ok_body(rebuild(doc), doc.features[-1].id).shape)
    fid = add_feature(doc, "delete_face", {"option": "patch", "hole_size": Param("12", 12.0)}, {})
    body = ok_body(rebuild(doc), fid)
    assert volume_of(body.shape) == pytest.approx(before + 3.14159265 * 25 * 10, rel=1e-6)


def test_no_hole_small_enough_says_so() -> None:
    doc, _ids = block_with_hole_and_boss()
    fid = add_feature(doc, "delete_face", {"option": "patch", "hole_size": Param("2", 2.0)}, {})
    result = rebuild(doc)[fid]
    assert result.state is FeatureState.ERROR
    assert "enter a larger hole size" in result.issues[0].message
