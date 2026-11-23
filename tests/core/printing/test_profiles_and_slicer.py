"""Printer profiles, material densities and opening a slicer (PLAN 8 item 16, D351, D352)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from fdcad.core.io.export import ExportError
from fdcad.core.printing import slicer
from fdcad.core.printing.profiles import (
    DEFAULT_DENSITIES,
    GENERIC,
    PrinterProfile,
    densities_from,
    profiles_from,
)


def test_generic_profile_matches_the_plan() -> None:
    assert (GENERIC.bed_x, GENERIC.bed_y, GENERIC.height) == (220, 220, 250)
    assert GENERIC.slicer == ""  # the system's default app for 3MF files
    assert math.degrees(GENERIC.overhang_angle) == pytest.approx(45)


def test_profile_round_trips_and_bad_values_fall_back() -> None:
    profile = PrinterProfile("Big", 300, 310, 400, 0.6, math.radians(50), 1.2, 0.3, "/x/slicer")
    assert PrinterProfile.from_dict(profile.to_dict()) == profile
    bad = PrinterProfile.from_dict(
        {"name": " ", "bed_x": -5, "nozzle": "wide", "overhang_angle": 3.0, "height": True}
    )
    assert bad == GENERIC
    assert PrinterProfile.from_dict("nonsense") == GENERIC


def test_profile_list_is_never_empty_and_names_are_unique() -> None:
    assert profiles_from(None) == [GENERIC]
    found = profiles_from([{"name": "A"}, {"name": "A"}, {"name": "B"}])
    assert [p.name for p in found] == ["A", "A 2", "B"]


def test_densities_have_every_preset_and_take_edits() -> None:
    assert set(DEFAULT_DENSITIES) == {"PLA", "PETG", "ABS", "ASA", "TPU", "Resin"}
    got = densities_from({"PLA": 1.3, "Nylon": "1.14", "PETG": -1, "": 2})
    assert got["PLA"] == 1.3 and got["Nylon"] == 1.14
    assert got["PETG"] == DEFAULT_DENSITIES["PETG"]


def test_slicer_commands_per_platform() -> None:
    f = Path("/tmp/part.3mf")
    assert slicer.command(f, "", "darwin") == ["open", str(f)]
    assert slicer.command(f, "", "win32") is None
    assert slicer.command(f, "", "linux") == ["xdg-open", str(f)]
    assert slicer.command(f, "/Apps/Slice.app", "darwin") == [
        "open",
        "-a",
        "/Apps/Slice.app",
        str(f),
    ]
    assert slicer.command(f, "C:/Slicer/slice.exe", "win32") == ["C:/Slicer/slice.exe", str(f)]


def test_launch_starts_the_program_and_reports_a_missing_one(tmp_path: Path) -> None:
    program = tmp_path / "slicer"
    program.write_text("", encoding="utf-8")
    started: list[list[str]] = []
    target = tmp_path / "p.3mf"
    slicer.launch(target, str(program), "linux", popen=lambda a, **_k: started.append(a))
    assert started == [[str(program), str(target)]]
    with pytest.raises(ExportError, match="was not found"):
        slicer.launch(target, str(tmp_path / "missing"), "linux", popen=lambda a, **_k: None)
    opened: list[str] = []
    slicer.launch(target, "", "win32", startfile=opened.append)
    assert opened == [str(target)]


def test_launch_turns_os_errors_into_export_errors(tmp_path: Path) -> None:
    program = tmp_path / "slicer"
    program.write_text("", encoding="utf-8")

    def fail(_args: list[str], **_k: object) -> None:
        raise PermissionError(13, "Permission denied")

    with pytest.raises(ExportError, match="Permission denied"):
        slicer.launch(tmp_path / "p.3mf", str(program), "linux", popen=fail)


def test_temp_path_is_safe_and_reused() -> None:
    a = slicer.temp_path("My part: v2/final")
    assert a.parent.name == slicer.TEMP_FOLDER and a.suffix == ".3mf"
    assert "/" not in a.name and ":" not in a.name
    assert slicer.temp_path("My part: v2/final") == a
