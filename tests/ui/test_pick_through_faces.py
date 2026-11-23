"""Select Through Faces on the Fillet and Chamfer panels (TR64 item 4, D1800)."""

from __future__ import annotations

from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.viewport.through_edges import first_edge
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def explore(shape: object, kind: object) -> list[object]:
    from OCP.TopExp import TopExp_Explorer

    found, it = [], TopExp_Explorer(shape, kind)
    while it.More():
        found.append(it.Current())
        it.Next()
    return found


def test_first_edge_skips_faces_in_front() -> None:
    box = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
    faces = explore(box, TopAbs_FACE)
    edges = explore(box, TopAbs_EDGE)
    found = first_edge([faces[0], faces[1], edges[3], edges[0]])
    assert found is not None and found.IsSame(edges[3])
    assert first_edge(faces) is None
    assert first_edge([]) is None


def test_tick_sets_the_view_and_clears_on_close(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window)
    view = window.tabs.currentWidget().viewport
    view.pick_through = False
    for command in ("feature.fillet", "feature.chamfer"):
        window.commands.actions[command].trigger()
        form = window.panel.form
        assert form is not None and hasattr(form, "pick_through")
        form.items.add({"kind": "edge", "name": "edge(a|b)"})
        form.pick_through.setChecked(True)
        assert view.pick_through is True
        made = window.panel.current_feature()
        assert made is not None and not any("through" in k for k in made.params)
        window.panel.reject()
        qtbot.waitUntil(lambda: view.pick_through is False, timeout=2000)
        # The tick is remembered for the session.
        window.commands.actions[command].trigger()
        form = window.panel.form
        assert form is not None and form.pick_through.isChecked()
        assert view.pick_through is True
        form.pick_through.setChecked(False)
        window.panel.reject()
