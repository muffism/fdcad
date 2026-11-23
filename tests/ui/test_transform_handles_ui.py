"""Transform handles in the app (PLAN Phase 3, PHASE3_SPEC P3.1.1 item 6, P3.7 item 3, D411):
the command picks the selected body, the view shows arrows, rings and scale boxes,
dragging a ring switches to turning, and the result is an editable feature."""

from __future__ import annotations

import math

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.features.base import PreviewHandle
from fdcad.core.features.solids import solids, volume_of
from fdcad.ui.body_tools import flow
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.viewport.handles import HandleDrag
from fdcad.ui.viewport.preview import arrow_shape
from tests.ui.test_body_display import _body_row, _face_of, _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def _ready(qtbot: QtBot, window: MainWindow) -> object:  # noqa: F811
    preview = window.preview
    assert preview is not None
    with qtbot.waitSignal(preview.ready, timeout=20000) as blocker:
        preview.show(window.panel.current_feature() if window.panel is not None else None)
    return blocker.args[0]


def test_command_and_tab(window: MainWindow) -> None:  # noqa: F811
    assert BY_ID["feature.transform_handles"].label == "Transform Handles"
    assert "feature.transform_handles" in window.commands.actions
    tabs = window.command_tabs
    panel = tabs.widget(tabs.index_of("bodies"))
    shown = {a.text() for b in panel.buttons() for a in b.group_actions}
    assert "Transform Handles" in shown


def test_handles_on_the_picked_body_and_a_ring_switches_to_turning(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = _open(qtbot, window)
    # An edge of body 2 is enough to pick the body.
    report = tab.session.report
    assert report is not None and report.body is not None
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer

    tab.selection = [TopExp_Explorer(solids(report.body.shape)[1], TopAbs_EDGE).Current()]
    assert flow.start(window, "feature.transform_handles")
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    feature = panel.current_feature()
    assert feature is not None and feature.type == "move_copy_body"
    assert len(feature.refs["bodies"]) == 1
    data = _ready(qtbot, window)
    params = [h.param for h in data.handles]  # type: ignore[attr-defined]
    assert params == ["dx", "dy", "dz", "rx", "ry", "rz"]
    # Dragging a ring turns the body about its own centre.
    window.preview.drag_to("rx", math.radians(90))  # type: ignore[union-attr]
    feature = panel.current_feature()
    assert feature is not None
    assert feature.params["mode"] == "rotate" and feature.params["rotate_by"] == "centroid"
    rx = feature.params["rx"]
    assert isinstance(rx, Param) and rx.value == pytest.approx(math.pi / 2)
    assert "dx" not in feature.params  # the hidden move fields are not written
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        panel.accept()
    added = tab.session.document.features[-1]
    assert added.type == "move_copy_body" and added.params["rotate_by"] == "centroid"
    body = tab.session.report.body  # type: ignore[union-attr]
    assert body is not None and len(solids(body.shape)) == 2
    # The feature opens again with its values (editable in the tree).
    assert flow.edit(window, added.id)
    assert window.panel.body_form.values()["rotate_by"] == "centroid"  # type: ignore[union-attr]
    window.panel.reject()  # type: ignore[union-attr]


def test_transform_from_the_solid_bodies_folder(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = _open(qtbot, window)
    assert window.tree is not None
    menu = window.tree._context_menu(tab.session, _body_row(window, 0))
    assert menu is not None
    actions = {a.text(): a for a in menu.actions()}
    actions["Transform Handles"].trigger()
    panel = window.panel
    assert panel is not None and panel.is_editing
    feature = panel.current_feature()
    assert feature is not None and feature.type == "move_copy_body"
    # Dragging the X arrow writes Delta X; snapping and the value box are the shared handle code.
    window.preview.drag_to("dx", 12.5)  # type: ignore[union-attr]
    feature = panel.current_feature()
    assert feature is not None
    dx = feature.params["dx"]
    assert isinstance(dx, Param) and dx.value == pytest.approx(12.5)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        panel.accept()
    body = tab.session.report.body  # type: ignore[union-attr]
    assert body is not None
    assert volume_of(body.shape) == pytest.approx(2 * 4000, rel=1e-9)


def test_scale_boxes_drag_the_factor(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    tab.selection = [_face_of(tab, 0)]
    assert flow.start(window, "feature.scale")
    data = _ready(qtbot, window)
    handles = data.handles  # type: ignore[attr-defined]
    assert [h.param for h in handles] == ["factor"] and handles[0].style == "box"
    window.preview.drag_to("factor", 1.5)  # type: ignore[union-attr]
    assert window.panel.body_form.widgets["factor"].edit.text() == "1.5"  # type: ignore[union-attr]
    # Near the ruler the factor snaps to tenths.
    h = handles[0]
    drag = HandleDrag(h)
    assert drag.update(1.234 / h.scale, on_ruler=True) == pytest.approx(1.2)
    assert drag.update(1.234 / h.scale, on_ruler=False) == pytest.approx(1.234)
    window.panel.reject()  # type: ignore[union-attr]


def test_scale_handle_is_a_cube() -> None:
    handle = PreviewHandle("factor", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 2.0, style="box")
    cube = arrow_shape(handle, 10.0)
    assert volume_of(cube) == pytest.approx(6.0**3)
