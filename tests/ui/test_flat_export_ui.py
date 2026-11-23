"""File, Export, DXF and SVG from the app (PLAN Phase 2, DECISIONS D350)."""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from fdcad.core.naming.select import is_planar_face
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.print_tools import flat_export
from fdcad.ui.strings_print import FLAT_NOTHING
from tests.ui.test_phase2_flow import _folders, plate_tab, window

__all__ = ["_folders", "window"]


def test_export_commands_are_in_the_export_menu(window: MainWindow) -> None:
    for cid in ("file.export_dxf", "file.export_svg"):
        assert cid in window.commands.actions


def test_nothing_picked_asks_for_a_face_or_sketch(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ext = plate_tab(qtbot, window)
    tab.selection = []
    assert window.tree is not None
    window.tree.clearSelection()
    assert flat_export.export(window, "dxf", "unused.dxf") is None
    assert window.status.text() == FLAT_NOTHING


def test_picked_face_exports_as_svg(qtbot: QtBot, window: MainWindow, tmp_path: Path) -> None:
    tab, ext = plate_tab(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    face = report.body.face(f"{ext}/cap/end")
    assert face is not None and is_planar_face(face)
    tab.selection = [face]
    target = tmp_path / "top.svg"
    job = flat_export.export(window, "svg", str(target))
    assert job is not None
    qtbot.waitUntil(lambda: "Exported top.svg" in window.status.text(), timeout=20000)
    assert 'width="50mm" height="50mm"' in target.read_text(encoding="utf-8")


def test_sketch_in_the_tree_exports_as_dxf(
    qtbot: QtBot, window: MainWindow, tmp_path: Path
) -> None:
    tab, _ext = plate_tab(qtbot, window)
    tab.selection = []
    sketch = next(f for f in tab.session.document.features if f.type == "sketch")
    assert window.tree is not None
    window.tree.select(sketch.id)
    target = tmp_path / "sketch.dxf"
    assert flat_export.export(window, "dxf", str(target)) is not None
    qtbot.waitUntil(lambda: "Exported sketch.dxf" in window.status.text(), timeout=20000)
    assert target.read_text(encoding="utf-8").count("\nLINE\n") == 4
