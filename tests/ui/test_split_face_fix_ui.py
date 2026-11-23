"""The fix for a picked face that split ties two depths in one undo step (D2628)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.rebuild.test_split_faces import _two_plates
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_tie_fix_is_one_undo_step(qtbot: QtBot, window: MainWindow) -> None:
    doc, a, b, hole = _two_plates()
    doc.feature(b).params["depth"] = Param("12", 12.0)
    error = next(i for i in rebuild(doc)[hole].issues if i.state is FeatureState.ERROR)
    fix = next(f for f in error.fixes if f"Extrude {a}'s" in f.label)
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        window.add_session(session)
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        window.apply_fix(hole, fix)
    (variable,) = session.document.variables
    depth = session.document.feature(b).params["depth"]
    assert isinstance(depth, Param) and depth.expr == f"={variable.name}"
    assert session.report is not None
    assert session.report.results[hole].state is FeatureState.OK
    session.undo.undo()
    assert session.document.variables == []
    depth = session.document.feature(b).params["depth"]
    assert isinstance(depth, Param) and depth.expr == "12"
