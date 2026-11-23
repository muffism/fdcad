"""Phase 4 groups of the Sketch command tab (PHASE4_SPEC).

The Phase 4 Features tools sit in ``tabs.FEATURE_GROUPS`` (RIBBON_SPEC R2).

Kept apart from ``tabs.py`` so parallel work on other groups does not clash.
"""

from __future__ import annotations

from typing import Any

from fdcad.ui import strings_phase4 as text

#: Phase 4 groups of the Sketch command tab.
PHASE4_SKETCH_GROUPS: list[tuple[str, list[Any], list[list[Any]]]] = [
    (text.GROUP_TEXT, [], [["sketch.text"]]),
]
