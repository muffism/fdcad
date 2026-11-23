"""The Features, Sketch and Evaluate command tabs (PHASE1_CORRECTIONS L1, L2, C6).

The layouts below say which tools are large, which sit in compact columns,
and which share a dropdown button. Icons and tooltips come from the command
ids, so they follow the theme and the user's shortcuts. A command that does
not exist yet (for example a later phase tool) is left out of the layout.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QGuiApplication, QMouseEvent
from PySide6.QtWidgets import QApplication, QMenu, QTabBar, QTabWidget, QToolButton, QWidget

from fdcad.ui import icons, strings, strings_import, strings_phase3
from fdcad.ui.command_tabs.phase4_groups import PHASE4_SKETCH_GROUPS
from fdcad.ui.command_tabs.ribbon import RibbonPanel, command_icon, tooltip
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.print_tools.tab_groups import EVALUATE_PRINT_GROUPS

if TYPE_CHECKING:
    from fdcad.ui.main_window.actions import CommandActions
    from fdcad.ui.preferences.settings import Settings

#: One entry of a layout: a command id, or a list of ids sharing a dropdown.
Item = str | list[str]
#: A group: title, large tools, then compact columns (up to three tools each).
Group = tuple[str, list[Item], list[list[Item]]]

#: Title of the Features tab group with Reference Geometry and Curves (RIBBON_SPEC R2.5).
GROUP_REFERENCE_CURVES = "Reference and Curves"

#: The Features tab (RIBBON_SPEC R2, D640). Tools most parts use (Hole Tool,
#: Draft, Shell, Rib, Mirror) have their own visible button; a dropdown only
#: holds close variants of one tool and shows the one used last (R1, D435).
FEATURE_GROUPS: list[Group] = [
    (strings.GROUP_SKETCH, ["sketch.sketch"], []),
    (
        strings.GROUP_BOSS,
        ["feature.extrude", "feature.revolve"],
        [["feature.sweep", ["feature.loft", "feature.primitive"]]],
    ),
    (
        strings.GROUP_CUT,
        [
            "feature.extruded_cut",
            ["feature.hole", "feature.modeled_thread", "feature.cosmetic_thread"],
            "feature.revolved_cut",
        ],
        [
            [
                "feature.swept_cut",
                "feature.lofted_cut",
                "feature.corner_relief",
                "feature.shaft_shape",
                "feature.ring_groove",
                "feature.oring_groove",
            ]
        ],
    ),
    (
        strings.GROUP_MODIFY,
        [
            ["feature.fillet", "feature.chamfer"],
            [
                "feature.linear_pattern",
                "feature.circular_pattern",
                "feature.sketch_pattern",
                "feature.table_pattern",
                "feature.fill_pattern",
                "feature.point_pattern",
                "feature.pattern_chain",
            ],
        ],
        [
            ["feature.rib", "feature.draft", "feature.shell"],
            [["feature.dome", "feature.roof"], "feature.wrap", "feature.mirror"],  # TR258
        ],
    ),
    (
        GROUP_REFERENCE_CURVES,
        [
            ["feature.ref_plane", "feature.ref_axis", "feature.ref_point", "feature.coord_system"],
            [
                "feature.helix",
                "feature.transition_spiral",
                "feature.projected_curve",
                "feature.composite_curve",
                "feature.point_curve",
                "feature.sketch3d",
                "feature.contour",
                "feature.pipe",
                "feature.curve_array",
            ],
        ],
        [],
    ),
    (
        strings_phase3.GROUP_DIRECT,
        [],
        [
            ["feature.move_face", "feature.offset_face", "feature.delete_face"],
            [["feature.merge_faces", "feature.face_relation"]],  # TR266 (D2418)
        ],
    ),
]

#: The Bodies tab: tools that work on whole bodies, deformations and imports.
#: Only close variants share a dropdown (R1, D641).
BODIES_GROUPS: list[Group] = [
    (
        strings_phase3.GROUP_BODIES,
        [
            ["feature.combine", "feature.intersect"],
            ["feature.move_copy_body", "feature.linked_copy"],  # TR154 (D2417)
            "feature.transform_handles",
        ],
        [
            [
                "feature.split",
                "feature.scale",
                "feature.offset_body",
                "feature.delete_body",
                "feature.mould_cavity",
            ]
        ],
    ),
    (
        strings.GROUP_DEFORM,
        [["feature.flow", "feature.bend", "feature.twist", "feature.taper", "feature.stretch"]],
        [[["feature.deform_point", "feature.deform_curve", "feature.surface_push"]]],  # TR67
    ),
    (
        strings.GROUP_IMPORT,
        [["feature.import_step", "feature.import_mesh", "feature.insert_part"]],  # TR71
        [],
    ),
]

#: The 3D Print tab: printing features, then the print checks and the slicer.
#: Few buttons share a dropdown (R1, D641): snap hook and groove, cable tie and hose fitting.
PRINT_GROUPS: list[Group] = [
    (
        strings.GROUP_PRINT_FEATURES,
        ["feature.split_for_print", "feature.mounting_boss"],
        [  # columns of three small buttons, so the ribbon keeps its height
            [["feature.snap_hook", "feature.snap_groove"], "feature.lip_groove", "feature.vent"],
            [
                "feature.inlay",
                ["feature.cable_tie", "feature.hose_fitting"],
                ["feature.half_lap", "feature.twist_lock", "feature.indent"],  # TR357, TR68
            ],
            [
                "feature.finger_joint",
                [
                    "feature.crush_ribs",
                    "feature.corner_ears",
                    "feature.drain_holes",
                    "feature.polygon_holes",
                    "feature.base_pad",
                    "feature.interlock",
                    "feature.lattice_fill",
                    "feature.mark",
                    "feature.hinge",
                    "feature.face_seats",
                    "feature.stone_setting",  # TR408 (D2410)
                    "feature.sprue_tree",  # TR408 (D2411)
                    "feature.edge_profile",
                    "feature.lightening_pockets",
                    "feature.landing_pad",
                    "feature.joint_helper",
                    "feature.knurl",
                ],
                "feature.living_hinge",
            ],
        ],
    ),
    *EVALUATE_PRINT_GROUPS,
]

SKETCH_GROUPS: list[Group] = [
    (strings.GROUP_SKETCH, ["sketch.sketch", "sketch.exit"], [["sketch.discard"]]),
    (
        strings.GROUP_DRAW,
        [],
        [
            [
                [
                    "sketch.line",
                    "sketch.centerline",
                    "sketch.midpoint_line",
                    "sketch.jog_line",
                    "sketch.infinite_line",
                ],
                [
                    "sketch.corner_rectangle",
                    "sketch.center_rectangle",
                    "sketch.three_point_corner_rectangle",
                    "sketch.three_point_center_rectangle",
                    "sketch.parallelogram",
                ],
                [
                    "sketch.circle",
                    "sketch.perimeter_circle",
                    "sketch.two_point_circle",
                    "sketch.tangent_circle",
                ],
            ],
            [
                ["sketch.center_arc", "sketch.tangent_arc", "sketch.three_point_arc"],
                "sketch.point",
                "sketch.select",
            ],
            [
                "sketch.slot",
                "sketch.polygon",
                [
                    "sketch.spline",
                    "sketch.ellipse",
                    "sketch.partial_ellipse",
                    "sketch.conic",
                    "sketch.parabola",
                    "sketch.hyperbola",  # TR374
                    "sketch.equation_curve",
                    "sketch.blend_curve",
                    "sketch.insert_spline_point",  # TR42
                    "sketch.fit_spline",
                    "sketch.simplify_spline",
                ],
            ],
        ],
    ),
    (
        strings.GROUP_MODIFY,
        [],
        [
            [
                ["sketch.trim", "sketch.extend", "sketch.split"],
                "sketch.offset",
                ["sketch.mirror", "sketch.dynamic_mirror"],
            ],
            [
                ["sketch.fillet", "sketch.chamfer"],
                # TR1 (D684): the five entity tools share one dropdown.
                [
                    "sketch.move_entities",
                    "sketch.copy_entities",
                    "sketch.rotate_entities",
                    "sketch.scale_entities",
                    "sketch.stretch_entities",
                ],
                ["sketch.linear_pattern", "sketch.circular_pattern"],
            ],
        ],
    ),
    (
        strings.GROUP_SKETCH_TOOLS,
        # TR45 (D1307): baseline and ordinate dimensions share Smart Dimension's dropdown.
        [["sketch.dimension", "sketch.baseline_dimension", "sketch.ordinate_dimension"]],
        [
            # Long labels share the widest column so the group stays narrow (window
            # minimum width under 1024 px).
            ["sketch.construction", "sketch.fully_define"],
            ["sketch.relations", ["sketch.check_sketch", "sketch.repair_sketch"]],
            [
                "sketch.convert",
                "sketch.intersection_curves",
                "sketch.silhouette",
                "sketch.turned_outline",
                "sketch.close_to_model",
                "sketch.picture",
                "sketch.insert_dxf",
                "sketch.insert_svg",
            ],
        ],
    ),
    *PHASE4_SKETCH_GROUPS,
]

EVALUATE_GROUPS: list[Group] = [
    (
        strings.GROUP_MEASURE,
        ["evaluate.measure", "evaluate.mass_properties", "view.section"],
        [
            [
                "evaluate.compare_bodies",
                "evaluate.interference",
                "evaluate.manufacturing",
                "feature.bounding_box",
            ],
            ["feature.sensor"],  # TR86
        ],
    ),
    (
        strings.GROUP_REBUILD,
        ["edit.rebuild"],
        [
            [
                "edit.force_rebuild",
                "tools.stats",
                "evaluate.change_test",
                "evaluate.model_health",
                "evaluate.repair_references",
            ]
        ],
    ),
    (
        strings_import.GROUP_CURVES,
        [],
        [["evaluate.curvature_graph", "evaluate.zebra", "evaluate.curvature_colors"]],
    ),
]

#: Tab object names, used for the show and hide menu and the saved settings.
TAB_FEATURES = "features"
TAB_SKETCH = "sketch"
TAB_EVALUATE = "evaluate"
TAB_BODIES = "bodies"
TAB_PRINT = "print"


def _actions_of(item: Item, actions: dict[str, QAction]) -> list[QAction]:
    ids = [item] if isinstance(item, str) else item
    return [actions[cid] for cid in ids if cid in actions]


def build_panel(name: str, groups: list[Group], actions: dict[str, QAction]) -> RibbonPanel:
    """Lay out ``groups`` as one command tab. Missing commands are skipped."""
    panel = RibbonPanel()
    panel.setObjectName(f"{name}_tab")
    for title, large, columns in groups:
        found_large = [a for a in (_actions_of(i, actions) for i in large) if a]
        found_columns = [
            [a for a in (_actions_of(i, actions) for i in column) if a] for column in columns
        ]
        found_columns = [c for c in found_columns if c]
        if not found_large and not found_columns:
            continue
        group = panel.add_group(title)
        for group_actions in found_large:
            group.add_large(*group_actions)
        # The small tools of a group flow into columns of ``COLUMN_ROWS`` in the order
        # they are listed, so a group is as narrow as its tools allow (D1034).
        small = [tool for column in found_columns for tool in column]
        if small:
            group.add_column(small)
    return panel


def remember_groups(panel: RibbonPanel, actions: dict[str, QAction], settings: Settings) -> None:
    """Grouped dropdowns show the tool used last, also after a restart (C6).

    A group is known by the id of its first tool, for example ``sketch.line``.
    """
    command_of = {id(a): cid for cid, a in actions.items()}
    chosen = settings.tool_groups
    for button in panel.buttons():
        if len(button.group_actions) < 2:
            continue
        ids = [command_of.get(id(a), "") for a in button.group_actions]
        group = ids[0]
        last = chosen.get(group)
        if last in ids:
            button.setDefaultAction(button.group_actions[ids.index(last)])
        for action, cid in zip(button.group_actions, ids, strict=True):
            action.triggered.connect(lambda _c=False, g=group, c=cid: settings.remember_tool(g, c))


def build_features_panel(actions: dict[str, QAction]) -> RibbonPanel:
    """The Features tab: Sketch, the boss and cut tools large, the rebuild tools compact."""
    return build_panel(TAB_FEATURES, FEATURE_GROUPS, actions)


def build_sketch_panel(actions: dict[str, QAction]) -> RibbonPanel:
    """The Sketch tab: Sketch, Exit Sketch and Smart Dimension large, drawing tools compact."""
    return build_panel(TAB_SKETCH, SKETCH_GROUPS, actions)


def build_bodies_panel(actions: dict[str, QAction]) -> RibbonPanel:
    """The Bodies tab: body tools, deformations and imports (D435)."""
    return build_panel(TAB_BODIES, BODIES_GROUPS, actions)


def build_print_panel(actions: dict[str, QAction]) -> RibbonPanel:
    """The 3D Print tab: printing features, print checks and the slicer (D435)."""
    return build_panel(TAB_PRINT, PRINT_GROUPS, actions)


def build_evaluate_panel(actions: dict[str, QAction]) -> RibbonPanel:
    """The Evaluate tab. Phase 1 has the rebuild tools; measuring comes in later phases."""
    return build_panel(TAB_EVALUATE, EVALUATE_GROUPS, actions)


class HoldToMoveTabBar(QTabBar):
    """A tab bar whose tabs move only after a long press (D582).

    A quick click still just switches tabs, so a shaky click never moves one.
    Holding the mouse on a tab for ``HOLD_MS`` turns on dragging and shows a
    grab cursor; the tab then follows the mouse until it is released.
    """

    HOLD_MS = 400

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMovable(False)
        self._press: QPointF | None = None
        self._last: QPointF | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self.HOLD_MS)
        self._timer.timeout.connect(self.start_hold)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt override)
        on_tab = self.tabAt(event.position().toPoint()) >= 0
        if event.button() == Qt.MouseButton.LeftButton and on_tab:
            self._press = self._last = event.position()
            self._timer.start()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt override)
        self._last = event.position()
        if self._timer.isActive() and self._press is not None:
            moved = (event.position() - self._press).manhattanLength()
            if moved > QApplication.startDragDistance():
                self._timer.stop()  # moved before the hold: an ordinary click
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt override)
        self._timer.stop()
        super().mouseReleaseEvent(event)
        self.end_hold()

    def start_hold(self) -> None:
        """Turn on dragging for the held tab, as if it was pressed again now."""
        if self._last is None:
            return
        self.setMovable(True)
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        press = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            self._last,
            self.mapToGlobal(self._last),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        super().mousePressEvent(press)

    def end_hold(self) -> None:
        """Back to click only tabs."""
        self._press = self._last = None
        if self.isMovable():
            self.setMovable(False)
            self.unsetCursor()


class CommandTabs(QTabWidget):
    """The command tabs above the document. Keeps icons and tooltips up to date."""

    #: Emitted after the icons were drawn again for a new theme.
    icons_changed = Signal()

    def __init__(self, commands: CommandActions, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTabBar(HoldToMoveTabBar(self))
        self.setObjectName("command_tab_widget")
        self.setDocumentMode(True)
        self.commands = commands
        self._default_order: list[str] = []
        self._reordering = False
        self.tabBar().tabMoved.connect(self._tab_moved)
        # A left click button at the start of the row lists the tabs to show or hide (D582).
        self.tabs_button = QToolButton(self)
        self.tabs_button.setObjectName("command_tabs_button")
        self.tabs_button.setArrowType(Qt.ArrowType.DownArrow)
        self.tabs_button.setAutoRaise(True)
        self.tabs_button.setToolTip(strings.TABS_BUTTON_TIP)
        self.tabs_button.setAccessibleName(strings.TABS_BUTTON_TIP)
        self.tabs_button.clicked.connect(self._button_menu)
        self.setCornerWidget(self.tabs_button, Qt.Corner.TopLeftCorner)
        self.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabBar().customContextMenuRequested.connect(self._tab_menu)
        hints = QGuiApplication.styleHints()
        hints.colorSchemeChanged.connect(self._scheme_changed)

    def add_panel(self, panel: RibbonPanel, title: str) -> None:
        """Add a tab, hidden when the user hid it before."""
        index = self.addTab(panel, title)
        name = panel.objectName().removesuffix("_tab")
        self._default_order.append(name)
        if name in self.commands.settings.hidden_command_tabs:
            self.setTabVisible(index, False)

    def names(self) -> list[str]:
        """Tab names ("features", "sketch", ...) in the order shown."""
        found = [self.widget(i) for i in range(self.count())]
        return [w.objectName().removesuffix("_tab") for w in found if w is not None]

    def apply_saved_order(self) -> None:
        """Put the tabs in the order the user dragged them to last time.

        Tabs missing from the saved order (for example a tab added by a newer
        version) come after the saved ones.
        """
        self.move_to_order(self.commands.settings.command_tab_order)

    def move_to_order(self, order: list[str]) -> None:
        """Rearrange the tabs to follow ``order``; unknown names are ignored."""
        current = self.currentWidget()
        bar = self.tabBar()
        self._reordering = True  # bar signals stay on: the tab pages follow them
        target = 0
        for name in order:
            index = self.index_of(name)
            if index < 0:
                continue
            if index != target:
                bar.moveTab(index, target)
            target += 1
        self._reordering = False
        if current is not None:
            self.setCurrentWidget(current)

    def reset_order(self) -> None:
        """Put the tabs back in the order FDCAD ships with and forget the saved order."""
        self.move_to_order(self._default_order)
        self.commands.settings.command_tab_order = []

    def show_all(self) -> None:
        """Show every tab."""
        for i in range(self.count()):
            self.setTabVisible(i, True)
        self.commands.settings.hidden_command_tabs = []

    def _tab_moved(self, _from: int, _to: int) -> None:
        if self._reordering:
            return
        self.commands.settings.command_tab_order = self.names()

    def panels(self) -> list[RibbonPanel]:
        """The tab contents, in order."""
        found = [self.widget(i) for i in range(self.count())]
        return [p for p in found if isinstance(p, RibbonPanel)]

    def index_of(self, name: str) -> int:
        """Index of the tab named ``name`` ("features", "sketch", "evaluate"), or -1."""
        for i in range(self.count()):
            widget = self.widget(i)
            if widget is not None and widget.objectName() == f"{name}_tab":
                return i
        return -1

    def show_tab(self, name: str) -> None:
        """Switch to a tab, showing it first if the user hid it."""
        index = self.index_of(name)
        if index >= 0:
            self.setTabVisible(index, True)
            self.setCurrentIndex(index)

    def tab_menu(self) -> QMenu:
        """The right click menu of the tab bar: one tick box per tab (W7.4)."""
        menu = QMenu(self)
        menu.setObjectName("command_tab_menu")
        for i in range(self.count()):
            action = menu.addAction(self.tabText(i))
            action.setCheckable(True)
            action.setChecked(self.isTabVisible(i))
            action.toggled.connect(lambda on, index=i: self.set_tab_shown(index, on))
        menu.addSeparator()
        menu.addAction(strings.TABS_SHOW_ALL, self.show_all)
        menu.addAction(strings.TABS_RESET_ORDER, self.reset_order)
        return menu

    def _button_menu(self) -> None:
        menu = self.tab_menu()
        button = self.tabs_button
        menu.popup(button.mapToGlobal(QPoint(0, button.height())))

    def _tab_menu(self, pos: QPoint) -> None:
        self.tab_menu().popup(self.tabBar().mapToGlobal(pos))

    def set_tab_shown(self, index: int, shown: bool) -> None:
        """Show or hide a tab and remember it. The last visible tab always stays."""
        visible = [i for i in range(self.count()) if self.isTabVisible(i)]
        if not shown and visible == [index]:
            return
        self.setTabVisible(index, shown)
        hidden = []
        for i in range(self.count()):
            widget = self.widget(i)
            if widget is not None and not self.isTabVisible(i):
                hidden.append(widget.objectName().removesuffix("_tab"))
        self.commands.settings.hidden_command_tabs = hidden

    def refresh(self) -> None:
        """Set every command's icon and tooltip from its id and current shortcuts."""
        for cid, action in self.commands.actions.items():
            if cid not in BY_ID:
                continue
            action.setIcon(command_icon(cid))
            keys = self.commands.shortcuts.keys(cid)
            action.setToolTip(tooltip(cid, BY_ID[cid].label, keys))
            action.setStatusTip(strings.TOOLTIP_TEXT.get(cid, ""))

    def _scheme_changed(self, _scheme: object) -> None:
        self.theme_changed()

    def theme_changed(self) -> None:
        """Draw the icons again in the new theme's colours."""
        icons.clear_cache()
        self.refresh()
        self.icons_changed.emit()
