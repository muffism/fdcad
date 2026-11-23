"""Preferences dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.units import UnitSystem
from fdcad.ui import strings
from fdcad.ui.preferences.input_editors import GestureEditor, ShortcutBarEditor, ShortcutEditor
from fdcad.ui.preferences.settings import Navigation, Settings, Theme
from fdcad.ui.sketch_tools.options import SWITCHES, OverDefine, SketchOptions


def _scrolling(page: QWidget) -> QWidget:
    """``page`` inside a frameless scroll area that scrolls up and down only."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QFrame, QScrollArea

    area = QScrollArea()
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidgetResizable(True)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Tab goes to the fields, not the frame
    area.setWidget(page)
    return area


class PreferencesDialog(QDialog):
    """Dialog for editing application preferences."""

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Preferences")

        form = QFormLayout()

        self.units_box = QComboBox()
        self.units_box.addItem("Millimetres (mm)", UnitSystem.MM)
        self.units_box.addItem("Inches (in)", UnitSystem.IN)
        self.units_box.setCurrentIndex(self.units_box.findData(settings.default_units))
        form.addRow("Default units", self.units_box)

        self.theme_box = QComboBox()
        for label, choice in strings.THEME_CHOICES:
            self.theme_box.addItem(label, Theme(choice))
        self.theme_box.setCurrentIndex(self.theme_box.findData(settings.theme))
        form.addRow("Theme", self.theme_box)

        self.navigation_box = QComboBox()
        self.navigation_box.addItem("Mouse", Navigation.MOUSE)
        self.navigation_box.addItem("Trackpad", Navigation.TRACKPAD)
        self.navigation_box.setCurrentIndex(self.navigation_box.findData(settings.navigation))
        form.addRow("Navigation", self.navigation_box)

        # Reduce motion (U4.5) is the stored "animations" switch, inverted (D664).
        self.reduce_motion_box = QCheckBox(strings.PREF_REDUCE_MOTION)
        self.reduce_motion_box.setToolTip(strings.PREF_REDUCE_MOTION_TIP)
        self.reduce_motion_box.setChecked(settings.reduce_motion)
        form.addRow("", self.reduce_motion_box)
        from fdcad.ui import strings_a11y

        self.large_controls_box = QCheckBox(strings_a11y.PREF_LARGE_CONTROLS)  # TR294 (D2017)
        self.large_controls_box.setObjectName("pref_large_controls")
        self.large_controls_box.setToolTip(strings_a11y.PREF_LARGE_CONTROLS_TIP)
        self.large_controls_box.setChecked(settings.large_controls)
        form.addRow("", self.large_controls_box)

        self.turn_style_box = QComboBox()  # TR209, TR415 (D1001)
        self.turn_style_box.setObjectName("pref_turn_style")
        self.turn_style_box.setToolTip(strings.PREF_TURN_STYLE_TIP)
        for key, label in strings.PREF_TURN_STYLES.items():
            self.turn_style_box.addItem(label, key)
        self.turn_style_box.setCurrentIndex(
            max(self.turn_style_box.findData(settings.turn_style), 0)
        )
        form.addRow(strings.PREF_TURN_STYLE, self.turn_style_box)

        self.pick_size_box = QComboBox()  # TR313
        self.pick_size_box.setObjectName("pref_pick_size")
        self.pick_size_box.setToolTip(strings.PREF_PICK_SIZE_TIP)
        for key, label in strings.PICK_SIZES.items():
            self.pick_size_box.addItem(label, key)
        self.pick_size_box.setCurrentIndex(max(self.pick_size_box.findData(settings.pick_size), 0))
        form.addRow(strings.PREF_PICK_SIZE, self.pick_size_box)

        self.isolate_box = QComboBox()  # TR99 (D939)
        self.isolate_box.setObjectName("pref_isolate_others")
        self.isolate_box.setToolTip(strings.PREF_ISOLATE_OTHERS_TIP)
        for key, label in strings.ISOLATE_LOOKS.items():
            self.isolate_box.addItem(label, key)
        self.isolate_box.setCurrentIndex(max(self.isolate_box.findData(settings.isolate_others), 0))
        form.addRow(strings.PREF_ISOLATE_OTHERS, self.isolate_box)

        self.rounding_box = QComboBox()  # TR350 (D949)
        self.rounding_box.setObjectName("pref_rounding")
        self.rounding_box.setToolTip(strings.PREF_ROUNDING_TIP)
        for key, label in strings.ROUNDING_RULES.items():
            self.rounding_box.addItem(label, key)
        self.rounding_box.setCurrentIndex(
            max(self.rounding_box.findData(settings.number_rounding), 0)
        )
        form.addRow(strings.PREF_ROUNDING, self.rounding_box)

        self.separator_box = QComboBox()
        self.separator_box.setObjectName("pref_separator")
        self.separator_box.setToolTip(strings.PREF_SEPARATOR_TIP)
        for key, label in strings.SEPARATORS.items():
            self.separator_box.addItem(label, key)
        self.separator_box.setCurrentIndex(
            max(self.separator_box.findData(settings.number_separator), 0)
        )
        form.addRow(strings.PREF_SEPARATOR, self.separator_box)

        self.fraction_box = QComboBox()
        self.fraction_box.setObjectName("pref_inch_fraction")
        self.fraction_box.setToolTip(strings.PREF_FRACTION_TIP)
        self.fraction_box.addItem(strings.FRACTION_OFF, 0)
        for d in (2, 4, 8, 16, 32, 64):
            self.fraction_box.addItem(f"1/{d}", d)
        self.fraction_box.setCurrentIndex(
            max(self.fraction_box.findData(settings.inch_fraction), 0)
        )
        form.addRow(strings.PREF_FRACTION, self.fraction_box)

        from PySide6.QtWidgets import QListWidget, QListWidgetItem, QPushButton

        self.hidden_messages = QListWidget()  # TR203 (D959)
        self.hidden_messages.setObjectName("pref_hidden_messages")
        self.hidden_messages.setToolTip(strings.PREF_HIDDEN_MESSAGES_TIP)
        self.hidden_messages.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.hidden_messages.setMaximumHeight(90)
        for key in settings.hidden_messages:
            item = QListWidgetItem(strings.MESSAGE_NAMES.get(key, key))
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.hidden_messages.addItem(item)
        self.restored: list[str] = []
        self.show_again = QPushButton(strings.PREF_SHOW_AGAIN)
        self.show_again.setObjectName("pref_show_again")
        self.show_again.clicked.connect(self._show_again)
        form.addRow(strings.PREF_HIDDEN_MESSAGES, self.hidden_messages)
        form.addRow("", self.show_again)

        self.colour_safe_box = QCheckBox(strings.PREF_COLOUR_SAFE)  # TR292
        self.colour_safe_box.setObjectName("pref_colour_safe")
        self.colour_safe_box.setToolTip(strings.PREF_COLOUR_SAFE_TIP)
        self.colour_safe_box.setChecked(settings.colour_safe)
        form.addRow("", self.colour_safe_box)

        self.follow_box = QCheckBox(strings.PREF_TREE_FOLLOW)  # TR200
        self.follow_box.setObjectName("pref_tree_follow")
        self.follow_box.setToolTip(strings.PREF_TREE_FOLLOW_TIP)
        self.follow_box.setChecked(settings.tree_follows_selection)
        form.addRow("", self.follow_box)
        self.name_new_box = QCheckBox(strings.PREF_NAME_NEW)  # TR221 (D963)
        self.name_new_box.setObjectName("pref_name_new")
        self.name_new_box.setToolTip(strings.PREF_NAME_NEW_TIP)
        self.name_new_box.setChecked(settings.name_new_features)
        form.addRow("", self.name_new_box)
        self.hover_box = QCheckBox(strings.PREF_TREE_HOVER)
        self.hover_box.setObjectName("pref_tree_hover")
        self.hover_box.setToolTip(strings.PREF_TREE_HOVER_TIP)
        self.hover_box.setChecked(settings.tree_hover_highlight)
        form.addRow("", self.hover_box)

        self.autosave_box = QSpinBox()
        self.autosave_box.setRange(1, 60)
        self.autosave_box.setSuffix(" min")
        self.autosave_box.setValue(settings.autosave_minutes)
        form.addRow("Autosave every", self.autosave_box)
        self.backups_box = QSpinBox()  # TR218 (D961)
        self.backups_box.setObjectName("pref_backups")
        self.backups_box.setRange(0, 20)
        self.backups_box.setToolTip(strings.PREF_BACKUPS_TIP)
        self.backups_box.setValue(settings.backup_count)
        form.addRow(strings.PREF_BACKUPS, self.backups_box)
        from PySide6.QtWidgets import QLineEdit

        self.backup_folder = QLineEdit(settings.backup_folder)
        self.backup_folder.setObjectName("pref_backup_folder")
        self.backup_folder.setPlaceholderText(strings.PREF_BACKUP_FOLDER_HINT)
        form.addRow(strings.PREF_BACKUP_FOLDER, self.backup_folder)
        self.reopen_box = QCheckBox(strings.PREF_REOPEN)
        self.reopen_box.setObjectName("pref_reopen_last")
        self.reopen_box.setToolTip(strings.PREF_REOPEN_TIP)
        self.reopen_box.setChecked(settings.reopen_last)
        form.addRow("", self.reopen_box)
        from fdcad.ui import strings_extra

        self.safe_graphics_box = QCheckBox(strings_extra.PREF_SAFE_GRAPHICS)  # TR219 (D2016)
        self.safe_graphics_box.setObjectName("pref_safe_graphics")
        self.safe_graphics_box.setToolTip(strings_extra.PREF_SAFE_GRAPHICS_TIP)
        self.safe_graphics_box.setChecked(settings.safe_graphics)
        form.addRow("", self.safe_graphics_box)

        self.simplify_threads_box = QCheckBox(strings.PREF_SIMPLIFY_THREADS)  # TR347
        self.simplify_threads_box.setObjectName("pref_simplify_threads")
        self.simplify_threads_box.setToolTip(strings.PREF_SIMPLIFY_THREADS_TIP)
        self.simplify_threads_box.setChecked(settings.simplify_threads)
        form.addRow("", self.simplify_threads_box)

        from fdcad.ui import strings_feedback
        from fdcad.ui.main_window.dev_overlay import overlay_enabled

        self.overlay_box = QCheckBox(strings_feedback.PREF_DEV_OVERLAY)
        self.overlay_box.setObjectName("pref_dev_overlay")
        self.overlay_box.setToolTip(strings_feedback.PREF_DEV_OVERLAY_TIP)
        self.overlay_box.setChecked(overlay_enabled(settings.store))
        form.addRow("", self.overlay_box)

        general = QWidget()
        general.setLayout(form)
        sketch = self._sketch_page(settings.sketch_options)
        self.shortcuts = ShortcutEditor(settings)
        self.gestures = GestureEditor(settings)
        self.shortcut_bar = ShortcutBarEditor(settings)
        self.shortcuts.reset_everything.connect(self.gestures.reset)
        self.shortcuts.reset_everything.connect(self.shortcut_bar.reset)
        self.tabs = QTabWidget()
        # Long pages scroll, so the window and its OK button always fit the screen
        # (the General page alone was taller than a 1080 px screen, D1034).
        self.tabs.addTab(_scrolling(general), strings.TAB_GENERAL)
        self.tabs.addTab(_scrolling(sketch), strings.TAB_SKETCH)
        self.tabs.addTab(_scrolling(self.shortcuts), strings.TAB_SHORTCUTS)
        self.tabs.addTab(_scrolling(self.gestures), strings.TAB_GESTURES)
        self.tabs.addTab(_scrolling(self.shortcut_bar), strings.TAB_SHORTCUT_BAR)
        from fdcad.ui.preferences.printing_page import PrintingPage
        from fdcad.ui.strings_print import TAB_PRINTING

        self.printing = PrintingPage(settings)
        self.tabs.addTab(_scrolling(self.printing), TAB_PRINTING)
        from fdcad.ui.preferences.view_page import TAB_VIEW, ViewPage

        self.view_page = ViewPage(settings.store)  # round 12 view options (TR212)
        self.tabs.insertTab(1, _scrolling(self.view_page), TAB_VIEW)
        self.resize(720, 560)

        layout = QVBoxLayout()
        layout.addWidget(self.tabs)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.setLayout(layout)

    def _sketch_page(self, options: SketchOptions) -> QWidget:
        """Preferences > Sketch (T11)."""
        form = QFormLayout()
        self.sketch_boxes: dict[str, QCheckBox] = {}
        for key in SWITCHES:
            label, tip = strings.PREF_SKETCH[key]
            box = QCheckBox(label)
            box.setObjectName(f"pref_sketch_{key}")
            box.setToolTip(tip)
            box.setChecked(getattr(options, key))
            self.sketch_boxes[key] = box
            form.addRow("", box)
        self.over_define_box = QComboBox()
        self.over_define_box.setToolTip(strings.PREF_OVER_DEFINE_TIP)
        for choice in OverDefine:
            self.over_define_box.addItem(strings.PREF_OVER_DEFINE_CHOICES[choice.value], choice)
        self.over_define_box.setCurrentIndex(self.over_define_box.findData(options.over_define))
        form.addRow(strings.PREF_OVER_DEFINE, self.over_define_box)
        from PySide6.QtWidgets import QDoubleSpinBox

        self.grid_snap_box = QComboBox()  # TR102
        self.grid_snap_box.setObjectName("pref_grid_snap")
        for key, label in strings.PREF_GRID_SNAP_CHOICES.items():
            self.grid_snap_box.addItem(label, key)
        self.grid_snap_box.setCurrentIndex(max(self.grid_snap_box.findData(options.grid_snap), 0))
        form.addRow(strings.PREF_GRID_SNAP, self.grid_snap_box)
        self.length_step_box = QDoubleSpinBox()
        self.length_step_box.setRange(0.001, 1000.0)
        self.length_step_box.setDecimals(3)
        self.length_step_box.setSuffix(" mm")
        self.length_step_box.setValue(options.length_step)
        self.length_step_box.setToolTip(strings.PREF_STEPS_TIP)
        form.addRow(strings.PREF_LENGTH_STEP, self.length_step_box)
        self.angle_step_box = QDoubleSpinBox()
        self.angle_step_box.setRange(0.1, 90.0)
        self.angle_step_box.setSuffix(" deg")
        self.angle_step_box.setValue(options.angle_step)
        self.angle_step_box.setToolTip(strings.PREF_STEPS_TIP)
        form.addRow(strings.PREF_ANGLE_STEP, self.angle_step_box)
        self.grid_kind_box = QComboBox()  # TR238 (D1014)
        self.grid_kind_box.setObjectName("pref_grid_kind")
        for key, label in strings.PREF_GRID_KINDS.items():
            self.grid_kind_box.addItem(label, key)
        self.grid_kind_box.setCurrentIndex(max(self.grid_kind_box.findData(options.grid_kind), 0))
        form.addRow(strings.PREF_GRID_KIND, self.grid_kind_box)
        self.polar_angle_box = QDoubleSpinBox()
        self.polar_angle_box.setObjectName("pref_polar_angle")
        self.polar_angle_box.setRange(1.0, 90.0)
        self.polar_angle_box.setSuffix(" deg")
        self.polar_angle_box.setValue(options.polar_angle)
        self.polar_angle_box.setToolTip(strings.PREF_POLAR_ANGLE_TIP)
        form.addRow(strings.PREF_POLAR_ANGLE, self.polar_angle_box)
        self.full_sketches_box = QCheckBox(strings.PREF_FULL_SKETCHES)  # TR36 item 6
        self.full_sketches_box.setObjectName("pref_full_sketches_only")
        self.full_sketches_box.setToolTip(strings.PREF_FULL_SKETCHES_TIP)
        self.full_sketches_box.setChecked(self.settings.full_sketches_only)
        form.addRow("", self.full_sketches_box)
        page = QWidget()
        page.setLayout(form)
        return page

    def sketch_options(self) -> SketchOptions:
        """The Sketch page as chosen in the dialog."""
        values = {key: box.isChecked() for key, box in self.sketch_boxes.items()}
        return SketchOptions(
            **values,
            over_define=self.over_define_box.currentData(),
            grid_snap=str(self.grid_snap_box.currentData()),
            length_step=self.length_step_box.value(),
            angle_step=self.angle_step_box.value(),
            grid_kind=str(self.grid_kind_box.currentData()),
            polar_angle=self.polar_angle_box.value(),
        )

    def _show_again(self) -> None:
        """Take the picked messages off the hidden list (all when none is picked)."""
        items = self.hidden_messages.selectedItems() or [
            self.hidden_messages.item(i) for i in range(self.hidden_messages.count())
        ]
        for item in items:
            self.restored.append(str(item.data(Qt.ItemDataRole.UserRole)))
            self.hidden_messages.takeItem(self.hidden_messages.row(item))

    def accept(self) -> None:
        """Write the chosen values back to settings and close."""
        self.settings.default_units = self.units_box.currentData()
        self.settings.theme = self.theme_box.currentData()
        self.settings.navigation = self.navigation_box.currentData()
        self.settings.reduce_motion = self.reduce_motion_box.isChecked()
        self.settings.large_controls = self.large_controls_box.isChecked()  # TR294
        self.settings.colour_safe = self.colour_safe_box.isChecked()
        self.settings.tree_follows_selection = self.follow_box.isChecked()
        self.settings.tree_hover_highlight = self.hover_box.isChecked()
        self.settings.name_new_features = self.name_new_box.isChecked()  # TR221
        self.settings.turn_style = str(self.turn_style_box.currentData())
        self.settings.pick_size = str(self.pick_size_box.currentData())
        self.settings.isolate_others = str(self.isolate_box.currentData())  # TR99
        self.settings.number_rounding = str(self.rounding_box.currentData())  # TR350
        self.settings.number_separator = str(self.separator_box.currentData())
        self.settings.inch_fraction = int(self.fraction_box.currentData())
        if self.restored:
            self.settings.restore_messages(self.restored)  # TR203
        self.settings.autosave_minutes = self.autosave_box.value()
        self.settings.backup_count = self.backups_box.value()  # TR218
        self.settings.backup_folder = self.backup_folder.text()
        self.settings.reopen_last = self.reopen_box.isChecked()
        self.settings.safe_graphics = self.safe_graphics_box.isChecked()  # TR219

        self.settings.simplify_threads = self.simplify_threads_box.isChecked()  # TR347
        from fdcad.ui.main_window.dev_overlay import set_overlay_enabled

        set_overlay_enabled(self.settings.store, self.overlay_box.isChecked())
        self.settings.sketch_options = self.sketch_options()
        self.settings.full_sketches_only = self.full_sketches_box.isChecked()
        self.shortcuts.apply(self.settings)
        self.gestures.apply(self.settings)
        self.shortcut_bar.apply(self.settings)
        self.printing.apply(self.settings)
        self.view_page.apply(self.settings.store)
        super().accept()
