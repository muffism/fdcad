"""Older copies of a part kept on save (TR218 item 3, D961).

Before a save writes over a part file, the old file is copied to the backup folder
as ``<name>.backup1.fdprt``; older copies move up one number and the copy past the
chosen count is deleted. A failed copy never stops the save. No Qt.
"""

from __future__ import annotations

import shutil
from pathlib import Path

#: The most copies the preference allows.
MAX_COPIES = 20
#: The folder beside the part used when no folder is chosen.
DEFAULT_FOLDER = "Backups"


def backup_name(path: Path, number: int) -> str:
    """The file name of copy ``number`` (1 is the newest) of ``path``."""
    return f"{path.stem}.backup{number}{path.suffix}"


def folder_for(path: Path, folder: str | Path | None) -> Path:
    """Where the copies of ``path`` go: the chosen folder, else Backups beside it."""
    return Path(folder) if folder else path.parent / DEFAULT_FOLDER


def keep_backup(path: Path, count: int, folder: str | Path | None = None) -> Path | None:
    """Copy the file at ``path`` before it is written over, keeping ``count`` copies.
    Returns the new copy, or None when nothing was kept (no file, count 0, or the copy
    failed)."""
    count = max(0, min(int(count), MAX_COPIES))
    if count == 0 or not path.is_file():
        return None
    target = folder_for(path, folder)
    try:
        target.mkdir(parents=True, exist_ok=True)
        oldest = target / backup_name(path, count)
        if oldest.exists():
            oldest.unlink()
        for n in range(count - 1, 0, -1):
            older = target / backup_name(path, n)
            if older.exists():
                older.replace(target / backup_name(path, n + 1))
        newest = target / backup_name(path, 1)
        shutil.copy2(path, newest)
    except OSError:
        return None
    return newest


def backups_of(path: Path, folder: str | Path | None = None) -> list[Path]:
    """The kept copies of ``path``, newest first."""
    target = folder_for(path, folder)
    found = []
    for n in range(1, MAX_COPIES + 1):
        candidate = target / backup_name(path, n)
        if candidate.is_file():
            found.append(candidate)
    return found
