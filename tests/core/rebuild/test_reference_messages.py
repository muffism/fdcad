"""A reference to a suppressed, later or deleted feature fails with a clear message
(naming stress tests, PLAN Phase 6, DECISIONS D431)."""

from __future__ import annotations

from fdcad.core.features.base import FeatureState
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.samples.make import SAMPLE_DIR


def _error(doc: fdef.Document, fid: str) -> str:
    result = RebuildEngine().rebuild(doc).results[fid]
    assert result.state is FeatureState.ERROR
    return result.issues[0].message


def _plate() -> fdef.Document:
    return fdef.load(SAMPLE_DIR / "plate_with_holes.fdprt")


def test_suppressed_sketch_is_named() -> None:
    doc = _plate()
    sketch = doc.feature("f5")
    sketch.suppressed = True
    message = _error(doc, "f6")
    assert message == (
        f"{doc.feature('f6').name}: {sketch.name} is suppressed. "
        f"Unsuppress {sketch.name} or choose another reference."
    )
    assert "f5" not in message


def test_feature_below_is_named() -> None:
    doc = _plate()
    sketch = doc.feature("f5")
    doc.features.remove(sketch)
    doc.features.append(sketch)
    message = _error(doc, "f6")
    assert message == (
        f"{doc.feature('f6').name}: {sketch.name} is below this feature in the tree. "
        f"Move {sketch.name} above it or choose another reference."
    )


def test_deleted_feature() -> None:
    doc = _plate()
    doc.features.remove(doc.feature("f5"))
    message = _error(doc, "f6")
    assert message == (
        f"{doc.feature('f6').name}: a reference points at a deleted feature. "
        "Choose another reference."
    )


def test_face_of_a_suppressed_feature_says_unsuppress() -> None:
    from tests.core.features.test_features import _hole, plate

    doc, ext = plate()
    _hole(doc, f"{ext}/cap/end")  # f7 sketch on the plate's top face, f8 cut
    doc.feature(ext).suppressed = True
    message = _error(doc, "f7")
    name = doc.feature(ext).name
    assert message == (
        f"{doc.feature('f7').name}: {name} is suppressed. "
        f"Unsuppress {name} or choose another reference."
    )
