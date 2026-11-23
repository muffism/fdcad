"""Sketch problem list (TR38, D1301)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Line, Relation, Sketch
from fdcad.ui import strings
from fdcad.ui.main_window.status_bar import SketchStatusLabel, sketch_state
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.sketch_tools import problem_list
from fdcad.ui.sketch_tools.problem_list import ProblemListDialog
from tests.ui.sketch_tools.p2_helpers import canvas_of, edit_of
from tests.ui.test_input import _open_plate
from tests.ui.test_main_window import _folders, window

__all__ = ["_folders", "window"]


def _dangling() -> Sketch:
    sk = edit_of().sketch
    line = sk.entities[sk.add_line(0.0, 0.0, 10.0, 0.0)]
    assert isinstance(line, Line)
    sk.relations.append(Relation("horizontal", ["e99"]))
    return sk


def test_status_shows_dangling_and_the_rest_still_solves() -> None:
    edit = edit_of(_dangling())
    assert edit.result is not None and edit.result.solved
    assert edit.dangling == ["r1"]
    status = edit.status()
    assert status.display == "dangling"
    text = strings.SKETCH_STATUS[status.display].format(dof=status.dof, message=status.message)
    assert sketch_state(text) == "dangling"


def test_status_shows_invalid_geometry() -> None:
    sk = edit_of().sketch
    sk.add_line(1.0, 1.0, 1.0, 1.0)
    assert edit_of(sk).status().display == "invalid"


def test_status_label_click_signals(qtbot: QtBot) -> None:
    from PySide6.QtCore import Qt

    label = SketchStatusLabel()
    qtbot.addWidget(label)
    label.setText("Fully defined")
    with qtbot.waitSignal(label.clicked, timeout=1000):
        qtbot.mouseClick(label, Qt.MouseButton.LeftButton)


def test_pick_new_item_and_delete(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot, _dangling())
    dialog = ProblemListDialog(canvas)
    qtbot.addWidget(dialog)
    assert dialog.rows[0].kind == "dangling"
    dialog.list.setCurrentRow(0)
    canvas.selection = []
    dialog.pick_new()
    assert dialog.message.text() == strings.PROBLEMS_PICK_FIRST
    line = next(e.id for e in canvas.edit.sketch.entities.values() if isinstance(e, Line))
    canvas.selection = [line]
    dialog.pick_new()
    assert canvas.edit.sketch.relations[1].entities == [line]
    assert canvas.edit.dangling == [] and canvas.edit.status().display == "under"
    assert dialog.rows == [] or all(r.kind != "dangling" for r in dialog.rows)
    canvas.edit.undo()
    canvas.changed()
    dialog.list.setCurrentRow(0)
    dialog.delete()
    assert len(canvas.edit.sketch.relations) == 1


def test_repair_all_dangling_asks_for_each(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    canvas, _panel = canvas_of(qtbot, _dangling())
    asked: list[str] = []
    monkeypatch.setattr(problem_list, "ask", lambda _w, text: asked.append(text) or True)
    dialog = ProblemListDialog(canvas)
    qtbot.addWidget(dialog)
    dialog.repair_all()
    assert len(asked) == 1 and "e99" in asked[0]
    assert canvas.edit.dangling == []
    assert "Repaired 1" in dialog.message.text()
    canvas.edit.undo()  # one undo step
    canvas.changed()
    assert canvas.edit.dangling == ["r1"]


def test_diagnose_steps_and_applies(qtbot: QtBot) -> None:
    sk = edit_of().sketch
    line = sk.entities[sk.add_line(0.0, 0.0, 10.0, 0.0)]
    assert isinstance(line, Line)
    sk.relate("horizontal", line.id)
    sk.dimension("distance", [line.p1, line.p2], Param("10", 10.0))
    sk.dimension("distance", [line.p1, line.p2], Param("12", 12.0))
    canvas, _panel = canvas_of(qtbot, sk)
    dialog = ProblemListDialog(canvas)
    qtbot.addWidget(dialog)
    row = next(i for i, p in enumerate(dialog.rows) if p.kind == "conflicting")
    dialog.list.setCurrentRow(row)
    assert dialog.buttons["diagnose"].isEnabled()
    dialog.diagnose()
    assert "Way 1 of" in dialog.message.text() and "reference" in dialog.message.text()
    assert dialog.buttons["apply"].isEnabled()
    dialog.apply_way()
    assert not any(d.driving for d in canvas.edit.sketch.dimensions if d.id == "d2")
    assert not [p for p in dialog.rows if p.kind == "conflicting"]


def test_select_under_defined(qtbot: QtBot) -> None:
    sk = edit_of().sketch
    line = sk.add_line(0.0, 0.0, 10.0, 5.0)
    canvas, _panel = canvas_of(qtbot, sk)
    dialog = ProblemListDialog(canvas)
    qtbot.addWidget(dialog)
    assert dialog.rows == [] and dialog.list.item(0).text() == strings.PROBLEMS_NONE
    dialog.select_under()
    assert line in canvas.selection


def test_status_bar_click_opens_the_list_and_closing_the_sketch_closes_it(
    qtbot: QtBot, window: MainWindow
) -> None:
    tab = _open_plate(qtbot, window, hole=False)
    front = next(f for f in tab.session.document.features if f.name == "Front Plane")
    mode = window.sketch_mode
    assert mode is not None
    mode.start(plane_id=front.id)
    window.sketch_status.clicked.emit()
    dialog = mode.problems_dialog
    assert isinstance(dialog, ProblemListDialog) and dialog.isVisible()
    mode.cancel()
    assert mode.problems_dialog is None
