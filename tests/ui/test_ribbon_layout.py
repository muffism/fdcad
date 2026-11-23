"""Command tab layout checks (docs/RIBBON_SPEC.md R4, D640 to D644)."""

from __future__ import annotations

from itertools import combinations, pairwise

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from fdcad.ui import strings, strings_import, strings_phase3
from fdcad.ui.command_tabs.ribbon import (
    CompactButton,
    LargeButton,
    RibbonMenu,
    RibbonPanel,
    text_width,
)
from fdcad.ui.command_tabs.tabs import (
    FEATURE_GROUPS,
    GROUP_REFERENCE_CURVES,
    SKETCH_GROUPS,
    build_panel,
)
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_main_window import _folders, window

__all__ = ["_folders", "window"]

#: R1 item 1: tools most parts use, each with its own visible button.
OWN_BUTTON = ("feature.draft", "feature.shell", "feature.rib", "feature.mirror", "feature.hole")
#: R1 item 2: tools that only share a heading never share a dropdown.
NEVER_TOGETHER = (("feature.shell", "feature.draft"), ("feature.rib", "feature.wrap"))

#: R2 as (group title, [(kind, ids)]) in the order seen left to right, top to bottom.
FEATURES_R2: list[tuple[str, list[tuple[str, list[str]]]]] = [
    (strings.GROUP_SKETCH, [("large", ["sketch.sketch"])]),
    (
        strings.GROUP_BOSS,
        [
            ("large", ["feature.extrude"]),
            ("large", ["feature.revolve"]),
            ("small", ["feature.sweep"]),
            ("small", ["feature.loft", "feature.primitive"]),
        ],
    ),
    (
        strings.GROUP_CUT,
        [
            ("large", ["feature.extruded_cut"]),
            ("large", ["feature.hole", "feature.modeled_thread", "feature.cosmetic_thread"]),
            ("large", ["feature.revolved_cut"]),
            ("small", ["feature.swept_cut"]),
            ("small", ["feature.lofted_cut"]),
            ("small", ["feature.corner_relief"]),  # TR244 (D785)
            ("small", ["feature.shaft_shape"]),  # TR247 (D841)
            ("small", ["feature.ring_groove"]),  # TR249 (D874)
            ("small", ["feature.oring_groove"]),  # TR250 (D886)
        ],
    ),
    (
        strings.GROUP_MODIFY,
        [
            ("large", ["feature.fillet", "feature.chamfer"]),
            (
                "large",
                [
                    "feature.linear_pattern",
                    "feature.circular_pattern",
                    "feature.sketch_pattern",
                    "feature.table_pattern",
                    "feature.fill_pattern",  # TR57 (D792)
                    "feature.point_pattern",  # TR365 (D887)
                    "feature.pattern_chain",  # TR141 (D1901)
                ],
            ),
            ("small", ["feature.rib"]),
            ("small", ["feature.draft"]),
            ("small", ["feature.shell"]),
            ("small", ["feature.dome", "feature.roof"]),  # TR258 (D2414)
            ("small", ["feature.wrap"]),
            ("small", ["feature.mirror"]),
        ],
    ),
    (
        GROUP_REFERENCE_CURVES,
        [
            (
                "large",
                [
                    "feature.ref_plane",
                    "feature.ref_axis",
                    "feature.ref_point",
                    "feature.coord_system",
                ],
            ),
            (
                "large",
                [
                    "feature.helix",
                    "feature.transition_spiral",  # TR408 (D2010)
                    "feature.projected_curve",
                    "feature.composite_curve",
                    "feature.point_curve",
                    "feature.sketch3d",  # TR7 (D1719)
                    "feature.contour",
                    "feature.pipe",
                    "feature.curve_array",
                ],
            ),
        ],
    ),
    (
        strings_phase3.GROUP_DIRECT,
        [
            ("small", ["feature.move_face"]),
            ("small", ["feature.offset_face"]),
            ("small", ["feature.delete_face"]),
            ("small", ["feature.merge_faces", "feature.face_relation"]),  # TR261, TR266
        ],
    ),
]


def _ids(window: MainWindow, button: LargeButton | CompactButton) -> list[str]:
    command_of = {id(a): cid for cid, a in window.commands.actions.items()}
    return [command_of[id(a)] for a in button.group_actions]


def _panel(window: MainWindow, name: str) -> RibbonPanel:
    tabs = window.command_tabs
    panel = tabs.widget(tabs.index_of(name))
    assert isinstance(panel, RibbonPanel)
    return panel


def _show(qtbot: QtBot, window: MainWindow, index: int, width: int) -> RibbonPanel:
    window.resize(width, 800)
    tabs = window.command_tabs
    tabs.setCurrentIndex(index)
    qtbot.wait(10)
    panel = tabs.widget(index)
    assert isinstance(panel, RibbonPanel)
    return panel


