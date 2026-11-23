"""Body tool length defaults in an inch part (D2645, bug hunt round 10c R10c.O2)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.units import UnitSystem
from fdcad.ui.body_tools import flow
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.features.test_deform import _bar
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


@pytest.mark.parametrize(
    ("command", "name", "text"),
    [
        ("feature.move_face", "distance", "0.04"),  # 1 mm
        ("feature.linear_pattern", "spacing1", "0.4"),  # 10 mm
    ],
)
def test_inch_parts_get_round_inch_lengths(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    command: str,
    name: str,
    text: str,
) -> None:
    """The defaults are millimetre texts; read in inches, a Move Face of "1" was 1 in
    (25.4 mm) and a pattern spacing of "10" was 10 in."""
    doc, _bar_id = _bar()
    doc.units = UnitSystem.IN
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    assert flow.start(window, command)
    panel = window.panel
    assert panel is not None
    feature = panel.current_feature()
    assert feature is not None
    value = feature.params[name]
    assert isinstance(value, Param) and value.expr == text
    assert value.value == pytest.approx(float(text) * 25.4)
    panel.reject()


def test_millimetre_parts_keep_the_defaults(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    doc, _bar_id = _bar()
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    assert flow.start(window, "feature.move_face")
    panel = window.panel
    assert panel is not None
    feature = panel.current_feature()
    assert feature is not None and feature.params["distance"] == Param("1", 1.0)
    panel.reject()
