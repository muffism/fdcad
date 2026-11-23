"""One shot rebuild, for tests and scripts. The app keeps a RebuildEngine for reuse."""

from __future__ import annotations

from collections.abc import Callable

from fdcad.core.document.model import Document
from fdcad.core.features.base import FeatureResult
from fdcad.core.rebuild.engine import RebuildEngine, document_variables

__all__ = ["document_variables", "rebuild"]


def rebuild(
    doc: Document, cancelled: Callable[[], bool] = lambda: False
) -> dict[str, FeatureResult]:
    """Build every feature from scratch. Returns results by feature id."""
    return RebuildEngine().rebuild(doc, cancelled=cancelled).results
