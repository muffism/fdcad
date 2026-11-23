"""Bed edge chamfer (TR177, DECISIONS D779).

One ordinary Chamfer feature on every edge of the face that sits on the printer
bed, hole edges included, by a small size, so the first layers do not spread
past the model (the "elephant foot"). The bed face is the print orientation's
face, or a picked flat face. Pure Python: it only builds the feature.
"""

from __future__ import annotations

import re
from typing import Any

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.units import UnitSystem

#: The size offered, in mm (about one first layer's spread).
DEFAULT_SIZE = 0.4
NAME = "Bed Chamfer"


def bed_chamfer(doc: Document, face_ref: dict[str, Any], size_mm: float) -> Feature:
    """A Chamfer on every edge of ``face_ref``, not yet in ``doc``. Raises ValueError for a
    size that is not more than 0."""
    if not size_mm > 0:
        raise ValueError("the chamfer size must be more than 0. Type a size.")
    used = [int(m.group(1)) for f in doc.features if (m := re.fullmatch(rf"{NAME} (\d+)", f.name))]
    typed = f"{size_mm / 25.4:.6g}in" if doc.units is UnitSystem.IN else f"{size_mm:.6g}mm"
    return Feature(
        doc.new_feature_id(),
        "chamfer",
        f"{NAME} {max(used, default=0) + 1}",
        params={
            "chamfer_type": "distance_distance",
            "method": "symmetric",
            "distance": Param(typed, size_mm),
        },
        refs={"faces": [dict(face_ref)]},
    )
