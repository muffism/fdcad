"""User preferences, stored with QSettings (PLAN section 8 item 16).

Only what Phase 1 uses. The update check stays off and has no setting until it
exists (CLAUDE.md rule 8).
"""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QSettings

from fdcad.core.units import UnitSystem
from fdcad.core.units.number_display import NumberStyle
from fdcad.ui.sketch_tools.options import SWITCHES, OverDefine, SketchOptions


class Theme(Enum):
    """Colour theme."""

    SYSTEM = "system"
    BEIGE = "beige"
    LIGHT = "light"  # Light Gray
    DARK = "dark"  # Dark Grey
    STEALTH = "stealth"  # black
    #: The system's contrast colours (TR378): used while a Windows contrast theme is on,
    #: never chosen in Preferences.
    CONTRAST = "contrast"


class Navigation(Enum):
    """Mouse or trackpad navigation (PLAN 8 item 9)."""

    MOUSE = "mouse"
    TRACKPAD = "trackpad"


MAX_RECENT = 10


#: How Isolate can draw the other bodies (TR99, D939).
ISOLATE_LOOKS = ("hidden", "transparent", "wireframe")


def _default(key: str) -> str:
    """The stored text of a sketch switch's default value."""
    return "true" if getattr(SketchOptions(), key) else "false"


