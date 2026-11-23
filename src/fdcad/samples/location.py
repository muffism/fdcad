"""Where the sample part files are, in a source checkout and in an installed app."""

from __future__ import annotations

import sys
from pathlib import Path


def sample_dir() -> Path:
    """The folder holding the sample part files."""
    bundle = getattr(sys, "_MEIPASS", None)  # set by PyInstaller in a packaged app
    if bundle:
        return Path(bundle) / "samples"
    return Path(__file__).resolve().parents[3] / "samples"


def sample_files() -> list[Path]:
    """Sample files, by name."""
    folder = sample_dir()
    from fdcad.core.io.fdef import is_part_file

    return sorted(p for p in folder.iterdir() if is_part_file(p)) if folder.is_dir() else []
