"""Show and hide state of sketches and planes, saved in the file (D114)."""

from pathlib import Path

from fdcad.core.document.display import hidden_ids, set_display, shown_ids
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine
from tests.core.features.test_features import plate

SAMPLES = Path(__file__).parents[3] / "samples"


def test_set_and_read_back_in_canonical_order() -> None:
    doc, _ext = plate()
    set_display(doc, set(), {"f2"})
    set_display(doc, {"f5"}, {"f2", "f3"})
    assert hidden_ids(doc) == {"f5"} and shown_ids(doc) == {"f2", "f3"}
    assert list(doc.appearance) == ["part_color", "faces", "hidden", "shown"]
    set_display(doc, set(), set())
    assert "hidden" not in doc.appearance and "shown" not in doc.appearance


def test_ids_of_deleted_features_are_dropped() -> None:
    doc, _ext = plate()
    set_display(doc, {"f5", "f99"}, {"f77"})
    assert hidden_ids(doc) == {"f5"} and "shown" not in doc.appearance


def test_saved_and_reopened(tmp_path: Path) -> None:
    doc, _ext = plate()
    set_display(doc, {"f5"}, {"f3"})
    path = tmp_path / "part.fdef"
    fdef.save(doc, path)
    again = fdef.load(path)
    assert hidden_ids(again) == {"f5"} and shown_ids(again) == {"f3"}


def test_older_files_open_and_save_unchanged() -> None:
    for path in sorted(SAMPLES.glob("*.fdprt")):
        text = path.read_text(encoding="utf-8")
        doc = fdef.loads(text)
        assert hidden_ids(doc) == set() and shown_ids(doc) == set()
        assert fdef.dumps(doc) == text, path.name


def test_display_state_does_not_change_the_cache_key() -> None:
    doc, ext = plate()
    before = RebuildEngine().rebuild(doc).results[ext].key
    set_display(doc, {"f5"}, {"f2"})
    assert RebuildEngine().rebuild(doc).results[ext].key == before
