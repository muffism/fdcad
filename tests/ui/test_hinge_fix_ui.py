"""Move the hinge to the edge where its bodies meet, from the error's button (D2627)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.features.base import FeatureState
from fdcad.core.features.fixes import ACTIONS
from fdcad.ui.main_window.window import FIX_ACTIONS, MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.features.test_hinge import P, _hinge, _leaves, _own_extrude
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_the_window_applies_every_fix_the_core_offers() -> None:
    assert set(ACTIONS) <= set(FIX_ACTIONS)


def test_move_the_hinge_fix_builds(qtbot: QtBot, window: MainWindow) -> None:
    doc = _leaves()
    _hinge(doc)
    hinge = doc.features[-1]
    _own_extrude(doc, hinge.refs["edge"]).params["depth"] = P(6.06)
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        window.add_session(session)
    assert session.report is not None
    result = session.report.results[hinge.id]
    assert result.state is FeatureState.ERROR
    (fix,) = result.issues[0].fixes
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        window.apply_fix(hinge.id, fix)
    assert session.document.feature(hinge.id).refs["edge"] == fix.data["refs"][0]
    assert session.report is not None
    assert session.report.results[hinge.id].state is FeatureState.OK
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        session.undo.undo()
    assert session.document.feature(hinge.id).refs["edge"] != fix.data["refs"][0]
