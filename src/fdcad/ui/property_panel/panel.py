"""Property panel: edit a feature's values with OK and Cancel (PLAN 8 item 2, L3, W6).

Layout: a header with the feature icon, its name, OK and Cancel, then folding
groups: From, Direction 1, Direction 2 (a tick box, folded until ticked) and
Thin Feature (extrude and revolve, D523). Revolve adds an Axis of Revolution group.

It edits a copy of the feature. ``values_changed`` sends the edited copy after
every change, so the live preview can follow it. OK applies the copy as one
undoable command. Typed values accept units and formulas and show their
evaluated value or what is wrong (CLAUDE.md section 8 item 4).

Public API for the workflow (confirmation corner, right click menu, Enter, Esc):
``begin``, ``accept``, ``reject`` (same as ``cancel``), ``current_feature``,
``set_value`` (drag handle), ``set_axis`` (picked axis line), ``set_axis_edge`` (picked part edge),
``active_param``.
"""

from __future__ import annotations

import copy
import math
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QEvent, QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.document.dependencies import referenced_ids
from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.extrude import direction1, direction2
from fdcad.core.features.extrude_end import END_CONDITIONS
from fdcad.core.features.preview import body_before
from fdcad.core.features.revolve_end import ENDS1, ENDS2, revolve_ends
from fdcad.core.rebuild.engine import document_variables
from fdcad.core.sketch.model import Line, sketch_from_data
from fdcad.core.units import ExpressionError, Kind, UnitSystem, evaluate
from fdcad.ui import strings
from fdcad.ui.commands.document import AddFeature
from fdcad.ui.icons import icon
from fdcad.ui.property_panel.end_group import EndControls, ThinControls
from fdcad.ui.property_panel.groups import Group, tool_button, with_icon
from fdcad.ui.property_panel.region_group import RegionControls
from fdcad.ui.property_panel.start_group import StartControls
from fdcad.ui.property_panel.stepping import Stepper
from fdcad.ui.session import DocumentSession
from fdcad.ui.themes.style import unit
from fdcad.ui.themes.typography import Role, tabular, type_font

if TYPE_CHECKING:
    from fdcad.ui.body_tools.form_widget import FeatureForm as BodyForm
    from fdcad.ui.property_panel.tabs import PanelTabs

_DECIMALS = {UnitSystem.MM: 2, UnitSystem.IN: 3}  # PLAN 8 item 13
_TIP = strings.PANEL_TIPS
#: Defaults for Phase 2 extrude fields that are not stored yet: (text, mm or radians).
_FIELD_DEFAULTS = {
    "end_twist": ("0", 0.0),  # TR240
    "end_scale": ("1", 1.0),
    "profile_offset": ("0", 0.0),  # TR344
    "end_offset": ("10", 10.0),
    "end_offset2": ("10", 10.0),
    "draft_angle": ("5", math.radians(5)),
    "draft_angle2": ("5", math.radians(5)),
    "thin_thickness": ("1", 1.0),
    "thin_thickness2": ("1", 1.0),
    "thin_cap_thickness": ("1", 1.0),
    "thin_fillet_radius": ("1", 1.0),
}
#: The same lengths in an inch part, sized like the inch depth and shell (bug hunt E5).
_INCH_DEFAULTS = {
    "start_offset": "0.5",
    "end_offset": "0.5",
    "end_offset2": "0.5",
    "thin_thickness": "0.05",
    "thin_thickness2": "0.05",
    "thin_cap_thickness": "0.05",
    "thin_fillet_radius": "0.05",
}
#: Fields written by the From, end and thin controls, not by the panel's own loop.
_OWN_FIELDS = ("start_offset", "end_offset", "draft_angle", "thin_")


#: A pattern with more copies than this asks before it is built (TR142, D962).
LARGE_PATTERN = 200


def pattern_instances(feature: Feature) -> int:
    """How many copies a linear or circular pattern makes by its typed counts (both
    directions, both sides when symmetric); 0 for other features or an Up to fill,
    whose count is found while building."""
    if feature.type not in ("linear_pattern", "circular_pattern"):
        return 0
    total = 1
    for k in (1, 2):
        if k == 2 and feature.params.get("second_direction") is not True:
            continue
        if feature.params.get(f"fill{k}") == "up_to":
            return 0
        value = feature.params.get(f"count{k}")
        if not isinstance(value, Param):
            return 0
        count = max(0, round(value.value))
        if feature.params.get(f"symmetric{k}") is True:
            count = 2 * count - 1
        total *= max(count, 1)
    return total


def format_value(value: float, kind: Kind, units: UnitSystem) -> str:
    """Display text for an internal value, in the part's units."""
    from fdcad.core.units import number_display as shown  # TR350 (D949)

    if kind is Kind.LENGTH:
        inch = units is UnitSystem.IN
        factor = 25.4 if inch else 1.0
        return f"{shown.length(value / factor, _DECIMALS[units], inch)} {units.value}"
    if kind is Kind.ANGLE:
        return f"{shown.fixed(math.degrees(value), 2)} deg"
    return f"{value:g}"


def typed_length(value: float, units: UnitSystem) -> str:
    """Text to put in a length field for ``value`` mm, in the part's units."""
    shown = value / 25.4 if units is UnitSystem.IN else value
    return f"{round(shown, _DECIMALS[units] + 1):g}"


def typed_angle(value: float) -> str:
    """Text to put in an angle field for ``value`` radians, in degrees."""
    return f"{round(math.degrees(value), 2):g}"


def feature_icon_name(feature: Feature) -> str:
    """Icon name for a feature: feature.extrude, feature.extruded_cut and so on."""
    from fdcad.ui.strings_phase3 import TYPE_COMMANDS

    if feature.type in TYPE_COMMANDS:  # Phase 3 types use their command icon
        return TYPE_COMMANDS[feature.type]
    cut = feature.params.get("operation") == "cut"
    special = {"sweep": "feature.swept_cut", "loft": "feature.lofted_cut"}
    if cut and feature.type in special:
        return special[feature.type]
    return f"feature.{feature.type}d_cut" if cut else f"feature.{feature.type}"


def _form_type(ftype: str) -> bool:
    from fdcad.ui.body_tools.forms import form_for

    return form_for(ftype) is not None


class ValueField(QWidget):
    """A text field for a typed value, with its evaluated value or error below."""

    def __init__(
        self,
        kind: Kind,
        units: UnitSystem,
        variables: dict[str, tuple[Kind, float]],
        param: Param | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.kind, self.units, self.variables = kind, units, variables
        self.edit = QLineEdit(param.expr if param else "")
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setObjectName("field_info")
        # Tabular figures, so digits keep their place while typing (U2.4).
        self.edit.setFont(tabular(self.edit.font()))
        self.info.setFont(tabular(type_font(Role.CAPTION, self.info.font())))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.edit)
        layout.addWidget(self.info)
        self.edit.textChanged.connect(self._check)
        self.stepper = Stepper(self.edit, kind, lambda: self.units)
        self._check()
        from fdcad.ui.property_panel.expression_tools import ExpressionTools

        self.tools = ExpressionTools(self)  # = expressions and new variables (T14.6)

    def setToolTip(self, text: str) -> None:  # noqa: N802
        """Show the tip on the text box too, with how to type expressions (T14.6.1)."""
        from fdcad.ui.strings_extra import EXPRESSION_TIP

        text = f"{text}<br>{EXPRESSION_TIP}" if text else EXPRESSION_TIP
        super().setToolTip(text)
        self.edit.setToolTip(text)

    def param(self) -> Param | None:
        """The value as a parameter, or None when the text is wrong."""
        try:
            return Param(
                self.edit.text().strip(),
                evaluate(self.edit.text(), self.kind, self.units, self.variables),
            )
        except ExpressionError:
            return None

    def _check(self) -> None:
        try:
            value = evaluate(self.edit.text(), self.kind, self.units, self.variables)
        except ExpressionError as exc:
            self.info.setText(str(exc))
            self._mark(True)
            return
        self._mark(False)
        self.info.setText("= " + format_value(value, self.kind, self.units))

    def _mark(self, invalid: bool) -> None:
        """Show the text box with the error border, or without it."""
        if bool(self.edit.property("invalid")) != invalid:
            self.edit.setProperty("invalid", invalid)
            self.edit.style().unpolish(self.edit)
            self.edit.style().polish(self.edit)


