"""Use Only Fully Defined Sketches (TR36 item 6, D763)."""

from __future__ import annotations

from fdcad.core.document.model import Document, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, rect


def _plate() -> Document:
    """A plate whose rectangle has no dimensions, so its sketch is under defined."""
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 50, 30)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    return doc


def test_off_by_default_and_refused_when_on() -> None:
    doc = _plate()
    ext = next(f for f in doc.features if f.type == "extrude")
    engine = RebuildEngine()
    assert not engine.full_sketches_only
    assert engine.rebuild(doc).results[ext.id].state is not FeatureState.ERROR
    engine.full_sketches_only = True
    result = engine.rebuild(doc).results[ext.id]  # the cache must not hide it
    assert result.state is FeatureState.ERROR
    sketch = doc.feature(ext.refs["sketch"]["feature"])
    message = result.issues[0].message
    assert sketch.name in message and "not fully defined" in message
    assert "Fully Define Sketch" in message  # what to do next
    engine.full_sketches_only = False
    assert engine.rebuild(doc).results[ext.id].state is not FeatureState.ERROR
