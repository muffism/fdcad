"""Command tabs, view toolbar and status bar (PHASE1_CORRECTIONS L1, L2, L5, L6, C6)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QAction, QMouseEvent
from PySide6.QtWidgets import QApplication, QWidget
from pytestqt.qtbot import QtBot

from fdcad.core.units import UnitSystem
from fdcad.ui import icons, strings
from fdcad.ui.command_tabs.ribbon import CompactButton, LargeButton, RibbonPanel
from fdcad.ui.command_tabs.tabs import SKETCH_GROUPS, CommandTabs, HoldToMoveTabBar, build_panel
from fdcad.ui.main_window.status_bar import sketch_state
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.node_editor.strings import TAB_GRAPH
from fdcad.ui.strings_sheetmetal import TAB_SHEET_METAL as SHEET_TAB
from tests.ui.test_main_window import _folders, _open_plate, window

__all__ = ["_folders", "window"]


def _buttons(window: MainWindow, name: str) -> dict[str, LargeButton | CompactButton]:
    tabs = window.command_tabs
    panel = tabs.widget(tabs.index_of(name))
    found: dict[str, LargeButton | CompactButton] = {}
    for button in panel.findChildren(QWidget):
        if isinstance(button, LargeButton | CompactButton):
            for action in button.group_actions:
                cid = next(k for k, v in window.commands.actions.items() if v is action)
                found[cid] = button
    return found


def test_tabs_in_order(window: MainWindow) -> None:
    tabs = window.command_tabs
    titles = [tabs.tabText(i) for i in range(tabs.count())]
    # PLAN section 8 item 1: Features, Sketch, Sheet Metal (Phase 5), Evaluate, Graph (Phase 7).
    assert titles == [
        strings.TAB_FEATURES,
        strings.TAB_SKETCH,
        strings.TAB_BODIES,
        strings.TAB_PRINT,
        SHEET_TAB,
        strings.TAB_EVALUATE,
        TAB_GRAPH,
    ]


def test_main_tools_are_large_and_the_rest_compact(window: MainWindow) -> None:
    features = _buttons(window, "features")
    # Add Material and Remove Material mirror each other (polish round 2).
    for cid in (
        "feature.extrude",
        "feature.revolve",
        "feature.extruded_cut",
        "feature.revolved_cut",
    ):
        assert isinstance(features[cid], LargeButton)
        assert features[cid].toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextUnderIcon
    # Families share one large dropdown button (D435).
    assert features["feature.fillet"] is features["feature.chamfer"]
    assert isinstance(features["feature.fillet"], LargeButton)
    assert features["feature.ref_plane"] is features["feature.coord_system"]
    assert features["feature.linear_pattern"] is features["feature.sketch_pattern"]
    assert isinstance(features["feature.mirror"], CompactButton)  # own button (RIBBON_SPEC R1)
    assert "edit.rebuild" not in features  # Rebuild lives in the Evaluate tab and Ctrl+B
    sketch = _buttons(window, "sketch")
    assert isinstance(sketch["sketch.sketch"], LargeButton)
    assert isinstance(sketch["sketch.dimension"], LargeButton)
    line = sketch["sketch.line"]
    assert isinstance(line, CompactButton) and line is sketch["sketch.centerline"]
    assert line.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon
    assert sketch["sketch.center_arc"] is sketch["sketch.three_point_arc"]


def test_every_button_has_an_icon_and_a_rich_tooltip(window: MainWindow) -> None:
    for name in ("features", "sketch", "evaluate"):
        for cid, button in _buttons(window, name).items():
            action = window.commands.actions[cid]
            assert not action.icon().isNull(), cid
            assert action.toolTip().startswith("<b>"), cid
            assert strings.TOOLTIP_TEXT[cid] in action.toolTip(), cid
            assert not button.icon().isNull(), cid


def test_menu_actions_carry_icons(window: MainWindow) -> None:
    listed = set(icons.listed_names())
    for cid, action in window.commands.actions.items():
        if cid in listed:
            assert not action.icon().isNull(), cid


def test_dropdown_remembers_the_last_tool(qtbot: QtBot) -> None:
    owner = QWidget()
    qtbot.addWidget(owner)
    ids = ["sketch.line", "sketch.centerline", "sketch.circle"]
    actions = {cid: QAction(cid, owner) for cid in ids}
    panel = build_panel("sketch", SKETCH_GROUPS, actions)  # other tools are left out
    qtbot.addWidget(panel)
    line = next(b for b in panel.buttons() if actions["sketch.line"] in b.group_actions)
    assert line.defaultAction() is actions["sketch.line"]
    assert line.menu() is not None
    actions["sketch.centerline"].trigger()
    assert line.defaultAction() is actions["sketch.centerline"]
    assert len(panel.buttons()) == 2  # line group and circle


def test_tab_bar_menu_hides_and_remembers_tabs(window: MainWindow) -> None:
    tabs = window.command_tabs
    menu = tabs.tab_menu()
    texts = [a.text() for a in menu.actions()]
    assert texts[:7] == [
        strings.TAB_FEATURES,
        strings.TAB_SKETCH,
        strings.TAB_BODIES,
        strings.TAB_PRINT,
        SHEET_TAB,
        strings.TAB_EVALUATE,
        TAB_GRAPH,
    ]
    from fdcad.ui.command_tabs.custom import SHOW_HIDDEN, SIMPLE_MODE  # TR222 (D2508)

    assert texts[8:] == [
        strings.TABS_SHOW_ALL,
        strings.TABS_RESET_ORDER,
        "",
        SHOW_HIDDEN,
        SIMPLE_MODE,
    ]
    menu.actions()[5].setChecked(False)
    assert not tabs.isTabVisible(5)
    assert window.settings.hidden_command_tabs == ["evaluate"]
    for index in (6, 0, 1, 2, 3):  # Graph, Features, Sketch, Bodies, 3D Print
        tabs.set_tab_shown(index, False)
    tabs.set_tab_shown(4, False)  # Sheet Metal is the last visible tab, so it stays
    assert tabs.isTabVisible(4)
    tabs.show_tab("evaluate")
    assert tabs.isTabVisible(5) and tabs.currentIndex() == 5
    menu.close()


def test_view_toolbar_and_corner(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ = _open_plate(qtbot, window)
    toolbar = tab.view_toolbar
    assert set(toolbar.buttons) == {
        "view.fit",
        "view.zoom_area",
        "view.section",  # PLAN 8 item 3 (P2.13, D253)
        "edit.appearance",  # colours easy to find (owner request)
        "views",
        "styles",
        "visibility",  # Hide or Show Items (D1089)
    }
    for button in toolbar.buttons.values():
        assert not button.icon().isNull()
    before = toolbar.styles.icon().pixmap(20).toImage()
    window.commands.actions["view.wireframe"].trigger()
    assert toolbar.styles.icon().pixmap(20).toImage() != before
    assert tab.corner_ok.text() == "" and not tab.corner_ok.icon().isNull()
    assert not tab.corner_cancel.icon().isNull()


def test_view_toolbar_says_what_each_button_does(qtbot: QtBot, window: MainWindow) -> None:
    # D1089: every button has a title and a line saying what it does on hover, and
    # the eye button lists each kind of item to show or hide, plus hidden bodies.
    tab, _ = _open_plate(qtbot, window)
    toolbar = tab.view_toolbar
    for name, button in toolbar.buttons.items():
        assert "<br>" in button.toolTip(), name
    hover = toolbar.visibility_list
    assert hover is not None
    rows = [a for a in hover.rows() if a is not None]
    texts = [a.text() for a in rows]
    for wanted in ("Planes", "Axes", "Points", "Sketches", "Hide All Types"):
        assert wanted in texts, texts
    assert window.commands.actions["view.show_all_bodies"] in rows
    planes = next(a for a in rows if a.text() == "Planes")
    planes.trigger()  # the same action as View > Show Types > Planes
    assert "planes" in tab.hidden_types
    planes.trigger()
    assert "planes" not in tab.hidden_types


def test_opening_the_eye_list_keeps_the_show_types_actions(
    qtbot: QtBot, window: MainWindow
) -> None:
    # D1093: the eye menu cleared itself each time it opened, which deleted the Show
    # Types actions, and Hide All Types then failed with "already deleted".
    import shiboken6

    tab, _ = _open_plate(qtbot, window)
    hover = tab.view_toolbar.visibility_list
    assert hover is not None
    for _ in range(3):
        hover.open_list()
        qtbot.wait(20)
    hover.hide()
    assert all(shiboken6.isValid(a) for a in window._type_toggles)
    window.hide_all_types()
    assert not window.type_actions["planes"].isChecked()
    window.hide_all_types()  # and back as they were
    assert window.type_actions["planes"].isChecked()


def test_clicking_the_eye_hides_everything_and_resting_on_it_lists_each_kind(
    qtbot: QtBot, window: MainWindow
) -> None:
    # D1096 (owner request): a click on the eye hides every kind at once and a second
    # click shows them again; resting the pointer on it opens the list, which takes no
    # mouse grab, so the click still reaches the eye.
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QCheckBox

    tab, _ = _open_plate(qtbot, window)
    eye = tab.view_toolbar.visibility
    hover = tab.view_toolbar.visibility_list
    assert hover is not None and eye.menu() is None and not eye.isChecked()
    QApplication.sendEvent(eye, QEvent(QEvent.Type.Enter))
    qtbot.waitUntil(hover.isVisible, timeout=2000)
    boxes = {b.text(): b for b in hover.findChildren(QCheckBox)}
    assert boxes["Planes"].isChecked()
    boxes["Planes"].click()  # a tick in the list turns the kind off
    assert not window.type_actions["planes"].isChecked()
    boxes["Planes"].click()
    assert window.type_actions["planes"].isChecked()
    window.type_actions["axes"].setChecked(False)  # one kind already off
    eye.click()
    assert not window.type_actions["planes"].isChecked()
    assert not window.show_sketches_action.isChecked()
    assert not boxes["Planes"].isChecked()  # the open list follows
    assert eye.isChecked()  # looks pressed while everything is hidden
    eye.click()
    assert window.type_actions["planes"].isChecked()
    assert window.show_sketches_action.isChecked()
    assert not window.type_actions["axes"].isChecked()  # back as it was, not all on
    assert not eye.isChecked()
    hover.hide()


def test_turning_planes_off_takes_them_off_the_screen(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    # D1092: Show Types redrew only the part, so the bike frame's 17 construction planes
    # stayed on screen after Planes was turned off; the plane picker drew them all too.
    from fdcad.core.document.model import Feature, Param
    from fdcad.ui.main_window.plane_pick import picker_faces
    from fdcad.ui.session import DocumentSession
    from tests.core.features.test_features import plate

    doc, _ext = plate()
    fid = doc.new_feature_id()
    params = {"method": "offset", "distance": Param("5", 5.0)}
    doc.features.append(
        Feature(fid, "ref_plane", "Helper Plane", params=params, refs={"first": {"feature": "f2"}})
    )
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = window.add_session(session)
    drawn: list[set[str]] = []
    monkeypatch.setattr(
        tab.viewport,
        "show_reference_planes",
        lambda planes, _names=None: drawn.append(set(planes)),
        raising=False,
    )
    main = {f.id for f in doc.features if isinstance(f.params.get("basis"), str)}
    assert set(picker_faces(tab)) == main | {fid}  # a reference plane on show can be picked
    window.type_actions["planes"].setChecked(False)
    assert drawn and drawn[-1] == set()  # off the screen at once
    assert set(picker_faces(tab)) == main  # only the three main planes to pick from
    window.type_actions["planes"].setChecked(True)
    assert drawn[-1] == {fid}


def test_status_bar_order_units_and_sketch_status(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ = _open_plate(qtbot, window)
    bar = window.statusBar()
    widgets = [window.bodies, window.progress, window.sketch_status, window.coords]
    xs = [w.x() for w in [*widgets, window.unit_button] if w.isVisible()]
    assert xs == sorted(xs)  # unit selector at the far right
    assert window.unit_button.parent() is not None and bar.isAncestorOf(window.unit_button)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        window.unit_button.unit_actions[UnitSystem.IN].trigger()
    assert tab.session.document.units is UnitSystem.IN
    assert window.unit_button.text() == "in"
    assert window.unit_button.unit_actions[UnitSystem.IN].isChecked()
    window.sketch_status.setText(strings.SKETCH_STATUS["over"].format(message="x"))
    assert window.sketch_status.state == "over" and window.sketch_status.isVisibleTo(bar)
    window.sketch_status.setText("")
    assert not window.sketch_status.isVisibleTo(bar)


def test_sketch_state_from_text() -> None:
    assert sketch_state(strings.SKETCH_STATUS["under"].format(dof=3)) == "under"
    assert sketch_state(strings.SKETCH_STATUS["full"]) == "full"
    assert sketch_state("Ready") is None


def test_theme_change_redraws_icons(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ = _open_plate(qtbot, window)
    with qtbot.waitSignal(window.command_tabs.icons_changed):
        window.command_tabs.theme_changed()
    assert not window.commands.actions["sketch.line"].icon().isNull()
    assert not tab.view_toolbar.styles.icon().isNull()


def test_window_fits_a_small_screen_and_tabs_scroll(qtbot: QtBot, window: MainWindow) -> None:
    # The Features and Sketch tabs made the window at least 1330 px wide, wider
    # than a 1280 px screen (round 10e, D632). The tabs now scroll sideways.
    from PySide6.QtCore import QPoint, QPointF
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtWidgets import QApplication

    from fdcad.ui.preferences.settings import Theme
    from fdcad.ui.themes import theme

    app = QApplication.instance()
    assert isinstance(app, QApplication)
    theme.apply_theme(app, Theme.LIGHT)
    try:
        assert window.minimumSizeHint().width() < 1024
        window.resize(1024, 700)
        tabs = window.command_tabs
        tabs.setCurrentIndex(tabs.index_of("features"))
        qtbot.wait(20)
        features = tabs.widget(tabs.index_of("features"))
        assert isinstance(features, RibbonPanel)
        bar = features.scroll_area.horizontalScrollBar()
        assert bar.maximum() > 0  # the rest of the groups is one scroll away
        # The thin scroll bar never covers the group captions.
        viewport = features.scroll_area.viewport().height()
        assert viewport >= features.content.minimumSizeHint().height()
        # The mouse wheel scrolls the tab sideways.
        wheel = QWheelEvent(
            QPointF(10, 10),
            QPointF(features.mapToGlobal(QPoint(10, 10))),
            QPoint(0, 0),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        features.wheelEvent(wheel)
        assert bar.value() > 0
    finally:
        theme.apply_theme(app, Theme.LIGHT)


def test_compact_labels_are_never_cut(qtbot: QtBot, window: MainWindow) -> None:
    # Compact buttons fixed their width before the style sheet padding was known,
    # so a narrow window cut "Swept Boss" to "Sw...ss" (round 10e, D632).
    window.resize(1024, 700)
    tabs = window.command_tabs
    for index in range(tabs.count()):
        tabs.setCurrentIndex(index)
        qtbot.wait(10)
        panel = tabs.widget(index)
        assert isinstance(panel, RibbonPanel)
        for button in panel.buttons():
            if isinstance(button, CompactButton):
                assert button.width() >= button.sizeHint().width(), button.text()


def test_every_tab_has_the_panel_colour(qtbot: QtBot, window: MainWindow) -> None:
    # Only Features, Sketch and Evaluate had the panel colour, so on the other
    # tabs the selected tab did not join its panel (round 10e, D632).
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QApplication

    from fdcad.ui.preferences.settings import Theme
    from fdcad.ui.themes import theme

    app = QApplication.instance()
    assert isinstance(app, QApplication)
    theme.apply_theme(app, Theme.DARK)
    try:
        window.resize(2400, 900)
        tabs = window.command_tabs
        # Every tab's tools sit on the same raised card, on the window colour (D1034).
        card, gap = QColor(theme.chrome().raised), QColor(theme.chrome().window)
        for index in range(tabs.count()):
            tabs.setCurrentIndex(index)
            qtbot.wait(10)
            panel = tabs.widget(index)
            assert isinstance(panel, RibbonPanel)
            image = panel.grab().toImage()
            inside = image.pixelColor(image.width() - 24, image.height() // 2)
            assert inside == card, (tabs.tabText(index), inside.name(), card.name())
            edge = image.pixelColor(image.width() - 2, image.height() // 2)
            assert edge == gap, (tabs.tabText(index), edge.name(), gap.name())
    finally:
        theme.apply_theme(app, Theme.LIGHT)


def _mouse(bar: QWidget, kind: QEvent.Type, pos: QPoint, held: bool = True) -> None:
    buttons = Qt.MouseButton.LeftButton if held else Qt.MouseButton.NoButton
    event = QMouseEvent(
        kind,
        QPointF(pos),
        QPointF(bar.mapToGlobal(pos)),
        Qt.MouseButton.LeftButton if kind != QEvent.Type.MouseMove else Qt.MouseButton.NoButton,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(bar, event)


def _drag(qtbot: QtBot, tabs: CommandTabs, src: int, dst: int, hold: bool) -> None:
    bar = tabs.tabBar()
    start = bar.tabRect(src).center()
    end = bar.tabRect(dst).center() + QPoint(bar.tabRect(dst).width() // 3, 0)
    _mouse(bar, QEvent.Type.MouseButtonPress, start)
    if hold:
        qtbot.wait(HoldToMoveTabBar.HOLD_MS + 150)
    steps = 12
    for k in range(1, steps + 1):
        pos = start + (end - start) * (k / steps)
        _mouse(bar, QEvent.Type.MouseMove, QPoint(round(pos.x()), round(pos.y())))
        qtbot.wait(5)
    _mouse(bar, QEvent.Type.MouseButtonRelease, end, held=False)
    qtbot.wait(300)  # the moving tab animates into place


def test_quick_drag_does_not_move_tabs(qtbot: QtBot, window: MainWindow) -> None:
    tabs = window.command_tabs
    before = tabs.names()
    _drag(qtbot, tabs, 0, 2, hold=False)
    assert tabs.names() == before
    assert not tabs.tabBar().isMovable()


def test_hold_and_drag_moves_a_tab_and_remembers(qtbot: QtBot, window: MainWindow) -> None:
    tabs = window.command_tabs
    window.settings.command_tab_order = []
    _drag(qtbot, tabs, 0, 2, hold=True)
    names = tabs.names()
    assert names[0] != "features" and "features" in names[1:3]
    assert window.settings.command_tab_order == names
    assert not tabs.tabBar().isMovable()  # back to click only after release
    # A new window puts the tabs in the saved order.
    tabs.move_to_order(["sketch"])
    assert tabs.names()[0] == "sketch"
    tabs.reset_order()
    assert tabs.names()[:3] == ["features", "sketch", "bodies"]
    assert window.settings.command_tab_order == []


def test_saved_order_is_applied_and_unknown_names_skipped(window: MainWindow) -> None:
    tabs = window.command_tabs
    window.settings.command_tab_order = ["print", "gone_tab", "evaluate"]
    tabs.apply_saved_order()
    names = tabs.names()
    assert names[:2] == ["print", "evaluate"]
    assert sorted(names) == sorted(tabs._default_order)
    tabs.reset_order()


def test_tabs_button_and_show_all(window: MainWindow) -> None:
    tabs = window.command_tabs
    button = tabs.cornerWidget(Qt.Corner.TopLeftCorner)
    assert button is tabs.tabs_button and button.toolTip() == strings.TABS_BUTTON_TIP
    tabs.set_tab_shown(tabs.index_of("print"), False)
    assert window.settings.hidden_command_tabs == ["print"]
    tabs.show_all()
    assert all(tabs.isTabVisible(i) for i in range(tabs.count()))
    assert window.settings.hidden_command_tabs == []


def test_leaving_a_sketch_goes_to_features_after_reorder(window: MainWindow) -> None:
    tabs = window.command_tabs
    tabs.move_to_order(["sketch", "features"])
    tabs.show_tab("features")
    assert tabs.currentWidget().objectName() == "features_tab"
    tabs.reset_order()
