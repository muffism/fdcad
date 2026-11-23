"""Display mode and transparency per body (TR216, D1606)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.body_modes import KEY, body_modes, with_body_mode
from fdcad.core.io import fdef
from fdcad.ui.main_window import body_modes_ui as bm
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.features.test_multibody import two_blocks
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def _open(qtbot: QtBot, window: MainWindow) -> DocumentTab:  # noqa: F811
    doc, _first, _second, _body = two_blocks(gap=10.0)
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = window.add_session(session)
    return tab


def test_modes_are_kept_per_body_and_saved(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    doc = tab.session.document
    body = tab.session.report.body  # type: ignore[union-attr]
    assert body_modes(doc, body) == [("", 0.0), ("", 0.0)]
    assert bm.set_mode(tab, 1, mode="wireframe")
    assert bm.set_mode(tab, 0, transparency=0.5)
    assert body_modes(doc, body) == [("", 0.5), ("wireframe", 0.0)]
    assert not bm.set_mode(tab, 1, mode="wireframe")  # no change, no undo step
    again = fdef.loads(fdef.dumps(doc))
    assert body_modes(again, body) == [("", 0.5), ("wireframe", 0.0)]
    solids = bm.solids_with_modes(tab)
    assert [(m, t) for _s, m, t in solids] == [("", 0.5), ("wireframe", 0.0)]
    tab.session.undo.undo()
    tab.session.undo.undo()
    assert KEY not in doc.appearance


def test_back_to_default_drops_the_entry(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    doc = tab.session.document
    body = tab.session.report.body  # type: ignore[union-attr]
    bm.set_mode(tab, 0, mode="shaded")
    assert with_body_mode(doc, body, 0, mode="") == {}
    assert with_body_mode(doc, body, 5, mode="shaded") == doc.appearance[KEY]


def test_tree_menu_offers_modes_and_window_routes_them(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = _open(qtbot, window)
    assert window.tree is not None
    menu = window.tree._body_menu(0)
    sub = next(a.menu() for a in menu.actions() if a.objectName() == "body_display_mode")
    labels = [a.text() for a in sub.actions()]
    assert labels == list(bm.MODE_LABELS.values())
    assert sub.actions()[0].isChecked()
    sub.actions()[3].trigger()  # Wireframe
    body = tab.session.report.body  # type: ignore[union-attr]
    assert body_modes(tab.session.document, body)[0] == ("wireframe", 0.0)
