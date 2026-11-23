"""Deformation features in the window: commands, the panel with defaults from the body,
the triad and trim plane handles, and the result (PHASE4_SPEC P4.9, D393)."""

from __future__ import annotations

import math

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.deform import TYPES
from fdcad.core.document.model import Param
from fdcad.core.features.direct import valid_solid
from fdcad.core.features.preview import build_preview
from fdcad.core.features.solids import volume_of
from fdcad.core.sketch.model import Sketch
from fdcad.ui.body_tools import flow
from fdcad.ui.body_tools.form_widget import PickBox
from fdcad.ui.body_tools.forms import FORMS
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.features.phase3_parts import add_sketch
from tests.core.features.test_deform import _bar
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def _open(qtbot: QtBot, window: MainWindow, with_path: bool = False) -> DocumentTab:  # noqa: F811
    doc, _bar_id = _bar()
    if with_path:
        path = Sketch()
        path.add_arc(-80.0, 0.0, 80.0, 0.0, math.pi / 2)
        add_sketch(doc, path, {"feature": "f3"})
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = window.add_session(session)
    return tab


def test_commands_forms_and_icons(window: MainWindow) -> None:  # noqa: F811
    for ftype in TYPES:
        cid = f"feature.{ftype}"
        assert cid in BY_ID and cid in window.commands.actions
        assert flow.COMMAND_TYPES[cid][0] == ftype
        assert ftype in FORMS


@pytest.mark.parametrize("ftype", ["twist", "bend", "taper", "stretch"])
def test_new_feature_panel_preview_and_ok(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    ftype: str,
) -> None:
    tab = _open(qtbot, window)
    session = tab.session
    assert flow.start(window, f"feature.{ftype}")
    panel = window.panel
    assert panel is not None and panel.feature is not None
    feature = panel.current_feature()
    assert feature is not None
    # Defaults fit the bar: the triad at its centre, the trim planes at its ends.
    start, end = feature.params["start"], feature.params["end"]
    assert isinstance(start, Param) and start.value == pytest.approx(-50.0)
    assert isinstance(end, Param) and end.value == pytest.approx(50.0)
    report = session.report
    assert report is not None
    preview = build_preview(session.document, feature, report.results)
    assert preview.error is None and preview.shape is not None
    assert {"ox", "oy", "oz", "start", "end"} <= {h.param for h in preview.handles}
    # Dragging the end trim plane's arrow changes the End field.
    panel.set_value("end", 40.0)
    edited = panel.current_feature()
    assert edited is not None and edited.params["end"] == Param("40", 40.0)
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        panel.accept()
    added = session.document.features[-1]
    assert added.type == ftype
    result = session.report.results[added.id] if session.report else None
    assert result is not None and result.body is not None
    assert valid_solid(result.body.shape)
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        session.undo.undo()
    assert session.document.features[-1].type == "extrude"


def test_flow_picks_a_sketch_curve(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window, with_path=True)
    session = tab.session
    assert flow.start(window, "feature.flow")
    panel = window.panel
    assert panel is not None
    form = panel.body_form
    box = form.widgets["path"]
    assert isinstance(box, PickBox) and box.combo is not None
    box.combo.setCurrentIndex(box.combo.count() - 1)
    box.combo.activated.emit(box.combo.count() - 1)
    feature = panel.current_feature()
    assert feature is not None
    assert feature.refs["path"]["feature"] == session.document.features[-1].id
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        panel.accept()
    report = session.report
    assert report is not None and report.body is not None
    assert volume_of(report.body.shape) == pytest.approx(10000.0, rel=5e-3)


@pytest.mark.parametrize("ftype", ["twist", "stretch"])
def test_a_new_axis_fits_the_trim_planes_to_the_body(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    ftype: str,
) -> None:
    """Axis X kept the Start and End fitted to Z, so the planes sat 45 mm past a 10 mm bar."""
    tab = _open(qtbot, window)
    assert flow.start(window, f"feature.{ftype}")
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    panel.body_form.widgets["ox"].edit.setText("2")  # a moved triad stays where it is
    axis = panel.body_form.widgets["axis"]
    axis.setCurrentIndex(axis.findData("x"))
    feature = panel.current_feature()
    assert feature is not None and feature.params["axis"] == "x"
    assert feature.params["ox"] == Param("2", 2.0)
    assert feature.params["start"] == Param("-7", -7.0)
    assert feature.params["end"] == Param("3", 3.0)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=30000):
        panel.accept()
    report = tab.session.report
    result = report.results[feature.id] if report is not None else None
    assert result is not None and result.body is not None and valid_solid(result.body.shape)


@pytest.mark.parametrize(
    ("ftype", "name", "text"), [("stretch", "distance", "0.4"), ("bend", "radius", "2")]
)
def test_inch_parts_get_inch_defaults(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    ftype: str,
    name: str,
    text: str,
) -> None:
    """In an inch part the mm default "0.01" was read as 0.01 inch: a 0.254 mm tolerance."""
    from fdcad.core.units import UnitSystem

    doc, _bar_id = _bar()
    doc.units = UnitSystem.IN
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    assert flow.start(window, f"feature.{ftype}")
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    if ftype == "bend":
        by = panel.body_form.widgets["bend_by"]
        by.setCurrentIndex(by.findData("radius"))
    feature = panel.current_feature()
    assert feature is not None
    tolerance = feature.params["tolerance"]
    assert isinstance(tolerance, Param) and tolerance.expr == "0.0004"
    assert tolerance.value == pytest.approx(0.01016)
    value = feature.params[name]
    assert isinstance(value, Param) and value.expr == text
    assert value.value == pytest.approx(float(text) * 25.4)


def test_picking_a_body_moves_the_triad_to_it(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """A body picked after Twist started kept the triad and planes fitted to every body."""
    from fdcad.core.features.solids import solids
    from tests.core.features.phase3_parts import add_extrude, face_ref, rect

    doc, _bar_id = _bar()
    other = Sketch()
    rect(other, 20, -5, 30, 5)
    second = add_extrude(doc, add_sketch(doc, other, {"feature": "f2"}), 10.0, merge=False)
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    report = session.report
    assert report is not None and report.body is not None
    assert len(solids(report.body.shape)) == 2
    assert flow.start(window, "feature.twist")
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    box = panel.body_form.widgets["bodies"]
    assert isinstance(box, PickBox)
    box.add(face_ref(report.body, f"{second}/cap/end"), "Body 2")
    feature = panel.current_feature()
    assert feature is not None
    assert feature.params["ox"].value == pytest.approx(25.0)
    assert feature.params["oz"].value == pytest.approx(5.0)
    assert feature.params["start"].value == pytest.approx(-5.0)
    assert feature.params["end"].value == pytest.approx(5.0)
