"""Display meshes, made on the rebuild thread or in the rebuild helper (D2600), never on
the UI thread (CLAUDE.md rule 2).

Mesh fineness scales with the model size (PLAN 11.3 item 5) and the part's display
quality (TR214, D1605): 1 (coarse) to 10 (fine), 5 being the old fineness.
"""

from __future__ import annotations

from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.features.solids import bounding_size

#: Display deviation as a fraction of the model size, and the angle in radians.
RELATIVE_DEVIATION = 0.0005
DISPLAY_ANGLE = 0.35
MIN_DEVIATION = 0.001  # mm


#: Display quality range and the default (the fineness used before TR214).
QUALITY_MIN, QUALITY_MAX, QUALITY_DEFAULT = 1, 10, 5


def quality_factor(quality: int) -> float:
    """How much coarser than the default a quality draws: 2 per 1.5 steps, 1 at 5."""
    q = max(QUALITY_MIN, min(QUALITY_MAX, int(quality)))
    return float(2.0 ** ((QUALITY_DEFAULT - q) / 1.5))


def deviation_for(size: float, quality: int = QUALITY_DEFAULT) -> float:
    """Chord deviation in mm for a model ``size`` (its box diagonal) at a quality."""
    return max(size * RELATIVE_DEVIATION * quality_factor(quality), MIN_DEVIATION)


def angle_for(quality: int = QUALITY_DEFAULT) -> float:
    """Angular deviation in radians at a quality, kept between 0.05 and 0.6."""
    return max(0.05, min(0.6, DISPLAY_ANGLE * quality_factor(quality)))


def display_deviation(shape: TopoDS_Shape, quality: int = QUALITY_DEFAULT) -> float:
    """Chord deviation for the display mesh of ``shape``, in mm."""
    return deviation_for(bounding_size(shape), quality)


def mesh_for_display(
    shape: TopoDS_Shape, quality: int = QUALITY_DEFAULT, coarser: bool = False
) -> None:
    """Triangulate ``shape`` in place. Faces that already have a fine enough mesh are
    kept, so with ``coarser`` (the quality went down) the old meshes are removed first."""
    if coarser:
        from OCP.BRepTools import BRepTools

        BRepTools.Clean_s(shape)
    BRepMesh_IncrementalMesh(
        shape, display_deviation(shape, quality), False, angle_for(quality), True
    )
