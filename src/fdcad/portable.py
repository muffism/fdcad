"""Portable mode (DECISIONS D1033): everything FDCAD writes stays beside the program.

A packaged FDCAD is portable when a file named ``portable.txt`` sits beside its
program file, or when the program file's name holds "portable" (the single file
build, ``FDCAD-portable.exe``). Preferences, autosaves, logs, templates and the
rebuild cache then go to a ``FDCAD Data`` folder beside the program, and nothing is
written to the registry or the user's profile. Copy the folder to another PC or a
USB stick and FDCAD starts there with the same settings.

When that folder cannot be written (a read only disk), FDCAD starts in the normal
way and uses the user's profile.
"""

from __future__ import annotations

import os
import sys
from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtCore import QSettings

#: A file with this name beside the program turns portable mode on.
MARKER = "portable.txt"
#: The folder beside the program that holds everything FDCAD writes.
DATA_FOLDER = "FDCAD Data"

#: The preferences file inside the data folder.
SETTINGS_FILE = "settings.ini"

_ACTIVE: Path | None = None


def portable_folder(
    executable: str | Path | None = None, frozen: bool | None = None
) -> Path | None:
    """The data folder of a portable copy, made if needed; None when not portable."""
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if not frozen:
        return None
    program = Path(executable or sys.executable).resolve()
    if not ((program.parent / MARKER).is_file() or "portable" in program.stem.lower()):
        return None
    folder = program.parent / DATA_FOLDER
    probe = folder / ".write_test"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe.write_text("", encoding="utf-8")
        probe.unlink()
    except OSError:
        return None
    return folder


def enable(
    env: MutableMapping[str, str] | None = None,
    executable: str | Path | None = None,
    frozen: bool | None = None,
) -> Path | None:
    """Turn portable mode on when this copy is portable. Call before anything reads
    the data folder or the preferences. Returns the data folder, or None."""
    global _ACTIVE
    folder = portable_folder(executable, frozen)
    if folder is None:
        return None
    target = os.environ if env is None else env
    target.setdefault("FDCAD_DATA_DIR", str(folder))
    target.setdefault("FDCAD_CACHE_DIR", str(folder / "Cache"))
    _ACTIVE = folder
    return folder


def settings() -> QSettings:
    """The preferences store: ``settings.ini`` in the data folder when portable, else
    the system's own place (the registry on Windows)."""
    from PySide6.QtCore import QSettings

    if _ACTIVE is not None:
        return QSettings(str(_ACTIVE / SETTINGS_FILE), QSettings.Format.IniFormat)
    return QSettings("FDCAD", "FDCAD")


def active() -> Path | None:
    """The data folder when portable mode is on, else None."""
    return _ACTIVE
