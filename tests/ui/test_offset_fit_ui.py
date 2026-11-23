"""Fit presets on Offset Face in the app (PLAN Phase 4, D311, D413): the tolerance comes from
the active printer profile and is written only once a fit is chosen."""

from __future__ import annotations

import math
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QComboBox
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.features.solids import volume_of
from fdcad.core.printing.profiles import PrinterProfile
from fdcad.ui.body_tools import flow
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.preferences import phase4_settings as prefs
from fdcad.ui.preferences import print_settings
from fdcad.ui.preferences.settings import Settings
from tests.ui.test_body_tools import BASE, _hole_wall, _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


@pytest.fixture(autouse=True)
def temp_prefs(tmp_path: Path) -> Iterator[Settings]:
    store = Settings(QSettings(str(tmp_path / "fit.ini"), QSettings.Format.IniFormat))
    prefs.OVERRIDE = store
    yield store
    prefs.OVERRIDE = None


def test_fit_tolerance_comes_from_the_active_profile(temp_prefs: Settings) -> None:
    assert prefs.fit_tolerance() == pytest.approx(0.2)  # no profile saved yet: the default
    profiles = [PrinterProfile("A", fit_tolerance=0.1), PrinterProfile("B", fit_tolerance=0.35)]
    print_settings.set_profiles(temp_prefs, profiles, "B")
    assert prefs.fit_tolerance() == pytest.approx(0.35)
    prefs.set_fit_tolerance(0.25)  # changes the active profile only
    found = {p.name: p.fit_tolerance for p in print_settings.profiles(temp_prefs)}
    assert found == {"A": pytest.approx(0.1), "B": pytest.approx(0.25)}


def test_offset_face_fit_preset(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    temp_prefs: Settings,
) -> None:
    print_settings.set_profiles(temp_prefs, [PrinterProfile("P", fit_tolerance=0.3)], "P")
    tab, _ids = _open(qtbot, window)
    assert flow.start(window, "feature.offset_face", _hole_wall(tab))
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    form = panel.body_form
    shown = {f.name for f in form.shown_fields()}
    assert "print_fit" in shown and "fit_tolerance" not in shown
    edited = panel.current_feature()
    assert edited is not None and "print_fit" not in edited.params
    assert "fit_tolerance" not in edited.params  # not written while no fit is chosen
    fit = form.widgets["print_fit"]
    assert isinstance(fit, QComboBox)
    fit.setCurrentIndex(fit.findData("clearance"))
    assert "fit_tolerance" in {f.name for f in form.shown_fields()}
    form.widgets["distance"].edit.setText("0")
    edited = panel.current_feature()
    assert edited is not None and edited.params["print_fit"] == "clearance"
    tol = edited.params["fit_tolerance"]
    assert isinstance(tol, Param) and tol.value == pytest.approx(0.3)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        panel.accept()
    body = tab.session.report.body  # type: ignore[union-attr]
    assert body is not None
    # The 10 mm hole grows to 10.6 mm: 0.3 mm per side.
    expected = BASE + math.pi * 25 * 10 - math.pi * 5.3**2 * 10
    assert volume_of(body.shape) == pytest.approx(expected, rel=1e-7)


def test_fit_is_not_offered_for_translate(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab, _ids = _open(qtbot, window)
    assert flow.start(window, "feature.move_face", _hole_wall(tab))
    form = window.panel.body_form  # type: ignore[union-attr]
    assert "print_fit" not in {f.name for f in form.shown_fields()}
    window.panel.reject()  # type: ignore[union-attr]
