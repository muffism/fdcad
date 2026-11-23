"""Open IGES files and Heal imported bodies in the app (TR31, D760)."""

from __future__ import annotations

from pathlib import Path

from OCP.gp import gp_Trsf, gp_Vec
from OCP.TopLoc import TopLoc_Location
from pytestqt.qtbot import QtBot

from fdcad.core.features.base import FeatureState
from fdcad.ui.main_window.imports import is_import
from fdcad.ui.main_window.window import MainWindow
from tests.core.io.test_iges_import import _box_faces, _centre_z, _iges
from tests.ui.test_main_window import _folders, window

__all__ = ["_folders", "window"]


def _open_gap_file(tmp_path: Path) -> Path:
    faces = _box_faces()
    move = gp_Trsf()
    move.SetTranslation(gp_Vec(0.0, 0.0, 0.05))
    top = max(faces, key=_centre_z)
    faces = [f.Moved(TopLoc_Location(move)) if f.IsSame(top) else f for f in faces]
    path = tmp_path / "gap.iges"
    path.write_bytes(_iges(tmp_path, faces))
    return path


def test_iges_files_open_as_imports() -> None:
    assert is_import(Path("part.igs")) and is_import(Path("PART.IGES"))


def test_open_an_iges_file_then_heal_it(qtbot: QtBot, window: MainWindow, tmp_path: Path) -> None:
    path = _open_gap_file(tmp_path)
    session = window.import_flow.open_file(path)
    assert session is not None
    qtbot.waitUntil(lambda: session.report is not None, timeout=20000)
    fid = session.document.features[-1].id
    assert session.report is not None
    assert session.report.results[fid].state is FeatureState.ERROR
    assert window.tree is not None
    item = window.tree.item_for(fid)
    assert item is not None
    menu = window.tree._context_menu(session, item)
    assert menu is not None and "Heal..." in [a.text() for a in menu.actions()]
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        assert window.import_flow.heal(fid, 0.1)
    assert session.report is not None
    assert session.report.results[fid].state is not FeatureState.ERROR
    qtbot.waitUntil(lambda: "Healed with a gap of 0.1 mm" in window.status.text(), timeout=5000)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.undo()
    assert "heal_gap" not in session.document.feature(fid).params
