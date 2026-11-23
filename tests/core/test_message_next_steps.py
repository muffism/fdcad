"""Every user facing error and warning says what to do next (CLAUDE.md 8.4, D550).

The test reads the source of ``fdcad`` and finds the messages written as text:
the reasons of the user facing exceptions (``FeatureError``, ``SketchSolveError``,
``NodeError`` and the other errors shown in the app) and the messages of feature
issues, sketch issues and geometry check issues. Each one must hold a sentence
that starts with a next step, such as "Pick a sketch." or "Enter a depth
greater than zero.". A message built from placeholders only (a wrapper such as
``f"{name}: {reason}"``) passes when its last part is the wrapped reason: that
reason is itself checked where it is raised.

Run ``uv run python tests/core/test_message_next_steps.py`` to list the messages
that fail.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "src" / "fdcad"

#: Exceptions whose text is shown to the user. ``DeformError`` is left out: its
#: text is a lower case reason clause that the deformation features always wrap
#: in a message with a next step (D550).
USER_ERRORS = frozenset(
    {
        "CircularReferenceError",
        "ConfigurationError",
        "CornerError",
        "DesignTableError",
        "EmbeddedError",
        "EquationError",
        "ExportError",
        "ExpressionError",
        "FeatureError",
        "FileFormatError",
        "GraphFormatError",
        "MeshImportError",
        "NeedsConfirmError",
        "NeedsConfirmationError",
        "NodeError",
        "OffsetError",
        "OrientationError",
        "PartialResultError",
        "PatternError",
        "ProfileError",
        "ShapeError",
        "SketchSolveError",
        "StepImportError",
        "TextError",
    }
)

#: Records that carry a message shown in the Errors tab or the sketch.
ISSUES = frozenset({"Issue", "SketchIssue", "GeometryIssue"})

#: Words that start a next step. The step may follow the feature name prefix.
STEP_WORDS = frozenset(
    {
        "add",
        "adjust",
        "apply",
        "change",
        "check",
        "choose",
        "clear",
        "click",
        "close",
        "connect",
        "constrain",
        "convert",
        "create",
        "delete",
        "dimension",
        "drag",
        "draw",
        "edit",
        "enter",
        "exclude",
        "export",
        "extend",
        "fill",
        "fix",
        "flatten",
        "flip",
        "give",
        "heal",
        "import",
        "include",
        "increase",
        "install",
        "join",
        "keep",
        "lay",
        "leave",
        "lengthen",
        "lower",
        "make",
        "mark",
        "move",
        "narrow",
        "open",
        "pick",
        "place",
        "point",
        "press",
        "raise",
        "read",
        "rebuild",
        "reduce",
        "reinstall",
        "remove",
        "rename",
        "reorder",
        "repair",
        "replace",
        "reselect",
        "restart",
        "reverse",
        "roll",
        "rotate",
        "round",
        "save",
        "scale",
        "select",
        "set",
        "shorten",
        "sketch",
        "split",
        "start",
        "suppress",
        "swap",
        "tick",
        "trim",
        "try",
        "turn",
        "type",
        "undo",
        "unsuppress",
        "untick",
        "update",
        "use",
        "widen",
    }
)

_PLACEHOLDER = "{X}"


def _template(node: ast.expr) -> str | None:
    """The message text with ``{X}`` for each value, or None if it is not text."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            else:
                parts.append(_PLACEHOLDER)
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _template(node.left), _template(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _is_wrapper(text: str) -> bool:
    """True when the message ends with a wrapped reason checked at its source."""
    body = text.rstrip()
    return body.endswith((": " + _PLACEHOLDER, _PLACEHOLDER)) and not body.endswith(
        ("(" + _PLACEHOLDER, "'" + _PLACEHOLDER)
    )


def has_next_step(text: str) -> bool:
    """True when a sentence of ``text`` starts with a next step word."""
    if _is_wrapper(text):
        return True
    for sentence in re.split(r"(?<=[.!?])\s+|:\s+", text):
        words = re.sub(r"^[^A-Za-z]+", "", sentence.replace(_PLACEHOLDER, " ")).split()
        if words and words[0].lower().strip(",.") in STEP_WORDS:
            return True
    return False


def _name(func: ast.expr) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def messages() -> Iterator[tuple[str, int, str]]:
    """Every message written as text: (file, line, text with placeholders)."""
    for path in sorted(SOURCE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        where = path.relative_to(SOURCE).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
                call = node.exc
                if _name(call.func) in USER_ERRORS and call.args:
                    text = _template(call.args[0])
                    if text is not None:
                        yield where, node.lineno, text
            elif isinstance(node, ast.Call) and _name(node.func) in ISSUES:
                values = list(node.args) + [k.value for k in node.keywords if k.arg == "message"]
                for value in values:
                    text = _template(value)
                    if text is not None and " " in text.strip():
                        yield where, node.lineno, text


#: Names of UI text constants that hold an error or a warning.
_UI_PROBLEM = re.compile(
    r"FAILED|ERROR|INVALID|CANNOT|MISSING|WARN|(^|_)NOT_|(^|_)NO_|BAD|UNREADABLE|REFUSED|LOST"
)

#: UI constants that match the names above but need no next step: labels and
#: states that tell the user nothing went wrong, and ``ORIENT_LOST``, which puts
#: the print orientation reason (holding its own next step) first.
UI_NOT_PROBLEMS = frozenset(
    {
        "NOT_AFFILIATED",
        "NO_HIDDEN_BODIES",
        "NO_PROBLEMS",
        "NO_RECENT",
        "ERRORS_SHOW_ERRORS",
        "ERRORS_SHOW_WARNINGS",
        "ORIENT_LOST",
        "TAB_ERRORS_COUNT",
        "TEXT_NO_CURVE",
        "WARN_SEPARATE_BODIES",
    }
)


def ui_messages() -> Iterator[tuple[str, int, str]]:
    """Error and warning texts of the UI strings modules, with ``{X}`` for each field."""
    for path in sorted((SOURCE / "ui").glob("strings*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        where = path.relative_to(SOURCE).as_posix()
        for node in tree.body:
            if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
                continue
            target = node.targets[0]
            if not isinstance(target, ast.Name) or not _UI_PROBLEM.search(target.id):
                continue
            if target.id in UI_NOT_PROBLEMS:
                continue
            text = _template(node.value)
            if text is not None and " " in text.strip():
                yield where, node.lineno, re.sub(r"\{[^{}]*\}", _PLACEHOLDER, text)


def missing_steps() -> list[str]:
    """The messages with no next step, as ``file:line: text``."""
    found = [*messages(), *ui_messages()]
    return [f"{f}:{n}: {t}" for f, n, t in found if not has_next_step(t)]


def test_the_scan_finds_the_messages() -> None:
    assert sum(1 for _ in messages()) > 900


def test_every_error_and_warning_says_what_to_do_next() -> None:
    missing = missing_steps()
    assert not missing, "\n".join(missing)


def test_no_dashes_in_messages() -> None:
    dashes = (chr(0x2013), chr(0x2014))
    found = [f"{f}:{n}" for f, n, t in messages() if any(d in t for d in dashes)]
    assert not found, found


def test_the_check_reads_steps_after_a_feature_name() -> None:
    assert has_next_step("{X}: enter a depth greater than zero.")
    assert has_next_step("{X}: the sketch is open. Close the contour.")
    assert has_next_step("{X}: {X}")
    assert not has_next_step("{X}: the depth must be greater than zero.")
    assert not has_next_step("Coincident needs two entities.")


if __name__ == "__main__":
    for line in missing_steps():
        print(line)
