"""STL and 3MF export options (TR182, D776)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QFileDialog
from pytestqt.qtbot import QtBot

from fdcad.core.io.export import MeshSettings
from fdcad.ui.main_window import mesh_export_dialog
from fdcad.ui.main_window.mesh_export_dialog import MeshExportDialog
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_display import _face_of, _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def test_presets_and_the_count(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    dialog = MeshExportDialog("stl", MeshSettings(), report.body.shape, window)
    qtbot.addWidget(dialog)
    assert dialog.preset.currentData() == "standard"
    qtbot.waitUntil(lambda: dialog.stats is not None, timeout=20000)
    assert "triangles" in dialog.info.text() and "kB" in dialog.info.text()
    dialog.preset.setCurrentIndex(dialog.preset.findData("coarse"))
    assert dialog.settings.deviation == pytest.approx(0.1)
    dialog.deviation.setValue(0.05)  # a typed value is a custom setting
    assert dialog.preset.currentData() == "custom"


def _export(qtbot, window, monkeypatch, tmp_path, kind, choose):  # type: ignore[no-untyped-def]  # noqa: F811
    target = tmp_path / f"out.{kind}"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))

    def fake(dialog: MeshExportDialog) -> bool:
        choose(dialog)
        return True

    monkeypatch.setattr(mesh_export_dialog, "run", fake)
    window.export(kind)
    qtbot.waitUntil(
        lambda: target.exists() and not window.feedback.running("export"), timeout=20000
    )
    return target


def test_options_are_used_and_kept_in_the_part(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tab = _open(qtbot, window)

    def text_inches(dialog: MeshExportDialog) -> None:
        dialog.format.setCurrentIndex(dialog.format.findData(True))
        dialog.unit.setCurrentIndex(dialog.unit.findData("in"))

    target = _export(qtbot, window, monkeypatch, tmp_path, "stl", text_inches)
    assert target.read_text(encoding="ascii").lstrip().startswith("solid")
    kept = tab.session.document.print_setup["mesh_export"]
    assert kept["ascii"] is True and kept["unit"] == "in"
    assert tab.session.undo.canUndo()  # kept as one undo step


def test_picked_bodies_only(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tab = _open(qtbot, window)
    tab.selection = [_face_of(tab, 1)]

    def picked(dialog: MeshExportDialog) -> None:
        dialog.bodies.setCurrentIndex(dialog.bodies.findData("picked"))

    target = _export(qtbot, window, monkeypatch, tmp_path, "3mf", picked)
    model = zipfile.ZipFile(target).read("3D/3dmodel.model").decode()
    assert model.count("<mesh>") == 1  # only the picked body (in the assembly object)


def test_largest_edge_and_the_preview(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """TR336 (D1200): the edge limit refines the count, the preview shows the mesh."""
    tab = _open(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    dialog = MeshExportDialog("stl", MeshSettings(), report.body.shape, window, tab.viewport)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: dialog.stats is not None, timeout=20000)
    plain = dialog.stats[0]
    assert "aspect ratio" in dialog.quality_info.text()
    dialog.preview.setChecked(True)
    assert "mesh_preview" in tab.viewport.print_meshes
    dialog.stats = None
    dialog.max_edge.setValue(2.0)
    dialog.count()
    qtbot.waitUntil(lambda: dialog.stats is not None, timeout=20000)
    assert dialog.stats[0] > plain
    assert dialog.settings.max_edge == pytest.approx(2.0)
    assert dialog.mesh.longest <= 2.0 + 1e-9
    dialog.reject()
    assert "mesh_preview" not in tab.viewport.print_meshes


def test_largest_aspect_ratio_is_used(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """TR336 (D2001): the aspect limit mends thin triangles in the preview."""
    tab = _open(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    dialog = MeshExportDialog("stl", MeshSettings(), report.body.shape, window)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: dialog.stats is not None, timeout=20000)
    before = dialog.mesh.worst
    dialog.stats = None
    dialog.max_aspect.setValue(2.0)
    dialog.count()
    qtbot.waitUntil(lambda: dialog.stats is not None, timeout=20000)
    assert dialog.settings.max_aspect == pytest.approx(2.0)
    assert dialog.mesh.worst <= 2.0 < before
    dialog.preset.setCurrentIndex(dialog.preset.findData("coarse"))  # presets keep it
    assert dialog.settings.max_aspect == pytest.approx(2.0)
    dialog.reject()


def test_slicer_target_says_what_it_keeps(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """TR385 (D1206)."""
    dialog = MeshExportDialog("3mf", MeshSettings(), None, window)
    qtbot.addWidget(dialog)
    assert "Bambu Studio" in dialog.slicer_support.text()
    dialog.slicer.setCurrentIndex(dialog.slicer.findData("plain"))
    assert "Any program" in dialog.slicer_support.text()
    assert dialog.settings.slicer == "plain"
