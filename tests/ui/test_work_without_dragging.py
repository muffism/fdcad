"""Work without dragging (TR293, D2209): click then click handles with arrow nudges,
sketch arrow nudges, Tab to the next sketch point, and Move Up and Move Down."""

from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Any

from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from fdcad.core.features.base import PreviewHandle
from fdcad.ui.viewport.handles import HandleDrag
from fdcad.ui.viewport.widget import ViewportWidget
from tests.ui.sketch_tools.test_dimension_panel_wp8 import canvas  # noqa: F401  (fixture)

NONE = Qt.KeyboardModifier.NoModifier


def _stub(handle: PreviewHandle) -> Any:
    sent: list[tuple[str, float]] = []
    stub = SimpleNamespace(
        _grab=(handle.param, 0.0),
        _drag_state=HandleDrag(handle, 0.0),
        _handle_value=handle.value,
        _handle_start_value=handle.value,
        handle_dragged=SimpleNamespace(emit=lambda p, v: sent.append((p, v))),
        finished=[],
    )
    stub.finish_click_handle = lambda: stub.finished.append(True)
    return stub, sent


def test_arrows_nudge_a_clicked_handle_and_escape_puts_it_back() -> None:
    handle = PreviewHandle("depth", (0, 0, 0), (0, 0, 1), 20.0, step=5.0)
    stub, sent = _stub(handle)
    assert ViewportWidget.handle_key(stub, Qt.Key.Key_Up, NONE)
    assert sent[-1] == ("depth", 25.0)
    assert ViewportWidget.handle_key(stub, Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier)
    assert sent[-1] == ("depth", 24.5)
    assert not ViewportWidget.handle_key(stub, Qt.Key.Key_A, NONE)
    assert ViewportWidget.handle_key(stub, Qt.Key.Key_Escape, NONE)
    assert sent[-1] == ("depth", 20.0) and stub.finished
    angle = PreviewHandle("angle", (1, 0, 0), (0, 0, 1), 0.5, 1.0, (0, 0, 0))
    stub, sent = _stub(angle)
    assert ViewportWidget.handle_key(stub, Qt.Key.Key_Down, NONE)
    assert math.isclose(sent[-1][1], 0.5 - math.radians(1))
    assert ViewportWidget.handle_key(stub, Qt.Key.Key_Return, NONE) and stub.finished


def test_arrows_nudge_sketch_items_and_tab_picks_the_next_point(
    qtbot: QtBot,
    canvas: Any,  # noqa: F811
) -> None:
    sk = canvas.edit.sketch
    a = sk.add_point(0.0, 0.0)
    b = sk.add_point(10.0, 0.0)
    canvas.edit.refresh()
    canvas.selection = [a]
    canvas.setFocus()
    qtbot.keyClick(canvas, Qt.Key.Key_Right)
    assert canvas.edit.sketch.xy(a) == (1.0, 0.0)
    qtbot.keyClick(canvas, Qt.Key.Key_Up, Qt.KeyboardModifier.ShiftModifier)
    x, y = canvas.edit.sketch.xy(a)
    assert math.isclose(x, 1.0) and math.isclose(y, 0.1)
    canvas.undo()
    assert canvas.edit.sketch.xy(a) == (1.0, 0.0)
    canvas.selection = [a]
    qtbot.keyClick(canvas, Qt.Key.Key_Tab)
    assert canvas.selection == [b]
    qtbot.keyClick(canvas, Qt.Key.Key_Tab)  # past the last point: back to the first
    assert canvas.selection == [next(iter(canvas.edit.sketch.entities))]


def test_move_up_and_down_in_the_tree(qtbot: QtBot) -> None:
    from fdcad.core.sketch.model import Sketch
    from fdcad.ui.tree.feature_tree import FeatureTree
    from tests.core.features.test_features import add_extrude, add_sketch, plate, rect
    from tests.ui.test_property_panel import _session

    doc, _ext = plate()
    s = Sketch()
    rect(s, 10, 10, 20, 20)
    sk = add_sketch(doc, s, {"feature": "f2"})
    add_extrude(doc, sk, 5.0)
    other = add_sketch(doc, Sketch(), {"feature": "f3"})
    session = _session(qtbot, doc)
    tree = FeatureTree()
    qtbot.addWidget(tree)
    tree.set_session(session)
    ids = [f.id for f in session.document.features]
    assert tree.step_feature(other, -1)
    moved = [f.id for f in session.document.features]
    assert moved.index(other) == ids.index(other) - 1
    assert tree.step_feature(other, 1)
    assert [f.id for f in session.document.features] == ids
    assert not tree.step_feature(other, 1)  # already last
    assert not tree.step_feature(sk, -10)
