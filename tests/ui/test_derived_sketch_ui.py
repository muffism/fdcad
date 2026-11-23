"""Derived Sketch, Edit Placement and Break Link (TR49, D845)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.tree import derived_sketch as ds
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_derive_move_and_break(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    tab, _ids = _open(qtbot, window)
    session = tab.session
    doc = session.document
    source = next(f for f in doc.features if f.type == "sketch")
    plane_name = next(f.name for f in doc.features if f.type == "plane")
    monkeypatch.setattr(ds, "ask_plane", lambda *_a: plane_name)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        fid = ds.make_derived(session, source.id)
    assert fid is not None and doc.feature(fid).name == "Derived Sketch 1"
    report = session.report
    assert report is not None and report.results[fid].sketch is not None
    window.sketch_mode.edit(fid)  # type: ignore[union-attr]
    assert not window.sketch_mode.is_open and "linked copy" in window.status.text()  # type: ignore[union-attr]

    def accept(dialog: ds.PlacementDialog) -> bool:
        dialog.dx.setText("5")
        return True

    monkeypatch.setattr(ds, "run", accept)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        assert ds.edit_placement(session, fid)
    assert doc.feature(fid).data["derived_place"]["dx"] == 5.0
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        assert ds.break_link(session, fid)
    broken = doc.feature(fid)
    assert "derived_from" not in broken.refs and broken.data["entities"]
