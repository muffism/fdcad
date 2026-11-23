"""Overlapping bodies on export (TR411, D907)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import new_document
from fdcad.core.sketch.model import Sketch
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.features.test_features import add_extrude, add_sketch, rect
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_stl_export_says_which_bodies_overlap(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc = new_document()
    a, b = Sketch(), Sketch()
    rect(a, 0, 0, 10, 10)
    rect(b, 5, 0, 15, 10)
    add_extrude(doc, add_sketch(doc, a, {"feature": "f2"}), 10.0)
    add_extrude(doc, add_sketch(doc, b, {"feature": "f2"}), 10.0, merge=False)
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    said: list[str] = []
    monkeypatch.setattr(window.feedback, "flash", lambda message: said.append(message))
    window.export("stl", tmp_path / "two.stl")
    qtbot.waitUntil(lambda: bool(said), timeout=60000)
    assert "Bodies 1 and 2" in said[0] and (tmp_path / "two.stl").exists()
