"""File, Export, Batch Export (TR368, D904)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param, Variable
from fdcad.core.units import Kind
from fdcad.ui.main_window import export_variants as ev
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_configurations_ui import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_every_combination_is_written(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tab = _open(qtbot, window)
    doc = tab.session.document
    doc.variables.append(Variable("depth", Kind.LENGTH, "10", 10.0))
    ext = next(f for f in doc.features if f.type == "extrude")
    ext.params["depth"] = Param("depth", 10.0)

    def fill(dialog: ev.BatchExportDialog) -> bool:
        row = next(
            i for i in range(dialog.table.rowCount()) if dialog.table.item(i, 0).text() == "depth"
        )
        dialog.table.item(row, 1).setText("4, 6")
        dialog.kind.setCurrentIndex(dialog.kind.findData("step"))
        dialog.template.setText("{part} d{depth}")
        dialog.folder.setText(str(tmp_path))
        return True

    monkeypatch.setattr(ev, "run", fill)
    job = ev.batch_export(window)
    assert job is not None
    qtbot.waitUntil(lambda: len(list(tmp_path.glob("*.step"))) == 2, timeout=30000)
    names = sorted(p.name for p in tmp_path.glob("*.step"))
    assert names[0].endswith("d4.step") and names[1].endswith("d6.step")
