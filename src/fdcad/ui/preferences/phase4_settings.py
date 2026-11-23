"""Phase 4 preferences: favourites per feature type, the printer fit tolerance and the
heat set insert table (PHASE4_SPEC common rules and P4.1 item 5, DECISIONS D311).

Kept apart from ``settings.py`` so parallel work on other preferences does not clash.
Favourites are stored per feature type as ``{name: params}``, params in the file
format of FDEF_SPEC 3 (typed values as ``{"expr", "value"}``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fdcad.core.document.model import Param, ParamValue
from fdcad.core.features import hole_data
from fdcad.ui.preferences.settings import Settings

#: Tests set this to a Settings on a temporary store.
OVERRIDE: Settings | None = None


def settings() -> Settings:
    """The preferences store."""
    return OVERRIDE if OVERRIDE is not None else Settings()


def params_to_json(params: dict[str, ParamValue]) -> dict[str, Any]:
    """Parameters in file form."""
    out: dict[str, Any] = {}
    for key, value in params.items():
        out[key] = {"expr": value.expr, "value": value.value} if isinstance(value, Param) else value
    return out


def params_from_json(raw: dict[str, Any]) -> dict[str, ParamValue]:
    """Parameters back from file form; unknown shapes are skipped."""
    out: dict[str, ParamValue] = {}
    for key, value in raw.items():
        if isinstance(value, dict) and "expr" in value and "value" in value:
            try:
                out[str(key)] = Param(str(value["expr"]), float(value["value"]))
            except (TypeError, ValueError):
                continue
        elif isinstance(value, str | bool | int | float) or value is None:
            out[str(key)] = value
    return out


def favourites(ftype: str) -> dict[str, dict[str, Any]]:
    """Saved favourites of a feature type, by name."""
    raw = settings()._json(f"favourites/{ftype}", {})
    if not isinstance(raw, dict):
        return {}
    return {str(k): v for k, v in raw.items() if isinstance(v, dict)}


def set_favourites(ftype: str, value: dict[str, dict[str, Any]]) -> None:
    """Store the favourites of a feature type."""
    settings()._set_json(f"favourites/{ftype}", value)


#: What a new feature of a type starts with (TR326, D947): the factory settings, the
#: settings of the last one made, or a favourite by name.
FACTORY, LAST_USED = "factory", "last"


def preset_default(ftype: str) -> str:
    """``FACTORY``, ``LAST_USED`` or a favourite's name."""
    value = settings()._json(f"presets/default/{ftype}", FACTORY)
    return value if isinstance(value, str) and value else FACTORY


def set_preset_default(ftype: str, value: str) -> None:
    """Choose what new features of ``ftype`` start with."""
    settings()._set_json(f"presets/default/{ftype}", value or FACTORY)


def last_used(ftype: str) -> dict[str, Any] | None:
    """The settings of the last ``ftype`` feature made, or None."""
    value = settings()._json(f"presets/last/{ftype}", None)
    return value if isinstance(value, dict) else None


def set_last_used(ftype: str, params: dict[str, Any]) -> None:
    """Remember the settings of a feature just made."""
    settings()._set_json(f"presets/last/{ftype}", params)


def start_params(ftype: str) -> dict[str, Any] | None:
    """The stored settings a new ``ftype`` feature starts with, or None for the
    factory settings (also when the chosen favourite is gone)."""
    choice = preset_default(ftype)
    if choice == FACTORY:
        return None
    if choice == LAST_USED:
        return last_used(ftype)
    return favourites(ftype).get(choice)


def rename_favourite(ftype: str, old: str, new: str) -> bool:
    """Rename a favourite, and the default choice with it. False when ``new`` is empty,
    taken or ``old`` is missing."""
    new = new.strip()
    stored = favourites(ftype)
    if not new or old not in stored or (new in stored and new != old):
        return False
    stored = {(new if k == old else k): v for k, v in stored.items()}
    set_favourites(ftype, stored)
    if preset_default(ftype) == old:
        set_preset_default(ftype, new)
    return True


