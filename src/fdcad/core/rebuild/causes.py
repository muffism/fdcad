"""Show the cause of an error (TR288, DECISIONS D773).

When a feature fails because a face it used is gone, the error names the earlier
feature that took the face away, and gets a Show Cause button. The cause is
found from the rebuild's own results: the face name (``f6/cap/end``) was made by
the feature its name starts with; walking the built features in order, the
cause is the first one after the last body that still had the name. When the
making feature itself failed or is suppressed, that feature is the cause.
Pure Python over the results (no kernel calls).
"""

from __future__ import annotations

import re
from dataclasses import replace

from fdcad.core.document.model import Document, Feature
from fdcad.core.features.base import FeatureResult, FeatureState, Fix, Issue

#: The fix action that selects the cause in the tree.
SHOW_CAUSE = "show_cause"
_FEATURE = re.compile(r"^(f\d+)/")


def _has(result: FeatureResult | None, name: str) -> bool:
    body = result.body if result is not None else None
    return body is not None and any(n == name for n, _f in body.faces)


def cause_of(
    doc: Document, active: list[Feature], index: int, results: dict[str, FeatureResult], name: str
) -> str | None:
    """The id of the earlier feature that took ``name`` away before ``active[index]``."""
    match = _FEATURE.match(name)
    owner = match.group(1) if match else None
    if owner is None:
        return None
    known = {f.id for f in doc.features}
    if owner not in known:
        return None  # deleted: the error already says to reselect
    owner_result = results.get(owner)
    if owner_result is None or owner_result.state is FeatureState.ERROR:
        return owner
    for wanted in _lineage(name):
        last = None
        for i in range(index):
            if _has(results.get(active[i].id), wanted):
                last = i
        if last is None:
            continue
        for i in range(last + 1, index):
            result = results.get(active[i].id)
            if result is not None and result.body is not None and not _has(result, wanted):
                return active[i].id
        return None  # the face the piece was cut from is still there: nothing took it (D2637)
    return owner  # the making feature no longer makes it (its sketch or values changed)


_PIECE = re.compile(r"#\d+$")


def _lineage(name: str) -> list[str]:
    """``name``, then the faces it is a split piece of (``f6/cap/end#1#2``, then
    ``f6/cap/end#1`` and ``f6/cap/end``): a piece that is no longer split off was not
    taken away by any feature, while the face it came from is still there (D2637)."""
    out = [name]
    while _PIECE.search(out[-1]):
        out.append(_PIECE.sub("", out[-1]))
    return out


def add_causes(doc: Document, active: list[Feature], results: dict[str, FeatureResult]) -> None:
    """Name the cause in every missing reference error, with a Show Cause fix."""
    for index, feature in enumerate(active):
        result = results.get(feature.id)
        if result is None or result.state is not FeatureState.ERROR:
            continue
        issues: list[Issue] = []
        changed = False
        for issue in result.issues:
            if issue.state is FeatureState.ERROR and "missing reference" in issue.message:
                cause = next(
                    (c for n in issue.highlight if (c := cause_of(doc, active, index, results, n))),
                    None,
                )
                if cause is not None and cause != feature.id:
                    name = doc.feature(cause).name
                    named = name in issue.message  # "X has an error. Fix X first." says it
                    issue = replace(
                        issue,
                        message=issue.message
                        if named
                        else f"{issue.message} It was lost at {name}.",
                        fixes=[
                            *issue.fixes,
                            Fix(f"Show Cause: {name}", SHOW_CAUSE, {"feature": cause}),
                        ],
                        code=issue.code or "missing_reference",
                    )
                    changed = True
            issues.append(issue)
        if changed:
            results[feature.id] = replace(result, issues=issues)


def cause_in(issue: Issue) -> str | None:
    """The cause feature id an issue names, for sorting the errors list."""
    return next((str(f.data["feature"]) for f in issue.fixes if f.action == SHOW_CAUSE), None)
