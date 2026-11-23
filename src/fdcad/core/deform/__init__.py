"""Deformation features (PLAN Phase 4, PHASE4_SPEC P4.9): bend, twist, taper, stretch and
flow along curve. Importing this package registers the feature types.

No Qt here (CLAUDE.md rule 11); kernel work runs on the rebuild worker.
"""

from fdcad.core.deform import bend, flow, local, stretch, taper, twist

TYPES = ("bend", "twist", "taper", "stretch", "flow")
#: Local modes that move part of a body, without the triad (TR67, D2412).
LOCAL_TYPES = ("deform_point", "deform_curve", "surface_push")

__all__ = ["LOCAL_TYPES", "TYPES", "bend", "flow", "local", "stretch", "taper", "twist"]
