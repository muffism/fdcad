"""Panel options of the Phase 2 sketch tools (PHASE2_SPEC P2.8), as plain data.

A tool lists its options; the tool panel builds one field per option, reads
the tool attribute named by ``key`` and writes it back when the user changes
it. Pure Python, no Qt.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Option:
    """One field of a tool panel.

    ``kind`` is ``bool`` (tick box), ``choice`` (list, ``choices`` holds
    (value, label) pairs), ``length`` or ``angle`` (a value field that takes
    expressions; the attribute holds mm or radians), ``number`` (a plain number),
    ``text`` (kept as typed, TR28), ``int`` (a number box from ``low`` to
    ``high``) or ``button`` (calls ``tool.option_changed(key)``).
    """

    key: str
    label: str
    kind: str
    choices: tuple[tuple[str, str], ...] = ()
    low: int = 0
    high: int = 1000
    tip: str = ""
    #: Also shown as a value label in the sketch (T15.5). Off for fields of tools that
    #: type their own sizes there, such as the rectangle extras (TR114, D1313).
    in_sketch: bool = True
