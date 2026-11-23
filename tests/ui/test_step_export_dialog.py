"""STEP export options in the app (TR302 item 1, D1202)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QFileDialog
from pytestqt.qtbot import QtBot

from fdcad.core.io.step_import import read_step
from fdcad.core.io.step_options import StepOptions
from fdcad.ui.main_window import step_export_dialog
from fdcad.ui.main_window.step_export_dialog import StepExportDialog
from fdcad.ui.main_window.window import MainWindow
from tests.core.features.test_features import volume
from tests.ui.test_body_display import _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def _export(qtbot, window, monkeypatch, tmp_path, choose):  # type: ignore[no-untyped-def]  # noqa: F811
    target = tmp_path / "out.step"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))

    def fake(dialog: StepExportDialog) -> bool:
        choose(dialog)
        return True

    monkeypatch.setattr(step_export_dialog, "run", fake)
    window.export("step")
    qtbot.waitUntil(lambda: not window.feedback.running("export"), timeout=30000)
    return target


def test_per_body_files_leave_out_hidden_bodies_and_keep_the_choice(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tab = _open(qtbot, window)
    window.body_display.rename(tab, 0, "Left")
    window.body_display.from_tree("hide", 1)

    def per_body_inches(dialog: StepExportDialog) -> None:
        dialog.unit.setCurrentIndex(dialog.unit.findData("in"))
        dialog.per_body.setChecked(True)

    _export(qtbot, window, monkeypatch, tmp_path, per_body_inches)
    files = sorted(p.name for p in tmp_path.glob("*.step"))
    assert files == ["out_Left.step"]  # the hidden body is left out
    text = (tmp_path / "out_Left.step").read_text(encoding="latin-1")
    assert "INCH" in text and "'Left'" in text
    kept = StepOptions.from_data(tab.session.document.print_setup["step_export"])
    assert kept.unit == "in" and kept.per_body

    def with_hidden(dialog: StepExportDialog) -> None:
        assert dialog.per_body.isChecked()  # the kept choice
        dialog.per_body.setChecked(False)
        dialog.hidden.setChecked(True)

    target = _export(qtbot, window, monkeypatch, tmp_path, with_hidden)
    both = read_step(target.read_bytes()).shape
    report = tab.session.report
    assert report is not None and report.body is not None
    assert volume(both) == pytest.approx(volume(report.body.shape), rel=1e-6)
