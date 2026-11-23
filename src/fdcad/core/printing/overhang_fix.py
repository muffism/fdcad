"""Fix overhangs from the analysis (TUTORIAL_REVIEW_SPEC_2 TR410, DECISIONS D909).

Flat faces that face straight down, other than the face on the bed, print over thin
air. :func:`underside_faces` finds them for the print orientation's build direction;
:func:`overhang_chamfer` makes one ordinary Chamfer feature on their edges (45
degrees, which prints without support), for the user to confirm, edit or undo.
:func:`rounded_overhangs` names fillet faces among the overhanging faces, since a
chamfer prints better there. No Qt; the face search is kernel work.
"""

from __future__ import annotations

import re
from typing import Any

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.units import UnitSystem

NAME = "Overhang Chamfer"
DEFAULT_SIZE = 1.0
#: A face counts as facing down within this (the cosine of about 1 degree).
DOWN = 0.9998


def underside_faces(named: Any, up: tuple[float, float, float]) -> list[Any]:
    """Flat faces facing down, except those at the lowest height (the bed)."""
    from fdcad.core.naming.names import centroid, faces_of
    from fdcad.core.plane_normal import plane_normal

    faces = faces_of(named.shape)
    heights = [sum(c * u for c, u in zip(centroid(f), up, strict=True)) for f in faces]
    lowest = min(heights) if heights else 0.0
    out = []
    for face, height in zip(faces, heights, strict=True):
        n = plane_normal(face)
        if n is None or sum(a * b for a, b in zip(n, up, strict=True)) > -DOWN:
            continue
        if height <= lowest + 1e-6:
            continue  # on the bed
        out.append(face)
    return out


def overhang_chamfer(doc: Document, face_refs: list[dict[str, Any]], size_mm: float) -> Feature:
    """One Chamfer on every edge of the given faces, not yet in ``doc``."""
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
        refs={"faces": [dict(r) for r in face_refs]},
    )


def rounded_overhangs(doc: Document, named: Any, faces: list[Any]) -> int:
    """How many of ``faces`` were made by a fillet."""
    fillets = {f.id for f in doc.features if f.type == "fillet"}
    count = 0
    for face in faces:
        name = next((n for n, f in named.faces if f.IsSame(face)), "")
        if name.split("/", 1)[0] in fillets:
            count += 1
    return count
