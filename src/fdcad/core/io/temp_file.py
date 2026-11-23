"""Temporary files for atomic saves that end up with normal file permissions.

``tempfile.mkstemp`` creates files only the owner can read (mode 0600). A save
that writes one and renames it over the target would leave a part or export
that other users and other accounts cannot open (bug hunt F2). These files are
created like any other file, so the user's umask applies, and a file that is
replaced keeps its permissions.
"""

from __future__ import annotations

import contextlib
import os
import secrets
import stat
from pathlib import Path


def make_temp(folder: Path, target: Path, suffix: str = ".tmp") -> tuple[int, str]:
    """Create a temporary file in ``folder`` for writing ``target``. Returns (fd, path)."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    for _ in range(100):
        path = folder / f".fdcad-{secrets.token_hex(8)}{suffix}"
        try:
            fd = os.open(path, flags, 0o666)
        except FileExistsError:
            continue
        if os.name != "nt":
            # A file being replaced keeps its permissions; a new one keeps the umask's.
            with contextlib.suppress(OSError):
                os.chmod(fd, stat.S_IMODE(os.stat(target).st_mode))
        return fd, str(path)
    raise FileExistsError(f"No free temporary file name in {folder}. Choose another folder.")
