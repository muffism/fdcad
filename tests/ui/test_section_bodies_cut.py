"""Choosing the bodies a section cuts (TR213 item 2, D2500)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import new_document
from fdcad.core.section import PlaneSetting, SectionState
from fdcad.core.section_store import from_json, to_json
from fdcad.core.sketch.model import Sketch
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.section.zones import SectionExtras
from fdcad.ui.session import DocumentSession
from tests.core.features.test_features import add_extrude, add_sketch, rect
from tests.ui.test_section_view import _folders, window  # noqa: F401


def _two_bodies(qtbot: QtBot, win: MainWindow) -> DocumentTab:
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 20, 20)
    rect(s, 40, 0, 60, 20)
    sk = add_sketch(doc, s, {"feature": "f2"})
    add_extrude(doc, sk, 10.0)
    session = DocumentSession(doc, None, win)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = win.add_session(session)
    return tab


def test_whole_bodies_round_trip() -> None:
    state = SectionState([PlaneSetting()], whole=[1])
    back = from_json(to_json(state))
    assert back is not None and back.whole == [1]
    assert "whole" not in to_json(SectionState())
    data = to_json(state)
    data["whole"] = [1, "x", -2]
    back = from_json(data)
    assert back is not None and back.whole == [1]


def test_extras_list_bodies_cut(qtbot: QtBot) -> None:
    extras = SectionExtras([], 3, [], 0.5, whole=[2])
    qtbot.addWidget(extras)
    assert not extras.cut_group.isHidden() and extras.cut_bodies.count() == 3
    assert extras.whole() == [2]
    extras.cut_bodies.item(0).setCheckState(Qt.CheckState.Unchecked)
    assert extras.whole() == [0, 2]
    one = SectionExtras([], 1, [], 0.5)
    qtbot.addWidget(one)
    assert one.cut_group.isHidden()  # one body: nothing to choose


def test_panel_keeps_a_body_whole(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _two_bodies(qtbot, window)
    seen: list[Any] = []
    tab.viewport.set_section_whole = lambda s: seen.append(len(s))  # type: ignore[attr-defined]
    tool = window.section_tool
    tool.open(tab)
    panel = tool.panel
    assert panel is not None and panel.extras.cut_bodies.count() == 2
    assert seen[-1] == 0
    panel.extras.cut_bodies.item(1).setCheckState(Qt.CheckState.Unchecked)
    state = tool.state_of(tab)
    assert state is not None and state.whole == [1]
    assert seen[-1] == 1
    tool.turn_off(tab)
    assert seen[-1] == 0


def test_cut_faces_follow_the_section_for_measure(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """TR213 (D2502): the cut faces are built on the worker and given to the 3D view."""
    tab = _two_bodies(qtbot, window)
    got: list[int] = []
    tab.viewport.set_section_faces = lambda f: got.append(len(f))  # type: ignore[attr-defined]
    tool = window.section_tool
    tool.open(tab)
    panel = tool.panel
    assert panel is not None
    panel.rows[0].offset.edit.setText("5")
    qtbot.waitUntil(lambda: bool(got) and got[-1] == 2, timeout=5000)
    panel.extras.cut_bodies.item(1).setCheckState(Qt.CheckState.Unchecked)
    qtbot.waitUntil(lambda: got[-1] == 1, timeout=5000)
    tool.turn_off(tab)
    assert got[-1] == 0
    tool.cut_faces.wait()
