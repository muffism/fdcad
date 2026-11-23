"""Clicking a pattern instance marker in the view (TR59 item 4, D2400)."""

from __future__ import annotations

from PySide6.QtCore import QPoint
from pytestqt.qtbot import QtBot

from fdcad.core.features.preview import PreviewGeometry
from fdcad.ui.body_tools.flow import new_feature
from fdcad.ui.property_panel.panel import PropertyPanel
from fdcad.ui.viewport.preview import FeaturePreview
from fdcad.ui.viewport.value_labels import MARKER_PREFIX, feature_labels
from tests.core.features.test_features import plate
from tests.ui.test_property_panel import _session
from tests.ui.test_value_labels import LabelView

MARKERS = [("2", (12.0, 0.0, 0.0)), ("1.2", (0.0, 20.0, 0.0))]


def _pattern_panel(qtbot: QtBot, preview: FeaturePreview | None = None) -> PropertyPanel:
    doc, _ext = plate()
    session = _session(qtbot, doc)
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    if preview is not None:
        view = LabelView()
        qtbot.addWidget(view)
        preview.bind(panel, lambda: view)
    panel.begin(session, new_feature(doc, "linear_pattern", {}), is_new=True)
    return panel


def test_markers_are_labels_only_on_pattern_panels(qtbot: QtBot) -> None:
    panel = _pattern_panel(qtbot)
    geometry = PreviewGeometry(None, anchor=None, markers=MARKERS)
    labels = [label for label in feature_labels(panel, geometry) if label.param.startswith("i")]
    assert [(label.param, label.text, label.point) for label in labels] == [
        (f"{MARKER_PREFIX}2", "#2", (12.0, 0.0, 0.0)),
        (f"{MARKER_PREFIX}1.2", "#1.2", (0.0, 20.0, 0.0)),
    ]
    panel.reject()
    doc, ext = plate()
    other = PropertyPanel()
    qtbot.addWidget(other)
    other.begin(_session(qtbot, doc), doc.feature(ext), is_new=False)
    assert not [
        label
        for label in feature_labels(other, PreviewGeometry(None, markers=MARKERS))
        if label.param.startswith(MARKER_PREFIX)
    ]
    other.reject()


def test_clicking_a_marker_starts_the_copy_entry(qtbot: QtBot) -> None:
    preview = FeaturePreview()
    panel = _pattern_panel(qtbot, preview)
    line = panel.body_form.widgets["instance_values"]
    line.setText("2: depth 4")
    assert preview.edit_value(f"{MARKER_PREFIX}1.2", QPoint(5, 5)) is None
    assert line.text() == "2: depth 4; 1.2: "
    preview.edit_value(f"{MARKER_PREFIX}2", QPoint(5, 5))  # already there: kept as it is
    assert line.text().rstrip() == "2: depth 4; 1.2:"
    assert line.cursorPosition() == len(line.text())
    panel.reject()


def test_a_box_over_markers_skips_those_copies(qtbot: QtBot) -> None:
    """TR270 item 3 (D2401): box the markers to skip, Ctrl box to bring them back."""
    preview = FeaturePreview()
    panel = _pattern_panel(qtbot, preview)
    line = panel.body_form.widgets["skip"]
    line.setText("3")
    preview.skip_boxed([f"{MARKER_PREFIX}2", f"{MARKER_PREFIX}2.2", "depth"])
    assert line.text() == "3, 2, 2.2"
    assert panel.feature is not None
    preview.skip_boxed([f"{MARKER_PREFIX}3", f"{MARKER_PREFIX}4"], True)
    assert line.text() == "2, 2.2, 4"
    panel.reject()


def test_the_view_finds_markers_inside_a_box(qtbot: QtBot) -> None:
    from PySide6.QtCore import QPointF

    from fdcad.ui.viewport.widget import ViewportWidget

    view = ViewportWidget.__new__(ViewportWidget)
    view._view = object()  # type: ignore[attr-defined]
    view._dpr = 1.0  # type: ignore[attr-defined]
    view._value_items = [  # type: ignore[attr-defined]
        (f"{MARKER_PREFIX}2", (10.0, 10.0, 0.0), "#2", None),
        (f"{MARKER_PREFIX}3", (50.0, 50.0, 0.0), "#3", None),
        ("depth", (12.0, 12.0, 0.0), "4 mm", None),
    ]
    view._screen = lambda p: (p[0], p[1])  # type: ignore[attr-defined]
    view._px = lambda q: (q.x(), q.y())  # type: ignore[attr-defined]
    assert view.markers_in(QPointF(20, 20), QPointF(0, 0)) == [f"{MARKER_PREFIX}2"]
    assert view.markers_in(QPointF(60, 60), QPointF(70, 70)) == []
