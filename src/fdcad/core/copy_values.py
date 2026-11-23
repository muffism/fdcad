"""Copy Values and Edit by Rule (TR160, D957).

Copy Values sets other features of the same kind to the values of one feature, for
example every hole to the size of the first. Only values are copied: picks
(faces, edges, sketches), names, the Boss or Cut choice and the body choices stay.
Edit by Rule finds the features of one kind whose number value passes a test (a
fillet radius under 2 mm) and sets that value on all of them. No Qt; the caller
makes one undo step from the changed copy.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

from fdcad.core.document.model import Document, Param, ParamValue

#: Values that say how a feature joins the part, not its size: never copied.
KEEP = frozenset({"operation", "merge", "bodies", "body", "keep_separate", "feature_scope"})
#: Comparisons Edit by Rule offers.
TESTS = ("<", "<=", "=", ">=", ">")
#: Two numbers closer than this are equal (mm or radians).
EQUAL = 1e-6


class CopyValuesError(ValueError):
    """The values cannot be copied or set; the message says what to do."""


def copyable(params: dict[str, ParamValue]) -> list[str]:
    """Names of the values Copy Values copies, in their order."""
    return [k for k in params if k not in KEEP]


def copy_values(doc: Document, source: str, targets: list[str]) -> list[str]:
    """Give each target the source's values. Returns the ids changed. Raises when a
    target is of another kind."""
    src = doc.feature(source)
    names = copyable(src.params)
    changed: list[str] = []
    for fid in dict.fromkeys(targets):
        if fid == source:
            continue
        target = doc.feature(fid)
        if target.type != src.type:
            raise CopyValuesError(
                f"{target.name} is not the same kind of feature as {src.name}. "
                f"Pick features of the same kind only."
            )
        before = copy.deepcopy(target.params)
        for name in names:
            target.params[name] = copy.deepcopy(src.params[name])
        if target.params != before:
            changed.append(fid)
    return changed


def number_params(doc: Document, ftype: str) -> list[str]:
    """Names of the number values features of ``ftype`` have, in first seen order."""
    out: dict[str, None] = {}
    for f in doc.features:
        if f.type == ftype:
            for name, value in f.params.items():
                if isinstance(value, Param) and name not in KEEP:
                    out.setdefault(name)
    return list(out)


def passes(value: float, test: str, limit: float) -> bool:
    """True when ``value`` passes ``test`` against ``limit``."""
    if test == "=":
        return abs(value - limit) <= EQUAL
    if test == "<":
        return value < limit - EQUAL
    if test == "<=":
        return value <= limit + EQUAL
    if test == ">":
        return value > limit + EQUAL
    if test == ">=":
        return value >= limit - EQUAL
    raise CopyValuesError(f"Unknown test '{test}'. Pick one of {', '.join(TESTS)}.")


@dataclass(frozen=True)
class Rule:
    """Features of ``ftype`` whose ``param`` passes ``test`` against ``limit``."""

    ftype: str
    param: str
    test: str
    limit: float


def find(doc: Document, rule: Rule) -> list[str]:
    """Ids of the features the rule finds, in tree order."""
    out: list[str] = []
    for f in doc.features:
        value = f.params.get(rule.param)
        typed = f.type == rule.ftype and isinstance(value, Param)
        if typed and passes(value.value, rule.test, rule.limit):  # type: ignore[union-attr]
            out.append(f.id)
    return out


def set_value(doc: Document, fids: list[str], param: str, value: Param) -> list[str]:
    """Set ``param`` of every feature in ``fids`` to ``value``. Returns the ids changed."""
    changed: list[str] = []
    for fid in fids:
        f = doc.feature(fid)
        if param in f.params and f.params[param] != value:
            f.params[param] = copy.deepcopy(value)
            changed.append(fid)
    return changed
