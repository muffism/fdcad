"""Selection sets in the window (TR94, D944)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.naming.names import faces_of
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.selection_sets import SetsDialog, describe
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)
from tests.ui.test_select_similar_ui import _View


def test_save_pick_rule_combine_delete(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for cid in ("select.save_set", "select.sets"):
        assert cid in BY_ID and cid in window.commands.actions and BY_ID[cid].keys == ()
    tab, ids = _open(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    view = _View(report.body.shape)
    monkeypatch.setattr(tab, "viewport", view)
    sets = window.selection_sets
    face = faces_of(report.body.shape)[0]
    view.picks = [face]
    assert sets.save_picks("Top")
    undo = tab.session.undo
    assert undo.count() == 1 and [s["name"] for s in sets.sets()] == ["Top"]
    view.picks = []
    assert sets.use("Top") and sets.wait()
    qtbot.waitUntil(lambda: bool(view.picks), timeout=5000)
    assert view.picks[0].IsSame(face)
    assert sets.add_rule("Boss", {"kind": "feature", "feature": ids["boss"]})
    assert sets.combine("Both", "union", ["Top", "Boss"])
    assert not sets.combine("Self", "union", ["Self", "Top"])
    assert not sets.delete("Boss")  # Both uses it
    assert "Delete those sets first" in window.status.text()
    view.picks = []
    assert sets.use("Both") and sets.wait()
    qtbot.waitUntil(lambda: len(view.picks) > 1, timeout=5000)
    assert sets.delete("Both") and sets.delete("Boss")
    undo.undo()
    assert [s["name"] for s in sets.sets()] == ["Top", "Boss"]
    names = {f.id: f.name for f in tab.session.document.features}
    lines = [describe(s, names) for s in sets.sets()]
    assert lines[0].startswith("Top: 1 picked") and "faces of" in lines[1]
    dialog = SetsDialog(sets, window)
    qtbot.addWidget(dialog)
    assert dialog.list.count() == 2
    view.picks = []
    assert not sets.save_picks("Empty")
