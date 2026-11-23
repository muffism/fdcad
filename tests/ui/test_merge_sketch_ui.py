"""Merge Into Sketch from the feature tree (TR122 item 1, D986)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Sketch, sketch_from_data
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from fdcad.ui.tree import merge_sketch
from tests.core.features.phase3_parts import add_sketch, rect
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_merge_a_loose_sketch_into_another(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fdcad.core.document.model import new_document

    doc = new_document()
    a, b = Sketch(), Sketch()
    rect(a, 0, 0, 10, 10)
    b.add_circle(30, 30, 5)
    first = add_sketch(doc, a, {"feature": "f2"})
    second = add_sketch(doc, b, {"feature": "f2"})
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    assert merge_sketch.same_plane_sketches(session, second) == [first]
    monkeypatch.setattr(merge_sketch, "ask_target", lambda _s, _f, _p: first)
    assert window.tree.merge_sketch(second)
    ids = [f.id for f in session.document.features]
    assert second not in ids
    kept = sketch_from_data(session.document.feature(first).data)
    assert sum(1 for e in kept.entities.values() if type(e).__name__ == "Circle") == 1
    session.undo.undo()
    assert second in [f.id for f in session.document.features]
