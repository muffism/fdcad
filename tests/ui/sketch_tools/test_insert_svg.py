"""Insert SVG into an open sketch (TR117, D863)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Circle
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.sketch_tools import dxf_dialog
from fdcad.ui.sketch_tools.paste_tool import PasteTool
from tests.core.sketch.test_svg_import import SVG
from tests.ui.sketch_tools.p2_helpers import canvas_of, ui_click


def test_insert_svg_places_like_dxf(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert BY_ID["sketch.insert_svg"].label == "Insert SVG"
    path = tmp_path / "logo.svg"
    path.write_text(SVG, encoding="utf-8")
    monkeypatch.setattr(dxf_dialog.DxfOptions, "exec", lambda self: 1)
    canvas, _panel = canvas_of(qtbot)
    assert dxf_dialog.insert_svg(canvas, str(path))
    assert isinstance(canvas.tool, PasteTool)
    ui_click(qtbot, canvas, (5, 5))
    circles = [e for e in canvas.edit.sketch.entities.values() if isinstance(e, Circle)]
    assert len(circles) == 1 and circles[0].radius == pytest.approx(10.0)
