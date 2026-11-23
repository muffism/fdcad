"""Name This Item and Tools, Named Items (TR152, D2105)."""

from __future__ import annotations

import pytest
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from pytestqt.qtbot import QtBot

from fdcad.core import named_items
from fdcad.ui.main_window import named_items as ui
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_design_table_ui import _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def test_name_a_face_and_find_it_in_the_list(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tab = _open(qtbot, window)
    session = tab.session
    face = TopExp_Explorer(session.report.body.shape, TopAbs_FACE).Current()
    monkeypatch.setattr(ui, "ask_name", lambda _parent, _current: "Lid")
    assert ui.name_item(window, tab, face) == "Lid"
    assert [i["name"] for i in named_items.items(session.document)] == ["Lid"]
    window.commands.actions["tools.named_items"].trigger()
    dialog = window.named_items_dialog  # type: ignore[attr-defined]
    assert dialog.list.count() == 1
    shape = dialog.show_item(dialog.list.item(0))
    assert shape is not None and shape.IsSame(face)
    dialog.list.setCurrentRow(0)
    monkeypatch.setattr(ui, "ask_name", lambda _parent, _current: "Cover")
    assert dialog.rename_current()
    assert named_items.find(session.document, "Cover") is not None
    session.undo.undo()
    assert named_items.find(session.document, "Lid") is not None
    dialog.refresh()
    dialog.list.setCurrentRow(0)
    assert dialog.remove_current()
    assert named_items.items(session.document) == []
    dialog.close()
