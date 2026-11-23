"""Lay Face Flat, the build volume overlay and exports in print orientation
(PLAN Phase 2, DECISIONS D353)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.io import fdef
from fdcad.core.printing.profiles import PrinterProfile
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.preferences import print_settings
from fdcad.ui.print_tools.build_volume import BuildVolume
from fdcad.ui.strings_print import ORIENT_CLEARED, ORIENT_NOT_FLAT, ORIENT_PICK, ORIENT_SET
from tests.ui.test_phase2_flow import _folders, plate_tab, top_edges, window

__all__ = ["_folders", "window"]


def _side_face(tab: DocumentTab) -> object:
    from fdcad.core.features.face_picks import outward_normal
    from fdcad.core.printing.orientation import faces_of

    report = tab.session.report
    assert report is not None and report.body is not None
    for face in faces_of(report.body.shape):
        normal = outward_normal(face)
        if normal is not None and abs(normal[0] - 1.0) < 1e-9:
            return face
    raise AssertionError("no side face")


def test_lay_flat_is_one_undoable_step_that_keeps_the_model(
    qtbot: QtBot, window: MainWindow, tmp_path: Path
) -> None:
    tab, _ext = plate_tab(qtbot, window)
    report = tab.session.report
    tab.selection = [_side_face(tab)]
    window.commands.actions["print.lay_flat"].trigger()
    assert window.status.text() == ORIENT_SET
    ref = tab.session.document.print_setup["down_face"]
    assert ref["kind"] == "face" and ref["name"]
    assert tab.session.report is report  # no rebuild: the model is unchanged
    path = tmp_path / "oriented.fdef"
    tab.session.save(path)
    assert fdef.load(path).print_setup["down_face"] == ref
    tab.session.undo.undo()
    assert tab.session.document.print_setup["down_face"] is None
    tab.session.undo.redo()
    assert tab.session.document.print_setup["down_face"] == ref
    window.commands.actions["print.clear_orientation"].trigger()
    assert tab.session.document.print_setup["down_face"] is None
    assert window.status.text() == ORIENT_CLEARED
    assert tab.session.undo.count() == 2


def test_lay_flat_refuses_edges_and_waits_without_a_pick(qtbot: QtBot, window: MainWindow) -> None:
    tab, ext = plate_tab(qtbot, window)
    tab.selection = [top_edges(tab, ext)[0]]
    window.commands.actions["print.lay_flat"].trigger()
    assert window.status.text() == ORIENT_NOT_FLAT
    assert tab.session.undo.count() == 0
    tab.selection = []
    window.commands.actions["print.lay_flat"].trigger()
    assert window.status.text() == ORIENT_PICK
    assert window.print_orientation.waiting is tab
    window.print_orientation._picked([_side_face(tab)])
    assert window.print_orientation.waiting is None
    assert tab.session.document.print_setup["down_face"] is not None


def test_a_pick_for_another_tool_does_not_lay_a_face_flat(qtbot: QtBot, window: MainWindow) -> None:
    """Lay Face Flat waiting for a pick stops when a feature panel takes over."""
    tab, _ext = plate_tab(qtbot, window)
    tab.selection = []
    window.commands.actions["print.lay_flat"].trigger()
    assert window.print_orientation.waiting is tab
    window.commands.trigger("feature.fillet")
    assert window.editing == "feature"
    window.print_orientation._picked([_side_face(tab)])
    assert window.print_orientation.waiting is None
    assert (tab.session.document.print_setup or {}).get("down_face") is None
    assert tab.session.undo.count() == 0
    assert window.panel is not None
    window.panel.reject()


def test_build_volume_warns_when_the_part_does_not_fit(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ext = plate_tab(qtbot, window)
    volume = window.build_volume
    assert isinstance(volume, BuildVolume)
    action = window.commands.actions["evaluate.build_volume"]
    action.trigger()
    assert action.isChecked()
    qtbot.waitUntil(lambda: "fits Generic printer" in window.status.text(), timeout=20000)
    layers = tab.viewport.print_layers  # type: ignore[attr-defined]
    assert len(layers["build_volume"]) == 1 and len(layers["build_volume_bed"]) == 1
    small = PrinterProfile("Tiny", bed_x=30, bed_y=30, height=30)
    print_settings.set_profiles(window.settings, [small], "Tiny")
    volume.refresh()
    qtbot.waitUntil(lambda: "does not fit Tiny" in window.status.text(), timeout=20000)
    assert "(X, Y too large)" in window.status.text()
    action.trigger()
    assert layers["build_volume"] == [] and layers["build_volume_bed"] == []


def test_build_volume_follows_the_orientation(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ext = plate_tab(qtbot, window)
    print_settings.set_profiles(
        window.settings, [PrinterProfile("Flat", bed_x=100, bed_y=100, height=20)], "Flat"
    )
    window.commands.actions["evaluate.build_volume"].trigger()
    qtbot.waitUntil(lambda: "fits Flat" in window.status.text(), timeout=20000)
    tab.selection = [_side_face(tab)]
    window.commands.actions["print.lay_flat"].trigger()  # stands the plate up: 50 mm tall
    qtbot.waitUntil(lambda: "does not fit Flat" in window.status.text(), timeout=20000)
    assert "(Z too large)" in window.status.text()


@pytest.mark.parametrize("kind", ["stl", "3mf"])
def test_mesh_exports_follow_the_orientation(
    qtbot: QtBot,
    window: MainWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    from fdcad.core.io.mesh_import import read_mesh

    tab, _ext = plate_tab(qtbot, window)
    tab.selection = [_side_face(tab)]
    window.commands.actions["print.lay_flat"].trigger()
    target = tmp_path / f"part.{kind}"
    monkeypatch.setattr(
        "fdcad.ui.main_window.window.QFileDialog.getSaveFileName",
        lambda *_a, **_k: (str(target), ""),
    )
    window.export(kind)
    qtbot.waitUntil(lambda: target.exists() and "part." in window.status.text(), timeout=20000)
    mesh = read_mesh(target.read_bytes(), kind)
    lo, hi = mesh.vertices.min(axis=0), mesh.vertices.max(axis=0)
    assert lo[2] == pytest.approx(0, abs=1e-4)
    assert hi[2] - lo[2] == pytest.approx(50, abs=1e-3)  # the 50 mm side now stands up
