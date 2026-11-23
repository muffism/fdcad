"""Before and after a change (TR289, D2019)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Param
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.rebuild_compare import volume_changes
from tests.core.features.test_features import plate


def test_only_changed_features_are_listed_with_their_volumes() -> None:
    doc, ext = plate(10.0)
    engine = RebuildEngine()
    before = engine.rebuild(doc)
    feature = doc.feature(ext)
    feature.params["depth"] = Param("12", 12.0)
    after = engine.rebuild(doc)
    rows = volume_changes(doc, before, after)
    assert [r.feature_id for r in rows] == [ext]
    assert rows[0].before == pytest.approx(25000.0)
    assert rows[0].after == pytest.approx(30000.0)
    assert rows[0].delta == pytest.approx(5000.0)
    assert volume_changes(doc, after, after) == []
    assert volume_changes(doc, None, after) == []
