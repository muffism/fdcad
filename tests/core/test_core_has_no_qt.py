"""Architecture rule 1: fdcad.core never imports Qt or fdcad.ui."""

import pkgutil
import subprocess
import sys

import fdcad.core


def test_core_imports_without_qt() -> None:
    modules = [m.name for m in pkgutil.walk_packages(fdcad.core.__path__, "fdcad.core.")]
    code = (
        "import importlib, sys\n"
        f"for name in {modules!r}: importlib.import_module(name)\n"
        "bad = [m for m in sys.modules if m.startswith(('PySide6', 'shiboken6', 'fdcad.ui'))]\n"
        "print(bad)\n"
        "raise SystemExit(1 if bad else 0)\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
