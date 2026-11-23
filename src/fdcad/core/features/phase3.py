"""Imports the Phase 3 feature types so they register (one module per type)."""

from fdcad.core.features import (
    circular_pattern,
    combine,
    delete_body,
    delete_face,
    intersect,
    linear_pattern,
    mirror,
    move_copy_body,
    move_face,
    scale,
    sketch_pattern,
    split,
)

__all__ = [
    "circular_pattern",
    "combine",
    "delete_body",
    "delete_face",
    "intersect",
    "linear_pattern",
    "mirror",
    "move_copy_body",
    "move_face",
    "scale",
    "sketch_pattern",
    "split",
]
