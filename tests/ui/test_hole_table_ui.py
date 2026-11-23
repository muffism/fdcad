"""Tools, Hole Table (TR316, D924)."""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from fdcad.core.hole_table import rows
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.units import UnitSystem
from fdcad.ui.main_window.hole_table import HoleTableDialog
from tests.core.features.test_hole import add_hole, on_top


def test_table_copy_and_save(qtbot: QtBot, tmp_path: Path) -> None:
    doc, _ext, sk, top = on_top([(10, 10), (40, 40)])
    add_hole(doc, sk, face=top, diameter=5.0, depth=6.0)
    found = rows(doc, rebuild(doc))
    dialog = HoleTableDialog(found, UnitSystem.MM, str(tmp_path))
    qtbot.addWidget(dialog)
    assert dialog.table.rowCount() == 2 and dialog.table.item(0, 0).text() == "A1"
    assert dialog.text().splitlines()[0].startswith("Tag\tFeature")
    out = tmp_path / "holes.csv"
    assert dialog.save(str(out)) and out.read_text(encoding="utf-8").count("\n") == 3
    dialog.copy()
    assert "clipboard" in dialog.message.text()


def test_empty_table(qtbot: QtBot, tmp_path: Path) -> None:
    dialog = HoleTableDialog([], UnitSystem.MM, str(tmp_path))
    qtbot.addWidget(dialog)
    assert "no holes" in dialog.message.text()
