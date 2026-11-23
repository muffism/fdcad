"""A Windows build finds DLLs only in Python and in Windows (D2864, D2875).

The CI runner put Java's folder on PATH, with its own copy of the C runtime, and the
build took those DLLs from it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "build_path", Path(__file__).parents[2] / "packaging" / "build_path.py"
)
assert SPEC and SPEC.loader
build_path = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_path)

PYTHON = [r"C:\py", r"C:\py\DLLs"]
JAVA = r"C:\hostedtoolcache\windows\Java_Temurin-Hotspot_jdk\17.0.21-9\x64\bin"


def test_folders_outside_windows_are_dropped() -> None:
    path = ";".join([JAVA, r"C:\Program Files\Git\mingw64\bin", r"C:\Windows\system32", ""])
    assert (
        build_path.build_path(path, PYTHON, r"C:\Windows")
        == r"C:\py;C:\py\DLLs;C:\Windows\system32"
    )


def test_windows_folders_keep_their_order_and_any_spelling() -> None:
    path = r"c:\windows\System32\Wbem;C:\Windows;C:\WINDOWS\system32\;C:\WindowsApps"
    kept = build_path.build_path(path, [], r"C:\Windows").split(";")
    assert kept == [r"c:\windows\System32\Wbem", r"C:\Windows", "C:\\WINDOWS\\system32\\"]


def test_the_spec_uses_it() -> None:
    spec = (Path(__file__).parents[2] / "packaging" / "fdcad.spec").read_text(encoding="utf-8")
    assert "build_path(" in spec
