"""Thread metadata in STEP files (PHASE4_SPEC P4.2, DECISIONS D314).

AP214 and AP242 as written here have no thread entity, so each cosmetic thread
is added as one line of the file's FILE_DESCRIPTION, which every STEP reader
keeps and ignores for geometry.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

_DESCRIPTION = re.compile(
    r"FILE_DESCRIPTION\(\((?P<items>\s*(?:'(?:[^']|'')*'\s*,?\s*)*)\)", re.DOTALL
)


def _step_string(text: str) -> str:
    """A STEP string literal: plain ASCII, quotes doubled."""
    clean = text.encode("ascii", "replace").decode("ascii").replace("'", "''")
    return f"'{clean}'"


def add_notes(step_text: str, notes: Sequence[str]) -> str:
    """``step_text`` with ``notes`` added to its FILE_DESCRIPTION."""
    if not notes:
        return step_text
    match = _DESCRIPTION.search(step_text)
    if match is None:
        return step_text
    items = match.group("items").strip()
    extra = ",".join(_step_string(n) for n in notes)
    joined = f"{items},{extra}" if items else extra
    return step_text[: match.start("items")] + joined + step_text[match.end("items") :]


def read_notes(step_text: str) -> list[str]:
    """The FILE_DESCRIPTION strings of a STEP file (for tests and import)."""
    match = _DESCRIPTION.search(step_text)
    if match is None:
        return []
    return [s.replace("''", "'") for s in re.findall(r"'((?:[^']|'')*)'", match.group("items"))]
