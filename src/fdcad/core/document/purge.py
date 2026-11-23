"""Purge Unused and the features below the rollback bar (TR159, D956).

Purge Unused finds what the part carries but does not use: sketches no feature or
graph uses, suppressed features, and global variables no formula, dimension or
sketch text uses (also through other such variables). The user ticks what goes.
Deleting a suppressed feature takes the features built on it too, so the part never
keeps a feature whose parent is gone. No Qt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fdcad.core.document import rollback
from fdcad.core.document.dependencies import BUILT_IN_COUNT, graphs_using
from fdcad.core.document.model import Document
from fdcad.core.equations.engine import cells
from fdcad.core.equations.orphans import _text_fields
from fdcad.core.units.expressions import references


@dataclass
class Unused:
    """What Purge Unused offers, in tree order."""

    sketches: list[str] = field(default_factory=list)  # feature ids
    suppressed: list[str] = field(default_factory=list)  # feature ids
    variables: list[str] = field(default_factory=list)  # variable names

    def empty(self) -> bool:
        """True when there is nothing to purge."""
        return not (self.sketches or self.suppressed or self.variables)


def _built_in(doc: Document) -> set[str]:
    return {f.id for f in doc.features[:BUILT_IN_COUNT]}


def unused_variables(doc: Document) -> list[str]:
    """Global variables nothing uses, directly or through a used variable."""
    names = {v.name for v in doc.variables}
    if not names:
        return []
    every = cells(doc)
    used: set[str] = set()
    for cell in every:
        if cell.section != "variable":
            used |= references(cell.expr) & names
    found: set[str] = set()
    for feature in doc.features:
        _text_fields(feature.data, found)
    used |= found & names
    var_refs = {c.name: references(c.expr) & names for c in every if c.section == "variable"}
    queue = list(used)
    while queue:  # a variable a used variable needs is used too
        name = queue.pop()
        for ref in var_refs.get(name, set()):
            if ref not in used:
                used.add(ref)
                queue.append(ref)
    return [v.name for v in doc.variables if v.name not in used]


def find_unused(doc: Document) -> Unused:
    """Everything Purge Unused offers."""
    built_in = _built_in(doc)
    out = Unused()
    for feature in doc.features:
        if feature.id in built_in:
            continue
        if feature.suppressed:
            out.suppressed.append(feature.id)
        elif (
            feature.type == "sketch"
            and not rollback.dependents(doc, feature.id)
            and not graphs_using(doc, feature.id)
        ):
            out.sketches.append(feature.id)
    out.variables = unused_variables(doc)
    return out


def features_to_delete(doc: Document, fids: list[str]) -> list[str]:
    """``fids`` with every feature built on them, in reverse tree order (the order to
    delete them in). Built in features are never included."""
    built_in = _built_in(doc)
    doomed = {f for f in fids if f not in built_in}
    for fid in list(doomed):
        doomed |= {f.id for f in rollback.dependents(doc, fid)}
    order = [f.id for f in doc.features]
    return sorted((f for f in doomed if f in order), key=order.index, reverse=True)


def below_bar(doc: Document) -> list[str]:
    """Features below the rollback bar, in reverse tree order (the order to delete)."""
    order = [f.id for f in doc.features]
    return sorted(rollback.rolled_back(doc), key=order.index, reverse=True)
