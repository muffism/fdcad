"""Insert DXF into an open sketch (TR5, D695)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Circle, Line
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.sketch_tools import dxf_dialog
from fdcad.ui.sketch_tools.paste_tool import PasteTool
from tests.core.sketch.test_dxf_import import CIRCLE, LINE, _dxf
from tests.ui.sketch_tools.p2_helpers import canvas_of, ui_click


def test_command() -> None:
    assert BY_ID["sketch.insert_dxf"].label == "Insert DXF"


def test_options_give_true_size_and_layers(qtbot: QtBot) -> None:
    drawing = dxf_dialog.parse(_dxf(LINE, CIRCLE, units=1))  # inches
    dialog = dxf_dialog.DxfOptions(drawing)
    qtbot.addWidget(dialog)
    assert dialog.units.currentText().startswith("From the file (in)")
    place, base = dialog.placement()
    assert place.scale == pytest.approx(25.4) and base == "origin" and place.layers is not None
    dialog.layer_boxes["Holes"].setChecked(False)
    place, _base = dialog.placement()
    assert place.layers == {"Outline"}


def test_insert_follows_the_cursor_and_a_click_places_it(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "plate.dxf"
    path.write_text(_dxf(LINE, CIRCLE), encoding="utf-8")
    monkeypatch.setattr(dxf_dialog.DxfOptions, "exec", lambda self: 1)
    canvas, _panel = canvas_of(qtbot)
    assert dxf_dialog.insert_dxf(canvas, str(path))
    assert isinstance(canvas.tool, PasteTool)
    ui_click(qtbot, canvas, (5, 5))  # the drawing origin lands here
    sk = canvas.edit.sketch
    line = next(e for e in sk.entities.values() if isinstance(e, Line))
    assert sk.xy(line.p1) == pytest.approx((5, 5), abs=0.5)
    assert any(isinstance(e, Circle) for e in sk.entities.values())
    assert canvas.tool is None


def test_a_file_with_nothing_to_insert_says_so(qtbot: QtBot, tmp_path: Path) -> None:
    path = tmp_path / "text.dxf"
    path.write_text(_dxf("0\nTEXT\n8\n0\n1\nhi\n"), encoding="utf-8")
    canvas, _panel = canvas_of(qtbot)
    messages: list[str] = []
    canvas.status_message.connect(messages.append)
    import fdcad.ui.sketch_tools.dxf_dialog as mod

    mod.DxfOptions.exec = lambda self: 1  # type: ignore[method-assign,assignment]
    try:
        assert not dxf_dialog.insert_dxf(canvas, str(path))
    finally:
        del mod.DxfOptions.exec
    assert messages and "no lines" in messages[-1]
