"""Collapse All and the hovered item in the status bar (TR221, D1611)."""

from __future__ import annotations

import math

import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from pytestqt.qtbot import QtBot

from fdcad.core.hover_info import hover_info
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.hover_status import hover_text
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_section_view import _folders, _open, window  # noqa: F401


def _all(shape: object, kind: object) -> list[object]:
    out = []
    explorer = TopExp_Explorer(shape, kind)
    while explorer.More():
        out.append(explorer.Current())
        explorer.Next()
    return out


def test_edge_length_and_radius() -> None:
    edge = _all(BRepPrimAPI_MakeBox(10, 20, 30).Shape(), TopAbs_EDGE)[0]
    info = hover_info(edge)
    assert info is not None and info.length in (10.0, 20.0, 30.0) and info.radius is None
    circles = [hover_info(e) for e in _all(BRepPrimAPI_MakeCylinder(5, 10).Shape(), TopAbs_EDGE)]
    round_one = next(i for i in circles if i is not None and i.radius is not None)
    assert round_one.radius == pytest.approx(5.0)
    assert round_one.length == pytest.approx(2 * math.pi * 5)


def test_angle_between_flat_faces() -> None:
    faces = _all(BRepPrimAPI_MakeBox(10, 20, 30).Shape(), TopAbs_FACE)
    info = hover_info(faces[0], [faces[2]])
    assert info is not None and info.angle == pytest.approx(math.pi / 2)
    assert hover_info(faces[0], [faces[1]]).angle == pytest.approx(0.0)  # type: ignore[union-attr]
    assert hover_info(faces[0], []) is None
    assert hover_info(None) is None


def test_status_text_and_collapse_command(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    edge = _all(tab.session.report.body.shape, TopAbs_EDGE)[0]  # type: ignore[union-attr]
    tab.viewport.shape_under_cursor = lambda: edge  # type: ignore[attr-defined]
    assert hover_text(tab).startswith("Length ")
    tab.viewport.shape_under_cursor = lambda: None  # type: ignore[attr-defined]
    assert hover_text(tab) == ""
    assert BY_ID["tree.collapse_all"].keys == ()
    assert window.commands.trigger("tree.collapse_all")
