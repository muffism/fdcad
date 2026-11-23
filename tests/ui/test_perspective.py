"""Perspective view toggle (TR15, D747)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_main_window import _folders, _open_plate, window
from tests.ui.test_view_centre import _small_part_and_big_planes, _view

__all__ = ["_folders", "window"]


class _View:
    def __init__(self) -> None:
        self.calls: list[bool] = []

    def set_perspective(self, on: bool) -> bool:
        self.calls.append(on)
        return on


def test_command_and_icon() -> None:
    from fdcad.ui.icons.audit import audit

    command = BY_ID["view.perspective"]
    assert command.label == "Perspective"
    assert command.keys == ()  # no default key (D683)
    assert audit("view.perspective") == []


def test_toggle_reaches_every_open_part(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ext = _open_plate(qtbot, window)
    view = _View()
    tab.viewport = view  # type: ignore[assignment]
    action = window.commands.actions["view.perspective"]
    assert action.isCheckable() and not action.isChecked()
    assert window.commands.trigger("view.perspective")
    assert view.calls == [True]
    assert window.commands.trigger("view.perspective")
    assert view.calls == [True, False]


def test_camera_switches_and_previous_view_keeps_it(qtbot: QtBot) -> None:
    from OCP.Graphic3d import Graphic3d_Camera

    view = _view(qtbot)
    _small_part_and_big_planes(view)
    camera = view._view.Camera()
    assert camera.ProjectionType() == Graphic3d_Camera.Projection_e.Projection_Orthographic
    view.set_view("iso")
    view.set_view("front")  # one view change to go back from
    assert view.set_perspective(True)
    assert (
        view._view.Camera().ProjectionType() == Graphic3d_Camera.Projection_e.Projection_Perspective
    )
    assert view.previous_view()
    # Going back moves the camera, but the projection stays the one the user chose.
    assert (
        view._view.Camera().ProjectionType() == Graphic3d_Camera.Projection_e.Projection_Perspective
    )
    assert not view.set_perspective(False)
    assert (
        view._view.Camera().ProjectionType()
        == Graphic3d_Camera.Projection_e.Projection_Orthographic
    )


def test_a_new_part_opens_in_the_chosen_projection(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PySide6.QtWidgets import QLabel

    from fdcad.ui.viewport.widget import ViewportWidget

    # Offscreen tests have no kernel view: the tab shows a label in its place.
    calls: list[bool] = []
    fake = lambda _self, on: calls.append(on)  # noqa: E731
    for kind in (QLabel, ViewportWidget):
        monkeypatch.setattr(kind, "set_perspective", fake, raising=False)
    assert window.commands.trigger("view.perspective")
    _open_plate(qtbot, window)
    assert calls == [True]
