"""Self tapping hole type in the Hole Tool panel (TR255, D840)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.property_panel.forms.hole_form import InsertTableDialog


def test_table_dialog_shows_the_self_tapping_rule(qtbot: QtBot) -> None:
    dialog = InsertTableDialog(None, self_tap=True)
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "Self Tapping Hole Sizes"
    first = dialog.table.item(0, 0)
    assert first is not None and first.text() == "M2"
    assert dialog.rows()[0]["diameter"] == "1.6"
