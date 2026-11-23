"""Keep separate body is saved in the part (IDEAS.md item 1, DECISIONS D527)."""

from __future__ import annotations

from pathlib import Path

from fdcad.core.document.model import Document
from fdcad.core.features.base import FeatureState, keeps_separate_body
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, plate, rect, volume


def separate() -> tuple[Document, str]:
    doc, _ = plate()
    s = Sketch()
    rect(s, 100, 0, 110, 10)
    return doc, add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 5.0)


def test_warning_is_not_reported_while_kept() -> None:
    doc, far = separate()
    before = rebuild(doc)[far]
    assert [i.code for i in before.issues] == ["separate_body"]
    doc.feature(far).data["keep_separate_body"] = True
    assert keeps_separate_body(doc.feature(far))
    after = rebuild(doc)[far]
    assert after.issues == [] and after.state is FeatureState.OK
    assert after.body is not None and before.body is not None
    assert volume(after.body.shape) == volume(before.body.shape)


def test_setting_the_key_rebuilds_nothing() -> None:
    doc, far = separate()
    engine = RebuildEngine()
    engine.rebuild(doc)
    doc.feature(far).data["keep_separate_body"] = True
    report = engine.rebuild(doc)
    assert report.rebuilt == []
    assert report.results[far].issues == []


def test_round_trip_and_old_files_unchanged(tmp_path: Path) -> None:
    doc, far = separate()
    old_text = fdef.dumps(doc)
    assert "keep_separate_body" not in old_text
    assert fdef.dumps(fdef.loads(old_text)) == old_text
    doc.feature(far).data["keep_separate_body"] = True
    path = tmp_path / "kept.fdef"
    fdef.save(doc, path)
    text = path.read_text(encoding="utf-8")
    assert '"keep_separate_body": true' in text
    again = fdef.load(path)
    assert keeps_separate_body(again.feature(far))
    assert fdef.dumps(again) == text
    assert rebuild(again)[far].issues == []
    # Clearing the key gives the old file back, byte for byte.
    again.feature(far).data.pop("keep_separate_body")
    assert fdef.dumps(again) == old_text
