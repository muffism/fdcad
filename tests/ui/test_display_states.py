"""Display states (TR88, D1608)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core import configurations as configs
from fdcad.core import display_states as ds
from fdcad.core.document.model import new_document
from fdcad.core.io import fdef
from fdcad.ui.main_window.display_states_ui import DisplayStatesDialog, after_configuration
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_modes import _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def test_save_apply_delete_and_links() -> None:
    doc = new_document()
    doc.appearance["hidden_bodies"] = ["f5/face0"]
    doc.appearance["bodies"] = {"1": "#112233"}
    assert ds.save(doc, "  Inside  view ") == "Inside view"
    doc.appearance.pop("hidden_bodies")
    doc.appearance["bodies"] = {"1": "#445566"}
    doc.appearance["faces"] = {"x": "#000000"}
    assert ds.apply(doc, "Inside view")
    assert doc.appearance["hidden_bodies"] == ["f5/face0"]
    assert doc.appearance["bodies"] == {"1": "#112233"}
    assert doc.appearance["faces"] == {"x": "#000000"}  # not part of a state
    with pytest.raises(ds.DisplayStateError):
        ds.check_name(doc, "inside VIEW")
    with pytest.raises(ds.DisplayStateError):
        ds.check_name(doc, "   ")
    ds.link(doc, "Default", "Inside view")
    ds.link(doc, "Other", "No such state")
    again = fdef.loads(fdef.dumps(doc))
    assert ds.names(again) == ["Inside view"] and ds.linked(again, "Default") == "Inside view"
    assert ds.linked(again, "Other") is None
    ds.delete(doc, "Inside view")
    assert ds.KEY not in doc.appearance
    assert not ds.apply(doc, "Inside view")


def test_dialog_steps_are_undoable(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    doc = tab.session.document
    dialog = DisplayStatesDialog(window, tab)
    qtbot.addWidget(dialog)
    assert not dialog.buttons["Apply"].isEnabled()
    dialog.ask_name = lambda *_a: ("All Shown", True)
    assert dialog.save()
    assert ds.names(doc) == ["All Shown"]
    window.body_display.set_hidden(tab, [1], True)
    assert doc.appearance.get("hidden_bodies")
    dialog.list.setCurrentRow(0)
    assert dialog.apply_selected()
    assert "hidden_bodies" not in doc.appearance
    tab.session.undo.undo()
    assert doc.appearance.get("hidden_bodies")
    assert dialog.link_selected()
    assert ds.linked(doc, configs.active_name(doc)) == "All Shown"
    assert "shows All Shown" in dialog.message.text()
    assert after_configuration(tab.session, configs.active_name(doc))
    assert "hidden_bodies" not in doc.appearance
    assert dialog.unlink() and dialog.delete_selected()
    assert ds.names(doc) == []
