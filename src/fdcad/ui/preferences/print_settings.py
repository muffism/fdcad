"""Printer profiles and material densities in the preferences (PLAN 8 item 16, D351).

Stored as JSON under ``printing/`` next to the other preferences.
"""

from __future__ import annotations

from fdcad.core.printing.profiles import (
    PrinterProfile,
    densities_from,
    profiles_from,
)
from fdcad.ui.preferences.settings import Settings


def profiles(settings: Settings) -> list[PrinterProfile]:
    """Every printer profile, in order. There is always at least one."""
    return profiles_from(settings._json("printing/profiles", []))


def set_profiles(settings: Settings, value: list[PrinterProfile], active: str) -> None:
    """Store the profiles and the name of the active one."""
    settings._set_json("printing/profiles", [p.to_dict() for p in value])
    settings.store.setValue("printing/active", active)


def active_profile(settings: Settings) -> PrinterProfile:
    """The profile the print tools use: the chosen one, else the first."""
    found = profiles(settings)
    name = settings._get("printing/active", "")
    return next((p for p in found if p.name == name), found[0])


def densities(settings: Settings) -> dict[str, float]:
    """Material name to density in g/cm3: the presets with the user's changes."""
    return densities_from(settings._json("printing/densities", {}))


def set_densities(settings: Settings, value: dict[str, float]) -> None:
    """Store the material densities."""
    settings._set_json("printing/densities", dict(value))


def last_material(settings: Settings) -> str:
    """The material picked last in the print estimate."""
    return settings._get("printing/material", "PLA")


def set_last_material(settings: Settings, name: str) -> None:
    """Remember the material picked in the print estimate."""
    settings.store.setValue("printing/material", name)


def wall_target(settings: Settings) -> float:
    """The Wall Thickness Analysis target in mm (TR87, D1808); 0 uses the profile's
    minimum wall."""
    try:
        return max(0.0, float(settings._get("printing/wall_target", "0")))
    except ValueError:
        return 0.0


def set_wall_target(settings: Settings, value: float) -> None:
    """Store the Wall Thickness Analysis target (0 for the profile's minimum wall)."""
    settings.store.setValue("printing/wall_target", f"{max(0.0, value):g}")
