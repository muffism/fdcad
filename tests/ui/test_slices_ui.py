"""Slice Body from the Tools menu (TR151 item 1, D1718)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.tree_info import folders
from fdcad.ui.main_window import slices as sl
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.test_goal_seek import block
from tests.ui.sweep_support import idle
from tests.ui.test_workflow import _folders, window  # noqa: F401  (fixtures)


def test_slices_are_one_undo_step_in_a_folder(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = DocumentSession(block(10.0), None, window)
    tab = window.add_session(session)
    assert idle(tab, 60)

    def fill(dialog: sl.SliceDialog) -> bool:
        dialog.base.setCurrentIndex(dialog.base.findText("Top Plane"))
        dialog.count.setValue(3)
        dialog.spacing.setValue(5.0)
        dialog.start.setValue(5.0)
        return True

    monkeypatch.setattr(sl, "run", fill)
    before = len(session.document.features)
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        job = sl.open_slices(window)
        assert job is not None
        qtbot.waitUntil(lambda: len(session.document.features) == before + 6, timeout=20000)
    (folder,) = folders(session.document.tree)
    assert folder["name"] == "Slices" and len(folder["features"]) == 6
    report = session.report
    assert report is not None
    sketches = [f for f in session.document.features[before:] if f.type == "sketch"]
    assert all(report.results[f.id].sketch is not None for f in sketches)
    session.undo.undo()
    assert len(session.document.features) == before and folders(session.document.tree) == []


def test_cancel_adds_nothing(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = DocumentSession(block(10.0), None, window)
    tab = window.add_session(session)
    assert idle(tab, 60)
    monkeypatch.setattr(sl, "run", lambda _d: False)
    assert sl.open_slices(window) is None


def test_slices_round_an_axis_from_the_dialog(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TR151 item 1 (D2204): pick an axis and the planes turn round it."""
    from fdcad.core.document.model import Feature

    doc = block(10.0)
    top = next(f.id for f in doc.features if f.name == "Top Plane")
    right = next(f.id for f in doc.features if f.name == "Right Plane")
    aid = doc.new_feature_id()
    doc.features.append(
        Feature(
            aid,
            "ref_axis",
            "Axis 1",
            params={"method": "two_planes"},
            refs={"first": {"feature": top}, "second": {"feature": right}},
        )
    )
    session = DocumentSession(doc, None, window)
    tab = window.add_session(session)
    assert idle(tab, 60)

    def fill(dialog: sl.SliceDialog) -> bool:
        dialog.base.setCurrentIndex(dialog.base.findText("Right Plane"))
        dialog.axis.setCurrentIndex(dialog.axis.findData(aid))
        assert not dialog.spacing.isEnabled() and dialog.angle_step.isEnabled()
        dialog.count.setValue(2)
        dialog.angle_step.setValue(30.0)
        dialog.start_angle.setValue(120.0)
        return True

    monkeypatch.setattr(sl, "run", fill)
    before = len(session.document.features)
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        job = sl.open_slices(window)
        assert job is not None
        qtbot.waitUntil(lambda: len(session.document.features) == before + 4, timeout=20000)
    planes = [f for f in session.document.features[before:] if f.type == "ref_plane"]
    assert [p.params["method"] for p in planes] == ["angle", "angle"]
