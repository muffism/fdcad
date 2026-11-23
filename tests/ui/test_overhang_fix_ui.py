"""Fix Overhangs (TR410, D909)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param, new_document
from fdcad.core.sketch.model import Sketch
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.print_tools import overhang_fix_tool as tool
from fdcad.ui.session import DocumentSession
from tests.core.features.test_features import add_extrude, add_sketch, rect
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_adds_one_chamfer_on_the_ledge_underside(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc = new_document()
    base, ledge = Sketch(), Sketch()
    rect(base, 0, 0, 10, 10)
    rect(ledge, 0, 0, 20, 10)
    add_extrude(doc, add_sketch(doc, base, {"feature": "f2"}), 20.0)
    add_extrude(
        doc,
        add_sketch(doc, ledge, {"feature": "f2"}),
        10.0,
        start_condition="offset",
        start_offset=Param("10", 10.0),
    )
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    monkeypatch.setattr(tool, "ask_size", lambda _w, _s: 1.0)
    count = len(doc.features)
    assert tool.fix_overhangs(window)
    qtbot.waitUntil(lambda: len(session.document.features) == count + 1, timeout=30000)
    made = session.document.features[-1]
    assert made.type == "chamfer" and made.name.startswith("Overhang Chamfer")
