"""STEP import in the main window (PHASE3_SPEC P3.5): open a STEP file as a new part,
insert one into the open part as one undoable step, the import report in the
status bar, and the file's colours sent to the view."""

from __future__ import annotations

from pathlib import Path

from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from pytestqt.qtbot import QtBot

from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import compound, solids
from fdcad.core.naming.names import faces_of
from fdcad.samples.step_source import colored_step_bytes
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.viewport.references import face_colors
from tests.ui.test_phase2_flow import _folders, plate_tab, window

__all__ = ["_folders", "window"]


def _step_file(tmp_path: Path, loose: bool = False) -> Path:
    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    shape = compound(faces_of(box)) if loose else box
    path = tmp_path / "block.step"
    path.write_bytes(colored_step_bytes(shape, "#22AA44"))
    return path


def test_open_step_makes_a_new_part(qtbot: QtBot, window: MainWindow, tmp_path: Path) -> None:
    path = _step_file(tmp_path, loose=True)
    before = window.tabs.count()
    window.open_path(path)
    assert window.tabs.count() == before + 1
    tab = window.tabs.currentWidget()
    assert isinstance(tab, DocumentTab)
    session = tab.session
    qtbot.waitUntil(lambda: session.report is not None and session.report.body is not None)
    assert session.path is None  # a new, unsaved part
    feature = session.document.features[-1]
    assert feature.type == "import_step"
    report = session.report
    assert report is not None
    assert report.results[feature.id].state is FeatureState.OK
    qtbot.waitUntil(lambda: "Joined 6 open surface pieces" in window.status.text())
    colors = face_colors(report, session.document)
    assert len(colors) == 6 and {c for _f, c in colors} == {"#22AA44"}


def test_open_step_goes_in_recent_and_opens_once(
    qtbot: QtBot, window: MainWindow, tmp_path: Path
) -> None:
    """Audit C item 18 (D741): a STEP file was not added to Open Recent, and opening it
    again made a second part."""
    path = _step_file(tmp_path)
    window.open_path(path)
    count = window.tabs.count()
    assert window.settings.recent_files[0] == str(path)
    tab = window.tabs.currentWidget()
    assert isinstance(tab, DocumentTab)
    qtbot.waitUntil(lambda: tab.session.report is not None)
    window.open_path(path)
    assert window.tabs.count() == count


def test_insert_step_is_one_undo_step(qtbot: QtBot, window: MainWindow, tmp_path: Path) -> None:
    tab, _ext = plate_tab(qtbot, window)
    session = tab.session
    path = _step_file(tmp_path)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        fid = window.import_flow.insert(path)
    assert fid is not None
    doc = session.document
    assert doc.features[-1].id == fid and "b1" in doc.embedded
    qtbot.waitUntil(lambda: "block.step imported" in window.status.text())
    report = session.report
    assert report is not None and report.body is not None
    assert len(solids(report.body.shape)) == 2
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.undo()
    assert all(f.id != fid for f in doc.features)
    assert doc.embedded == {}
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.redo()
    assert doc.features[-1].id == fid and "b1" in doc.embedded


def test_import_command_is_in_the_insert_menu(window: MainWindow) -> None:
    assert "feature.import_step" in BY_ID
    action = window.commands.actions["feature.import_step"]
    assert action.text() == "Import STEP Body"
