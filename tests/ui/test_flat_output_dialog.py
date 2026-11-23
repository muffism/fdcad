"""The Flat Pattern Output dialog (TR173, D1108) and quoting rows (TR172, D1106)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from fdcad.core.features.sheetmetal.export import flat_drawing
from fdcad.ui.sheet_metal.flat_output_dialog import FlatOutputDialog
from fdcad.ui.sheet_metal.flow import quote_rows
from tests.core.features.sheetmetal.test_flat_output import _result


def test_unticked_items_are_left_out(qtbot: QtBot) -> None:
    result = _result()
    dialog = FlatOutputDialog(flat_drawing(result), False)
    qtbot.addWidget(dialog)
    assert dialog.items.count() == 2 and not dialog.box.isChecked()
    dialog.items.item(1).setCheckState(Qt.CheckState.Unchecked)
    dialog.origin.setCurrentIndex(dialog.origin.findData("lower_left"))
    dialog.up_colour.setValue(3)
    options = dialog.options()
    assert options.removed == frozenset({("bend", 1)})
    assert options.origin == "lower_left" and options.up_colour == 3 and not options.box


def test_quote_rows_for_the_panel() -> None:
    rows = dict(quote_rows(_result()))
    assert rows["bends"] == "2" and rows["cut_outs"] == "0"
    assert rows["blank_area"].endswith("mm²")
