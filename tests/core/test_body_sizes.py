"""Select bodies by size (TR70, D894)."""

from __future__ import annotations

import pytest

from fdcad.core.body_sizes import pick, sizes
from fdcad.core.document.model import new_document
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, rect


def _part():  # type: ignore[no-untyped-def]
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 40, 40)  # 16000
    rect(s, 50, 0, 52, 2)  # 40
    rect(s, 60, 0, 70, 10)  # 1000
    fid = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    return doc, fid


def test_sizes_and_pick() -> None:
    doc, fid = _part()
    found = sizes(body(rebuild(doc), fid))
    assert sorted(b.volume for b in found) == pytest.approx([40.0, 1000.0, 16000.0])
    assert all(b.ref is not None for b in found)
    small = pick(found, 10.0)  # under 1600
    assert sorted(b.volume for b in small) == pytest.approx([40.0, 1000.0])
    assert [b.volume for b in pick(found, 10.0, larger=True)] == pytest.approx([16000.0])