def _rect_in(widget: QWidget, panel: QWidget) -> QRect:
    return QRect(widget.mapTo(panel, QPoint(0, 0)), widget.size())


def test_features_tab_order_and_grouping(qtbot: QtBot, window: MainWindow) -> None:
    """R4.1: groups, buttons per group, large or small, and dropdown contents (R2)."""
    panel = _show(qtbot, window, window.command_tabs.index_of("features"), 1920)
    seen = []
    for group in panel.groups:
        buttons = sorted(group.buttons, key=lambda b: (_rect_in(b, panel).x(), b.y()))
        kinds = [
            ("large" if isinstance(b, LargeButton) else "small", _ids(window, b)) for b in buttons
        ]
        seen.append((group.caption.text(), kinds))
    assert seen == FEATURES_R2
    # The group titles run left to right in the R2 order.
    xs = [_rect_in(g, panel).x() for g in panel.groups]
    assert xs == sorted(xs)
    # Small tools sit in the columns R2 names, in order.
    by_id = {_ids(window, b)[0]: b for b in panel.buttons()}

    def column_x(*cids: str) -> int:
        found = {_rect_in(by_id[c], panel).x() for c in cids}
        assert len(found) == 1, cids
        return found.pop()

    column_x("feature.sweep", "feature.loft")
    column_x("feature.swept_cut", "feature.lofted_cut")
    # Small tools flow into balanced columns in the R2 order (D1034): six make
    # three and three, the columns R2 names.
    first = column_x("feature.rib", "feature.draft", "feature.shell")
    second = column_x("feature.dome", "feature.wrap", "feature.mirror")
    assert first < second
    pattern = _rect_in(by_id["feature.linear_pattern"], panel)
    assert pattern.right() < first
    column_x("feature.move_face", "feature.offset_face", "feature.delete_face")
    # No Fasten group any more, and the Curves title is gone from the Features tab.
    titles = [g.caption.text() for g in panel.groups]
    assert strings_import.GROUP_CURVES not in titles


def test_common_tools_have_their_own_button(window: MainWindow) -> None:
    """R4.2: Draft, Shell, Rib, Mirror and the Hole Tool are each shown on a button."""
    shown_first: set[str] = set()
    for panel in window.command_tabs.panels():
        for button in panel.buttons():
            ids = _ids(window, button)
            shown_first.add(ids[0])
            for a, b in NEVER_TOGETHER:
                assert not {a, b} <= set(ids), ids
    for cid in OWN_BUTTON:
        assert cid in shown_first, cid
    # Also true in the layout data, before any tool was used.
    for _title, large, columns in FEATURE_GROUPS:
        items = [*large, *(item for column in columns for item in column)]
        for item in items:
            if isinstance(item, list):
                assert not set(item[1:]) & set(OWN_BUTTON), item


@pytest.mark.parametrize("width", [1280, 1920])
def test_every_tab_lays_out_evenly(qtbot: QtBot, window: MainWindow, width: int) -> None:
    """R4.3: no overlaps, arrows inside their button under or beside the label, and
    one height, icon size and label row for the large buttons of a tab (R3)."""
    tabs = window.command_tabs
    assert tabs.count() == 7
    for index in range(tabs.count()):
        panel = _show(qtbot, window, index, width)
        name = tabs.tabText(index)
        buttons = [b for b in panel.buttons() if b.isVisibleTo(panel)]
        assert buttons, name
        rects = [_rect_in(b, panel) for b in buttons]
        for (a, ra), (b, rb) in combinations(zip(buttons, rects, strict=True), 2):
            assert not ra.intersects(rb), (name, a.text(), b.text())
        large = [b for b in buttons if isinstance(b, LargeButton)]
        if large:
            assert len({b.height() for b in large}) == 1, name
            assert len({b.iconSize().width() for b in large}) == 1, name
            assert len({_rect_in(b, panel).y() + b.label_rect().top() for b in large}) == 1
        for button in buttons:
            arrow, label = button.arrow_rect(), button.label_rect()
            assert button.is_dropdown() == (len(button.group_actions) > 1)
            if not button.is_dropdown():
                assert arrow.isEmpty()
                continue
            assert button.rect().contains(arrow), (name, button.text())
            if isinstance(button, LargeButton):
                label = button.text_rect()  # the lines the label has (R3B, D2744)
            assert not arrow.intersects(label), (name, button.text())
            assert button.menu_rect().contains(arrow), (name, button.text())
            if isinstance(button, LargeButton):
                assert arrow.top() > label.bottom(), (name, button.text())
                assert abs(arrow.center().x() - label.center().x()) <= 1
                assert button.menu_rect().top() < label.top()  # the whole strip opens the list
            else:
                assert arrow.left() > label.right(), (name, button.text())
                assert abs(arrow.center().y() - label.center().y()) <= 1


