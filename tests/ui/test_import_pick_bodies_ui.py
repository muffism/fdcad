"""Pick Bodies after inserting a STEP file (TR302 item 2, D1203)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog
from pytestqt.qtbot import QtBot

from fdcad.core.features.solids import solids
from fdcad.core.io.export import export_step
from fdcad.ui import strings_import
from fdcad.ui.main_window import body_pick_dialog
from fdcad.ui.main_window.body_pick_dialog import BodyPickDialog
from fdcad.ui.main_window.window import MainWindow
from tests.core.io.test_3mf_conformance import _two_boxes
from tests.ui.test_phase2_flow import _folders, plate_tab, window

__all__ = ["_folders", "window"]


def test_insert_offers_the_pick_and_untick_leaves_a_body_out(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "two.step"
    export_step(_two_boxes(), path)
    tab, _ext = plate_tab(qtbot, window)
    session = tab.session
    before = len(solids(session.report.body.shape)) if session.report and session.report.body else 0
    seen: list[BodyPickDialog] = []

    def untick_first(dialog: BodyPickDialog) -> bool:
        seen.append(dialog)
        assert dialog.list.count() == 2
        assert "step_pick" in tab.viewport.print_layers  # the preview
        dialog.list.item(0).setCheckState(Qt.CheckState.Unchecked)
        assert len(tab.viewport.print_layers["step_pick"]) == 1
        return True

    monkeypatch.setattr(body_pick_dialog, "run", untick_first)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(path), ""))
    window.import_flow.insert_dialog("step")
    qtbot.waitUntil(lambda: bool(seen), timeout=30000)
    feature = session.document.features[-1]
    assert feature.params["keep_bodies"] == "2"
    qtbot.waitUntil(
        lambda: (
            session.report is not None
            and feature.id in session.report.results
            and session.report.body is not None
            and len(solids(session.report.body.shape)) == before + 1
        ),
        timeout=30000,
    )
    assert tab.viewport.print_layers["step_pick"] == []  # the preview is gone
    assert window.tree is not None
    item = window.tree.item_for(feature.id)
    assert item is not None
    menu = window.tree._context_menu(session, item)
    assert menu is not None
    assert strings_import.PICK_BODIES in [a.text() for a in menu.actions()]
