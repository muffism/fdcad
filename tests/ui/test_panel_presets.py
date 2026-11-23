"""Presets for any panel: favourites everywhere, rename, and what new ones start with
(TR326, D947)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.ui.main_window.new_feature import new_feature
from fdcad.ui.preferences import phase4_settings as prefs
from fdcad.ui.property_panel.panel import PropertyPanel
from tests.core.features.test_features import plate
from tests.ui.test_property_panel import _session


def test_settings_store() -> None:
    assert prefs.preset_default("extrude") == prefs.FACTORY
    assert prefs.start_params("extrude") is None
    prefs.set_favourites("extrude", {"Deep": {"depth": {"expr": "25", "value": 25.0}}})
    prefs.set_preset_default("extrude", "Deep")
    assert prefs.start_params("extrude") == {"depth": {"expr": "25", "value": 25.0}}
    assert prefs.rename_favourite("extrude", "Deep", "Very deep")
    assert prefs.preset_default("extrude") == "Very deep"
    assert not prefs.rename_favourite("extrude", "Very deep", " ")
    assert not prefs.rename_favourite("extrude", "Missing", "Other")
    prefs.set_favourites("extrude", {})
    assert prefs.start_params("extrude") is None  # the chosen favourite is gone
    prefs.set_last_used("extrude", {"depth": {"expr": "7", "value": 7.0}})
    prefs.set_preset_default("extrude", prefs.LAST_USED)
    assert prefs.start_params("extrude") == {"depth": {"expr": "7", "value": 7.0}}


def test_every_panel_has_favourites_and_start_settings(qtbot: QtBot) -> None:
    doc, _ext = plate()
    session = _session(qtbot, doc)
    sketch = next(f for f in doc.features if f.type == "sketch")
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    panel.begin(session, new_feature(doc, sketch, "extrude", "boss"), is_new=True)
    assert "favourites" in panel.groups
    box = panel.presets_box
    assert box.buttons["rename"].text() and not box.buttons["rename"].isEnabled()
    panel.values["depth"].edit.setText("25")
    assert box.save("Deep")
    assert box.rename("Deep", "Deep one") and box.names.currentText() == "Deep one"
    box.set_default("Deep one")
    assert box.start_with.currentData() == "Deep one"
    # A command start uses it; the command's Boss or Cut stays.
    panel.begin(session, new_feature(doc, sketch, "extrude", "cut"), is_new=True, preset=True)
    feature = panel.current_feature()
    assert feature is not None
    assert feature.params["depth"].value == 25.0
    assert feature.params["operation"] == "cut"
    # Other starts (a drag, editing) do not.
    panel.begin(session, new_feature(doc, sketch, "extrude", "boss"), is_new=True)
    feature = panel.current_feature()
    assert feature is not None and feature.params["depth"].value != 25.0


def test_last_used(qtbot: QtBot) -> None:
    doc, _ext = plate()
    session = _session(qtbot, doc)
    sketch = next(f for f in doc.features if f.type == "sketch")
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    made = new_feature(doc, sketch, "extrude", "boss")
    made.params["depth"] = Param("13", 13.0)
    panel.begin(session, made, is_new=True)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        panel.accept()
    stored = prefs.last_used("extrude")
    assert stored is not None
    prefs.set_preset_default("extrude", prefs.LAST_USED)
    panel.begin(session, new_feature(doc, sketch, "extrude", "boss"), is_new=True, preset=True)
    feature = panel.current_feature()
    assert feature is not None and feature.params["depth"].value == 13.0
