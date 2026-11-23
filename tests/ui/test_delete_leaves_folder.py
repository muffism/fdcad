"""A deleted feature leaves its tree folder and comment (D2646, audit D3 item 20)."""

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document import tree_info
from fdcad.ui.commands.document import DeleteFeature
from fdcad.ui.session import DocumentSession
from tests.core.features.test_features import plate


@pytest.fixture(autouse=True)
def _cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "cache"))


def test_deleting_every_feature_of_a_folder_frees_its_name(qtbot: QtBot) -> None:
    """The folder stayed in the file with no feature to show, so its name was still
    taken: making a new folder of that name was refused."""
    doc, ext = plate()
    doc.tree = {"folders": [{"name": "Base", "features": [ext]}], "comments": {ext: "Plate"}}
    session = DocumentSession(doc)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.request_rebuild()
    before = dict(doc.tree)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.push(DeleteFeature(session, ext))
    assert doc.tree == {}
    assert tree_info.name_problem(doc.tree, "Base") == ""
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.undo()
    assert doc.tree == before
    assert tree_info.folder_of(doc.tree, ext) == "Base"
    assert tree_info.comment(doc.tree, ext) == "Plate"
