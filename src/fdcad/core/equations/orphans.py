"""Variables only some features use (TR91, D940).

When features are deleted, the global variables that only they used (directly, or
through other such variables) are offered for deletion too. A variable no formula
used before stays out of the list: it was not left behind by this delete. No Qt.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from fdcad.core.document.model import Document
from fdcad.core.equations.engine import cells
from fdcad.core.sketch.text_fields import FIELD
from fdcad.core.units.expressions import references


def _text_fields(value: Any, out: set[str]) -> None:
    """Names in ``{name}`` fields of sketch text, anywhere in feature data."""
    if isinstance(value, str):
        out.update(m.group(1) for m in FIELD.finditer(value))
    elif isinstance(value, dict):
        for item in value.values():
            _text_fields(item, out)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _text_fields(item, out)


def only_used_by(doc: Document, fids: Iterable[str]) -> list[str]:
    """Names of the variables that only the features ``fids`` use, in list order."""
    gone = set(fids)
    names = {v.name for v in doc.variables}
    every = cells(doc)
    used_by_gone: set[str] = set()
    for cell in every:
        if cell.fid in gone:
            used_by_gone |= references(cell.expr) & names
    for feature in doc.features:
        if feature.id in gone:
            found: set[str] = set()
            _text_fields(feature.data, found)
            used_by_gone |= found & names
    if not used_by_gone:
        return []
    kept_fields: set[str] = set()
    for feature in doc.features:
        if feature.id not in gone:
            _text_fields(feature.data, kept_fields)
    var_refs = {c.name: references(c.expr) & names for c in every if c.section == "variable"}
    other = [
        references(c.expr) & names for c in every if c.section != "variable" and c.fid not in gone
    ]
    used_elsewhere = set().union(*other) | (kept_fields & names) if other else kept_fields & names
    orphan: set[str] = set()
    changed = True
    while changed:
        changed = False
        for name in sorted(names - orphan):
            if name in used_elsewhere:
                continue
            users = [v for v, refs in var_refs.items() if name in refs and v != name]
            if any(u not in orphan for u in users):
                continue
            left_behind = name in used_by_gone or any(name in var_refs[u] for u in users)
            if left_behind:
                orphan.add(name)
                changed = True
    return [v.name for v in doc.variables if v.name in orphan]
