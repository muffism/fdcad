"""Mirror Part to a new file (TUTORIAL_REVIEW_SPEC TR73, DECISIONS D899).

The opposite hand of a part: its finished bodies mirrored about the Right plane (the
YZ plane, so left becomes right), held in a new part as an embedded STEP import. The
original part is not changed. No Qt; kernel work, so run it off the UI thread.
"""

from __future__ import annotations

from typing import Any

from fdcad.core.document.model import Document
from fdcad.core.units import UnitSystem

#: Mirror planes by name: the normal of each.
PLANES = {"right": (1.0, 0.0, 0.0), "top": (0.0, 1.0, 0.0), "front": (0.0, 0.0, 1.0)}


def mirrored_shape(shape: Any, plane: str = "right") -> Any:
    """``shape`` mirrored about a main plane through the origin."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf

    trsf = gp_Trsf()
    trsf.SetMirror(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(*PLANES[plane])))
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()


def mirrored_document(shape: Any, units: UnitSystem, name: str, plane: str = "right") -> Document:
    """A new part holding ``shape`` mirrored, as one embedded STEP import."""
    from fdcad.core.features.import_step import part_from_step
    from fdcad.core.io.save_bodies import step_bytes

    data = step_bytes(mirrored_shape(shape, plane))
    return part_from_step(f"{name} (mirrored).step", data, units)
