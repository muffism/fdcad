"""Geometry Check in the Evaluate tab (PLAN section 5A item 10, DECISIONS D356)."""

from __future__ import annotations

import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from pytestqt.qtbot import QtBot

from fdcad.core.naming.names import NamedShape
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.print_tools.geometry_check import GeometryCheck
from fdcad.ui.strings_print import CHECK_NOTHING
from tests.ui.test_phase2_flow import _folders, plate_tab, window

__all__ = ["_folders", "window"]


def test_clean_part_reports_no_problems(qtbot: QtBot, window: MainWindow) -> None:
    plate_tab(qtbot, window)
    window.commands.actions["evaluate.geometry_check"].trigger()
    tool = window.geometry_check
    assert isinstance(tool, GeometryCheck) and tool.panel.isVisible()
    qtbot.waitUntil(lambda: tool.summary.text() == "No problems found in the body.", timeout=20000)
    assert tool.list.count() == 0


def test_problems_are_listed_and_highlighted(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ext = plate_tab(qtbot, window)
    report = tab.session.report
    assert report is not None
    list(report.results.values())[-1].body = NamedShape(BRepPrimAPI_MakeBox(10, 10, 0.004).Shape())
    tool = window.geometry_check
    tool.open()
    qtbot.waitUntil(lambda: tool.list.count() == 8, timeout=20000)
    assert "8 problems found" in tool.summary.text()
    assert "8 problems found" in window.status.text()
    tool.list.setCurrentRow(0)
    assert tab.viewport.check_highlight == [tool.issues[0].shape]  # type: ignore[attr-defined]
    tool.sliver_box.setValue(0.001)
    tool.edge_box.setValue(0.001)
    tool.run()
    qtbot.waitUntil(lambda: "No problems" in tool.summary.text(), timeout=20000)


def test_check_needs_a_part(window: MainWindow) -> None:
    window.geometry_check.open()
    assert window.geometry_check.summary.text() == CHECK_NOTHING


def test_tour_ignore_and_fix(qtbot: QtBot, window: MainWindow) -> None:
    """TR262 (D1416): Next and Back, Ignore, and Fix for a sliver face."""
    from fdcad.ui import strings

    tab, _ext = plate_tab(qtbot, window)
    report = tab.session.report
    assert report is not None
    list(report.results.values())[-1].body = NamedShape(BRepPrimAPI_MakeBox(10, 10, 0.004).Shape())
    tool = window.geometry_check
    tool.open()
    qtbot.waitUntil(lambda: tool.list.count() == 8, timeout=20000)
    tool.list.setCurrentRow(0)
    tool.step(1)
    assert tool.list.currentRow() == 1
    tool.step(-2)
    assert tool.list.currentRow() == 7
    tool.list.setCurrentRow(0)
    tool.ignore()
    assert tool.list.count() == 7
    tool.run()
    qtbot.waitUntil(lambda: tool.list.count() == 7, timeout=20000)
    edge = next(i for i, issue in enumerate(tool.issues) if issue.kind == "tiny_edge")
    tool.list.setCurrentRow(edge)
    assert not tool.fix()
    assert tool.summary.text() == strings.CHECK_NO_FIX


def test_fix_adds_a_delete_face_feature(qtbot: QtBot, window: MainWindow) -> None:
    """TR262 (D1416): Fix on a sliver adds Delete Face, one undo step."""
    from PySide6.QtWidgets import QListWidgetItem

    from fdcad.core.geometry_check import GeometryIssue

    tab, ext = plate_tab(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    face = report.body.face(f"{ext}/side/e5")
    tool = window.geometry_check
    tool.issues = [GeometryIssue("sliver", face, 1, "a sliver")]
    item = QListWidgetItem("a sliver")
    item.setData(256, 0)
    tool.list.addItem(item)
    tool.list.setCurrentRow(0)
    count = len(tab.session.document.features)
    assert tool.fix()
    made = tab.session.document.features[-1]
    assert len(tab.session.document.features) == count + 1 and made.type == "delete_face"
    assert made.refs["faces"][0]["name"] == f"{ext}/side/e5"
    tab.session.undo.undo()
    assert len(tab.session.document.features) == count


def test_symmetry_check_about_a_selected_face(qtbot: QtBot, window: MainWindow) -> None:
    """TR87 item 3 (D1416)."""
    from fdcad.ui import strings

    tab, ext = plate_tab(qtbot, window)
    tool = window.geometry_check
    assert tool.check_symmetry() == strings.CHECK_SYMMETRY_PICK
    report = tab.session.report
    assert report is not None and report.body is not None
    tab.selection = [report.body.face(f"{ext}/cap/end")]
    assert tool.check_symmetry() is None
    qtbot.waitUntil(lambda: "plane" in tool.summary.text() and "Select" not in tool.summary.text(),
                    timeout=20000)  # fmt: skip
    assert tool.summary.text() in (strings.CHECK_SYMMETRIC, strings.CHECK_NOT_SYMMETRIC.format(
        count=tool.list.count()))  # fmt: skip


def test_fix_on_a_gap_adds_heal_edges(qtbot: QtBot, window: MainWindow) -> None:
    """TR262 (D1807): Fix on an edge with a gap adds Heal Edges with a covering tolerance."""
    from OCP.BRep import BRep_Builder
    from PySide6.QtWidgets import QListWidgetItem

    from fdcad.core.features.modify import edges_of
    from fdcad.core.geometry_check import GeometryIssue

    tab, ext = plate_tab(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    face = report.body.face(f"{ext}/side/e5")
    edge = edges_of(face)[0]
    BRep_Builder().UpdateEdge(edge, 0.05)
    tool = window.geometry_check
    tool.issues = [GeometryIssue("gap", edge, 1, "edge 1 closes a gap")]
    item = QListWidgetItem("a gap")
    item.setData(256, 0)
    tool.list.addItem(item)
    tool.list.setCurrentRow(0)
    count = len(tab.session.document.features)
    assert tool.fix()
    made = tab.session.document.features[-1]
    assert len(tab.session.document.features) == count + 1 and made.type == "heal_edges"
    assert made.params["tolerance"].value == 0.055
    tab.session.undo.undo()
    assert len(tab.session.document.features) == count


def test_fix_on_a_nearly_square_edge_adds_move_face(qtbot: QtBot, window: MainWindow) -> None:
    """TR262 (D2303): Fix turns the face with a Move Face rotate about the edge."""
    from PySide6.QtWidgets import QListWidgetItem

    from fdcad.core.features.modify import edges_of
    from fdcad.core.geometry_check import GeometryIssue

    tab, ext = plate_tab(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    face = report.body.face(f"{ext}/side/e5")
    edge = edges_of(face)[0]
    tool = window.geometry_check
    tool.issues = [GeometryIssue("not_square", edge, 1, "off square", (face, 0.01))]
    item = QListWidgetItem("off square")
    item.setData(256, 0)
    tool.list.addItem(item)
    tool.list.setCurrentRow(0)
    count = len(tab.session.document.features)
    assert tool.fix()
    made = tab.session.document.features[-1]
    assert made.type == "move_face" and made.params["mode"] == "rotate"
    assert made.params["angle"].value == pytest.approx(0.01, rel=1e-8)
    assert made.refs["faces"][0]["name"] == f"{ext}/side/e5"
    assert made.refs["axis"]["kind"] == "edge"
    tab.session.undo.undo()
    assert len(tab.session.document.features) == count


def test_clip_box_round_the_finding_and_back(qtbot: QtBot, window: MainWindow) -> None:
    """TR262 (D2303): the tour clips the view to a box round each finding."""
    from fdcad.core.geometry_check import clip_box

    planes = clip_box((0.0, 0.0, 0.0), (10.0, 2.0, 2.0))
    assert len(planes) == 6
    assert max(p.origin[0] for p in planes) == 15.0  # padded by half the size
    assert min(p.origin[1] for p in planes) == -5.0  # at least 2 mm, here 5 mm
    tab, _ext = plate_tab(qtbot, window)
    report = tab.session.report
    assert report is not None
    list(report.results.values())[-1].body = NamedShape(BRepPrimAPI_MakeBox(10, 10, 0.004).Shape())
    tool = window.geometry_check
    tool.open()
    qtbot.waitUntil(lambda: tool.list.count() == 8, timeout=20000)
    view = tab.viewport  # a placeholder without a 3D view offscreen: record the calls
    if not hasattr(view, "set_section"):
        view.set_section = lambda clip: setattr(view, "_section_clip", clip)  # type: ignore[attr-defined]
    before = getattr(tab.viewport, "_section_clip", None)
    tool.clip_check.setChecked(True)
    tool.list.setCurrentRow(0)
    tool.step(1)
    clip = getattr(tab.viewport, "_section_clip", None)
    assert isinstance(clip, list) and len(clip) == 6
    tool.clip_check.setChecked(False)
    assert getattr(tab.viewport, "_section_clip", None) is before
    tool.clip_check.setChecked(True)
    assert isinstance(getattr(tab.viewport, "_section_clip", None), list)
    tool.panel.hide()
    assert getattr(tab.viewport, "_section_clip", None) is before
