"""Bodies to Part Files (TR280, D2421)."""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from fdcad.core.io import fdef
from fdcad.ui import strings
from fdcad.ui.main_window import bodies_to_files
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.features.test_features import plate
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_linked_parts_need_a_saved_part_then_are_written(
    qtbot: QtBot, window: MainWindow, tmp_path: Path
) -> None:
    doc, _ext = plate()
    path = tmp_path / "master.fdprt"
    fdef.save(doc, path)
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    assert not bodies_to_files.run(window, "linked", str(tmp_path))
    assert window.status.text() == strings.BODIES_FILES_SAVE_FIRST
    session.path = path
    out = tmp_path / "out"
    out.mkdir()
    assert bodies_to_files.run(window, "linked", str(out))
    assert [p.name for p in out.iterdir()] == ["master body 1.fdprt"]
    assert "insert_part" in (out / "master body 1.fdprt").read_text(encoding="utf-8")
    assert window.commands.actions.get("tools.bodies_to_files") is not None