def export_favourites(ftype: str, path: str | Path) -> None:
    """Write the favourites of ``ftype`` to a JSON file."""
    data = {"format": "fdcad-favourites", "type": ftype, "favourites": favourites(ftype)}
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def import_favourites(ftype: str, path: str | Path) -> int:
    """Add the favourites in a file to ``ftype``'s. Returns how many were read.

    Raises ValueError when the file is not a favourites file of this type.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(
            "The file could not be read. Check that it is a favourites file saved by FDCAD."
        ) from exc
    if not isinstance(data, dict) or data.get("format") != "fdcad-favourites":
        raise ValueError(
            "The file is not an FDCAD favourites file. Choose a file made with Export."
        )
    if data.get("type") != ftype:
        raise ValueError(
            f"The file holds favourites for {data.get('type')}, not for {ftype}. "
            "Import it in the panel of that feature."
        )
    found = data.get("favourites")
    if not isinstance(found, dict):
        return 0
    current = favourites(ftype)
    count = 0
    for name, params in found.items():
        if isinstance(params, dict):
            current[str(name)] = params
            count += 1
    set_favourites(ftype, current)
    return count


def fit_tolerance() -> float:
    """The active printer profile's fit tolerance in mm (D311, D413).

    Before any printer profile was saved, the older ``printer/fit_tolerance``
    preference (D311) is used.
    """
    from fdcad.ui.preferences import print_settings

    store = settings()
    if store._json("printing/profiles", None):
        return print_settings.active_profile(store).fit_tolerance
    raw = store._json("printer/fit_tolerance", hole_data.DEFAULT_FIT_TOLERANCE)
    try:
        value = float(str(raw))
    except ValueError:
        return hole_data.DEFAULT_FIT_TOLERANCE
    return value if value >= 0 else hole_data.DEFAULT_FIT_TOLERANCE


def set_fit_tolerance(value: float) -> None:
    """Store the fit tolerance in mm in the active printer profile."""
    from dataclasses import replace

    from fdcad.ui.preferences import print_settings

    store = settings()
    store._set_json("printer/fit_tolerance", value)
    if store._json("printing/profiles", None):
        found = print_settings.profiles(store)
        active = print_settings.active_profile(store)
        changed = [replace(p, fit_tolerance=value) if p == active else p for p in found]
        print_settings.set_profiles(store, changed, active.name)


def insert_rows() -> list[dict[str, object]]:
    """The user's heat set insert table rows (empty for the defaults)."""
    raw = settings()._json("holes/inserts", [])
    return [r for r in raw if isinstance(r, dict)] if isinstance(raw, list) else []


def set_insert_rows(rows: list[dict[str, object]]) -> None:
    """Store the heat set insert table (an empty list restores the defaults)."""
    settings()._set_json("holes/inserts", rows)


def fit_table_text() -> str:
    """The printer fit table (TR412, D1919): one row per line; empty for none."""
    raw = settings()._json("printing/fit_table", "")
    return raw if isinstance(raw, str) else ""


def set_fit_table_text(text: str) -> None:
    """Keep the printer fit table."""
    settings()._set_json("printing/fit_table", text)


def nozzle() -> float:
    """The active printer profile's nozzle size in mm (0.4 before any profile)."""
    from fdcad.ui.preferences import print_settings

    store = settings()
    if store._json("printing/profiles", None):
        return float(print_settings.active_profile(store).nozzle)
    return 0.4


def user_hole_text() -> str:
    """The user's hole size file, as last loaded (TR144, D1914); empty for none."""
    raw = settings()._json("holes/user_sizes", "")
    return raw if isinstance(raw, str) else ""


def set_user_hole_text(text: str) -> None:
    """Keep the user's hole size file text, so the sizes come back next time."""
    settings()._set_json("holes/user_sizes", text)


def apply_user_holes() -> None:
    """Put the kept user sizes into the hole tables (a bad file leaves them empty)."""
    try:
        hole_data.USER_SIZES[:] = hole_data.parse_user_sizes(user_hole_text())
    except ValueError:
        hole_data.USER_SIZES[:] = []


def insert_margin() -> float:
    """Extra depth (mm) added to a heat set insert hole's table depth, room for melted
    plastic below the insert (TR189 item 4, D935). 0 by default."""
    value = settings()._json("holes/insert_margin", 0.0)
    return float(value) if isinstance(value, (int, float)) and 0 <= value <= 20 else 0.0


def set_insert_margin(mm: float) -> None:
    """Store the insert depth margin."""
    settings()._set_json("holes/insert_margin", max(0.0, min(20.0, float(mm))))


def inserts() -> list[hole_data.InsertSize]:
    """The insert table in use."""
    return hole_data.insert_table(insert_rows())


def self_tap_rows() -> list[dict[str, object]]:
    """The user's self tapping hole table rows (empty for FDCAD's rule, TR255)."""
    raw = settings()._json("holes/self_tapping", [])
    return [r for r in raw if isinstance(r, dict)] if isinstance(raw, list) else []


def set_self_tap_rows(rows: list[dict[str, object]]) -> None:
    """Store the self tapping hole table (an empty list restores FDCAD's rule)."""
    settings()._set_json("holes/self_tapping", rows)


def self_tap() -> list[hole_data.InsertSize]:
    """The self tapping hole table in use."""
    return hole_data.self_tap_table(self_tap_rows())


def size_carry_over() -> bool:
    """True (the default) when the Hole Tool keeps the size when the type changes; off,
    each hole type gets back its own last size (TR66, D892)."""
    return settings()._json("holes/carry_size", True) is not False


def set_size_carry_over(on: bool) -> None:
    """Turn the size carry over on or off."""
    settings()._set_json("holes/carry_size", bool(on))


def last_size(hole_type: str) -> str:
    """The size last used for ``hole_type`` ("" when none)."""
    raw = settings()._json("holes/last_sizes", {})
    value = raw.get(hole_type) if isinstance(raw, dict) else None
    return value if isinstance(value, str) else ""


def set_last_size(hole_type: str, size: str) -> None:
    """Remember the size used for ``hole_type``."""
    raw = settings()._json("holes/last_sizes", {})
    sizes = dict(raw) if isinstance(raw, dict) else {}
    if sizes.get(hole_type) != size:
        sizes[hole_type] = size
        settings()._set_json("holes/last_sizes", sizes)
