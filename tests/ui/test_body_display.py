"""Isolate, hide and show bodies in the app (PHASE3_SPEC P3.4 item 6, D116 item 4, D410):
the I, H, Shift+Tab and Ctrl+Shift+Tab commands and the Solid Bodies folder menu."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.body_visibility import hidden_names
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.naming.names import faces_of
from fdcad.ui.input.commands import BY_ID, ShortcutMap
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.session import DocumentSession
from fdcad.ui.tree.feature_tree import BODY_ROLE
from tests.core.features.test_multibody import BLOCK, two_blocks
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def _open(qtbot: QtBot, window: MainWindow) -> DocumentTab:  # noqa: F811
    doc, _first, _second, _body = two_blocks(gap=10.0)
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = window.add_session(session)
    return tab


def _face_of(tab: DocumentTab, index: int):  # type: ignore[no-untyped-def]
    report = tab.session.report
    assert report is not None and report.body is not None
    return faces_of(solids(report.body.shape)[index])[0]


def _shown_volume(tab: DocumentTab) -> float:
    shape = tab.shown_part()
    return 0.0 if shape is None else volume_of(shape)


def _body_row(window: MainWindow, index: int):  # type: ignore[no-untyped-def]  # noqa: F811
    assert window.tree is not None
    return next(i for i in window.tree.all_items() if i.data(0, BODY_ROLE) == index)


def test_commands_and_keys(window: MainWindow) -> None:  # noqa: F811
    keys, mac = ShortcutMap(), ShortcutMap(mac=True)
    assert keys.keys("view.isolate") == ["I"]
    assert keys.keys("view.hide_show") == ["H"]
    assert keys.keys("view.show_hovered") == ["Shift+Tab"]
    assert keys.keys("view.show_all_bodies") == ["Ctrl+Shift+Tab"]
    assert mac.keys("view.show_all_bodies") == ["Meta+Shift+Tab"]  # SHORTCUTS.md 1.2.5
    for cid in ("view.isolate", "view.show_hovered", "view.show_all_bodies"):
        assert BY_ID[cid].group == "View" and cid in window.commands.actions


def test_hide_and_show_selected_bodies_with_undo(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = _open(qtbot, window)
    session = tab.session
    tab.selection = [_face_of(tab, 1)]
    assert window.hide_or_show()
    assert abs(_shown_volume(tab) - BLOCK) < 1e-6
    assert window.tree is not None and window.tree.hidden_bodies() == {1}
    assert "Body 2 is hidden" in window.status.text()
    assert session.is_dirty  # saved in the part, on the undo list
    session.undo.undo()
    assert hidden_names(session.document) == set()
    session.undo.redo()
    # H on the hidden body's tree row shows it again.
    tab.selection = []
    window.tree.setCurrentItem(_body_row(window, 1))
    assert window.tree.selected_body() == 1
    assert window.hide_or_show()
    assert hidden_names(session.document) == set()
    assert abs(_shown_volume(tab) - 2 * BLOCK) < 1e-6


def test_isolate_and_show_all(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    session = tab.session
    tab.selection = [_face_of(tab, 0)]
    window.body_display.isolate()
    assert tab.isolated is not None
    assert abs(_shown_volume(tab) - BLOCK) < 1e-6
    assert session.undo.count() == 0  # a view state, not a change to the part
    window.body_display.isolate()  # I again: back to every body
    assert tab.isolated is None
    assert abs(_shown_volume(tab) - 2 * BLOCK) < 1e-6
    # Nothing picked: a message says what to do.
    tab.selection = []
    window.body_display.isolate()
    assert "Select a face" in window.status.text()
    # Hide both, isolate, then Ctrl+Shift+Tab shows everything in one undo step.
    tab.selection = [_face_of(tab, 0), _face_of(tab, 1)]
    window.body_display.isolate()
    assert window.hide_or_show()
    assert tab.shown_part() is None
    window.body_display.show_all()
    assert tab.isolated is None
    assert hidden_names(session.document) == set()
    assert "Showing 2 hidden bodies" in window.status.text()
    session.undo.undo()
    assert len(hidden_names(session.document)) == 2
    window.body_display.show_all()
    window.body_display.show_all()
    assert window.status.text() == "No bodies are hidden."


def test_show_hovered_body(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    tab.selection = [_face_of(tab, 1)]
    assert window.hide_or_show()
    # Offscreen there is no 3D view to point at.
    window.body_display.show_hovered()
    assert "Point at a hidden body" in window.status.text()
    # A ray that misses the hidden body (it passes over block A only).
    window.body_display.show_hovered(((10.0, 10.0, 100.0), (0.0, 0.0, -1.0)))
    qtbot.waitUntil(lambda: "No hidden body under the cursor" in window.status.text())
    # A ray straight down onto block B (x 30..50) shows it again.
    window.body_display.show_hovered(((40.0, 10.0, 100.0), (0.0, 0.0, -1.0)))
    qtbot.waitUntil(lambda: "Body 2 is shown again" in window.status.text())
    assert hidden_names(tab.session.document) == set()


def test_solid_bodies_folder_menu(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    tree = window.tree
    assert tree is not None and tree.session is tab.session

    def actions(index: int) -> dict[str, object]:
        menu = tree._context_menu(tab.session, _body_row(window, index))
        assert menu is not None
        return {a.text(): a for a in menu.actions()}

    folder = actions(-1)
    assert list(folder) == ["Show All Hidden Bodies"]
    row = actions(0)
    assert list(row) == [
        "Hide Body",
        "Make Body See Through",  # TR21
        "Isolate",
        "Lock Body",  # TR269
        "Transform Handles",
        "Rename Body...",  # TR183
        "Display Mode",  # TR216
        "Transparency...",
        "Print Role",  # TR382
        "Print Settings...",  # TR383
        "Feature History",  # TR153
        "Move to Folder...",  # TR153 (D2106)
        "Show All Hidden Bodies",
    ]
    row["Hide Body"].trigger()  # type: ignore[attr-defined]
    assert tree.hidden_bodies() == {0}
    hidden_row = actions(0)
    assert list(hidden_row) == [
        "Show Body",
        "Rename Body...",
        "Print Role",
        "Print Settings...",
        "Feature History",
        "Move to Folder...",
        "Show All Hidden Bodies",
    ]
    hidden_row["Show Body"].trigger()  # type: ignore[attr-defined]
    assert tree.hidden_bodies() == set()
    actions(1)["Isolate"].trigger()  # type: ignore[attr-defined]
    assert tab.isolated is not None and abs(_shown_volume(tab) - BLOCK) < 1e-6
    actions(-1)["Show All Hidden Bodies"].trigger()  # type: ignore[attr-defined]
    assert tab.isolated is None


def test_isolate_leaves_out_hidden_bodies_and_one_body_message(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """Round 10c: I on a face of a hidden body isolated it and the view went empty."""
    tab = _open(qtbot, window)
    face = _face_of(tab, 0)
    tab.selection = [face]
    assert window.hide_or_show()  # Body 1 hidden; its face is still selected
    tab.selection = [face]
    window.body_display.isolate()
    assert tab.isolated is None
    assert "not hidden" in window.status.text()
    tab.selection = [face, _face_of(tab, 1)]
    window.body_display.isolate()  # only the shown body is isolated
    assert tab.isolated is not None and abs(_shown_volume(tab) - BLOCK) < 1e-6
    window.body_display.show_all()
    assert window.status.text() == "Showing the hidden body."


def test_new_section_cuts_through_the_shown_bodies(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """Round 10c: a new section went through the middle of every body, hidden ones too."""
    from fdcad.ui.section.tool import part_centre

    tab = _open(qtbot, window)
    assert part_centre(tab) == pytest.approx((25.0, 10.0, 5.0))
    tab.selection = [_face_of(tab, 1)]
    assert window.hide_or_show()  # Body 2 (x 30 to 50) hidden
    assert part_centre(tab) == pytest.approx((10.0, 10.0, 5.0))


def test_escape_leaves_isolate(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """Audit D11 item 3 (D719): T12.4 says Isolate lasts until I or Esc."""
    tab = _open(qtbot, window)
    tab.selection = [_face_of(tab, 0)]
    window.body_display.isolate()
    assert tab.isolated is not None
    window._escape()
    assert tab.isolated is None


@pytest.mark.parametrize("look", ["hidden", "transparent", "wireframe"])
def test_isolate_draws_the_other_bodies(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    look: str,
) -> None:
    """TR99 (D939): the other bodies are hidden, see through or edges only."""
    window.settings.isolate_others = look
    tab = _open(qtbot, window)
    tab.selection = [_face_of(tab, 0)]
    window.body_display.isolate()
    assert tab.isolate_look == look
    assert abs(_shown_volume(tab) - BLOCK) < 1e-6  # only the isolated body is picked
    others = tab.isolate_others()
    assert others is not None and abs(volume_of(others) - BLOCK) < 1e-6
    view_look = getattr(tab.viewport, "isolate_look", None)
    if view_look is not None:
        assert view_look == look
    window.body_display.isolate()  # I again: back to normal
    assert tab.isolate_others() is None
    if view_look is not None:
        assert tab.viewport.isolate_look == "hidden"
    window.settings.isolate_others = "hidden"


def test_isolate_look_preference(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from PySide6.QtCore import QSettings

    from fdcad.ui.preferences.settings import Settings

    settings = Settings(QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    assert settings.isolate_others == "hidden"
    settings.isolate_others = "wireframe"
    assert settings.isolate_others == "wireframe"
    settings.isolate_others = "nonsense"
    assert settings.isolate_others == "hidden"
