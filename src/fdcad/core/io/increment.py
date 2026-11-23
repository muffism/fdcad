"""Save Increment file names (TUTORIAL_REVIEW_SPEC_2 TR305, DECISIONS D923).

"Bracket.fdprt" becomes "Bracket 01.fdprt", "Bracket 01" becomes "Bracket 02", and
a name that already ends in a number keeps its separator and width ("box_7" becomes
"box_8", "v009" becomes "v010"). A name already taken is skipped. No Qt.
"""

from __future__ import annotations

import re
from pathlib import Path

_TAIL = re.compile(r"^(.*?)(\d+)$")


def next_name(stem: str) -> str:
    """The stem with its number raised by one, or " 01" added."""
    m = _TAIL.match(stem)
    if m is None or not m.group(1):
        return f"{stem} 01"
    head, digits = m.group(1), m.group(2)
    return f"{head}{int(digits) + 1:0{len(digits)}d}"


def next_path(path: Path) -> Path:
    """The next numbered file beside ``path`` that does not exist yet."""
    stem = next_name(path.stem)
    candidate = path.with_name(stem + path.suffix)
    while candidate.exists():
        stem = next_name(stem)
        candidate = path.with_name(stem + path.suffix)
    return candidate
