"""Window level checks for the round 2 sketch packages (WP5 relations, WP6, WP7)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.input.commands import BY_ID, DEFAULT_BAR
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.sketch_tools.relations_panel import RelationsPanel
from tests.ui.test_workflow import (  # noqa: F401  (fixtures)
    _folders,
    click,
    new_part,
    plane_id,
    ready_canvas,
    window,
)


def test_relations_command_opens_the_relations_panel(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    assert "sketch.relations" in BY_ID
    assert "sketch.relations" in DEFAULT_BAR["sketch"]
    tab = new_part(qtbot, window)
    mode = window.sketch_mode
    assert mode is not None
    assert not mode.relations_panel_action.isEnabled()
    mode.start(plane_id=plane_id(tab, "Front Plane"))
    canvas = ready_canvas(qtbot, window, (10.0, 10.0))
    canvas.set_tool("line")
    click(qtbot, canvas, 0, 0)
    click(qtbot, canvas, 20, 0)
    canvas.set_tool(None)
    assert mode.relations_panel_action.isEnabled()
    mode.relations_panel_action.trigger()
    panel = mode.relations_panel
    assert isinstance(panel, RelationsPanel)
    assert window.properties is not None
    assert window.properties.currentWidget() is panel
    types = {canvas.edit.sketch.relations[i].type for i in panel.listed()}
    assert "horizontal" in types
    panel.back.click()
    assert window.properties.currentWidget() is mode.panel
    assert mode.accept()
    assert mode.relations_panel is None
