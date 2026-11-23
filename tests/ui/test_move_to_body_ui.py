"""Move to Body... in the feature tree (TR155, D2107)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window import move_to_body_ui
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from fdcad.ui.strings_config import MOVE_BODY
from tests.core.test_move_to_body import _with_cut
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def test_move_a_cut_to_another_body(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc, cut = _with_cut()
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    item = window.tree.item_for(cut)
    menu = window.tree._context_menu(session, item)
    assert MOVE_BODY in [a.text() for a in menu.actions()]
    monkeypatch.setattr(move_to_body_ui, "ask_body", lambda _p, labels, _c: 1)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        assert move_to_body_ui.move_feature(window.tree, session, cut)
    assert session.document.feature(cut).params["bodies_scope"] == "selected"
    first = next(f for f in session.document.features if f.type == "extrude")
    assert not move_to_body_ui.offered(session, first.id)
    session.undo.undo()
    assert "bodies_scope" not in session.document.feature(cut).params
