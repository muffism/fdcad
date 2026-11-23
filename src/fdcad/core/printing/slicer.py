"""Open in Slicer (PLAN Phase 2, DECISIONS D352): write the part as 3MF to a temporary
file and start the slicer of the printer profile with it.

No network access: the slicer is a local program, or the system's default app
for 3MF files when the profile names none.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from fdcad.core.io.export import ExportError

#: Folder under the system temporary folder that holds the files sent to a slicer.
TEMP_FOLDER = "fdcad-slicer"


def temp_path(title: str) -> Path:
    """A temporary 3MF path for a part called ``title``. Sending again overwrites it."""
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "_", title).strip(" .") or "Part"
    folder = Path(tempfile.gettempdir()) / TEMP_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{safe}.3mf"


def command(file: Path, slicer: str, platform: str = sys.platform) -> list[str] | None:
    """The command that opens ``file`` in ``slicer``; None means the system default app.

    On a Mac an ``.app`` bundle is opened with ``open -a``.
    """
    program = slicer.strip()
    if not program:
        if platform == "darwin":
            return ["open", str(file)]
        if platform.startswith("win"):
            return None  # os.startfile
        return ["xdg-open", str(file)]
    if platform == "darwin" and program.rstrip("/").endswith(".app"):
        return ["open", "-a", program, str(file)]
    return [program, str(file)]


def launch(
    file: Path,
    slicer: str,
    platform: str = sys.platform,
    popen: Callable[..., object] = subprocess.Popen,
    startfile: Callable[[str], None] | None = None,
) -> None:
    """Start the slicer with ``file`` and return at once. ExportError when it cannot start."""
    program = slicer.strip()
    if program and not (Path(program).exists() or _on_path(program)):
        raise ExportError(
            f"The slicer {program} was not found. Check the slicer path in Preferences, Printing."
        )
    args = command(file, slicer, platform)
    try:
        if args is None:
            opener = startfile or getattr(os, "startfile", None)
            if opener is None:
                raise ExportError(
                    "This system cannot open files with their default app. "
                    "Set the slicer path in Preferences, Printing."
                )
            opener(str(file))
        else:
            popen(args, close_fds=True)
    except OSError as exc:
        raise ExportError(
            f"{exc.strerror or exc}. Check the slicer path in Preferences, Printing."
        ) from exc


def _on_path(program: str) -> bool:
    import shutil

    return shutil.which(program) is not None
