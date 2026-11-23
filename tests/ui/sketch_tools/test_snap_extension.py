"""A faint extension of a line under an on-line snap (TR341 item 3, D1316)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.ui.sketch_tools.inference import Snap
from tests.ui.sketch_tools.p2_helpers import canvas_of, edit_of


def test_on_line_snap_shows_the_line_carried_on(qtbot: QtBot) -> None:
    sk = edit_of().sketch
    lid = sk.add_line(0.0, 0.0, 10.0, 0.0)
    canvas, _panel = canvas_of(qtbot, sk)
    snap = Snap("on_curve", 4.0, 0.0, [("coincident", [lid])], target=lid)
    ext = canvas.snap_extension(snap)
    assert ext is not None
    (x0, y0), (x1, y1) = ext
    assert x0 < 0.0 and x1 > 10.0 and y0 == pytest.approx(0.0) and y1 == pytest.approx(0.0)
    assert canvas.snap_extension(Snap("point", 0.0, 0.0)) is None
    canvas.snap = snap
    canvas.grab()
