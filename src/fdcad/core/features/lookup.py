"""Reference lookups for the Phase 3 features, imported late.

``fdcad.core.naming.resolve`` imports the feature package, which imports the
Phase 3 features; importing ``resolve`` here only when a lookup runs breaks
that cycle.
"""

from __future__ import annotations

from typing import Any

from OCP.TopoDS import TopoDS_Edge, TopoDS_Face

from fdcad.core.features.base import Issue
from fdcad.core.naming.names import NamedShape


def resolve_face(
    body: NamedShape | None, ref: dict[str, Any], owner: str
) -> tuple[TopoDS_Face, list[Issue]]:
    """See ``fdcad.core.naming.resolve.resolve_face``."""
    from fdcad.core.naming import resolve

    return resolve.resolve_face(body, ref, owner)


def resolve_edge(
    body: NamedShape | None, ref: dict[str, Any], owner: str
) -> tuple[TopoDS_Edge, list[Issue]]:
    """See ``fdcad.core.naming.resolve.resolve_edge``."""
    from fdcad.core.naming import resolve

    return resolve.resolve_edge(body, ref, owner)


def resolve_vertex(
    body: NamedShape | None, ref: dict[str, Any], owner: str
) -> tuple[tuple[float, float, float], list[Issue]]:
    """See ``fdcad.core.naming.resolve.resolve_vertex``."""
    from fdcad.core.naming import resolve

    return resolve.resolve_vertex(body, ref, owner)