class Settings:
    """Typed access to the stored preferences."""

    def __init__(self, store: QSettings | None = None) -> None:
        from fdcad import portable

        self.store = store or portable.settings()  # a file beside a portable copy (D1033)

    def _get(self, key: str, default: str) -> str:
        return str(self.store.value(key, default))

    @property
    def default_units(self) -> UnitSystem:
        """Units preselected in the New Part dialog."""
        try:
            return UnitSystem(self._get("units/default", "mm"))
        except ValueError:
            return UnitSystem.MM

    @default_units.setter
    def default_units(self, value: UnitSystem) -> None:
        self.store.setValue("units/default", value.value)

    @property
    def theme(self) -> Theme:
        """Light, dark or follow the system. Default light (owner request, D434)."""
        try:
            chosen = Theme(self._get("appearance/theme", "light"))
        except ValueError:
            return Theme.LIGHT
        return Theme.LIGHT if chosen is Theme.CONTRAST else chosen

    @theme.setter
    def theme(self, value: Theme) -> None:
        self.store.setValue("appearance/theme", value.value)

    @property
    def navigation(self) -> Navigation:
        """Mouse or trackpad navigation."""
        try:
            return Navigation(self._get("input/navigation", "mouse"))
        except ValueError:
            return Navigation.MOUSE

    @navigation.setter
    def navigation(self, value: Navigation) -> None:
        self.store.setValue("input/navigation", value.value)

    @property
    def animations(self) -> bool:
        """Animate view turns, such as turning to face a sketch (W1.3). Until it is set
        in Preferences it follows the system's reduce motion setting (TR294, D975)."""
        if self.store.value("appearance/animations") is None:
            from fdcad.ui.themes.motion import system_reduce_motion

            return not system_reduce_motion()
        return self._get("appearance/animations", "true").lower() not in ("false", "0", "no")

    @animations.setter
    def animations(self, value: bool) -> None:
        self.store.setValue("appearance/animations", "true" if value else "false")

    @property
    def turn_style(self) -> str:
        """How the view turns (TR415, D1001): "free", "turntable" (the model's Z stays
        upright, TR209) or "arcball". Settings from before keep their upright choice."""
        style = self._get("view/turn_style", "")
        if style in ("free", "turntable", "arcball"):
            return style
        old = self._get("view/lock_up", "false").lower() in ("true", "1", "yes")
        return "turntable" if old else "free"

    @turn_style.setter
    def turn_style(self, value: str) -> None:
        self.store.setValue("view/turn_style", value)

    @property
    def lock_up(self) -> bool:
        """Keep the model upright while turning (TR209, D832): the turntable style."""
        return self.turn_style == "turntable"

    @lock_up.setter
    def lock_up(self, value: bool) -> None:
        self.turn_style = "turntable" if value else "free"

    @property
    def colour_safe(self) -> bool:
        """Colour vision safe status colours (TR292, D769). Default off."""
        return self._get("appearance/colour_safe", "false").lower() in ("true", "1", "yes")

    @colour_safe.setter
    def colour_safe(self, value: bool) -> None:
        self.store.setValue("appearance/colour_safe", "true" if value else "false")

    @property
    def full_sketches_only(self) -> bool:
        """Use Only Fully Defined Sketches (TR36 item 6, D763). Default off."""
        return self._get("sketch/full_sketches_only", "false").lower() in ("true", "1", "yes")

    @full_sketches_only.setter
    def full_sketches_only(self, value: bool) -> None:
        self.store.setValue("sketch/full_sketches_only", "true" if value else "false")

    @property
    def simplify_threads(self) -> bool:
        """Show modelled threads as cosmetic while editing (TR347, D1921). Off."""
        return self._get("rebuild/simplify_threads", "false").lower() in ("true", "1", "yes")

    @simplify_threads.setter
    def simplify_threads(self, value: bool) -> None:
        self.store.setValue("rebuild/simplify_threads", "true" if value else "false")

    @property
    def tree_follows_selection(self) -> bool:
        """The tree opens to the feature of a pick in the view (TR200, D808). Default on."""
        return self._get("tree/follow_selection", "true").lower() in ("true", "1", "yes")

    @tree_follows_selection.setter
    def tree_follows_selection(self, value: bool) -> None:
        self.store.setValue("tree/follow_selection", "true" if value else "false")

    @property
    def tree_hover_highlight(self) -> bool:
        """Hovering a tree row draws its feature in the view (TR200, D808). Default on."""
        return self._get("tree/hover_highlight", "true").lower() in ("true", "1", "yes")

    @tree_hover_highlight.setter
    def tree_hover_highlight(self, value: bool) -> None:
        self.store.setValue("tree/hover_highlight", "true" if value else "false")

    @property
    def pick_size(self) -> str:
        """How close the cursor must be to pick: a key of ``input.pick_size.SIZES`` (TR313)."""
        from fdcad.ui.input.pick_size import SIZES

        key = self._get("selection/pick_size", "normal")
        return key if key in SIZES else "normal"

    @pick_size.setter
    def pick_size(self, value: str) -> None:
        self.store.setValue("selection/pick_size", value)

    @property
    def name_new_features(self) -> bool:
        """Type a new feature's name as soon as it is made (TR221). Off by default."""
        return str(self._get("tree/name_new", "false")).lower() == "true"

    @name_new_features.setter
    def name_new_features(self, on: bool) -> None:
        self.store.setValue("tree/name_new", "true" if on else "false")

    @property
    def backup_count(self) -> int:
        """Older copies kept on each save, 0 for none (TR218, D961)."""
        try:
            return max(0, min(20, int(self._get("files/backups", "0"))))
        except (TypeError, ValueError):
            return 0

    @backup_count.setter
    def backup_count(self, value: int) -> None:
        self.store.setValue("files/backups", int(value))

    @property
    def backup_folder(self) -> str:
        """Where older copies go; empty means a Backups folder beside the part."""
        return str(self._get("files/backup_folder", ""))

    @backup_folder.setter
    def backup_folder(self, value: str) -> None:
        self.store.setValue("files/backup_folder", value.strip())

    @property
    def reopen_last(self) -> bool:
        """Open the parts from last time at start (TR218). Off by default."""
        return str(self._get("files/reopen_last", "false")).lower() == "true"

    @reopen_last.setter
    def reopen_last(self, on: bool) -> None:
        self.store.setValue("files/reopen_last", "true" if on else "false")

    @property
    def large_controls(self) -> bool:
        """Larger command tab buttons and tree rows (TR294 item 3, D2017). Off by default."""
        return str(self._get("view/large_controls", "false")).lower() == "true"

    @large_controls.setter
    def large_controls(self, on: bool) -> None:
        self.store.setValue("view/large_controls", "true" if on else "false")

    @property
    def safe_graphics(self) -> bool:
        """Draw in software from the next start (TR219, D2016). Off by default."""
        return str(self._get("view/safe_graphics", "false")).lower() == "true"

    @safe_graphics.setter
    def safe_graphics(self, on: bool) -> None:
        self.store.setValue("view/safe_graphics", "true" if on else "false")

    @property
    def last_session(self) -> list[str]:
        """The saved parts that were open when FDCAD last closed."""
        raw = self.store.value("files/last_session", [])
        if isinstance(raw, str):
            raw = [raw] if raw else []
        return [str(p) for p in raw] if isinstance(raw, list | tuple) else []

    @last_session.setter
    def last_session(self, paths: list[str]) -> None:
        self.store.setValue("files/last_session", list(paths))

    @property
    def hidden_messages(self) -> list[str]:
        """Keys of the message bars the user chose not to see again (TR203, D959)."""
        raw = self.store.value("messages/hidden", [])
        if isinstance(raw, str):
            raw = [raw] if raw else []
        return [str(k) for k in raw] if isinstance(raw, list | tuple) else []

    def hide_message(self, key: str) -> None:
        """Do not show the message bar ``key`` again."""
        keys = self.hidden_messages
        if key not in keys:
            self.store.setValue("messages/hidden", [*keys, key])

    def restore_messages(self, keys: list[str] | None = None) -> None:
        """Show these hidden messages again (all of them without ``keys``)."""
        left = [] if keys is None else [k for k in self.hidden_messages if k not in keys]
        self.store.setValue("messages/hidden", left)

    @property
    def number_rounding(self) -> str:
        """Rounding of shown numbers (TR350, D949): half_away, half_even or truncate."""
        from fdcad.core.units.number_display import ROUNDING

        key = self._get("units/rounding", "half_away")
        return key if key in ROUNDING else "half_away"

    @number_rounding.setter
    def number_rounding(self, value: str) -> None:
        self.store.setValue("units/rounding", value)

    @property
    def number_separator(self) -> str:
        """Decimal separator of shown numbers: "system", "." or "," (TR350)."""
        key = self._get("units/separator", "system")
        return key if key in ("system", ".", ",") else "system"

    @number_separator.setter
    def number_separator(self, value: str) -> None:
        self.store.setValue("units/separator", value)

    @property
    def inch_fraction(self) -> int:
        """Show inch values as fractions to this denominator; 0 shows decimals (TR350)."""
        from fdcad.core.units.number_display import DENOMINATORS

        try:
            value = int(self._get("units/inch_fraction", "0"))
        except (TypeError, ValueError):
            return 0
        return value if value in DENOMINATORS else 0

    @inch_fraction.setter
    def inch_fraction(self, value: int) -> None:
        self.store.setValue("units/inch_fraction", int(value))

    def number_style(self) -> NumberStyle:
        """The shown number style these settings choose; "system" asks the locale."""
        from fdcad.core.units.number_display import NumberStyle

        separator = self.number_separator
        if separator == "system":
            from PySide6.QtCore import QLocale

            separator = "," if QLocale().decimalPoint() == "," else "."
        return NumberStyle(self.number_rounding, separator, self.inch_fraction).clean()

    def apply_number_style(self) -> None:
        """Use these settings for every shown number."""
        from fdcad.core.units.number_display import set_style

        set_style(self.number_style())

    @property
    def isolate_others(self) -> str:
        """How Isolate draws the other bodies: "hidden", "transparent" or "wireframe"
        (TR99, D939). Default hidden, as before."""
        key = self._get("view/isolate_others", "hidden")
        return key if key in ISOLATE_LOOKS else "hidden"

    @isolate_others.setter
    def isolate_others(self, value: str) -> None:
        self.store.setValue("view/isolate_others", value if value in ISOLATE_LOOKS else "hidden")

    @property
    def reduce_motion(self) -> bool:
        """Turn off every animation (U4.5). The same stored value as ``animations``, inverted."""
        return not self.animations

    @reduce_motion.setter
    def reduce_motion(self, value: bool) -> None:
        self.animations = not value

    @property
    def sketch_options(self) -> SketchOptions:
        """The Sketch page of the preferences (T11)."""
        values: dict[str, bool] = {
            key: self._get(f"sketch/{key}", _default(key)).lower() not in ("false", "0", "no")
            for key in SWITCHES
        }
        try:
            over = OverDefine(self._get("sketch/over_define", "ask"))
        except ValueError:
            over = OverDefine.ASK
        snap = self._get("sketch/grid_snap", "off")
        if snap not in ("off", "shown", "always"):
            snap = "off"

        def number(key: str, default: float) -> float:
            try:
                found = float(self._get(f"sketch/{key}", str(default)))
            except ValueError:
                return default
            return found if found > 0 else default

        return SketchOptions(
            **values,
            over_define=over,
            grid_snap=snap,
            length_step=number("length_step", 1.0),
            angle_step=number("angle_step", 15.0),
            grid_kind="polar" if self._get("sketch/grid_kind", "square") == "polar" else "square",
            polar_angle=number("polar_angle", 15.0),
        )

    @sketch_options.setter
    def sketch_options(self, value: SketchOptions) -> None:
        for key in SWITCHES:
            self.store.setValue(f"sketch/{key}", "true" if getattr(value, key) else "false")
        self.store.setValue("sketch/over_define", value.over_define.value)
        self.store.setValue("sketch/grid_snap", value.grid_snap)  # TR102
        self.store.setValue("sketch/length_step", str(value.length_step))
        self.store.setValue("sketch/angle_step", str(value.angle_step))
        self.store.setValue("sketch/grid_kind", value.grid_kind)  # TR238
        self.store.setValue("sketch/polar_angle", str(value.polar_angle))

    @property
    def autosave_minutes(self) -> int:
        """Minutes between autosaves, 1 to 60. Default 5 (PLAN Phase 1)."""
        try:
            minutes = int(self._get("files/autosave_minutes", "5"))
        except ValueError:
            return 5
        return min(max(minutes, 1), 60)

    @autosave_minutes.setter
    def autosave_minutes(self, value: int) -> None:
        self.store.setValue("files/autosave_minutes", min(max(int(value), 1), 60))

    @property
    def recent_files(self) -> list[str]:
        """Most recently opened files first."""
        value = self.store.value("files/recent", [])
        if isinstance(value, str):
            return [value]
        return [str(v) for v in value] if isinstance(value, list) else []

    def add_recent(self, path: str) -> None:
        """Move ``path`` to the top of the recent files list."""
        files = [p for p in self.recent_files if p != path]
        self.store.setValue("files/recent", [path, *files][:MAX_RECENT])
        from fdcad.ui.system_integration import add_to_system_recent

        add_to_system_recent(path)  # TR379: the jump list and Start; off in tests

    def remove_recent(self, path: str) -> None:
        """Take ``path`` off the recent files list (a file that no longer exists)."""
        self.store.setValue("files/recent", [p for p in self.recent_files if p != path])

    def clear_recent(self) -> None:
        """Empty the recent files list."""
        self.store.setValue("files/recent", [])

    @property
    def pinned_files(self) -> list[str]:
        """Parts pinned on the start page, kept first and never pushed off (TR218)."""
        value = self.store.value("files/pinned", [])
        if isinstance(value, str):
            return [value]
        return [str(v) for v in value] if isinstance(value, list) else []

    def set_pinned(self, path: str, pinned: bool) -> None:
        """Pin ``path`` on the start page, or unpin it."""
        files = [p for p in self.pinned_files if p != path]
        self.store.setValue("files/pinned", [*files, path] if pinned else files)

    # Input: shortcuts, gestures and the shortcut bar (SHORTCUTS.md) ------------------------

    def _json(self, key: str, default: object) -> object:
        import json

        raw = self.store.value(key, "")
        if not raw:
            return default
        try:
            return json.loads(str(raw))
        except ValueError:
            return default

    def _set_json(self, key: str, value: object) -> None:
        import json

        self.store.setValue(key, json.dumps(value, sort_keys=True))

    @property
    def shortcut_overrides(self) -> dict[str, list[str]]:
        """Shortcuts the user changed, by command id."""
        raw = self._json("input/shortcuts", {})
        if not isinstance(raw, dict):
            return {}
        return {str(k): [str(x) for x in v] for k, v in raw.items() if isinstance(v, list)}

    @shortcut_overrides.setter
    def shortcut_overrides(self, value: dict[str, list[str]]) -> None:
        self._set_json("input/shortcuts", value)

    @property
    def search_words(self) -> dict[str, str]:
        """Search words the user changed in the shortcut editor, by command id (T14.7.2)."""
        raw = self._json("input/search_words", {})
        if not isinstance(raw, dict):
            return {}
        return {str(k): str(v) for k, v in raw.items()}

    @search_words.setter
    def search_words(self, value: dict[str, str]) -> None:
        self._set_json("input/search_words", value)

    @property
    def gestures(self) -> dict[str, dict[str, str]]:
        """Gesture commands per context and direction."""
        from fdcad.ui.input.commands import DEFAULT_GESTURES

        raw = self._json("input/gestures", None)
        if not isinstance(raw, dict):
            return {k: dict(v) for k, v in DEFAULT_GESTURES.items()}
        return {
            str(ctx): {str(d): str(c) for d, c in m.items()}
            for ctx, m in raw.items()
            if isinstance(m, dict)
        }

    @gestures.setter
    def gestures(self, value: dict[str, dict[str, str]]) -> None:
        self._set_json("input/gestures", value)

    @property
    def gesture_directions(self) -> int:
        """4 or 8 gesture directions."""
        return 8 if self._get("input/gesture_directions", "4") == "8" else 4

    @gesture_directions.setter
    def gesture_directions(self, value: int) -> None:
        self.store.setValue("input/gesture_directions", "8" if value == 8 else "4")

    @property
    def shortcut_bar(self) -> dict[str, list[str]]:
        """Commands on the shortcut bar, per context."""
        from fdcad.ui.input.commands import DEFAULT_BAR

        raw = self._json("input/shortcut_bar", None)
        if not isinstance(raw, dict):
            return {k: list(v) for k, v in DEFAULT_BAR.items()}
        return {str(k): [str(x) for x in v] for k, v in raw.items() if isinstance(v, list)}

    @shortcut_bar.setter
    def shortcut_bar(self, value: dict[str, list[str]]) -> None:
        self._set_json("input/shortcut_bar", value)

    @property
    def hidden_command_tabs(self) -> list[str]:
        """Command tabs the user hid from the tab bar's right click menu."""
        raw = self._json("appearance/hidden_command_tabs", [])
        return [str(x) for x in raw] if isinstance(raw, list) else []

    @hidden_command_tabs.setter
    def hidden_command_tabs(self, value: list[str]) -> None:
        self._set_json("appearance/hidden_command_tabs", list(value))

    @property
    def custom_commands(self) -> list[str]:
        """Command ids on the user's own My Commands tab, in order (TR222, D2508)."""
        raw = self._json("appearance/custom_commands", [])
        return [str(x) for x in raw] if isinstance(raw, list) else []

    @custom_commands.setter
    def custom_commands(self, value: list[str]) -> None:
        self._set_json("appearance/custom_commands", list(value))

    @property
    def hidden_buttons(self) -> list[str]:
        """Command ids whose buttons the user hid from the command tabs (TR222)."""
        raw = self._json("appearance/hidden_buttons", [])
        return [str(x) for x in raw] if isinstance(raw, list) else []

    @hidden_buttons.setter
    def hidden_buttons(self, value: list[str]) -> None:
        self._set_json("appearance/hidden_buttons", list(value))

    @property
    def simple_mode(self) -> bool:
        """Simple mode: fewer command tabs and buttons for new users (TR222). Off by default."""
        return bool(self._json("appearance/simple_mode", False))

    @simple_mode.setter
    def simple_mode(self, on: bool) -> None:
        self._set_json("appearance/simple_mode", bool(on))

    @property
    def command_tab_order(self) -> list[str]:
        """Command tab names in the order the user dragged them to; empty for the default (D582)."""
        raw = self._json("appearance/command_tab_order", [])
        return [str(x) for x in raw] if isinstance(raw, list) else []

    @command_tab_order.setter
    def command_tab_order(self, value: list[str]) -> None:
        self._set_json("appearance/command_tab_order", list(value))

    @property
    def tool_groups(self) -> dict[str, str]:
        """The last tool used from each grouped dropdown, by group id (C6)."""
        raw = self._json("appearance/tool_groups", {})
        if not isinstance(raw, dict):
            return {}
        return {str(k): str(v) for k, v in raw.items() if isinstance(v, str)}

    def remember_tool(self, group: str, command: str) -> None:
        """Remember ``command`` as the tool shown on dropdown ``group``."""
        groups = self.tool_groups
        if groups.get(group) != command:
            groups[group] = command
            self._set_json("appearance/tool_groups", groups)

    @property
    def welcome_seen(self) -> bool:
        """True once the first run welcome was closed (D552). It is never shown again."""
        return self._get("help/welcome_seen", "false").lower() in ("true", "1", "yes")

    @welcome_seen.setter
    def welcome_seen(self, value: bool) -> None:
        self.store.setValue("help/welcome_seen", "true" if value else "false")
