"""Windows only names of ctypes are read with getattr, so mypy passes on a Mac (D2704)."""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "fdcad"

# The names typeshed gives ctypes on Windows only. mypy checks for the platform it runs on,
# so ``ctypes.windll`` is an error on a Mac unless the line sits under a ``sys.platform`` test.
WINDOWS_ONLY = {
    "windll",
    "oledll",
    "WinDLL",
    "OleDLL",
    "WINFUNCTYPE",
    "WinError",
    "FormatError",
    "GetLastError",
    "HRESULT",
    "DllCanUnloadNow",
    "DllGetClassObject",
}


def _ignored(line: str) -> bool:
    """True when the line already tells mypy to skip the name on other platforms."""
    return "type: ignore[" in line and "unused-ignore" in line


def _is_windows_test(test: ast.expr) -> bool:
    """True for ``sys.platform == "win32"``, the test mypy itself understands."""
    return (
        isinstance(test, ast.Compare)
        and ast.unparse(test.left) == "sys.platform"
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Eq)
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == "win32"
    )


def direct_uses(source: str) -> list[tuple[int, str]]:
    """The (line, name) of each ``ctypes.<Windows only name>`` in ``source``.

    A use under ``if sys.platform == "win32":`` is left out: mypy skips that block elsewhere.
    """
    lines = source.splitlines()
    found: list[tuple[int, str]] = []

    def walk(node: ast.AST) -> None:
        if isinstance(node, ast.If) and _is_windows_test(node.test):
            for other in node.orelse:
                walk(other)
            return
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "ctypes"
            and node.attr in WINDOWS_ONLY
            and not _ignored(lines[node.lineno - 1])
        ):
            found.append((node.lineno, node.attr))
        for child in ast.iter_child_nodes(node):
            walk(child)

    walk(ast.parse(source))
    return sorted(found)


def test_the_scan_sees_a_direct_use() -> None:
    assert direct_uses("import ctypes\nx = ctypes.windll.user32\n") == [(2, "windll")]
    assert direct_uses('import ctypes\nx = getattr(ctypes, "windll").user32\n') == []
    guarded = 'if sys.platform == "win32":\n    x = ctypes.windll\nelse:\n    y = ctypes.oledll\n'
    assert direct_uses(guarded) == [(4, "oledll")]
    assert direct_uses('if platform == "win32":\n    x = ctypes.windll\n') == [(2, "windll")]


def test_no_module_reads_a_windows_only_name_directly() -> None:
    problems = [
        f"{path.relative_to(SRC)}:{line}: ctypes.{name}"
        for path in sorted(SRC.rglob("*.py"))
        for line, name in direct_uses(path.read_text(encoding="utf-8"))
    ]
    assert not problems, "use getattr(ctypes, name), so mypy passes off Windows:\n" + "\n".join(
        problems
    )
