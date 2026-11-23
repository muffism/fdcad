"""Change a fillet to a chamfer and back from the tree (TR134, D994)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.features.phase3_parts import add_feature, block_with_hole_and_boss
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_fillet_becomes_chamfer_and_back(qtbot: QtBot, window: MainWindow) -> None:
    doc, ids = block_with_hole_and_boss()
    fid = add_feature(
        doc,
        "fillet",
        {"fillet_type": "constant", "radius": Param("1", 1.0)},
        {"faces": [{"kind": "face", "name": f"{ids['boss']}/cap/end"}]},
    )
    doc.feature(fid).name = "Fillet 1"
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        window.add_session(session)
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        assert window.tree.swap_kind(fid)
    feature = session.document.feature(fid)
    assert feature.type == "chamfer" and feature.name == "Chamfer 1"
    assert session.report is not None and session.report.results[fid].state.value == "ok"
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        session.undo.undo()
    assert session.document.feature(fid).type == "fillet"
