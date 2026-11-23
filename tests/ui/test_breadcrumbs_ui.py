"""Selection breadcrumbs in the view strip (TR20, D756)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.features.solids import solids
from fdcad.core.naming.names import faces_of
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.tree.feature_tree import BODY_ROLE, FID_ROLE, PART_MARK
from tests.ui.test_body_display import _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def test_a_pick_shows_its_chain_and_crumbs_select_tree_rows(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = _open(qtbot, window)
    bar = tab.breadcrumbs
    assert not bar.isVisibleTo(tab)  # nothing picked yet
    report = tab.session.report
    assert report is not None and report.body is not None
    face = faces_of(solids(report.body.shape)[1])[0]
    window._selection_changed(tab, [face])
    assert bar.isVisibleTo(tab)
    assert [b.text() for b in bar.buttons] == ["Untitled", "Body 2", "Extrude f8", "Sketch f7"]
    tree = window.tree
    assert tree is not None
    bar.buttons[2].click()
    assert tree.selected_id() == "f8"
    bar.buttons[3].click()
    assert tree.selected_id() == "f7"
    bar.buttons[1].click()
    assert tree.selected_body() == 1
    bar.buttons[0].click()
    current = tree.currentItem()
    assert current is not None and current.data(0, FID_ROLE) == PART_MARK
    window._selection_changed(tab, [])
    assert not bar.isVisibleTo(tab)


def test_right_click_builds_the_tree_menu_of_the_crumb(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    from fdcad.ui.main_window.breadcrumbs import tree_item

    tab = _open(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    window._selection_changed(tab, [faces_of(solids(report.body.shape)[0])[0]])
    shown: list[list[str]] = []
    from fdcad.ui.main_window import breadcrumbs

    monkeypatch.setattr(
        breadcrumbs, "show_menu", lambda menu, _at: shown.append([a.text() for a in menu.actions()])
    )
    bar = tab.breadcrumbs
    body_crumb = next(c for c in bar.chain if c.kind == "body")
    assert window.tree is not None
    item = tree_item(window.tree, body_crumb)
    assert item is not None and item.data(0, BODY_ROLE) == 0
    bar.menu_requested.emit(body_crumb, bar.mapToGlobal(bar.rect().center()))
    assert shown and "Hide Body" in shown[-1]