def test_large_button_width_is_icon_or_label_plus_padding(qtbot: QtBot, window: MainWindow) -> None:
    """R3.3: no button is padded wider to fit its arrow."""
    for index in range(window.command_tabs.count()):
        panel = _show(qtbot, window, index, 1920)
        for button in panel.buttons():
            if not isinstance(button, LargeButton):
                continue
            lines = [line for a in button.group_actions for line in button._lines(a.text())]
            widest = max(text_width(button, line) for line in lines)
            content = max(button.iconSize().width(), widest)
            assert button.sizeHint().width() == content + 2 * button.padding()
            assert button.width() == button.sizeHint().width()


def test_small_columns_line_up_on_the_left(qtbot: QtBot, window: MainWindow) -> None:
    """R3.4: one column shares its left edge and row spacing; a column of two is centred."""
    panel = _show(qtbot, window, window.command_tabs.index_of("features"), 1920)
    by_id = {_ids(window, b)[0]: b for b in panel.buttons()}
    column = [by_id[c] for c in ("feature.rib", "feature.draft", "feature.shell")]
    rects = [_rect_in(b, panel) for b in column]
    assert len({r.left() for r in rects}) == 1
    assert len({r.width() for r in rects}) == 1
    gaps = {b.top() - a.bottom() for a, b in pairwise(rects)}
    assert len(gaps) == 1
    pair = [_rect_in(by_id[c], panel) for c in ("feature.sweep", "feature.loft")]
    boss = _rect_in(by_id["feature.extrude"], panel)
    middle = (pair[0].top() + pair[1].bottom()) / 2
    assert abs(middle - boss.center().y()) <= 2


def test_group_titles_are_centred(qtbot: QtBot, window: MainWindow) -> None:
    """R3.5: each title is centred under its group's buttons."""
    tabs = window.command_tabs
    for index in range(tabs.count()):
        panel = _show(qtbot, window, index, 1920)
        for group in panel.groups:
            caption = group.caption
            assert caption.alignment() & Qt.AlignmentFlag.AlignHCenter
            rects = [_rect_in(b, group) for b in group.buttons if b.isVisibleTo(group)]
            left = min(r.left() for r in rects)
            right = max(r.right() for r in rects)
            middle = caption.geometry().center().x()
            assert abs((left + right) / 2 - middle) <= 3, caption.text()


def test_dropdown_list_marks_the_shown_tool(qtbot: QtBot) -> None:
    """R3.6 and R1.3: the list holds every tool in order and marks the one shown."""
    owner = QWidget()
    qtbot.addWidget(owner)
    ids = ["sketch.trim", "sketch.extend"]
    actions = {cid: QAction(cid, owner) for cid in ids}
    panel = build_panel("sketch", SKETCH_GROUPS, actions)
    qtbot.addWidget(panel)
    panel.show()
    button = panel.buttons()[0]
    menu = button.menu()
    assert isinstance(menu, RibbonMenu)
    assert menu.actions() == [actions["sketch.trim"], actions["sketch.extend"]]
    assert menu.shown_action is actions["sketch.trim"]
    actions["sketch.extend"].trigger()
    assert menu.shown_action is actions["sketch.extend"]
    menu.popup(QPoint(0, 0))
    qtbot.waitExposed(menu)
    mark = menu.mark_rect()
    assert not mark.isEmpty()
    assert menu.actionGeometry(actions["sketch.extend"]).contains(mark.center())
    menu.close()


def test_menu_strip_opens_the_list_and_the_icon_runs_the_tool(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R1.3 and R3.1: the button runs the tool it shows; the strip opens the list."""
    owner = QWidget()
    qtbot.addWidget(owner)
    ids = ["feature.fillet", "feature.chamfer"]
    actions = {cid: QAction(cid, owner) for cid in ids}
    panel = build_panel("features", FEATURE_GROUPS, actions)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitExposed(panel)
    button = panel.buttons()[0]
    assert isinstance(button, LargeButton)
    opened: list[bool] = []
    monkeypatch.setattr(button, "showMenu", lambda: opened.append(True))
    ran: list[bool] = []
    actions["feature.fillet"].triggered.connect(lambda: ran.append(True))
    icon_point = QPoint(
        button.width() // 2, button.label_rect().top() - button.iconSize().height() // 2
    )
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton, pos=icon_point)
    assert ran == [True] and opened == []
    for point in (button.label_rect().center(), button.arrow_rect().center()):
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton, pos=point)
    assert opened == [True, True] and ran == [True]
