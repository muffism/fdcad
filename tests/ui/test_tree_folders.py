"""Tree folders and feature comments in the feature tree (TR23, D692)."""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from fdcad.core.document import tree_info
from fdcad.core.io import fdef
from fdcad.samples.make import SAMPLE_DIR
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.session import DocumentSession
from fdcad.ui.tree.feature_tree import COMMENT_ROLE, FID_ROLE, FOLDER_ROLE
from tests.ui.test_main_window import _folders, window

__all__ = ["_folders", "window"]


def _bracket(qtbot: QtBot, win: MainWindow) -> DocumentTab:
    doc = fdef.loads((SAMPLE_DIR / "bracket.fdprt").read_text(encoding="utf-8"))
    session = DocumentSession(doc, None, win)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = win.add_session(session)
    return tab


def _folder_rows(win: MainWindow) -> list[object]:
    assert win.tree is not None
    return [i for i in win.tree.all_items() if isinstance(i.data(0, FOLDER_ROLE), str)]


def test_add_two_neighbours_to_a_folder_then_rename_and_remove(
    qtbot: QtBot, window: MainWindow, tmp_path: Path
) -> None:
    tab = _bracket(qtbot, window)
    tree = window.tree
    assert tree is not None
    top = tree.top_level_features()
    assert "f8" in top and "f10" in top
    i = top.index("f8")
    pair = top[i : i + 2]
    assert tree.add_to_new_folder(pair)
    rows = _folder_rows(window)
    assert len(rows) == 1
    folder = rows[0]
    assert folder.text(0) == "Folder 1"  # type: ignore[attr-defined]
    kids = [folder.child(j).data(0, FID_ROLE) for j in range(folder.childCount())]  # type: ignore[attr-defined]
    assert kids == pair
    assert tree.rename_folder("Folder 1", "Holes")
    assert tree_info.folder_of(tab.session.document.tree, pair[0]) == "Holes"
    tree.remove_folder("Holes")
    assert not _folder_rows(window)
    tab.session.undo.undo()
    qtbot.waitUntil(lambda: bool(_folder_rows(window)), timeout=3000)  # the tree refreshes soon
    assert [r.text(0) for r in _folder_rows(window)] == ["Holes"]  # type: ignore[attr-defined]
    # Saved in the part file.
    path = tmp_path / "foldered.fdprt"
    fdef.save(tab.session.document, path)
    assert tree_info.folder_of(fdef.load(path).tree, pair[0]) == "Holes"


def test_features_apart_are_refused(qtbot: QtBot, window: MainWindow) -> None:
    _bracket(qtbot, window)
    tree = window.tree
    assert tree is not None
    assert not tree.add_to_new_folder(["f6", "f10"])
    assert "next to each other" in tree.message


def test_comment_mark_and_hover_text(qtbot: QtBot, window: MainWindow) -> None:
    tab = _bracket(qtbot, window)
    tree = window.tree
    assert tree is not None
    assert tree.set_comment("f8", "Clearance for M6")
    item = tree.item_for("f8")
    assert item is not None
    assert item.data(0, COMMENT_ROLE) == "Clearance for M6"
    assert "Clearance for M6" in item.toolTip(0)
    assert tree.set_comment("f8", "")
    item = tree.item_for("f8")
    assert item is not None and item.data(0, COMMENT_ROLE) is None
    assert tab.session.document.tree == {}


def test_menus_offer_folder_and_comment(qtbot: QtBot, window: MainWindow) -> None:
    tab = _bracket(qtbot, window)
    tree = window.tree
    assert tree is not None
    item = tree.item_for("f8")
    assert item is not None
    menu = tree._context_menu(tab.session, item)
    assert menu is not None
    texts = [a.text() for a in menu.actions()]
    assert "Add to New Folder" in texts and "Comment..." in texts
    tree.add_to_new_folder(["f8"])
    folder = _folder_rows(window)[0]
    menu = tree._context_menu(tab.session, folder)  # type: ignore[arg-type]
    assert menu is not None
    assert [a.text() for a in menu.actions()] == ["Rename", "Remove Folder"]


def test_switch_boss_and_cut_from_the_tree(qtbot: QtBot, window: MainWindow) -> None:
    """TR387, D890."""
    tab = _bracket(qtbot, window)
    tree = window.tree
    assert tree is not None
    extrude = next(f for f in tab.session.document.features if f.type == "extrude")
    item = tree.item_for(extrude.id)
    assert item is not None
    menu = tree._context_menu(tab.session, item)
    assert menu is not None
    action = next(a for a in menu.actions() if a.text() in ("Switch to Cut", "Switch to Boss"))
    before = extrude.params.get("operation", "boss")
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        action.trigger()
    after = tab.session.document.feature(extrude.id).params["operation"]
    assert after != before
    assert "Make Thin" in [a.text() for a in menu.actions()]
    tab.session.undo.undo()
    assert tab.session.document.feature(extrude.id).params.get("operation", "boss") == before
