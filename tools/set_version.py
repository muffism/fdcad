"""Set the app version in its two places at once (D556).

The version lives in ``pyproject.toml`` (``[project] version``) and in
``src/fdcad/__init__.py`` (``__version__``). The build backend cannot read one
from the other, so this script writes both and a test checks they match.

    uv run python tools/set_version.py 1.0.0
    uv lock

Run it, then ``uv lock``, on the release commit just before tagging ``v1.0.0``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
INIT = ROOT / "src" / "fdcad" / "__init__.py"
#: Release versions such as 1.0.0, or development versions such as 1.0.0.dev0.
VERSION = re.compile(r"^\d+\.\d+\.\d+(\.dev\d+)?$")


def set_version(version: str, root: Path = ROOT) -> None:
    """Write ``version`` into pyproject.toml and ``__version__``."""
    if not VERSION.match(version):
        raise ValueError(f"'{version}' is not a version such as 1.0.0 or 1.0.0.dev0.")
    pyproject = root / PYPROJECT.relative_to(ROOT)
    init = root / INIT.relative_to(ROOT)
    text = pyproject.read_text(encoding="utf-8")
    text, count = re.subn(r'(?m)^version = "[^"]*"', f'version = "{version}"', text, count=1)
    if count != 1:
        raise ValueError("pyproject.toml has no version line.")
    pyproject.write_text(text, encoding="utf-8")
    code = init.read_text(encoding="utf-8")
    code, count = re.subn(r'(?m)^__version__ = "[^"]*"', f'__version__ = "{version}"', code)
    if count != 1:
        raise ValueError("src/fdcad/__init__.py has no __version__ line.")
    init.write_text(code, encoding="utf-8")


def main(argv: list[str]) -> int:
    """Command line entry: one argument, the new version."""
    if len(argv) != 2:
        print("usage: set_version.py VERSION", file=sys.stderr)
        return 2
    try:
        set_version(argv[1])
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"version set to {argv[1]}; now run: uv lock")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
