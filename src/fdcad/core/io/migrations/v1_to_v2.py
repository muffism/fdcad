"""Schema 1 to schema 2 (FDEF_SPEC 9 and 15, DECISIONS D391).

Schema 2 adds node graphs (FDEF_SPEC 12A, D370): a schema 1 part has none. It
also changes the configurations block (D391): each configuration's ``suppressed``
list becomes ``<feature id>.suppressed`` overrides, and overrides may hold any
feature value (parameter objects, strings, booleans, numbers). Nothing else
changes. Works on raw JSON data only; never runs code.
"""

from __future__ import annotations

from typing import Any

from fdcad.core.configurations import migrate_suppressed_lists


def migrate_1_to_2(data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade raw schema 1 data. The caller sets ``schema`` to 2."""
    out = dict(data)
    out.setdefault("graphs", [])
    if "configurations" in out:
        out["configurations"] = migrate_suppressed_lists(out["configurations"])
    return out
