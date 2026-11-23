"""Tools, Part Notes (TR392, D931)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.io import fdef
from fdcad.ui.main_window import part_notes as pn
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_workflow import _folders, new_part, window  # noqa: F401  (fixtures)


def test_notes_are_saved_with_the_part_and_undo(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tab = new_part(qtbot, window)
    session = tab.session
    monkeypatch.setattr(
        pn, "run", lambda dialog: (dialog.edit.setPlainText("Change Width only."), True)[1]
    )
    assert pn.open_notes(window)
    assert pn.stored(session) == "Change Width only.\n"
    assert not pn.open_notes(window)  # the same text again: no new undo step
    path = tmp_path / "noted.fdprt"
    fdef.save(session.document, path)
    assert fdef.load(path).extra["notes"] == "Change Width only.\n"
    session.undo.undo()
    assert pn.stored(session) == "" and "notes" not in session.document.extra
