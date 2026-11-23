"""Repair Lost References window (TR125, D795)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.features.base import FeatureState
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.features.test_fillet import _plate_and_refs, add_fillet
from tests.core.naming.test_repair import _moved
from tests.ui.test_main_window import _folders, window

__all__ = ["_folders", "window"]


def test_command_and_icon() -> None:
    from fdcad.ui.icons.audit import audit

    assert BY_ID["evaluate.repair_references"].label == "Repair Lost References"
    assert BY_ID["evaluate.repair_references"].keys == ()
    assert audit("evaluate.repair_references") == []


def _broken(qtbot: QtBot, window: MainWindow) -> tuple[DocumentSession, str, str]:
    doc, _ext, _b, refs = _plate_and_refs(2)
    fid = add_fillet(doc, 2.0, edges=[_moved(refs[0], 0.5), refs[1]])
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    assert session.report is not None
    assert session.report.results[fid].state is FeatureState.ERROR
    return session, fid, str(refs[0]["name"])


def test_use_the_offered_match_as_one_undo_step(qtbot: QtBot, window: MainWindow) -> None:
    session, fid, good = _broken(qtbot, window)
    tool = window.repair_references
    assert window.commands.trigger("evaluate.repair_references")
    qtbot.waitUntil(lambda: tool.rows is not None, timeout=20000)
    assert tool.rows is not None and len(tool.rows) == 1
    lost, ghost, match = tool.rows[0]
    assert lost.fid == fid and lost.suggestion is not None
    assert ghost is not None and match is not None
    tool.found.setCurrentRow(0)
    assert window.tree is not None and window.tree.selected_id() == fid
    assert not tool.use_offered()  # nothing ticked yet: nothing changes
    tool.tick_all()
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        assert tool.use_offered()
    assert session.document.feature(fid).refs["edges"][0]["name"] == good
    assert session.report is not None
    assert session.report.results[fid].state is not FeatureState.ERROR
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.undo()
    assert session.document.feature(fid).refs["edges"][0]["name"] != good


def test_remove_from_the_tree_menu(qtbot: QtBot, window: MainWindow) -> None:
    session, fid, _good = _broken(qtbot, window)
    tree = window.tree
    assert tree is not None
    item = tree.item_for(fid)
    menu = tree._context_menu(session, item)
    assert menu is not None
    repair = next(a for a in menu.actions() if a.text() == "Repair Lost References")
    tool = window.repair_references
    repair.trigger()
    qtbot.waitUntil(lambda: tool.rows is not None, timeout=20000)
    assert tool.only == [fid]
    tool.tick_all()
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        assert tool.remove()
    assert len(session.document.feature(fid).refs["edges"]) == 1


def test_pick_again_and_clear_all_missing(qtbot: QtBot) -> None:
    """In a panel's pick list a selected lost item is replaced by the next pick (TR125)."""
    from fdcad.core.document.model import new_document
    from fdcad.ui.property_panel.forms.base import PickList

    picks = PickList(new_document(), "")
    qtbot.addWidget(picks)
    seen: list[object] = []
    picks.lost_selected.connect(seen.append)
    for name in ("a", "b", "c"):
        picks.add({"kind": "edge", "name": name})
    picks.mark_lost(["b", "c"])
    assert picks.names() == ["b", "c", "a"] and not picks.clear_missing.isHidden()
    picks.list.setCurrentRow(0)
    assert isinstance(seen[-1], dict) and seen[-1]["name"] == "b"
    assert picks.add({"kind": "edge", "name": "d"})
    assert picks.names() == ["d", "c", "a"] and seen[-1] is None
    picks.remove_lost()
    assert picks.names() == ["d", "a"] and picks.clear_missing.isHidden()
