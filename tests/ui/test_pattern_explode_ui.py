"""Explode Pattern from the tree menu (TR270 item 1, D1902)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.features.phase3_parts import add_feature
from tests.core.features.test_patterns import X, centred, count, length
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_explode_makes_one_feature_per_copy_and_undoes(qtbot: QtBot, window: MainWindow) -> None:
    doc, _plate, boss = centred()
    fid = add_feature(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(3), "reverse1": True},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    tree = window.tree
    assert tree is not None
    item = tree.item_for(fid)
    assert item is not None
    menu = tree._context_menu(session, item)
    assert menu is not None
    from fdcad.ui import strings

    assert strings.EXPLODE_PATTERN in [a.text() for a in menu.actions()]
    count_before = len(session.document.features)
    assert tree.explode_pattern(fid)
    assert len(session.document.features) == count_before + 1
    assert session.document.feature(fid).data["only"] == [2, 1]
    session.undo.undo()
    assert len(session.document.features) == count_before
    assert "only" not in session.document.feature(fid).data


def test_add_to_pattern_repeats_a_feature_at_every_copy(qtbot: QtBot, window: MainWindow) -> None:
    """TR399 items 1 and 2 (D1904): a bump on copy 2 is added at the other copies."""
    from tests.core.features.test_follow_pattern import _bump_on

    doc, _plate, boss = centred()
    pid = add_feature(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(3), "reverse1": True},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    bump = _bump_on(doc, f"{pid}/instance2.1/{boss}/cap/end", -4.0)
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    tree = window.tree
    assert tree is not None
    from fdcad.ui import strings

    pattern_item = tree.item_for(pid)
    assert pattern_item is not None
    menu = tree._context_menu(session, pattern_item)
    assert menu is not None and strings.ADD_TO_PATTERN not in [a.text() for a in menu.actions()]
    item = tree.item_for(bump)
    assert item is not None
    menu = tree._context_menu(session, item)
    assert menu is not None and strings.ADD_TO_PATTERN in [a.text() for a in menu.actions()]
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        assert tree.add_to_pattern(bump)
    made = session.document.features[-1]
    assert made.type == "follow_pattern" and made.data["on"] == [2, 1]
    assert made.name == "Follow Pattern 1"
    report = session.report
    assert report is not None and report.results[made.id].state.value != "error"