class _Message(QLabel):
    """The panel's hint line: takes no space while empty."""

    def setText(self, text: str) -> None:  # noqa: N802  (Qt override)
        """Show the hint, or hide the line when there is none."""
        super().setText(text)
        self.setHidden(not text)

    def clear(self) -> None:
        """Remove the hint and hide the line."""
        super().clear()
        self.hide()


class PropertyPanel(QWidget):
    """Edits one feature at a time."""

    finished = Signal()
    #: The panel's help button: open the guide at this tool (TR291 item 1, D2018).
    help_requested = Signal()
    #: Pinned and OK on a new feature: start the same command again (TR206).
    again = Signal()
    #: OK applied a feature: its id, and True when it was new (TR221, D963).
    applied = Signal(str, bool)
    #: The last preview could not be built: the title shows red (TR314).
    incomplete = False
    started = Signal()
    #: The edited copy (a Feature) after any change, or None while a value is wrong.
    values_changed = Signal(object)
    #: The value the user works on ("depth", "depth2", "angle" or "angle2"), for the handles.
    active_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session: DocumentSession | None = None
        self.feature: Feature | None = None
        self.is_new = False
        #: True when the last edit closed with OK, False after Cancel (bug hunt B2).
        self.accepted = False
        self.active_param = "depth"
        self._loading = False

        self.icon = QLabel()
        self.icon.setObjectName("panel_icon")
        self.title = QLabel()
        self.title.setObjectName("panel_title")
        self.title.setFont(type_font(Role.TITLE))
        self.setObjectName("property_panel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        # Words only, as in every window (D2692): the tick is drawn in the accent, so
        # it could not be seen on the accent fill of OK and pushed the word off centre.
        self.ok_button = self._header_button(strings.OK, _TIP["ok"])
        self.ok_button.setObjectName("panel_ok")
        self.cancel_button = self._header_button(strings.CANCEL, _TIP["cancel"])
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        # Pin (TR206, D861): after OK on a new feature, the same command starts again.
        # A pin icon (D2701): the word is its accessible name and starts its tooltip.
        # Pinned shows twice: the checked look, and the pin drawn pushed in, in the accent.
        u = unit(self.font())
        self.pin_button = QPushButton()
        self.pin_button.setObjectName("panel_pin")
        self.pin_button.setAccessibleName(strings.PANEL_PIN)
        self.pin_button.setToolTip(strings.PANEL_PIN_TIP)
        self.pin_button.setCheckable(True)
        self.pin_button.setIconSize(QSize(4 * u, 4 * u))
        self.pin_button.setMinimumSize(QSize(6 * u, 6 * u))  # 24 px target size (U3.3)
        self.pin_button.setFocusPolicy(Qt.FocusPolicy.ClickFocus)  # outside the Tab chain
        self.pin_button.toggled.connect(lambda _on: self.refresh_icons())
        header_box = QWidget()
        header_box.setObjectName("panel_header")
        header_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        # Two rows (D1034): the tool's name, then OK and Cancel at full width. In one
        # row the four buttons did not fit a narrow panel and drew over each other.
        rows = QVBoxLayout(header_box)
        rows.setContentsMargins(3 * u, 3 * u, 3 * u, 3 * u)  # 12 px panel padding (U2.2)
        rows.setSpacing(2 * u)
        header = QHBoxLayout()
        header.setSpacing(2 * u)
        actions = QHBoxLayout()
        actions.setSpacing(2 * u)
        rows.addLayout(header)
        rows.addLayout(actions)
        header.addWidget(self.icon)
        header.addWidget(self.title, 1)
        from PySide6.QtWidgets import QToolButton

        from fdcad.ui import strings_help

        self.help_button = QToolButton()  # TR291 item 1 (D2018)
        self.help_button.setObjectName("panel_help")
        # The icon of Help for This Tool, the command it runs (D2701); it was a "?".
        self.help_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.help_button.setIconSize(QSize(4 * u, 4 * u))
        self.help_button.setMinimumSize(6 * u, 6 * u)  # 24 px target size (U3.3)
        self.help_button.setToolTip(strings_help.PANEL_HELP_TIP)
        self.help_button.setAccessibleName(strings_help.PANEL_HELP)
        self.help_button.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.help_button.clicked.connect(self.help_requested.emit)
        header.addWidget(self.help_button)
        header.addWidget(self.pin_button)
        actions.addWidget(self.ok_button, 1)
        actions.addWidget(self.cancel_button, 1)
        self.refresh_icons()

        #: A one line hint the first time a tool is used (TR291 item 1, D2018).
        self.hint = QLabel()
        self.hint.setObjectName("panel_hint")
        self.hint.setWordWrap(True)
        self.hint.setTextFormat(Qt.TextFormat.RichText)
        self.hint.linkActivated.connect(self._hint_link)
        self.hint.hide()
        #: Where the seen tools and the hint switch are kept (the window sets it).
        self.hint_store: Any = None
        self.message = _Message()
        self.message.setWordWrap(True)
        self.message.setObjectName("panel_message")
        self.message.hide()
        self.groups_box = QWidget()
        self.groups_layout = QVBoxLayout(self.groups_box)
        self.groups_layout.setContentsMargins(3 * u, 0, 3 * u, 3 * u)
        self.groups_layout.setSpacing(4 * u)  # groups 16 px apart
        self.groups_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # Sideways only as a last resort: the rows are fitted to the panel (D2791), and
        # a row that cannot be can still be reached.
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(self.groups_box)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3 * u)
        layout.addWidget(header_box)
        layout.addWidget(self.hint)
        layout.addWidget(self.message)
        #: The tab bar of a panel with tabs sits here, above the scrolling groups (D2790).
        self.tab_bar_box = QWidget()
        self.tab_bar_layout = QVBoxLayout(self.tab_bar_box)
        self.tab_bar_layout.setContentsMargins(3 * u, 0, 3 * u, 0)
        self.tab_bar_box.hide()
        layout.addWidget(self.tab_bar_box)
        self.groups_scroll = scroll
        self.page_tabs: PanelTabs | None = None
        self._tab_of: dict[str, str] = {}
        self._other_tab = ""
        layout.addWidget(scroll, 1)

        self.values: dict[str, ValueField] = {}
        self.choices: dict[str, QComboBox] = {}
        self.flags: dict[str, QAbstractButton] = {}
        self.groups: dict[str, Group] = {}
        self.sketch_box = QComboBox()
        self.axis_box = QComboBox()
        self.start: StartControls | None = None
        self.regions: RegionControls | None = None
        self.ends: dict[str, EndControls] = {}
        self.thin: ThinControls | None = None
        self.form: Any = None  # FeatureForm for fillet, chamfer, shell, draft, sweep, loft
        self.body_form: BodyForm | None = None  # Phase 3 types (ui/body_tools)
        self.bodies_box: Any = None  # the Bodies box (TR33)
        self.value_names: dict[str, str] = {}  # value names set here (TR32)
        self.setEnabled(False)

    @staticmethod
    def _header_button(text: str, tip: str) -> QPushButton:
        button = QPushButton(text)
        button.setToolTip(tip)
        return button

    def refresh_icons(self) -> None:
        """Help and Pin in the current theme's colours (again after the theme changes).
        While Pin is on, the pin is drawn pushed in, in the accent (D2701)."""
        self.help_button.setIcon(icon("help.tool"))
        pinned = icon("ui.pin_on")
        self.pin_button.setIcon(pinned if self.pin_button.isChecked() else icon("ui.pin"))

    @property
    def is_editing(self) -> bool:
        """True while a feature is open in the panel."""
        return self.feature is not None

    # Opening ----------------------------------------------------------------------

    def begin(
        self, session: DocumentSession, feature: Feature, is_new: bool, preset: bool = False
    ) -> None:
        """Open ``feature`` for editing. New features are added only on OK. With
        ``preset`` (a command started it), a new one starts with the settings chosen
        for its type (TR326, D947)."""
        self.session = session
        self.feature = copy.deepcopy(feature)
        self.is_new = is_new
        if is_new and preset:
            self._start_with_preset(self.feature)
        self.active_param = "depth" if feature.type == "extrude" else "angle"
        from fdcad.ui.property_panel.forms import FORMS

        form_class = FORMS.get(feature.type)
        if form_class is not None:
            self.active_param = form_class.first_param
        elif _form_type(feature.type):
            self.active_param = "distance"
        self._loading = True
        try:
            self._build()
            self._add_bodies_box()  # TR33
            self._add_presets_box()  # TR326
            if self.page_tabs is not None:
                self.page_tabs.sync()
            self.align_columns()
        finally:
            self._loading = False
        self.setEnabled(True)
        self.started.emit()
        self._changed()
        first = self.values.get(self.active_param)
        if first is None and self.form is not None:
            first = self.form.fields.get(self.active_param)
        if first is not None:
            first.edit.setFocus()
            first.edit.selectAll()

    def align_columns(self) -> int:
        """One label column for the whole panel (D2742): the fields of every row, in
        every group, start at one x. A form calls this again after it adds rows."""
        from fdcad.ui.property_panel.columns import keep_aligned

        return keep_aligned(self.groups_box)

    @staticmethod
    def _start_with_preset(feature: Feature) -> None:
        """Put the chosen start settings into a new feature; its picks stay."""
        from fdcad.ui.preferences import phase4_settings as prefs

        try:
            stored = prefs.start_params(feature.type)
            if stored:
                found = prefs.params_from_json(stored)
                found.pop("operation", None)  # the command chose Boss or Cut
                feature.params.update(found)
        except Exception:  # a broken stored preset never stops a new feature
            return

    def _add_presets_box(self) -> None:
        """Favourites for every panel (TR326): forms that have their own keep it."""
        if self.feature is None or getattr(self.form, "favourites_box", None) is not None:
            return
        from fdcad.ui import strings_phase4 as text4
        from fdcad.ui.property_panel.favourites import FavouritesBox

        group = self._add_group("favourites", Group(text4.GROUP_FAVOURITES, text4.FAVOURITES_TIP))
        self.presets_box = FavouritesBox(self, self.feature.type, self.message.setText)
        group.form.addRow(self.presets_box)

    def _clear(self) -> None:
        for group in self.groups.values():
            self.groups_layout.removeWidget(group)
            group.hide()  # out of the label column at once (D2742), deleted a turn later
            group.deleteLater()
        self.values, self.choices, self.flags, self.groups = {}, {}, {}, {}
        if self.page_tabs is not None:
            self.tab_bar_layout.removeWidget(self.page_tabs.bar)
            for page in self.page_tabs.pages.values():
                self.groups_layout.removeWidget(page)
            self.page_tabs.discard()
            self.page_tabs = None
        self._tab_of, self._other_tab = {}, ""
        self.tab_bar_box.hide()
        self.sketch_box = QComboBox()
        self.axis_box = QComboBox()
        self.start = None
        self.regions = None
        self.ends = {}
        self.thin = None
        if self.form is not None:
            # The pre check box lives in the panel, not in the form, so deleting the
            # form left it: a cancelled feature's note showed in every later panel (D1042).
            check = self.form.check
            self.groups_layout.removeWidget(check)
            check.hide()
            check.deleteLater()
            self.form.deleteLater()
        self.form = None
        if self.body_form is not None:
            self.body_form.deleteLater()
        self.body_form = None
        self.bodies_box = None
        #: Value names set in this panel (TR32), stored on OK.
        self.value_names = {}
        self.message.clear()

    def _show_hint(self, kind: str) -> None:
        """The tool's one line hint, once per tool, unless hints are turned off."""
        from fdcad.ui.help.hints import hint_for, mark_seen, should_show

        self.hint.hide()
        store = self.hint_store
        if store is None or not should_show(store, kind):
            return
        line = hint_for(kind)
        if not line:
            return
        self.hint.setText(line)
        self.hint.show()
        mark_seen(store, kind)

    def _hint_link(self, link: str) -> None:
        from fdcad.ui.help.hints import turn_off

        if link == "show":
            self.help_requested.emit()
        elif link == "off" and self.hint_store is not None:
            turn_off(self.hint_store)
            self.hint.hide()

    def _add_group(self, key: str, group: Group) -> Group:
        self.groups[key] = group
        if not self._on_tab(key, group):
            self.groups_layout.insertWidget(self.groups_layout.count() - 1, group)
        return group

    def use_tabs(
        self, tabs: list[tuple[str, str, str]], where: dict[str, str], other: str
    ) -> PanelTabs:
        """Put the groups added from now on onto pages under a row of tabs (D2790).

        ``tabs`` are (key, title, tooltip). ``where`` gives the tab of a group by the
        group's key; a group not named there goes to tab ``other``. A form calls this
        at the start of ``build``.
        """
        from fdcad.ui.property_panel.tabs import PanelTabs

        self.page_tabs = PanelTabs(tabs, self)
        self._tab_of, self._other_tab = dict(where), other
        self.tab_bar_layout.addWidget(self.page_tabs.bar)
        self.tab_bar_box.show()
        index = self.groups_layout.count() - 1
        if self.form is not None:
            index = max(0, self.groups_layout.indexOf(self.form.check))
        for page in self.page_tabs.pages.values():
            self.groups_layout.insertWidget(index, page)
            index += 1
        self.page_tabs.changed.connect(self._tab_changed)
        return self.page_tabs

    def _on_tab(self, key: str, group: Group) -> bool:
        """Put ``group`` on its tab's page. False when the panel has no tabs."""
        if self.page_tabs is None:
            return False
        self.page_tabs.add(self._tab_of.get(key, self._other_tab), group)
        return True

    def _tab_changed(self, _key: str) -> None:
        self.groups_scroll.verticalScrollBar().setValue(0)  # a new page starts at its top
        self.align_columns()

    def _build(self) -> None:
        self._clear()
        assert self.session is not None and self.feature is not None
        doc = self.session.document
        feature = self.feature
        self.title.setText(feature.name)
        self._show_hint(feature.type)
        size = self.style().pixelMetric(QStyle.PixelMetric.PM_LargeIconSize)
        self.icon.setFixedSize(QSize(size, size))
        found = icon(feature_icon_name(feature))
        self.icon.clear()
        if not found.isNull():
            self.icon.setPixmap(found.pixmap(QSize(size, size), self.devicePixelRatioF()))
        try:
            variables = document_variables(doc)
        except ExpressionError:
            variables = {}
        units = doc.units
        if self._build_form(variables):
            return
        revolve = feature.type == "revolve"
        from fdcad.ui.property_panel.forms import FORMS

        form_class = FORMS.get(feature.type)
        if form_class is not None:
            self._variables = variables
            self.form = form_class(self, feature)
            self.form.check.setParent(self.groups_box)
            self.groups_layout.insertWidget(self.groups_layout.count() - 1, self.form.check)
            self.form.build()
            self.form.changed.connect(self._changed)
            return

        # From: the sketch the feature starts on.
        source = self._add_group("from", Group(strings.GROUP_FROM, _TIP["from"]))
        index = next(
            (i for i, f in enumerate(doc.features) if f.id == feature.id), len(doc.features)
        )
        for sk in doc.features[:index]:
            if sk.type == "sketch":
                self.sketch_box.addItem(sk.name, sk.id)
        current = feature.refs.get("sketch", {}).get("feature")
        if current is not None:
            self.sketch_box.setCurrentIndex(max(self.sketch_box.findData(current), 0))
        self.sketch_box.setToolTip(_TIP["sketch"])
        source.form.addRow(with_icon("field.sketch", _TIP["sketch"], self.sketch_box))
        self.sketch_box.currentIndexChanged.connect(self._changed)
        if not revolve:
            self.start = StartControls(
                source,
                doc,
                feature,
                lambda group, name, kind: self._value_row(group, name, kind, units, variables),
            )
            self.start.changed.connect(self._changed)

        if revolve:
            axis = self._add_group("axis", Group(strings.GROUP_AXIS, _TIP["axis"]))
            self.axis_box.setToolTip(_TIP["axis"])
            self.axis_box.setPlaceholderText(strings.CHOOSE_AXIS)
            axis.form.addRow(with_icon("field.axis", _TIP["axis"], self.axis_box))
            self.sketch_box.currentIndexChanged.connect(self._fill_axes)
            self._fill_axes()
            self.axis_box.currentIndexChanged.connect(self._changed)

        # Direction 1: reverse button beside the end condition, then the value.
        first = self._add_group("direction1", Group(strings.GROUP_DIRECTION1, _TIP["direction1"]))
        reverse = tool_button(
            "ui.reverse_direction", strings.FIELD_REVERSE, _TIP["reverse"], checkable=True
        )
        reverse.setChecked(bool(feature.params.get("reverse", False)))
        reverse.toggled.connect(self._changed)
        self.flags["reverse"] = reverse
        mode_name = "direction" if revolve else "end_condition"
        box = QComboBox()
        box.setToolTip(_TIP[mode_name])
        if revolve:
            dir1, stored2 = revolve_ends(feature)
        else:
            dir1, stored2 = direction1(feature), direction2(feature)
        options = list(ENDS1) if revolve else self._extrude_ends(dir1, True)
        for choice in options:
            box.addItem(strings.CHOICES[choice], choice)
        box.setCurrentIndex(max(box.findData(dir1), 0))
        box.currentIndexChanged.connect(self._mode_changed)
        self.choices[mode_name] = box
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(reverse)
        row_layout.addWidget(box, 1)
        first.form.addRow(row)
        value_name = "angle" if revolve else "depth"
        kind = Kind.ANGLE if revolve else Kind.LENGTH
        self._value_row(first, value_name, kind, units, variables)
        self.direction_box: QComboBox | None = None
        self.depth_along_box: QComboBox | None = None
        if not revolve:
            self._direction_controls(first, doc, feature)  # TR239
            self._value_row(first, "end_twist", Kind.ANGLE, units, variables)  # TR240
            self._value_row(first, "end_scale", Kind.NUMBER, units, variables)
            self._value_row(first, "profile_offset", Kind.LENGTH, units, variables)  # TR344
        self._end_controls(first, "", doc, units, variables, revolve)
        merge = QCheckBox(strings.FIELD_MERGE)
        merge.setToolTip(_TIP["merge"])
        merge.setChecked(feature.params.get("merge", True) is not False)
        merge.toggled.connect(self._changed)
        self.flags["merge"] = merge
        first.form.addRow(merge)
        if not revolve:  # TR334 (D2110): the operation chosen from where it sits
            self._auto_operation_rows(first, feature)
        if not revolve:  # TR164 (D1809): kept for the session, never saved
            self.detailed_box = QCheckBox(strings.FIELD_DETAILED_PREVIEW)
            self.detailed_box.setObjectName("extrude_detailed_preview")
            self.detailed_box.setToolTip(strings.FIELD_DETAILED_PREVIEW_TIP)
            self.detailed_box.setChecked(PropertyPanel.detailed_preview)
            self.detailed_box.toggled.connect(self._detailed_toggled)
            first.form.addRow(self.detailed_box)
        if feature.params.get("operation") == "cut":
            outside = QCheckBox(strings.FIELD_CUT_OUTSIDE)
            outside.setToolTip(_TIP["cut_outside"])
            outside.setChecked(feature.params.get("cut_outside", False) is True)
            outside.toggled.connect(self._changed)
            self.flags["cut_outside"] = outside
            first.form.addRow(outside)
            if not revolve:  # TR157 (D1023): which side of an open line is cut
                flip = QCheckBox(strings.FIELD_FLIP_SIDE)
                flip.setObjectName("flip_side")
                flip.setToolTip(_TIP["flip_side"])
                flip.setChecked(feature.params.get("flip_side", False) is True)
                flip.toggled.connect(self._changed)
                self.flags["flip_side"] = flip
                first.form.addRow(flip)
            if not revolve:  # TR175 (D784): teardrop or flat tops on round holes
                from fdcad.ui import strings_phase4

                top = QComboBox()
                top.setObjectName("print_top")
                for value, label in strings_phase4.PRINT_TOPS.items():
                    top.addItem(label, value)
                top.setToolTip(strings_phase4.TIPS["print_top"])
                index = top.findData(feature.params.get("print_top", "none"))
                top.setCurrentIndex(max(index, 0))
                top.currentIndexChanged.connect(self._changed)
                self.choices["print_top"] = top
                first.form.addRow(strings_phase4.LABEL_PRINT_TOP, top)
            if not revolve and _sheet_metal(doc):
                self._link_thickness(first, feature)  # TR30.1
                normal = QCheckBox(strings.FIELD_NORMAL_CUT)  # TR12.2
                normal.setToolTip(_TIP["normal_cut"])
                normal.setChecked(feature.params.get("normal_cut", True) is not False)
                normal.toggled.connect(self._changed)
                self.flags["normal_cut"] = normal
                first.form.addRow(normal)

        elif not revolve and _sheet_metal(doc):
            self._link_thickness(first, feature)  # bosses too (TR165, D1100)
        # Direction 2: folded until ticked.
        second = self._add_group(
            "direction2", Group(strings.GROUP_DIRECTION2, _TIP["direction2"], checkable=True)
        )
        box2 = QComboBox()
        box2.setToolTip(_TIP["end_condition2"])
        choices2 = list(ENDS2) if revolve else self._extrude_ends(stored2 or "blind", False)
        for choice in choices2:
            box2.addItem(strings.CHOICES[choice], choice)
        box2.setCurrentIndex(max(box2.findData(stored2 or "blind"), 0))
        box2.currentIndexChanged.connect(self._mode_changed)
        self.choices["end_condition2"] = box2
        second.form.addRow(with_icon("field.depth", _TIP["end_condition2"], box2))
        self._value_row(second, value_name + "2", kind, units, variables)
        self._end_controls(second, "2", doc, units, variables, revolve)
        second.set_checked(stored2 is not None)
        second.toggled.connect(self._mode_changed)

        # Selected Regions (T5.1.6, T5.3): active once clicked, until another field has focus.
        regions = self._add_group("regions", Group(strings.GROUP_REGIONS, _TIP["regions"]))
        self.regions = RegionControls(regions, feature)
        if self.session is not None:
            self.regions.units = self.session.document.units  # TR242
        self.regions.changed.connect(self._changed)
        self.sketch_box.currentIndexChanged.connect(self._sketch_changed)

        thin = self._add_group("thin", Group(strings.GROUP_THIN, _TIP["thin"], checkable=True))
        self.thin = ThinControls(
            thin,
            feature,
            lambda group, name, kind: self._value_row(group, name, kind, units, variables),
        )
        self.thin.changed.connect(self._changed)
        self._update_visibility()

    def add_form_group(self, key: str, group: Group) -> Group:
        """Add a group for a feature form (``forms``), above the pre check box."""
        self.groups[key] = group
        if self._on_tab(key, group):
            return group
        index = self.groups_layout.count() - 1
        if self.form is not None:
            index = max(0, self.groups_layout.indexOf(self.form.check))
        self.groups_layout.insertWidget(index, group)
        return group

    def make_field(self, kind: Kind, param: Param | None) -> ValueField:
        """A value field in the open part's units, for feature forms."""
        units = self.session.document.units if self.session is not None else UnitSystem.MM
        return ValueField(kind, units, getattr(self, "_variables", {}), param)

    def preview_checked(self, geometry: Any) -> None:
        """A preview finished: let the form show its pre check (PLAN 5A items 4 and 5).
        The title is red while the feature cannot be built yet (TR314)."""
        self.set_incomplete(getattr(geometry, "shape", None) is None)
        if self.form is not None:
            self.form.preview_checked(geometry)
        if self.body_form is not None:
            self.body_form.preview_checked(geometry)

    def _extrude_ends(self, stored: str, first: bool) -> list[str]:
        """Extrude end conditions in list order (T16 item 1). The ones that need a
        body are offered for cuts and once a body exists, or when already stored."""
        applies = self._through_all_applies()
        out = ["blind"]
        body_ends = ["through_all", "through_all_both", "up_to_next"]
        if not first:
            body_ends.remove("through_all_both")
        out += [c for c in body_ends if applies or stored == c]
        out += list(END_CONDITIONS)
        if applies or stored == "up_to_body":
            out.append("up_to_body")
        if first:
            out.append("mid_plane")
        return out

    def _end_controls(
        self,
        group: Group,
        which: str,
        doc: Any,
        units: UnitSystem,
        variables: dict[str, tuple[Kind, float]],
        revolve: bool = False,
    ) -> None:
        assert self.feature is not None
        controls = EndControls(
            group,
            which,
            doc,
            self.feature,
            lambda g, name, kind: self._value_row(g, name, kind, units, variables),
            "end_ref" if revolve else "end",
            revolve,
        )
        controls.changed.connect(self._changed)
        self.ends[which] = controls

    def _build_form(self, variables: dict[str, tuple[Kind, float]]) -> bool:
        """Phase 3 types get their panel from ``ui/body_tools/forms.py``."""
        from fdcad.ui.body_tools.form_widget import FeatureForm
        from fdcad.ui.body_tools.forms import form_for

        assert self.feature is not None
        form = form_for(self.feature.type)
        if form is None:
            return False
        self.body_form = FeatureForm(self, form, self._add_group, variables)
        self.body_form.changed.connect(self._changed)
        return True

    def _value_row(
        self,
        group: Group,
        name: str,
        kind: Kind,
        units: UnitSystem,
        variables: dict[str, tuple[Kind, float]],
    ) -> ValueField:
        assert self.feature is not None
        current = self.feature.params.get(name)
        inch = kind is Kind.LENGTH and units is UnitSystem.IN
        if not isinstance(current, Param) and inch and name in _INCH_DEFAULTS:
            text = _INCH_DEFAULTS[name]
            current = Param(text, float(text) * 25.4)
        elif not isinstance(current, Param) and name == "start_offset":
            current = Param("10", 10.0)
        elif not isinstance(current, Param) and name in _FIELD_DEFAULTS:
            current = Param(*_FIELD_DEFAULTS[name])
        elif not isinstance(current, Param):
            primary = self.feature.params.get(name.rstrip("2"))
            current = primary if isinstance(primary, Param) else None
        field = ValueField(kind, units, variables, current)
        field.setToolTip(_TIP[name])
        field.edit.textChanged.connect(self._changed)
        field.edit.returnPressed.connect(self.accept)
        field.tools.create = self._create_variable
        field.edit.installEventFilter(self)
        field.edit.setProperty("param_name", name)
        self.values[name] = field
        icon_name = "field.angle" if kind is Kind.ANGLE else "field.depth"
        group.form.addRow(with_icon(icon_name, _TIP[name], field))
        return field

    def _fill_axes(self) -> None:
        """List the sketch's lines. A single centerline is chosen by itself (W6.3)."""
        assert self.session is not None and self.feature is not None
        self.axis_box.blockSignals(True)
        self.axis_box.clear()
        sketch_id = self.sketch_box.currentData()
        if isinstance(sketch_id, str):
            sketch = sketch_from_data(self.session.document.feature(sketch_id).data)
            lines = [e for e in sketch.entities.values() if isinstance(e, Line)]
            lines.sort(key=lambda e: not e.construction)
            for ent in lines:
                text = strings.SKETCH_CENTERLINE if ent.construction else strings.SKETCH_LINE
                self.axis_box.addItem(text.format(id=ent.id), ent.id)
            centerlines = [e.id for e in lines if e.construction]
            self._add_axis_features()
            stored = self.feature.refs.get("axis", {})
            if stored.get("kind") in ("edge", "face"):
                self._add_edge_item(stored)
                self.axis_box.setCurrentIndex(self.axis_box.count() - 1)
            elif isinstance(stored.get("feature"), str):
                for i in range(self.axis_box.count()):
                    if self.axis_box.itemData(i) == stored:
                        self.axis_box.setCurrentIndex(i)
            else:
                current = stored.get("sketch_entity")
                if current is None and len(centerlines) == 1:
                    current = centerlines[0]
                self.axis_box.setCurrentIndex(self.axis_box.findData(current))
        self.axis_box.blockSignals(False)

    def _add_axis_features(self) -> None:
        """List the origin's axes and the reference axes above this feature (spec 2
        section 20 item 3, D712)."""
        from fdcad.ui import strings_phase3

        assert self.session is not None and self.feature is not None
        for f in self.session.document.features:
            if f.id == self.feature.id:
                break
            if f.type == "origin":
                for key, label in strings_phase3.ORIGIN_AXES.items():
                    self.axis_box.addItem(label, {"feature": f.id, "axis": key})
            elif f.type == "ref_axis":
                self.axis_box.addItem(f.name, {"feature": f.id})

    def _add_edge_item(self, ref: dict[str, Any]) -> None:
        """List a part edge or round face as an axis choice, replacing an earlier pick."""
        for i in reversed(range(self.axis_box.count())):
            data = self.axis_box.itemData(i)
            if isinstance(data, dict) and data.get("kind") in ("edge", "face"):
                self.axis_box.removeItem(i)
        assert self.session is not None
        doc = self.session.document
        owners = [f.name for f in doc.features if f.id in referenced_ids(ref)]
        label = strings.AXIS_FACE if ref.get("kind") == "face" else strings.AXIS_EDGE
        self.axis_box.addItem(
            label.format(feature=", ".join(owners) or "the part"), copy.deepcopy(ref)
        )

    def set_axis(self, entity_id: str) -> bool:
        """Use sketch line ``entity_id`` as the axis (for a line picked in the view)."""
        index = self.axis_box.findData(entity_id)
        if index < 0:
            return False
        self.axis_box.setCurrentIndex(index)
        return True

    def set_axis_edge(self, ref: dict[str, Any]) -> str | None:
        """Use a straight part edge as the axis (W6.3). Returns why not, or None when done.

        ``ref`` is the edge reference (FDEF_SPEC 7). The edge must come from a
        feature before the one being edited.
        """
        if self.session is None or self.feature is None or self.feature.type != "revolve":
            return None
        doc = self.session.document
        order = [f.id for f in doc.features]
        mine = order.index(self.feature.id) if self.feature.id in order else len(order)
        used = referenced_ids(ref)
        if any(fid not in order or order.index(fid) >= mine for fid in used):
            return strings.AXIS_EDGE_TOO_LATE.format(feature=self.feature.name)
        self._add_edge_item(ref)
        self.axis_box.setCurrentIndex(self.axis_box.count() - 1)
        return None

    # Changes ----------------------------------------------------------------------

    def _dir1(self) -> str:
        """Direction 1's end condition choice."""
        name = "direction" if "direction" in self.choices else "end_condition"
        box = self.choices.get(name)
        return str(box.currentData()) if box is not None else "blind"

    def _dir2_on(self) -> bool:
        """True when Direction 2 is ticked and allowed with Direction 1's choice."""
        second = self.groups.get("direction2")
        if second is None or not second.is_checked():
            return False
        return self._dir1() not in self._no_dir2()

    def _no_dir2(self) -> tuple[str, ...]:
        """Direction 1 choices that leave no Direction 2 (T5.1.4, T16)."""
        revolve = "direction" in self.choices
        return ("mid_plane", "through_all") if revolve else ("mid_plane", "through_all_both")

    def _dir2(self) -> str:
        box = self.choices.get("end_condition2")
        return str(box.currentData()) if box is not None else "blind"

    def _mode(self) -> str:
        """The stored end condition or direction value for the current choices."""
        dir1 = self._dir1()
        if dir1 == "blind" and self._dir2_on():
            return "two_directions"
        if "direction" in self.choices and dir1 == "blind":
            return "one_direction"
        return dir1

    def _mode_changed(self) -> None:
        self._update_visibility()
        uses_second = self._dir2_on() and self._dir2() == "blind"
        if not uses_second and self.active_param.endswith("2"):
            self._set_active(self.active_param[:-1])
        self._changed()

    def _update_visibility(self) -> None:
        if self.feature is None:
            return
        dir1 = self._dir1()
        second = self.groups.get("direction2")
        if second is not None:
            # Not with Mid Plane (T5.1.4); hidden with a full turn or Through All Both (T16).
            second.setEnabled(dir1 not in self._no_dir2())
            second.setVisible(dir1 == "mid_plane" or dir1 not in self._no_dir2())
        valued = ("blind", "mid_plane")
        for value_name, hidden in (
            ("depth", dir1 not in valued),
            ("angle", dir1 not in valued),
            ("depth2", self._dir2() != "blind"),
            ("angle2", self._dir2() != "blind"),
        ):
            field = self.values.get(value_name)
            if field is not None:
                row = field.parentWidget()
                if row is not None:
                    row.setVisible(not hidden)
        if self.start is not None:
            self.start.update_visibility()
        if "" in self.ends:
            self.ends[""].update(dir1)
        if "2" in self.ends:
            self.ends["2"].update(self._dir2())
        merge = self.flags.get("merge")
        if merge is not None:
            merge.setVisible(self._merge_applies())

    def _through_all_applies(self) -> bool:
        """Through All is offered for cuts, and for bosses once a body exists (T5.1.3)."""
        if self.feature is None:
            return False
        return self.feature.params.get("operation") == "cut" or self._has_body()

    def _has_body(self) -> bool:
        if self.session is None or self.feature is None or self.session.report is None:
            return False
        report = self.session.report
        return body_before(self.session.document, self.feature, report.results) is not None

    def _link_thickness(self, group: Group, feature: Feature) -> None:
        """Add the Link to thickness tick box to ``group``."""
        link = _link_box(feature, self._changed)
        self.flags["link_thickness"] = link
        group.form.addRow(link)

    def _direction_controls(self, group: Group, doc: Document, feature: Feature) -> None:
        """Along: the sketch's normal, a plane's normal, an axis, or an edge picked in the
        view; and how the depth is measured along it (TR239, D815)."""
        box = QComboBox()
        box.setObjectName("extrude_direction")
        box.setToolTip(strings.ALONG_TIP)
        box.addItem(strings.ALONG_NORMAL, None)
        order = [f.id for f in doc.features]
        mine = order.index(feature.id) if feature.id in order else len(order)
        for other in doc.features[:mine]:
            if other.type in ("plane", "ref_plane", "ref_axis"):
                box.addItem(other.name, {"feature": other.id})
        box.addItem(strings.ALONG_PICK, "pick")
        stored = feature.refs.get("direction")
        if isinstance(stored, dict):
            index = box.findData(stored)
            if index < 0:
                box.insertItem(box.count() - 1, strings.ALONG_EDGE, stored)
                index = box.count() - 2
            box.setCurrentIndex(index)
        along = QComboBox()
        along.setObjectName("extrude_depth_along")
        along.addItem(strings.DEPTH_ALONG["direction"], "direction")
        along.addItem(strings.DEPTH_ALONG["normal"], "normal")
        along.setCurrentIndex(max(along.findData(feature.params.get("depth_along")), 0))
        group.form.addRow(strings.ALONG, box)
        group.form.addRow(strings.DEPTH_MEASURED, along)
        box.currentIndexChanged.connect(self._changed)
        box.currentIndexChanged.connect(lambda _i: self._show_along())
        along.currentIndexChanged.connect(self._changed)
        self.direction_box, self.depth_along_box = box, along
        self._show_along()

    def _show_along(self) -> None:
        box, along = self.direction_box, self.depth_along_box
        if box is None or along is None:
            return
        on = isinstance(box.currentData(), dict)
        along.setVisible(on)
        holder = along.parentWidget()
        label = holder.layout() if holder is not None else None
        if label is not None and hasattr(label, "labelForField"):
            text = label.labelForField(along)
            if text is not None:
                text.setVisible(on)

    def set_start_pick(self, ref: dict[str, Any]) -> str | None:
        """Use a face, plane or vertex picked in the view for From. Returns why not, or None."""
        box = self.direction_box
        if box is not None and box.currentData() == "pick":  # TR239: an edge sets Along
            if ref.get("kind") != "edge":
                return strings.ALONG_PICK_EDGE
            box.insertItem(box.count() - 1, strings.ALONG_EDGE, ref)
            box.setCurrentIndex(box.count() - 2)
            return None
        for end in self._live_ends():
            if end.wants_pick():
                return end.set_pick(ref)
        if self.start is None:
            return None
        return self.start.set_pick(ref)

    def end_wants_pick(self) -> bool:
        """True when an extrude end condition waits for a face, plane or vertex, or Along
        waits for an edge (TR239)."""
        box = getattr(self, "direction_box", None)
        if box is not None and box.currentData() == "pick":
            return True
        return any(end.wants_pick() for end in self._live_ends())

    def _live_ends(self) -> list[EndControls]:
        """The end controls in use: Direction 2 only while it is on (bug hunt E3)."""
        return [end for which, end in self.ends.items() if which == "" or self._dir2_on()]

    def _merge_applies(self) -> bool:
        """Merge result is offered for a boss when the part already has a body (W6.2)."""
        if self.session is None or self.feature is None:
            return False
        if self.feature.params.get("operation", "boss") != "boss":
            return False
        report = self.session.report
        if report is None:
            return False
        return body_before(self.session.document, self.feature, report.results) is not None

    #: Detailed preview on the Extrude panel (TR164, D1809), kept for the session.
    detailed_preview = False

    def _detailed_toggled(self, on: bool) -> None:
        PropertyPanel.detailed_preview = on
        self._changed()

    def _changed(self) -> None:
        if self._loading or self.feature is None:
            return
        feature = self.current_feature()
        if feature is not None and self.form is not None:
            feature = self.form.for_preview(feature)
        elif feature is not None and feature.type == "extrude" and PropertyPanel.detailed_preview:
            import copy

            feature = copy.deepcopy(feature)  # the flag is on the preview copy only
            feature.data["preview_detailed"] = True
        self.values_changed.emit(feature)

    def _sketch_changed(self) -> None:
        """Picked regions belong to the old sketch: drop them."""
        if self.regions is not None and not self._loading:
            self.regions.clear()

    def toggle_region(self, ref: dict[str, Any]) -> bool:
        """Add or remove a region clicked in the view (T5.3.2). False when the box is off."""
        if self.regions is None or not self.regions.active:
            return False
        self.regions.toggle(ref)
        return True

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Track which length the user works on, for the active drag handle; offer
        Name This Value on a value field's right click menu (TR32)."""
        if event.type() == QEvent.Type.ContextMenu and isinstance(watched, QLineEdit):
            name = watched.property("param_name")
            if isinstance(name, str) and self.feature is not None:
                menu = watched.createStandardContextMenu()
                menu.addSeparator()
                menu.addAction(strings.NAME_VALUE).triggered.connect(
                    lambda _c=False, n=name: self.ask_value_name(n)
                )
                menu.exec(event.globalPos())  # type: ignore[attr-defined]
                menu.deleteLater()
                return True
        if event.type() == QEvent.Type.FocusIn and isinstance(watched, QLineEdit):
            if self.regions is not None:
                self.regions.set_active(False)
            name = watched.property("param_name")
            if isinstance(name, str):
                self._set_active(name)
        return super().eventFilter(watched, event)

    def ask_value_name(self, target: str, name: str | None = None) -> str:
        """Name value ``target`` of the open feature (asks when ``name`` is None). The
        name is stored when OK is pressed. Returns why it cannot be used, or ""."""
        from fdcad.core.equations.value_names import name_problem, set_value_name, value_name

        if self.feature is None:
            return ""
        if name is None:
            from PySide6.QtWidgets import QInputDialog

            current = self.value_names.get(target, value_name(self.feature, target))
            shown = "" if current == target else current
            text, ok = QInputDialog.getText(
                self, strings.NAME_VALUE_TITLE, strings.NAME_VALUE_PROMPT, text=shown
            )
            if not ok:
                return ""
            name = text
        probe = copy.deepcopy(self.feature)
        for t, n in self.value_names.items():
            set_value_name(probe, t, n)
        problem = name_problem(probe, target, name)
        if problem:
            self.message.setText(problem)
            return problem
        self.value_names[target] = name.strip()
        self._changed()
        return ""

    def set_active_param(self, name: str) -> None:
        """Make ``name`` the value the view works on (its drag handle, its label, T15.3)."""
        self._set_active(name)

    def _set_active(self, name: str) -> None:
        if name != self.active_param:
            self.active_param = name
            self.active_changed.emit(name)

    def set_value(self, name: str, value: float) -> None:
        """Set a field from a dragged handle (mm or radians). Keeps them in sync."""
        if self.body_form is not None and self.body_form.set_value(name, value):
            self._set_active(name)
            return
        field = self.values.get(name)
        if field is None and self.form is not None:
            field = self.form.fields.get(name)
        if field is None or self.session is None or value <= 0:
            return
        self._set_active(name)
        if field.kind is Kind.ANGLE:
            text = typed_angle(value)
        else:
            text = typed_length(value, self.session.document.units)
        if field.edit.text() != text:
            field.edit.setText(text)

    def set_text(self, name: str, text: str) -> str | None:
        """Type ``text`` into a value field (the handle value box). Returns what is wrong, or None.

        The text is kept as typed, so units and formulas stay (PLAN section 7).
        """
        field = self.values.get(name)
        if field is None and self.form is not None:
            field = self.form.fields.get(name)
        if field is None:
            return None
        if field.tools.try_new_variable(text):  # ="Name" makes a variable (T14.6.3)
            return None
        previous = field.edit.text()
        field.edit.setText(text)
        if field.param() is None:
            error = field.info.text()
            field.edit.setText(previous)
            return error or strings.FIX_ERRORS
        self._set_active(name)
        return None

    def _create_variable(self, name: str, kind: Kind, expr: str, value: float) -> bool:
        """Ask, then add a global variable as one undoable step (T14.6.3)."""
        from fdcad.core.document.model import Variable
        from fdcad.ui import strings_extra
        from fdcad.ui.commands.document import SetVariables

        session = self.session
        if session is None:
            return False
        shown = format_value(value, kind, session.document.units)
        answer = QMessageBox.question(
            self,
            strings_extra.VARIABLE_TITLE,
            strings_extra.VARIABLE_CONFIRM.format(name=name, value=shown),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False
        variables = [*session.document.variables, Variable(name, kind, expr, value)]
        session.undo.push(SetVariables(session, variables))
        return True

    def link_end(self, name: str, ref: dict[str, Any]) -> bool:
        """A depth arrow was snapped to the part vertex ``ref`` (TR395, D2207): its end
        becomes Up to Vertex on that vertex, so the depth follows the point when the part
        changes. Only a Blind direction is linked. True when linked."""
        which = {"depth": "", "depth2": "2"}.get(name)
        box = self.choices.get("end_condition" if which == "" else "end_condition2")
        if which is None or which not in self.ends or box is None:
            return False
        if box.currentData() != "blind" or box.findData("up_to_vertex") < 0:
            return False
        box.setCurrentIndex(box.findData("up_to_vertex"))
        self._update_visibility()
        linked = self.ends[which].set_pick(ref) is None
        if not linked:
            box.setCurrentIndex(box.findData("blind"))
        self._changed()
        return linked

    def flip(self, name: str) -> None:
        """A handle was dragged past its start: reverse the direction (T5.2.5)."""
        if self.body_form is not None:
            self.body_form.flip(name)
            return
        button = self.flags.get("reverse")
        if button is not None and name in ("depth", "angle"):
            button.setChecked(not button.isChecked())

    def set_length(self, name: str, value: float) -> None:
        """Set a length field from a dragged handle (``value`` in mm). Same as ``set_value``."""
        self.set_value(name, value)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Enter accepts and Esc cancels while the panel has focus (W6.5)."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            self.accept(again=shift)  # TR314: Shift and Enter makes another one
        elif event.key() == Qt.Key.Key_Escape:
            hook = getattr(self, "escape_hook", None)  # stop a slow preview first (TR126)
            if hook is None or not hook():
                self.reject()
        else:
            super().keyPressEvent(event)

    # Results ----------------------------------------------------------------------

    def _auto_operation_rows(self, group: Any, feature: Feature) -> None:
        """Pick Operation and Alternate Solution, with the choice the last rebuild made
        (TR334, D2110)."""
        from fdcad.ui import strings_config as text_config

        auto = QCheckBox(text_config.AUTO_OPERATION)
        auto.setObjectName("auto_operation")
        auto.setToolTip(text_config.AUTO_OPERATION_TIP)
        auto.setChecked(feature.params.get("auto_operation") is True)
        auto.toggled.connect(self._changed)
        self.flags["auto_operation"] = auto
        group.form.addRow(auto)
        other = QCheckBox(text_config.AUTO_ALTERNATE)
        other.setObjectName("auto_alternate")
        other.setToolTip(text_config.AUTO_ALTERNATE_TIP)
        other.setChecked(feature.params.get("auto_alternate") is True)
        other.setEnabled(auto.isChecked())
        auto.toggled.connect(other.setEnabled)
        other.toggled.connect(self._changed)
        self.flags["auto_alternate"] = other
        group.form.addRow(other)
        results = getattr(getattr(self.session, "report", None), "results", None) or {}
        found = results.get(feature.id)
        chosen = getattr(found, "extras", {}).get("operation") if found is not None else None
        if auto.isChecked() and isinstance(chosen, str):
            note = QLabel(text_config.AUTO_CHOSEN.format(op=text_config.AUTO_NAMES[chosen]))
            note.setObjectName("auto_chosen")
            group.form.addRow(note)

    def _add_bodies_box(self) -> None:
        """The Bodies box (TR33) for cuts, bosses and holes in a multibody part."""
        from fdcad.ui import strings_extra
        from fdcad.ui.property_panel.bodies_box import BodiesBox, wanted

        if self.session is None or self.feature is None:
            return
        doc = self.session.document
        if not wanted(doc, self.feature, getattr(self.session.report, "results", None)):
            return
        group = self._add_group(
            "bodies", Group(strings_extra.BODIES_GROUP, strings_extra.BODIES_TIP)
        )
        box = BodiesBox(doc, self.feature)
        box.changed.connect(self._changed)
        group.form.addRow(box)
        self.bodies_box = box

    def bodies_want_pick(self) -> bool:
        """True while view picks go to the Bodies box (TR33)."""
        box = getattr(self, "bodies_box", None)
        return box is not None and box.wants_pick()

    def current_feature(self) -> Feature | None:
        """The edited copy with the panel's values, or None while something is wrong.

        A wrong value is shown in the message line. The document is not changed.
        """
        feature = self._current_feature()
        if feature is not None and getattr(self, "value_names", None):
            from fdcad.core.equations.value_names import set_value_name

            for target, name in self.value_names.items():
                set_value_name(feature, target, name)
        box = getattr(self, "bodies_box", None)
        if feature is not None and box is not None:
            problem = box.apply(feature)
            if problem is not None:
                self.message.setText(problem)
                return None
        return feature

    def _current_feature(self) -> Feature | None:
        """``current_feature`` without the Bodies box."""
        if self.feature is None:
            return None
        feature = copy.deepcopy(self.feature)
        if self.form is not None:
            problem = self.form.apply(feature)
            if problem is not None:
                self.message.setText(problem)
                return None
            self.message.clear()
            return feature
        if self.body_form is not None:
            edited, problem = self.body_form.apply(feature)
            if edited is None:
                self.message.setText(problem or strings.FIX_ERRORS)
                return None
            self.message.clear()
            return edited
        sketch_id = self.sketch_box.currentData()
        if not isinstance(sketch_id, str):
            self.message.setText(strings.CHOOSE_SKETCH)
            return None
        feature.refs["sketch"] = {"feature": sketch_id}
        if feature.type == "revolve":
            axis = self.axis_box.currentData()
            if isinstance(axis, dict):
                feature.refs["axis"] = copy.deepcopy(axis)
            elif isinstance(axis, str):
                feature.refs["axis"] = {"sketch_entity": axis}
            else:
                # Say the sketch has no line when it has none (audit B item 6, D729).
                has_line = any(
                    isinstance(self.axis_box.itemData(i), str) for i in range(self.axis_box.count())
                )
                self.message.setText(strings.CHOOSE_AXIS if has_line else strings.NO_AXIS)
                return None
        mode = self._mode()
        dir1, dir2_on, dir2 = self._dir1(), self._dir2_on(), self._dir2()
        if feature.type == "revolve":
            # T16 item 2: ``direction`` as before; the new keys only when they are needed.
            if dir1 == "mid_plane":
                feature.params["direction"] = "mid_plane"
            else:
                feature.params["direction"] = "two_directions" if dir2_on else "one_direction"
            if dir1 in ("blind", "mid_plane"):
                feature.params.pop("end_condition", None)
            else:
                feature.params["end_condition"] = dir1
            if dir2_on and dir2 != "blind":
                feature.params["end_condition2"] = dir2
            else:
                feature.params.pop("end_condition2", None)
            for which, end in self.ends.items():
                problem = end.apply(feature, which == "" or dir2_on)
                if problem is not None:
                    self.message.setText(problem)
                    return None
        else:
            feature.params["end_condition"] = mode
            # D141: Direction 2's condition is stored only when it is not plain Blind after Blind.
            plain = ("blind", "mid_plane")
            if dir2_on and (dir1 not in plain or dir2 != "blind"):
                feature.params["end_condition2"] = dir2
            else:
                feature.params.pop("end_condition2", None)
            if self.start is not None:
                problem = self.start.apply(feature, self.session_units())
                if problem is not None:
                    self.message.setText(problem)
                    return None
            for which, end in self.ends.items():
                problem = end.apply(feature, which == "" or dir2_on)
                if problem is not None:
                    self.message.setText(problem)
                    return None
        if self.thin is not None:
            problem = self.thin.apply(feature)
            if problem is not None:
                self.message.setText(problem)
                return None
        feature.params["reverse"] = self.flags["reverse"].isChecked()
        if self._merge_applies():
            feature.params["merge"] = self.flags["merge"].isChecked()
        else:
            feature.params.pop("merge", None)
        if self.regions is not None:
            problem = self.regions.apply(feature)
            if problem:
                self.message.setText(problem)
                return None
        box, along = getattr(self, "direction_box", None), getattr(self, "depth_along_box", None)
        if box is not None and along is not None:  # TR239 (D815)
            chosen = box.currentData()
            if isinstance(chosen, dict):
                feature.refs["direction"] = dict(chosen)
                feature.params["depth_along"] = str(along.currentData())
            else:
                feature.refs.pop("direction", None)
                feature.params.pop("depth_along", None)
        flip = self.flags.get("flip_side")
        if flip is not None and flip.isChecked():
            feature.params["flip_side"] = True
        else:
            feature.params.pop("flip_side", None)
        for key in ("auto_operation", "auto_alternate"):  # TR334 (D2110)
            box = self.flags.get(key)
            if box is not None and box.isChecked():
                feature.params[key] = True
            elif box is not None:
                feature.params.pop(key, None)
        outside = self.flags.get("cut_outside")
        if outside is not None and outside.isChecked():
            feature.params["cut_outside"] = True
        else:
            feature.params.pop("cut_outside", None)
        top = self.choices.get("print_top")
        if top is not None and top.currentData() not in (None, "none"):
            feature.params["print_top"] = str(top.currentData())
        else:
            feature.params.pop("print_top", None)
        link = self.flags.get("link_thickness")
        if link is not None and link.isChecked():
            feature.params["link_thickness"] = True
        else:
            feature.params.pop("link_thickness", None)
        normal = self.flags.get("normal_cut")
        if normal is not None and not normal.isChecked():
            feature.params["normal_cut"] = False  # stored only when off (it is the default)
        else:
            feature.params.pop("normal_cut", None)
        second_used = dir2_on and dir2 == "blind"
        for name, field in self.values.items():
            if name.startswith(_OWN_FIELDS):
                continue  # written by the From, end and thin controls
            second = name.endswith("2")
            if second and not second_used:
                feature.params.pop(name, None)
                continue
            param = field.param()
            if param is None:
                if dir1 not in ("blind", "mid_plane") and name in ("depth", "angle"):
                    continue  # the value is not used; keep the stored one
                self.message.setText(strings.FIX_ERRORS)
                return None
            feature.params[name] = param
        # End twist and scale are kept only when they do something (TR240, D816).
        for name, neutral in (("end_twist", 0.0), ("end_scale", 1.0), ("profile_offset", 0.0)):
            kept = feature.params.get(name)
            if isinstance(kept, Param) and abs(kept.value - neutral) < 1e-12:
                feature.params.pop(name, None)
        self.message.clear()
        return feature

    def session_units(self) -> UnitSystem:
        """The open part's units (millimetres when nothing is open)."""
        return self.session.document.units if self.session is not None else UnitSystem.MM

    def accept(self, again: bool = False) -> None:
        """Apply the edited copy as one undoable command (OK, Enter, confirmation corner).
        With ``again`` (Shift and Enter, TR314) a new feature's command starts again
        empty, as the pin does."""
        if self.session is None or self.feature is None:
            return
        feature = self.current_feature()
        if feature is None:
            return
        session = self.session
        if not self.is_new and all(f.id != feature.id for f in session.document.features):
            # Undo took the feature out while it was open (bug hunt E7).
            self.message.setText(strings.FEATURE_UNDONE.format(name=feature.name))
            return
        if self.form is not None:
            self.form.accepted(feature)
        many = pattern_instances(feature)
        if many > LARGE_PATTERN and not self.confirm_large_pattern(feature.name, many):
            return  # TR142 (D962): the panel stays open to change the count
        if self.is_new:
            import contextlib

            from fdcad.ui.preferences import phase4_settings as prefs

            with contextlib.suppress(Exception):  # TR326: for Last used; never stops OK
                prefs.set_last_used(feature.type, prefs.params_to_json(feature.params))
            session.undo.push(AddFeature(session, feature))
            if self.pin_button.isChecked() or again:
                QTimer.singleShot(0, self.again.emit)  # TR206: make another one
        else:
            from fdcad.ui.equations.scope import push_edit

            fields = {**self.values, **getattr(self.form, "fields", {})}
            push_edit(session, feature, fields)  # configuration scopes (P4.10)
        self.accepted = True
        applied = (feature.id, self.is_new)
        self._close()
        self.applied.emit(*applied)  # TR221: recently edited, name a new one

    def confirm_large_pattern(self, name: str, count: int) -> bool:
        """Ask before building a pattern with very many copies (a seam for tests)."""
        from PySide6.QtWidgets import QMessageBox

        answer = QMessageBox.question(
            self,
            strings.LARGE_PATTERN_TITLE,
            strings.LARGE_PATTERN_PROMPT.format(name=name, count=count),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def reject(self) -> None:
        """Discard the edits (Cancel, Esc, confirmation corner)."""
        self.accepted = False
        self._close()

    def cancel(self) -> None:
        """Discard the edits. Same as ``reject``."""
        self.reject()

    def set_incomplete(self, on: bool) -> None:
        """Show the title in the error colour while the feature is not complete."""
        self.incomplete = on
        if on:
            from fdcad.ui.themes.theme import palette

            self.title.setStyleSheet(f"color: {palette().state_error};")
            self.title.setToolTip(strings.PANEL_INCOMPLETE)
        else:
            self.title.setStyleSheet("")
            self.title.setToolTip("")

    def _close(self) -> None:
        self.set_incomplete(False)
        if self.regions is not None:
            self.regions.set_active(False)
        self.feature = None
        self._clear()
        self.title.clear()
        self.icon.clear()
        self.setEnabled(False)
        self.finished.emit()


def _link_box(feature: object, changed: object) -> QCheckBox:
    """The Link to thickness tick box (TR30.1 for cuts, TR165 for bosses)."""
    link = QCheckBox(strings.FIELD_LINK_THICKNESS)
    link.setToolTip(_TIP["link_thickness"])
    params = getattr(feature, "params", {})
    link.setChecked(params.get("link_thickness", False) is True)
    link.toggled.connect(changed)
    return link


def _sheet_metal(doc: object) -> bool:
    """True when the part has sheet metal features (Link to thickness, TR30.1)."""
    from fdcad.core.features.sheetmetal.common import SHEET_TYPES

    features = getattr(doc, "features", [])
    return any(f.type in (*SHEET_TYPES, "sheet_metal") for f in features)
