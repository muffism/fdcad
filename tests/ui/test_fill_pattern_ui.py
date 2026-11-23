"""Fill Pattern panel (TR57, D792)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.body_tools import flow
from fdcad.ui.body_tools.forms import FORMS
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_command_icon_and_form() -> None:
    from fdcad.ui.command_tabs.tabs import FEATURE_GROUPS
    from fdcad.ui.icons.audit import audit

    assert BY_ID["feature.fill_pattern"].label == "Fill Pattern"
    assert BY_ID["feature.fill_pattern"].keys == () and audit("feature.fill_pattern") == []
    assert "feature.fill_pattern" in repr(FEATURE_GROUPS)
    names = {f.name for f in FORMS["fill_pattern"].fields()}
    assert {"face", "layout", "spacing", "row_spacing", "margin", "shape", "skip"} <= names


def test_a_cut_shape_hides_the_seed_picks(qtbot: QtBot, window: MainWindow) -> None:
    tab, ids = _open(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    top = report.body.face(f"{ids['plate']}/cap/end")
    window._selection_changed(tab, [top])
    assert flow.start(window, "feature.fill_pattern")
    panel = window.panel
    assert panel is not None and panel.feature is not None
    assert panel.feature.name == "Fill Pattern 1"
    form = panel.body_form

    def shown() -> set[str]:
        return {f.name for f in form.shown_fields()}

    assert "features" in shown() and "size" not in shown()
    shape = form.widgets["shape"]
    shape.setCurrentIndex(shape.findData("circle"))
    assert "size" in shown() and "features" not in shown()
    layout = form.widgets["layout"]
    layout.setCurrentIndex(layout.findData("staggered"))
    assert "stagger_angle" in shown() and "row_spacing" not in shown()
    edited = panel.current_feature()
    assert edited is not None and edited.params["shape"] == "circle"
    with qtbot.waitSignal(tab.session.rebuilt, timeout=30000):
        panel.accept()
    made = tab.session.document.features[-1]
    assert made.type == "fill_pattern"
    built = tab.session.report
    assert built is not None
    result = built.results[made.id]
    assert result.state.value != "error", [i.message for i in result.issues]
    assert result.extras["count"] > 0


def test_the_panel_shows_the_count(qtbot: QtBot, window: MainWindow) -> None:
    """The number of copies shows in the panel (TR57 item 3)."""
    from fdcad.core.features.preview import build_preview

    tab, ids = _open(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    window._selection_changed(tab, [report.body.face(f"{ids['plate']}/cap/end")])
    assert flow.start(window, "feature.fill_pattern")
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    label = panel.body_form.count_label
    assert label is not None and label.text() == "Not counted yet"
    shape = panel.body_form.widgets["shape"]
    shape.setCurrentIndex(shape.findData("circle"))
    feature = panel.current_feature()
    assert feature is not None
    doc = tab.session.document
    geometry = build_preview(doc, feature, report.results)
    assert geometry.error is None and geometry.info["count"] > 0
    panel.preview_checked(geometry)
    assert label.text() == str(int(geometry.info["count"]))
    panel.reject()


def test_size_gradient_fields(qtbot: QtBot, window: MainWindow) -> None:
    """TR324 (D1518): the end size and origin show once the gradient is ticked."""
    tab, ids = _open(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    window._selection_changed(tab, [report.body.face(f"{ids['plate']}/cap/end")])
    assert flow.start(window, "feature.fill_pattern")
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    form = panel.body_form
    shape = form.widgets["shape"]
    shape.setCurrentIndex(shape.findData("circle"))
    names = {f.name for f in form.shown_fields()}
    assert "gradient" in names and "size_end" not in names
    form.widgets["gradient"].setChecked(True)
    names = {f.name for f in form.shown_fields()}
    assert {"size_end", "gradient_from"} <= names
    made = panel.current_feature()
    assert made is not None and made.params["gradient"] is True
    assert made.params["size_end"].value == 8.0
    panel.reject()
