"""Overhang analysis (PLAN Phase 2, DECISIONS D354): which faces are steeper than the
printer profile's overhang angle, measured from the build direction.

The part is triangulated once and every triangle is tested in one numpy pass
(CLAUDE.md 5A rule 2). Triangles come from the kernel as one binary STL; the
kernel writes faces in explorer order, so the triangle count of each face says
which face a triangle belongs to.
"""

from __future__ import annotations

import math
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.StlAPI import StlAPI_Writer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS_Face, TopoDS_Shape

from fdcad.core.features.solids import bounding_size
from fdcad.core.printing.orientation import Vec3, faces_of

#: Same mesh fineness as the display mesh, so the shown part's mesh is reused.
RELATIVE_DEVIATION = 0.0005
MIN_DEVIATION = 0.001
MESH_ANGLE = 0.35
#: A face counts as overhanging when at least this share of its area does.
FULL_SHARE = 0.9
#: Below this share a face is not marked at all (rounding at its edges).
PARTIAL_SHARE = 0.02
_STL = np.dtype([("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attr", "<u2")])


@dataclass(frozen=True)
class FaceOverhang:
    """One face that overhangs: the face, its overhanging share of area, and the area."""

    face: TopoDS_Face
    share: float
    area: float

    @property
    def full(self) -> bool:
        """True when (nearly) the whole face overhangs."""
        return self.share >= FULL_SHARE


def triangles_by_face(
    shape: TopoDS_Shape,
) -> tuple[list[TopoDS_Face], NDArray[np.float64], NDArray[np.int64]]:
    """Faces, the (n, 3, 3) triangle corners and the face index of each triangle.

    Kernel work (meshing): worker only. Also used by the wall thickness analysis.
    """
    deviation = max(bounding_size(shape) * RELATIVE_DEVIATION, MIN_DEVIATION)
    BRepMesh_IncrementalMesh(shape, deviation, False, MESH_ANGLE, True)
    faces = faces_of(shape)
    counts = []
    for face in faces:
        tri = BRep_Tool.Triangulation_s(face, TopLoc_Location())
        counts.append(0 if tri is None else tri.NbTriangles())
    writer = StlAPI_Writer()
    writer.ASCIIMode = False
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "overhang.stl"
        if not writer.Write(shape, str(path)):
            raise ValueError("The part could not be meshed. Rebuild it and try again.")
        data = path.read_bytes()
    total = int(np.frombuffer(data, dtype="<u4", count=1, offset=80)[0])
    if total != sum(counts):
        raise ValueError("The part's mesh is incomplete. Rebuild it and try again.")
    records = np.frombuffer(data, dtype=_STL, count=total, offset=84)
    corners = records["vertices"].astype(np.float64)
    owner = np.repeat(np.arange(len(faces), dtype=np.int64), counts)
    return faces, corners, owner


def overhangs(
    shape: TopoDS_Shape, build_direction: Vec3, angle: float, bed_tolerance: float = 1e-3
) -> list[FaceOverhang]:
    """Faces steeper than ``angle`` (radians, from the build direction), largest share first.

    A surface overhangs where its outward normal points down by more than
    ``sin(angle)`` along the build direction, that is where the surface leans
    more than ``angle`` away from the build direction. Surface lying on the bed
    (at the lowest height) is supported and never counts.
    """
    faces, corners, owner = triangles_by_face(shape)
    if len(corners) == 0:
        return []
    up = np.asarray(build_direction, dtype=np.float64)
    up /= np.linalg.norm(up)
    cross = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    doubled = np.linalg.norm(cross, axis=1)
    area = doubled / 2
    keep = doubled > 1e-15
    normal = np.zeros_like(cross)
    normal[keep] = cross[keep] / doubled[keep, None]
    heights = corners @ up  # (n, 3) height of every corner along the build direction
    on_bed = np.all(heights <= heights.min() + bed_tolerance, axis=1)
    steep = (normal @ up) < -math.sin(angle)
    hanging = steep & ~on_bed & keep
    face_area = np.bincount(owner, weights=area, minlength=len(faces))
    hang_area = np.bincount(owner, weights=area * hanging, minlength=len(faces))
    share = np.divide(hang_area, face_area, out=np.zeros_like(hang_area), where=face_area > 0)
    picked = np.nonzero(share >= PARTIAL_SHARE)[0]
    order = picked[np.argsort(-share[picked], kind="stable")]
    return [FaceOverhang(faces[i], float(share[i]), float(face_area[i])) for i in order]
