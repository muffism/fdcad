"""Feature tree: rollback bar, reorder rules, error and warning marks (TOOL_SPEC T14.5)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Document
from fdcad.core.features.base import FeatureState, Issue
from fdcad.core.io import fdef
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.session import DocumentSession
from fdcad.ui.themes.theme import palette
from fdcad.ui.tree.feature_tree import FID_ROLE, PART_MARK, ROLLBACK_MARK
from tests.core.features.test_features import plate
from tests.ui.test_input import _hole
from tests.ui.test_workflow import (  # noqa: F401  (fixtures)
    _folders,
    canvas_of,
    draw_rectangle,
    plane_id,
    window,
)


def _open(qtbot: QtBot, win: MainWindow, doc: Document | None = None) -> DocumentTab:
    if doc is None:
        doc, ext = plate()
        _hole(doc, f"{ext}/cap/end")  # f5 sketch, f6 extrude, f7 sketch, f8 cut
    session = DocumentSession(doc, None, win)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = win.add_session(session)
    return tab


def _roll(qtbot: QtBot, tab: DocumentTab, action: object) -> None:
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        action()  # type: ignore[operator]


def _bar_index(win: MainWindow) -> int:
    tree = win.tree
    assert tree is not None
    rows = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
    return next(
        i for i, r in enumerate(rows) if r is not None and r.data(0, FID_ROLE) == ROLLBACK_MARK
    )


def _row_ids(win: MainWindow) -> list[object]:
    tree = win.tree
    assert tree is not None
    return [tree.topLevelItem(i).data(0, FID_ROLE) for i in range(tree.topLevelItemCount())]  # type: ignore[union-attr]


def test_arrow_keys_and_roll_commands(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    tree = window.tree
    assert tree is not None
    doc = tab.session.document
    _roll(qtbot, tab, lambda: tree._rollback("f6"))
    ids = _row_ids(window)
    assert ids.index(ROLLBACK_MARK) == ids.index("f6") + 1
    bar = tree.topLevelItem(_bar_index(window))
    assert bar is not None and bar.flags() & Qt.ItemFlag.ItemIsSelectable
    tree.setCurrentItem(bar)
    tree.setFocus()
    _roll(qtbot, tab, lambda: qtbot.keyClick(tree, Qt.Key.Key_Up))
    assert doc.rollback == "f5"
    current = tree.currentItem()
    assert current is not None and current.data(0, FID_ROLE) == ROLLBACK_MARK  # still on the bar
    _roll(qtbot, tab, lambda: qtbot.keyClick(tree, Qt.Key.Key_Up))
    assert doc.rollback == "f4"  # above every feature, below the default planes
    ids = _row_ids(window)
    assert ids.index(ROLLBACK_MARK) == ids.index("f1") + 1
    _roll(qtbot, tab, lambda: qtbot.keyClick(tree, Qt.Key.Key_Down))
    assert doc.rollback == "f5"
    # Roll to Previous goes back to where the bar was before its last move.
    _roll(qtbot, tab, tree.roll_previous)
    assert doc.rollback == "f4"
    menu = tree.empty_menu()
    assert menu is not None
    assert [a.text() for a in menu.actions()] == ["Roll Forward", "Roll to Previous", "Roll to End"]
    _roll(qtbot, tab, lambda: window.commands.trigger("tree.roll_forward"))
    assert doc.rollback == "f5"
    _roll(qtbot, tab, lambda: window.commands.trigger("tree.roll_end"))
    assert doc.rollback is None
    assert ROLLBACK_MARK not in _row_ids(window)
    _roll(qtbot, tab, lambda: window.commands.trigger("tree.roll_back"))
    assert doc.rollback == "f7"


def test_rolled_back_part_greys_and_new_features_go_above_the_bar(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = _open(qtbot, window)
    tree, mode = window.tree, window.sketch_mode
    assert tree is not None and mode is not None
    doc = tab.session.document
    _roll(qtbot, tab, lambda: tree._rollback("f6"))
    cut = tree.item_for("f8")
    assert cut is not None and cut.foreground(0).color() != QColor("#000000")
    mode.start(plane_id=plane_id(tab, "Top Plane"))
    draw_rectangle(qtbot, window)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert mode.accept()
    ids = [f.id for f in doc.features]
    new = next(i for i in ids if i not in ("f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8"))
    assert ids.index(new) == ids.index("f6") + 1 and doc.rollback == new
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.undo()
    assert doc.rollback == "f6" and new not in [f.id for f in doc.features]


def test_bar_position_is_saved_and_restored(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    tab = _open(qtbot, window)
    tree = window.tree
    assert tree is not None
    _roll(qtbot, tab, lambda: tree._rollback("f6"))
    path = tmp_path / "rolled.fdef"
    fdef.save(tab.session.document, path)
    loaded = fdef.load(path)
    assert loaded.rollback == "f6"
    _open(qtbot, window, loaded)
    ids = _row_ids(window)
    assert ids.index(ROLLBACK_MARK) == ids.index("f6") + 1


def test_delete_rolled_back_feature_with_its_dependents(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tab = _open(qtbot, window)
    tree = window.tree
    assert tree is not None
    doc = tab.session.document
    _roll(qtbot, tab, lambda: tree._rollback("f5"))
    asked: list[str] = []

    def answer(_parent: object, _title: str, text: str, *_a: object) -> QMessageBox.StandardButton:
        asked.append(text)
        return QMessageBox.StandardButton.Yes

    names = [doc.feature(f).name for f in ("f7", "f8")]
    monkeypatch.setattr(QMessageBox, "question", answer)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tree.delete("f6")
    assert len(asked) == 1 and all(n in asked[0] for n in names)
    assert [f.id for f in doc.features] == ["f1", "f2", "f3", "f4", "f5"]
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.undo()
    assert [f.id for f in doc.features][-4:] == ["f5", "f6", "f7", "f8"]


def test_deleting_the_feature_above_the_bar_keeps_the_part_rolled_back(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tab = _open(qtbot, window)
    tree = window.tree
    assert tree is not None
    doc = tab.session.document
    _roll(qtbot, tab, lambda: tree._rollback("f7"))  # the cut f8 is rolled back
    before = fdef.dumps(doc)
    from fdcad.ui.tree import delete_dialog

    # Keep the cut that uses f7: untick it in the list of dependents (TR201, D807).
    monkeypatch.setattr(delete_dialog, "ask", lambda *_a: [])
    _roll(qtbot, tab, lambda: tree.delete("f7"))
    assert [f.id for f in doc.features][-2:] == ["f6", "f8"]
    assert doc.rollback == "f6"  # the bar stays above the cut
    assert "f8" not in tab.session.report.results  # type: ignore[union-attr]
    assert _row_ids(window).index(ROLLBACK_MARK) < _row_ids(window).index("f8")
    _roll(qtbot, tab, tab.session.undo.undo)
    assert fdef.dumps(doc) == before


def test_a_refused_drag_says_why_in_the_status_bar(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    tree = window.tree
    assert tree is not None
    ids = [f.id for f in tab.session.document.features]
    assert not tree.move_feature("f8", ids.index("f7"))
    assert "must stay below" in window.status.text()
    assert "Drop it lower in the tree." in window.status.text()
    folder = next(i for i in tree.all_items() if i.data(0, FID_ROLE) is None)
    problem = tree.drop_problem("f8", folder, above=False)
    assert problem is not None and "default planes" not in problem
    assert "Drop it on a feature row." in problem


def test_a_row_clicked_after_select_stays_selected_after_a_rebuild(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    from fdcad.ui.commands.document import SetSuppressed

    tab = _open(qtbot, window)
    tree = window.tree
    assert tree is not None
    session = tab.session
    tree.select("f6")  # for example from Appearance or the Errors tab
    tree.setCurrentItem(tree.item_for("f8"))  # then the user clicks another row
    _roll(qtbot, tab, lambda: session.undo.push(SetSuppressed(session, "f8", True)))
    assert tree.selected_id() == "f8"


def test_double_click_edits_the_feature_without_a_name_editor(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    from PySide6.QtWidgets import QAbstractItemView

    _open(qtbot, window)
    tree = window.tree
    assert tree is not None and window.panel is not None
    item = tree.item_for("f8")
    assert item is not None
    centre = tree.visualItemRect(item).center()
    qtbot.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=centre)
    qtbot.mouseDClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=centre)
    assert window.panel.is_editing
    window.panel.cancel()
    assert tree.state() is not QAbstractItemView.State.EditingState
    tree.setCurrentItem(item)
    tree.rename("f8")  # Rename in the menu still opens the name editor
    assert tree.state() is QAbstractItemView.State.EditingState


def test_rename_from_a_shared_sketch_link_row_edits_the_sketch_name(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    from PySide6.QtWidgets import QAbstractItemView

    from tests.core.features.test_features import add_extrude

    doc, _ext = plate()  # f5 sketch, f6 extrude
    add_extrude(doc, "f5", 5.0)  # f7 uses the same sketch: a link row under it
    _open(qtbot, window, doc)
    tree = window.tree
    assert tree is not None
    second = tree.item_for("f7")
    assert second is not None and second.childCount() == 1
    link = second.child(0)
    assert link.data(0, FID_ROLE) == "f5"
    sketch_row = tree.item_for("f5")
    assert sketch_row is not None and sketch_row is not link
    sketch_row.parent().setExpanded(False)  # type: ignore[union-attr]
    menu = tree._context_menu(window.current.session, link)  # type: ignore[union-attr]
    assert menu is not None
    next(a for a in menu.actions() if a.text() == "Rename").trigger()
    assert tree.state() is QAbstractItemView.State.EditingState
    assert tree.currentItem() is sketch_row


def test_drag_rules_keep_parents_before_children(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    tree = window.tree
    assert tree is not None
    doc = tab.session.document
    sketch, extrude, cut = tree.item_for("f5"), tree.item_for("f6"), tree.item_for("f8")
    assert sketch is not None and extrude is not None and cut is not None
    # The extrude above its own sketch: not allowed, with the reason.
    problem = tree.drop_problem("f6", tree.item_for("f2"), above=False)
    assert problem is not None and "must stay below" in problem
    # The cut above the extrude it cuts: not allowed.
    assert tree.drop_problem("f8", extrude, above=True) is not None
    assert tree.drop_problem("f1", cut, above=False) is not None
    # The rollback bar can be dropped on a row.
    _roll(qtbot, tab, lambda: tree.drop_bar(extrude, above=False))
    assert doc.rollback == "f6"
    _roll(qtbot, tab, lambda: tree.drop_bar(tree.item_for("f6"), above=True))
    assert doc.rollback == "f5"
    _roll(qtbot, tab, lambda: tree.drop_bar(None, above=False))
    assert doc.rollback is None


def test_independent_features_can_be_reordered(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    from fdcad.core.sketch.model import Sketch
    from tests.core.features.test_features import add_sketch, rect

    doc, _ext = plate()
    s = Sketch()
    rect(s, 0, 0, 10, 10)
    add_sketch(doc, s, {"feature": "f3"})  # f7, on Top, uses nothing of the plate
    tab = _open(qtbot, window, doc)
    tree = window.tree
    assert tree is not None
    assert tree.drop_problem("f7", tree.item_for("f5"), above=True) is None
    assert tree.drop_index("f7", tree.item_for("f5"), above=True) == 4
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert tree.move_feature("f7", 4)
    assert [f.id for f in tab.session.document.features][4:] == ["f7", "f5", "f6"]


def test_error_and_warning_marks_box_and_list(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    tree = window.tree
    assert tree is not None
    report = tab.session.report
    assert report is not None
    plain_part = tree.topLevelItem(0).icon(0).pixmap(18).toImage()  # type: ignore[union-attr]
    plain_sketch = tree.item_for("f5").icon(0).pixmap(18).toImage()  # type: ignore[union-attr]
    report.results["f6"].issues.append(
        Issue(FeatureState.WARNING, "Extrude 1: thin wall. Make the depth larger.")
    )
    report.results["f8"].issues.append(
        Issue(FeatureState.ERROR, "Cut 1 failed: no body. Edit the cut or its sketch.")
    )
    tree.refresh()
    colors = palette()
    cut, extrude = tree.item_for("f8"), tree.item_for("f6")
    assert cut is not None and extrude is not None
    assert cut.foreground(0).color() == QColor(colors.state_error)
    assert extrude.foreground(0).color() == QColor(colors.state_warning)
    part = tree.topLevelItem(0)
    assert part is not None and part.data(0, FID_ROLE) == PART_MARK
    assert part.icon(0).pixmap(18).toImage() != plain_part
    # The extrude's parent sketch gets a smaller mark.
    assert tree.item_for("f5").icon(0).pixmap(18).toImage() != plain_sketch  # type: ignore[union-attr]
    # Clicking the cut shows its box with the message and the edit buttons.
    edits: list[str] = []
    tree.edit_requested.connect(edits.append)
    tree._clicked(cut, 0)
    box = tree.problem_box
    assert box.isVisible() and "no body" in box.labels[0].text()
    assert box.sketch_button is not None
    box.sketch_button.click()
    assert edits == ["f7"] and not box.isVisible()
    # Clicking the part name lists every problem, errors first; a row selects its feature.
    tree._clicked(part, 0)
    rows = tree.problem_list.rows
    assert [rows.item(i).text().split(":")[0] for i in range(rows.count())] == [
        "Extrude f8",
        "Extrude f6",
    ]
    rows.itemClicked.emit(rows.item(1))
    assert tree.selected_id() == "f6" and not tree.problem_list.isVisible()
    if window.sketch_mode is not None and window.sketch_mode.is_open:
        window.sketch_mode._close()


def test_selecting_the_part_name_is_not_a_feature(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """Clicking the part name row crashed the plane highlight (owner note 2026-10-30)."""
    _open(qtbot, window)
    tree = window.tree
    assert tree is not None
    part = tree.topLevelItem(0)
    assert part is not None and part.data(0, FID_ROLE) == PART_MARK
    tree.setCurrentItem(part)  # runs the plane highlight; must not raise
    assert tree.selected_id() is None
    window._plane_selection()


def test_undo_is_off_while_a_feature_panel_is_open(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    import copy

    from fdcad.ui.commands.document import AddFeature

    tab = _open(qtbot, window)
    session = tab.session
    doc = session.document
    extra = copy.deepcopy(doc.feature("f6"))
    extra.id, extra.name = doc.new_feature_id(), "Extra"
    _roll(qtbot, tab, lambda: session.undo.push(AddFeature(session, extra)))
    assert window.undo_group.canUndo()
    window.edit_feature(extra.id)
    assert window.panel is not None and window.panel.is_editing
    # Undo here would remove the feature under the panel, and OK then failed.
    assert not window.undo_group.canUndo()
    window.undo_group.undo()
    assert any(f.id == extra.id for f in doc.features)
    _roll(qtbot, tab, window.confirm_ok)
    assert window.undo_group.canUndo()


def test_rows_follow_the_document_before_the_rebuild_ends(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    from fdcad.ui.commands.document import DeleteFeature

    tab = _open(qtbot, window)
    tree = window.tree
    assert tree is not None
    session = tab.session
    session.undo.push(DeleteFeature(session, "f8"))
    stale = tree.item_for("f8")  # the rows refill on the next turn of the event loop
    assert stale is not None
    assert tree._context_menu(session, stale) is None  # a right click must not fail
    tree._double_clicked(stale, 0)
    tree._clicked(stale, 0)
    qtbot.waitUntil(lambda: tree.item_for("f8") is None, timeout=1000)
    session.wait()


def test_up_at_the_top_does_not_pull_the_selection_back_to_the_bar(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    from fdcad.ui.commands.document import SetSuppressed

    tab = _open(qtbot, window)
    tree = window.tree
    assert tree is not None
    session = tab.session
    _roll(qtbot, tab, lambda: tree._rollback("f4"))  # the bar at the top
    bar = tree.topLevelItem(_bar_index(window))
    tree.setCurrentItem(bar)
    tree.setFocus()
    qtbot.keyClick(tree, Qt.Key.Key_Up)  # cannot go higher: nothing changes
    tree.setCurrentItem(tree.item_for("f2"))
    _roll(qtbot, tab, lambda: session.undo.push(SetSuppressed(session, "f6", True)))
    assert tree.selected_id() == "f2"


def test_moving_the_feature_above_the_bar_rolls_nothing_else_back(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    from fdcad.core.document import rollback
    from fdcad.core.sketch.model import Sketch
    from tests.core.features.test_features import add_sketch, rect

    doc, _ext = plate()  # f5 sketch, f6 extrude
    for plane in ("f3", "f4"):  # f7 on Top and f8 on Right use nothing of the plate
        s = Sketch()
        rect(s, 0, 0, 10, 10)
        add_sketch(doc, s, {"feature": plane})
    doc.rollback = "f7"  # f8 is rolled back
    tab = _open(qtbot, window, doc)
    tree = window.tree
    assert tree is not None
    before = fdef.dumps(doc)
    _roll(qtbot, tab, lambda: tree.move_feature("f7", 4))  # to the top
    assert [f.id for f in doc.features][4:] == ["f7", "f5", "f6", "f8"]
    assert rollback.rolled_back(doc) == ["f8"]  # the plate is still built
    _roll(qtbot, tab, tab.session.undo.undo)
    assert fdef.dumps(doc) == before


def test_every_feature_row_shows_its_full_name_as_a_tip(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    # Round 10a (D594): long names were cut off with no way to read them.
    tab = _open(qtbot, window)
    tree = window.tree
    assert tree is not None
    for feature in tab.session.document.features:
        item = tree.item_for(feature.id)
        if item is not None:
            assert item.toolTip(0).splitlines()[0] == feature.name
