"""Phase 4 feature commands and the values a new Phase 4 feature starts with.

Kept apart from ``window.py`` and ``new_feature.py`` so parallel work does not clash.
"""

from __future__ import annotations

from typing import Any

from fdcad.core.document.model import Document
from fdcad.core.rebuild.engine import RebuildReport

#: Command id, feature type and operation of each Phase 4 feature command.
PHASE4_INSERTS: tuple[tuple[str, str, str], ...] = (
    ("feature.hole", "hole", "boss"),
    ("feature.cosmetic_thread", "cosmetic_thread", "boss"),
    ("feature.modeled_thread", "modeled_thread", "boss"),
    ("feature.mounting_boss", "mounting_boss", "boss"),
    ("feature.snap_hook", "snap_hook", "boss"),
    ("feature.snap_groove", "snap_groove", "boss"),
    ("feature.lip_groove", "lip_groove", "boss"),
    ("feature.vent", "vent", "boss"),
    ("feature.rib", "rib", "boss"),
    ("feature.dome", "dome", "boss"),
    ("feature.corner_relief", "corner_relief", "boss"),  # TR244
    ("feature.wrap", "wrap", "boss"),
)


def phase4_defaults(doc: Document, ftype: str) -> dict[str, Any]:
    """Parameters of a new Phase 4 feature, or an empty dict for other types."""
    if ftype == "hole":
        from fdcad.ui.property_panel.forms.hole_form import hole_defaults

        return hole_defaults(doc.units)
    if ftype == "cosmetic_thread":
        from fdcad.ui.property_panel.forms.thread_forms import thread_defaults

        return thread_defaults(doc.units)
    if ftype == "modeled_thread":
        from fdcad.ui.property_panel.forms.thread_forms import modeled_defaults

        return modeled_defaults(doc.units)
    if ftype == "rib":
        from fdcad.ui.property_panel.forms.shape_forms import rib_defaults

        return rib_defaults(doc.units)
    if ftype == "dome":
        from fdcad.ui.property_panel.forms.shape_forms import dome_defaults

        return dome_defaults(doc.units)
    if ftype == "corner_relief":
        from fdcad.ui.property_panel.forms.shape_forms import relief_defaults

        return relief_defaults(doc.units)
    if ftype == "wrap":
        from fdcad.ui.property_panel.forms.shape_forms import wrap_defaults

        return wrap_defaults(doc.units)
    from fdcad.ui.property_panel.forms.fastening_forms import fastening_defaults

    return fastening_defaults(ftype, doc.units)


def thread_marks(doc: Document, report: RebuildReport) -> list[Any]:
    """Cosmetic thread marks of every built, unsuppressed feature (P4.2)."""
    live = {f.id for f in doc.features if not f.suppressed}
    return [m for fid, r in report.results.items() if fid in live for m in r.threads]


def thread_notes(doc: Document, report: RebuildReport) -> list[str]:
    """STEP description lines for the cosmetic threads (D314)."""
    from fdcad.core.features.cosmetic_thread import step_notes

    return step_notes(thread_marks(doc, report))
