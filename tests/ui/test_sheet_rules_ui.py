"""The Sheet Metal Rules window (TR332, D1111)."""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.sheet_metal import flow
from fdcad.ui.sheet_metal.rules_dialog import SheetRulesDialog
from tests.core.features.sheetmetal.parts import plate, sheet_doc
from tests.ui.test_revolve_edge_axis import _folders, window
from tests.ui.test_sheet_metal_ui import _open

__all__ = ["_folders", "window"]


def test_save_a_rule_then_apply_it(qtbot: QtBot, window: MainWindow, tmp_path: Path) -> None:
    library = str(tmp_path / "rules.json")
    doc = sheet_doc(3.0, 2.0)
    plate(doc)
    tab = _open(qtbot, window, doc)

    def save(dialog: SheetRulesDialog) -> bool:
        assert dialog.save_current("Thick")
        assert dialog.list.count() == 1
        return False

    assert not flow.sheet_rules(window, library, save)
    folder = flow.folder_of(tab.session.document)
    assert folder is not None
    folder.params["thickness"] = Param("1", 1.0)

    def apply(dialog: SheetRulesDialog) -> bool:
        dialog.list.setCurrentRow(0)
        dialog.apply_picked()
        return dialog.chosen == "Thick"

    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert flow.sheet_rules(window, library, apply)
    folder = flow.folder_of(tab.session.document)
    assert folder is not None and folder.params["thickness"].value == 3.0
    assert folder.params["rule_name"] == "Thick"
    tab.session.undo.undo()
    assert "rule_name" not in flow.folder_of(tab.session.document).params  # type: ignore[union-attr]


def test_delete_needs_a_picked_rule(qtbot: QtBot, window: MainWindow, tmp_path: Path) -> None:
    doc = sheet_doc(2.0, 1.0)
    plate(doc)
    _open(qtbot, window, doc)

    def act(dialog: SheetRulesDialog) -> bool:
        assert not dialog.delete_picked() and dialog.info.text()
        assert dialog.save_current("A") and dialog.save_current("B")
        dialog.list.setCurrentRow(0)
        assert dialog.delete_picked() and dialog.list.count() == 1
        return False

    assert not flow.sheet_rules(window, str(tmp_path / "r.json"), act)
