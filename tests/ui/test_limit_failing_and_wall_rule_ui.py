"""Limit Failing Areas fix (TR271, D1802) and the Shell Wall rule (TR322, D1803)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.features.base import Fix
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.features.test_fillet_limit_areas import _fillet, _part
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_limit_failing_fix_is_one_undo_step(qtbot: QtBot, window: MainWindow) -> None:
    doc, _hole, ref = _part()
    fid = _fillet(doc, ref, 4.0)
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        window.add_session(session)
    fix = Fix("Limit", "limit_failing", {"feature": fid, "parts": [[ref["name"], 0.0, 80.0]]})
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        window.apply_fix(fid, fix)
    feature = session.document.feature(fid)
    assert feature.params["partial"] == "percent"
    assert feature.params["end_percent"].value == 80.0
    session.undo.undo()
    assert "partial" not in session.document.feature(fid).params


def test_shell_wall_rule_is_written(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window)
    window.commands.actions["feature.shell"].trigger()
    form = window.panel.form
    assert form is not None and hasattr(form, "wall_rule")
    made = window.panel.current_feature()
    assert made is not None and "wall_rule" not in made.params
    form.wall_rule.setCurrentIndex(form.wall_rule.findData("never_thicker"))
    made = window.panel.current_feature()
    assert made is not None and made.params["wall_rule"] == "never_thicker"
    window.panel.reject()


def test_draft_fixed_edge_is_written(qtbot: QtBot, window: MainWindow) -> None:
    """TR323 (D1804): the Fixed Edge type writes the faces, the fixed edges and the pull."""
    _open(qtbot, window)
    window.commands.actions["feature.draft"].trigger()
    form = window.panel.form
    assert form is not None and hasattr(form, "fixed")
    form.draft_type.setCurrentIndex(form.draft_type.findData("fixed_edge"))
    assert form.fixed.isVisibleTo(form.fixed.window())
    form._set_neutral({"feature": "f2"})
    form.faces.add({"kind": "face", "name": "f5/side/e5"})
    assert window.panel.current_feature() is None  # no fixed edge yet
    form.fixed.add({"kind": "edge", "name": "edge(a|b)"})
    made = window.panel.current_feature()
    assert made is not None and made.params["draft_type"] == "fixed_edge"
    assert made.refs["fixed_edges"] == [{"kind": "edge", "name": "edge(a|b)"}]
    window.panel.reject()


def test_dome_direction_pick_is_written(qtbot: QtBot, window: MainWindow) -> None:
    """TR147 (D1805): an optional direction pick on the Dome panel."""
    _open(qtbot, window)
    window.commands.actions["feature.dome"].trigger()
    form = window.panel.form
    assert form is not None and "direction" in form.picks
    form.picks["faces"].add({"kind": "face", "name": "f5/cap/end"})
    made = window.panel.current_feature()
    assert made is not None and "direction" not in made.refs
    form.picks["direction"].set_refs([{"kind": "edge", "name": "edge(a|b)"}])
    made = window.panel.current_feature()
    assert made is not None and made.refs["direction"] == [{"kind": "edge", "name": "edge(a|b)"}]
    window.panel.reject()
