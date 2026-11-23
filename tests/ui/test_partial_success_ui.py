"""The Cut the holes that work fix (TR400, D2109)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature
from fdcad.core.features import partial
from fdcad.core.features.base import FeatureError
from fdcad.ui.body_tools import flow
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_design_table_ui import _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def test_skip_points_fix_is_one_undo_step(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    session = tab.session
    sketch = next(f for f in session.document.features if f.type == "sketch")
    hole = Feature("f90", "hole", "Hole 9", refs={"sketch": {"feature": sketch.id}})
    session.document.features.append(hole)
    fix = partial.skip_error(hole, ["p1"], FeatureError("x")).fixes[0]
    assert flow.apply_fix(window, hole.id, fix)
    assert session.document.feature(hole.id).data["skip_points"] == ["p1"]
    session.undo.undo()
    assert "skip_points" not in session.document.feature(hole.id).data
