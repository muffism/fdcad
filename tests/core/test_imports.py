"""Every core module imports on its own, so there are no import cycles."""

from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import fdcad.core

CORE = Path(fdcad.core.__file__).parent
CODE = "import importlib, sys; importlib.import_module(sys.argv[1])"


def test_each_core_module_imports_alone() -> None:
    modules = sorted(
        "fdcad.core." + ".".join(p.relative_to(CORE).with_suffix("").parts)
        for p in CORE.rglob("*.py")
        if p.name != "__init__.py"
    )
    # A bounded pool: one process per module at once needs about 130 MB each and
    # runs out of memory on small machines once there are a few hundred modules.
    workers = max(2, min(8, os.cpu_count() or 2))

    def run(module: str) -> str | None:
        proc = subprocess.run(
            [sys.executable, "-c", CODE, module],
            capture_output=True,
            text=True,
            timeout=300,  # slow CI runners import OCP cold
        )
        if proc.returncode != 0:
            return f"{module}: {proc.stderr.strip().splitlines()[-1]}"
        return None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        failed = [r for r in pool.map(run, modules) if r is not None]
    assert failed == []
