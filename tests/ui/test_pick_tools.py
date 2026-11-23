"""More pick tools: one pick type at once, paint pick and Pick in Volume (TR329, D2208)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.ui.input.selection_rules import SelectionFilter
from fdcad.ui.main_window import pick_volume as pv
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.test_goal_seek import block
from tests.ui.sweep_support import idle
from tests.ui.test_workflow import _folders, window  # noqa: F401  (fixtures)


def test_only_one_type_then_every_type() -> None:
    model = SelectionFilter()
    assert model.only("face")
    assert model.active == {"face"} and model.is_on()
    assert model.view_kinds() == {"face"}
    assert model.only("edge") and model.active == {"edge"}
    assert not model.only("edge")
    assert not model.is_on()


def test_pick_only_commands_and_paint_toggle(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    session = DocumentSession(block(10.0), None, window)
    tab = window.add_session(session)
    assert idle(tab, 60)
    window.commands.actions["select.only_faces"].trigger()
    assert window.selection_filter.active == {"face"}
    window.commands.actions["select.only_faces"].trigger()
    assert not window.selection_filter.is_on()
    window.commands.actions["select.paint"].setChecked(True)
    window.toggle_paint()
    assert getattr(tab.viewport, "paint", True)


def test_pick_in_volume_picks_in_a_job(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = DocumentSession(block(10.0), None, window)
    tab = window.add_session(session)
    assert idle(tab, 60)
    picked: list[object] = []
    monkeypatch.setattr(
        tab.viewport,
        "select_shapes",
        lambda shapes, add=False: picked.extend(shapes),
        raising=False,
    )

    def fill(dialog: pv.PickVolumeDialog) -> bool:
        dialog.shape.setCurrentIndex(dialog.shape.findData("sphere"))
        assert not dialog.size_boxes[0].isEnabled() and dialog.radius.isEnabled()
        dialog.radius.setValue(100.0)
        dialog.kind.setCurrentIndex(dialog.kind.findData("face"))
        return True

    monkeypatch.setattr(pv, "run", fill)
    job = pv.open_pick_volume(window)
    assert job is not None
    qtbot.waitUntil(lambda: len(picked) == 6, timeout=20000)
    assert "6 items" in window.status.text()
