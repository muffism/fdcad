"""Edit Sketch Plane (TOOL_SPEC T14.2): move a finished sketch to another plane."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.sketch_plane import SketchPlanePanel, ref_comes_first
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_workflow import (  # noqa: F401  (fixtures)
    _folders,
    new_part,
    plane_id,
    rectangle_sketch,
    window,
)


def test_edit_sketch_plane_moves_the_sketch_and_undoes(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    assert BY_ID["sketch.edit_plane"].label == "Edit Sketch Plane"
    tab = new_part(qtbot, window)
    sid = rectangle_sketch(qtbot, window, tab)
    session = tab.session
    front, top = plane_id(tab, "Front Plane"), plane_id(tab, "Top Plane")
    assert session.document.feature(sid).refs["plane"] == {"feature": front}
    tree = window.tree
    assert tree is not None
    item = tree.item_for(sid)
    assert item is not None
    menu = tree._context_menu(session, item)
    assert menu is not None
    labels = [a.text() for a in menu.actions()]
    assert "Edit Sketch Plane" in labels
    next(a for a in menu.actions() if a.text() == "Edit Sketch Plane").trigger()
    mode = window.sketch_mode
    assert mode is not None
    editor = mode.plane_editor
    assert editor.active and isinstance(editor.panel, SketchPlanePanel)
    assert window.properties is not None
    assert window.properties.currentWidget() is editor.panel
    assert editor.panel.pick.text() == "Front Plane"
    assert mode.picker.active
    mode.picker.pick({"feature": top})
    assert editor.panel.pick.text() == "Top Plane"
    assert mode.picker.active  # another pick may still replace it
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        editor.panel.buttons.accepted.emit()
    assert not editor.active and not mode.picker.active
    assert session.document.feature(sid).refs["plane"] == {"feature": top}
    assert session.undo.undoText().startswith("Edit Sketch Plane")
    report = session.report
    assert report is not None
    result = report.results.get(sid)
    assert result is not None and result.state.value == "ok"
    assert result.sketch is not None
    assert result.sketch.plane.normal == pytest.approx((0.0, 1.0, 0.0))
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.undo()
    assert session.document.feature(sid).refs["plane"] == {"feature": front}


def test_cancel_and_command_without_a_sketch(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = new_part(qtbot, window)
    sid = rectangle_sketch(qtbot, window, tab)
    mode = window.sketch_mode
    assert mode is not None
    tree = window.tree
    assert tree is not None
    tree.select(plane_id(tab, "Top Plane"))
    tree.setCurrentItem(tree.item_for(plane_id(tab, "Top Plane")))
    mode.edit_plane()  # a plane is selected, not a sketch
    assert not mode.plane_editor.active
    assert "Select a sketch" in window.status.text()
    mode.plane_editor.start(sid)
    mode.picker.pick({"feature": plane_id(tab, "Right Plane")})
    assert mode.plane_editor.panel is not None
    mode.plane_editor.panel.buttons.rejected.emit()
    assert not mode.plane_editor.active
    front = plane_id(tab, "Front Plane")
    assert tab.session.document.feature(sid).refs["plane"] == {"feature": front}


def test_a_face_made_after_the_sketch_is_refused(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = new_part(qtbot, window)
    sid = rectangle_sketch(qtbot, window, tab)
    doc = tab.session.document
    later = {"kind": "face", "name": "face(f99/cap/end)"}
    assert not ref_comes_first(doc, sid, later)
    assert ref_comes_first(doc, sid, {"feature": plane_id(tab, "Top Plane")})
    mode = window.sketch_mode
    assert mode is not None
    mode.plane_editor.start(sid)
    mode.picker.pick(later)
    assert mode.plane_editor.ref is None
    assert "comes after it" in window.status.text()
    mode.plane_editor.cancel()


def test_tree_refresh_while_picking_a_plane(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """Bug hunt B3: with the plane pick armed, a tree refresh raised KeyError on the
    part row and could pick the plane row it restored as a new plane."""
    tab = new_part(qtbot, window)
    sid = rectangle_sketch(qtbot, window, tab)
    front, top = plane_id(tab, "Front Plane"), plane_id(tab, "Top Plane")
    tree = window.tree
    mode = window.sketch_mode
    assert tree is not None and mode is not None
    tree.select(top)
    mode.plane_editor.start(sid)
    editor = mode.plane_editor
    assert mode.picker.active and isinstance(editor.panel, SketchPlanePanel)
    mode.picker.pick({"feature": front})
    assert editor.panel.pick.text() == "Front Plane"
    tree.refresh()  # restores the Top Plane row as the current row
    assert editor.panel.pick.text() == "Front Plane"
    part = tree.topLevelItem(0)
    assert part is not None
    tree.setCurrentItem(part)  # the part row is not a feature: no error
    assert editor.panel.pick.text() == "Front Plane"
    editor.panel.buttons.rejected.emit()
