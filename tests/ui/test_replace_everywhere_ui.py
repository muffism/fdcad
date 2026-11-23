"""Replace Everywhere from the tree and from Delete (TR277, D838)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature
from fdcad.core.sketch.model import Sketch, sketch_to_data
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.tree import delete_dialog, replace_dialog
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def _spare_sketch(tab) -> str:  # type: ignore[no-untyped-def]
    doc = tab.session.document
    s = Sketch()
    s.add_line(0, 0, 10, 0)
    fid = doc.new_feature_id()
    sketch = Feature(
        fid, "sketch", "Spare", refs={"plane": {"feature": "f2"}}, data=sketch_to_data(s)
    )
    doc.features.insert(1, sketch)  # above every user
    return fid


def test_replace_then_delete_instead(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    tab, _ids = _open(qtbot, window)
    session = tab.session
    doc = session.document
    used = next(f for f in doc.features if f.type == "extrude").refs["sketch"]["feature"]
    spare = _spare_sketch(tab)
    assert spare in [f.id for f in replace_dialog.candidates(doc, used)]
    monkeypatch.setattr(replace_dialog, "ask", lambda *_a: (spare, False))
    assert replace_dialog.replace_everywhere(session, used, False, None, window.status)
    first = next(f for f in doc.features if f.type == "extrude")
    assert first.refs["sketch"]["feature"] == spare
    assert "now use Spare" in window.status.text()
    session.undo.undo()
    assert next(f for f in doc.features if f.type == "extrude").refs["sketch"]["feature"] == used
    monkeypatch.setattr(delete_dialog, "ask", lambda *_a: delete_dialog.REPLACE)
    monkeypatch.setattr(replace_dialog, "ask", lambda *_a: (spare, True))
    assert window.tree is not None
    window.tree.delete(used)
    assert not any(f.id == used for f in doc.features)
    assert next(f for f in doc.features if f.type == "extrude").refs["sketch"]["feature"] == spare
