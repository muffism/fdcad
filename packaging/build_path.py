"""The PATH a Windows build runs with (D2864, D2875).

PyInstaller looks for the DLLs a module needs on PATH. Any folder there can hand the
build a copy of a DLL: Git's folder gave it OpenSSL, and the CI runner's Java folder
gave it the C runtime. So the build keeps only Python's own folders, first, and the
folders inside Windows. PySide6's folder is added by PyInstaller's own hooks.
"""

from __future__ import annotations

import ntpath


def _inside(folder: str, base: str) -> bool:
    folder = ntpath.normcase(ntpath.normpath(folder)).rstrip("\\")
    base = ntpath.normcase(ntpath.normpath(base)).rstrip("\\")
    return folder == base or folder.startswith(base + "\\")


def build_path(path: str, python_dirs: list[str], windows_dir: str) -> str:
    """Python's folders, then the PATH folders inside Windows, in their order."""
    kept = [part for part in path.split(";") if part and _inside(part, windows_dir)]
    return ";".join([*python_dirs, *kept])
