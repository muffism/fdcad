"""Draft analysis and the draft assistant (PHASE2_SPEC P2.7 item 4, DECISIONS D522).

Every face is sorted by its draft from a pull direction: the angle between the
surface and the pull, positive where the outward normal leans toward the pull.
The part is triangulated once and every triangle is tested in one numpy pass
(CLAUDE.md 5A rule 2), as the overhang analysis does.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane
from OCP.TopoDS import TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import BuildContext, FeatureError
from fdcad.core.printing.overhang import PARTIAL_SHARE, triangles_by_face

Vec3 = tuple[float, float, float]

POSITIVE = "positive"
NEGATIVE = "negative"
NEEDS = "needs"
STRADDLE = "straddle"
#: Groups in legend order.
GROUPS = (POSITIVE, NEGATIVE, NEEDS, STRADDLE)


@dataclass(frozen=True)
class FaceDraft:
    """The share of a face's area in each draft group."""

    face: TopoDS_Face
    positive: float
    negative: float
    needs: float
    area: float

    @property
    def group(self) -> str:
        """Straddle when the face has both positive and negative draft, else its largest group."""
        if self.positive >= PARTIAL_SHARE and self.negative >= PARTIAL_SHARE:
            return STRADDLE
        shares = {POSITIVE: self.positive, NEGATIVE: self.negative, NEEDS: self.needs}
        return max(shares, key=lambda k: shares[k])


def draft_faces(shape: TopoDS_Shape, pull: Vec3, angle: float) -> list[FaceDraft]:
    """Every face of ``shape`` with its draft shares from ``pull`` and the minimum ``angle``
    (radians). Kernel work (meshing): worker only."""
    faces, corners, owner = triangles_by_face(shape)
    if len(faces) == 0:
        return []
    d = np.asarray(pull, dtype=np.float64)
    d /= np.linalg.norm(d)
    if len(corners) == 0:
        return [FaceDraft(f, 0.0, 0.0, 0.0, 0.0) for f in faces]
    cross = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    doubled = np.linalg.norm(cross, axis=1)
    keep = doubled > 1e-15
    area = np.where(keep, doubled / 2, 0.0)
    sine = np.zeros(len(cross))
    sine[keep] = (cross[keep] @ d) / doubled[keep]
    limit = math.sin(angle) - 1e-9
    count = len(faces)
    face_area = np.bincount(owner, weights=area, minlength=count)

    def share(mask: np.ndarray) -> np.ndarray:
        part = np.bincount(owner, weights=area * mask, minlength=count)
        return np.divide(part, face_area, out=np.zeros_like(part), where=face_area > 0)

    pos = share(sine >= limit)
    neg = share(sine <= -limit)
    needs = share(np.abs(sine) < limit)
    return [
        FaceDraft(f, float(pos[i]), float(neg[i]), float(needs[i]), float(face_area[i]))
        for i, f in enumerate(faces)
    ]


def can_tilt(face: TopoDS_Face) -> bool:
    """True for the face kinds the kernel's draft can tilt: flat, cylindrical, conical."""
    return BRepAdaptor_Surface(face).GetType() in (GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone)


def faces_needing_draft(shape: TopoDS_Shape, pull: Vec3, angle: float) -> list[TopoDS_Face]:
    """Faces whose draft from ``pull`` is mostly smaller than ``angle``, for the draft
    assistant. Only faces the kernel can tilt are returned. Worker only."""
    return [
        f.face for f in draft_faces(shape, pull, angle) if f.group == NEEDS and can_tilt(f.face)
    ]


def assistant_faces(feature: Feature, ctx: BuildContext) -> list[TopoDS_Face]:
    """The draft assistant: faces of the part before ``feature`` that need draft from its
    neutral plane's pull at its draft angle. Worker only."""
    from fdcad.core.features.draft import neutral_plane

    if ctx.body is None:
        raise FeatureError(f"{feature.name}: there is no part to draft. Add a feature first.")
    angle = feature.params.get("angle")
    if not isinstance(angle, Param) or angle.value <= 0:
        raise FeatureError(f"{feature.name}: enter a draft angle first.")
    _point, pull, _issues = neutral_plane(feature, ctx)
    return faces_needing_draft(ctx.body.shape, pull, angle.value)
