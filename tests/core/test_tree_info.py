"""Tree folders and feature comments in the part file (TR23, D692)."""

from __future__ import annotations

import pytest

from fdcad.core.document import tree_info as ti
from fdcad.core.document.model import Document
from fdcad.core.io import fdef
from fdcad.core.io.migrations import FileFormatError

TOP = ["f5", "f6", "f7", "f8"]


def test_folder_and_comment_round_trip() -> None:
    doc = Document()
    doc.tree = ti.set_comment(ti.add_folder({}, "Holes", ["f6", "f7"], TOP), "f6", "M6 clearance")
    back = fdef.loads(fdef.dumps(doc))
    assert ti.folder_of(back.tree, "f7") == "Holes"
    assert ti.comment(back.tree, "f6") == "M6 clearance"
    assert '"tree"' not in fdef.dumps(Document())


def test_only_neighbours_go_in_a_folder() -> None:
    with pytest.raises(ti.TreeInfoError):
        ti.add_folder({}, "Gap", ["f5", "f7"], TOP)
    tree = ti.add_folder({}, "Pair", ["f8", "f7"], TOP)
    assert ti.folders(tree)[0]["features"] == ["f7", "f8"]


def test_runs_keep_only_members_that_stay_together() -> None:
    tree = ti.add_folder({}, "Pair", ["f6", "f7"], TOP)
    assert ti.runs(tree, TOP) == {"f6": "Pair", "f7": "Pair"}
    moved = ["f6", "f5", "f7", "f8"]  # a feature was moved between them
    assert ti.runs(tree, moved) == {"f6": "Pair"}


def test_names_rename_remove_and_forget() -> None:
    tree = ti.add_folder({}, ti.next_name({}), ["f5"], TOP)
    assert ti.next_name(tree) == "Folder 2"
    with pytest.raises(ti.TreeInfoError):
        ti.add_folder(tree, "folder 1", ["f6"], TOP)
    tree = ti.rename_folder(tree, "Folder 1", "Base")
    assert ti.folder_of(tree, "f5") == "Base"
    tree = ti.add_folder(tree, "Again", ["f5", "f6"], TOP)  # f5 moves to the new folder
    assert ti.folder_of(tree, "f5") == "Again" and len(ti.folders(tree)) == 1
    tree = ti.set_comment(tree, "f6", "note")
    tree = ti.forget(tree, {"f6"})
    assert ti.comment(tree, "f6") == "" and ti.folders(tree)[0]["features"] == ["f5"]
    assert ti.remove_folder(tree, "Again") == {}
    assert ti.set_comment({"comments": {"f5": "x"}}, "f5", "  ") == {}


def test_damaged_tree_data() -> None:
    data = fdef.to_json_data(Document())
    data["tree"] = {"folders": [{"name": 3}]}
    with pytest.raises(FileFormatError):
        fdef.from_json_data(data)
