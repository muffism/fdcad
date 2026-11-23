"""Compare two bodies (TR27, DECISIONS D758).

Two solids are compared by cutting each from the other: what is left of the
first is the volume only the first has, and the other way round. Faces of the
first body that do not lie on the second are the faces that differ, found by
the faces of the leftover pieces: where a face of what only one body has lies
on a face of the first, that face differs. Kernel work, so
callers run it in a kernel job (CLAUDE.md 5.2). Never raises: a kernel failure
is a result with an error message (CLAUDE.md 5.7).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.BRepTools import BRepTools
from OCP.GProp import GProp_GProps
from OCP.TopoDS import TopoDS_Face, TopoDS_Shape

from fdcad.core.features.booleans import boolean_shape
from fdcad.core.features.solids import solids
from fdcad.core.naming.names import faces_of

#: Gaps smaller than this (mm) count as the same surface.
TOLERANCE = 1e-4
#: Differences smaller than this (mm3) count as none, after the kernel's fuzzy cuts.
VOLUME_NOISE = 1e-6


@dataclass
class Comparison:
    """What differs between a first and a second body."""

    only_first: float = 0.0  # mm3
    only_second: float = 0.0
    only_first_shape: TopoDS_Shape | None = None
    only_second_shape: TopoDS_Shape | None = None
    #: Faces of the first body that do not lie on the second.
    differing: list[TopoDS_Face] = field(default_factory=list)
    error: str = ""

    @property
    def same(self) -> bool:
        """True when nothing differs."""
        return not self.error and not self.differing and self.only_first == self.only_second == 0


def _volume(shape: TopoDS_Shape | None) -> float:
    if shape is None or not solids(shape):
        return 0.0
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    value = abs(props.Mass())
    return value if value > VOLUME_NOISE else 0.0


def _inside_point(face: TopoDS_Face) -> TopoDS_Shape:
    """A vertex at the middle of the face's parameter box, moved onto the face."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.gp import gp_Pnt2d
    from OCP.TopAbs import TopAbs_IN

    u0, u1, v0, v1 = BRepTools.UVBounds_s(face)
    surface = BRep_Tool.Surface_s(face)
    # The middle, or failing that a few points across the face, until one is inside it.
    for fu, fv in ((0.5, 0.5), (0.25, 0.25), (0.75, 0.75), (0.25, 0.75), (0.75, 0.25)):
        u, v = u0 + (u1 - u0) * fu, v0 + (v1 - v0) * fv
        if BRepClass_FaceClassifier(face, gp_Pnt2d(u, v), 1e-7).State() == TopAbs_IN:
            return BRepBuilderAPI_MakeVertex(surface.Value(u, v)).Vertex()
    return BRepBuilderAPI_MakeVertex(surface.Value((u0 + u1) / 2, (v0 + v1) / 2)).Vertex()


def _off(point: TopoDS_Shape, other: TopoDS_Shape) -> bool:
    dist = BRepExtrema_DistShapeShape(point, other)
    return not dist.IsDone() or dist.Value() > TOLERANCE


def differing_faces(first: TopoDS_Shape, pieces: list[TopoDS_Shape | None]) -> list[TopoDS_Face]:
    """Faces of ``first`` that a face of a leftover piece lies on: there the bodies
    differ. A face that only partly differs counts, unlike a test at its middle."""
    marks = [_inside_point(f) for piece in pieces if piece is not None for f in faces_of(piece)]
    return [face for face in faces_of(first) if any(not _off(m, face) for m in marks)]


def compare(first: TopoDS_Shape, second: TopoDS_Shape) -> Comparison:
    """Compare two bodies (see the module notes)."""
    try:
        a_only = boolean_shape("cut", first, second)
        b_only = boolean_shape("cut", second, first)
        if a_only is None or b_only is None:
            return Comparison(
                error="the kernel could not cut one body from the other. "
                "Check both bodies with Geometry Check, then compare again."
            )
        out = Comparison(_volume(a_only), _volume(b_only), a_only, b_only)
        out.differing = differing_faces(first, [a_only, b_only])
        return out
    except Exception as exc:  # never let a kernel error escape (CLAUDE.md 5.7)
        return Comparison(error=f"the comparison failed ({type(exc).__name__}). Compare again.")
