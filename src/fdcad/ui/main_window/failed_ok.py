"""OK does not finish a feature that fails to build (D2876).

The owner asked that a feature such as a fillet that cannot be built must not close
its command as if it worked. OK still applies the feature as one undoable command, so
the rebuild works it out off the UI thread as always. When that rebuild reports the
feature as an error, the command is undone and the panel opens again with the values
as they were at OK and the error above them. The user can change a value and press OK
again, or press Cancel.
"""

from __future__ import annotations

import contextlib
from typing import Any

from fdcad.core.features.base import FeatureState
from fdcad.ui import strings


def failure(report: Any, fid: str) -> str | None:
    """The error message of feature ``fid`` in ``report``, or None when it built."""
    results = getattr(report, "results", None) or {}
    result = results.get(fid)
    if result is None:
        return None
    for issue in result.issues:
        if issue.state is FeatureState.ERROR:
            return str(issue.message)
    return None


def watch(window: Any) -> None:
    """Check the build of what the panel's OK just applied, once, when the part has
    been rebuilt."""
    panel = window.panel
    applied = getattr(panel, "last_ok", None) if panel is not None else None
    if applied is None:
        return
    panel.last_ok = None
    session = applied.session

    def rebuilt(report: object) -> None:
        with contextlib.suppress(RuntimeError, TypeError):
            session.rebuilt.disconnect(rebuilt)
        message = failure(report, applied.feature.id)
        if message is None or session.undo.index() != applied.after:
            return  # it built, or something else changed the part since
        while session.undo.index() > applied.before:
            session.undo.undo()
        reopen(window, applied, message)

    session.rebuilt.connect(rebuilt)


def reopen(window: Any, applied: Any, message: str) -> None:
    """Open the panel again on the feature as OK applied it, with its error."""
    panel = window.panel
    if panel is None:
        return
    if panel.is_editing:
        panel.reject()  # a command started since (the pin): the failed one comes first
    panel.begin(applied.session, applied.feature, is_new=applied.is_new)
    window._left_tab(1)
    panel.message.setText(strings.OK_NOT_APPLIED.format(name=applied.feature.name, error=message))
