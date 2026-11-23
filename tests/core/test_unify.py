"""Face merge fallback (spec 2 section 19 item 2, audit E item 2, D704)."""

from __future__ import annotations

from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.features.solids import _unify
from fdcad.core.naming.names import NamedShape, faces_of
from fdcad.core.unify import unify_faces
from fdcad.samples.make import measure


def _cone(r0: float, z0: float, r1: float, z1: float) -> TopoDS_Shape:
    def ring(r: float, z: float):  # type: ignore[no-untyped-def]
        circle = gp_Circ(gp_Ax2(gp_Pnt(0, 0, z), gp_Dir(0, 0, 1)), r)
        return BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(circle).Edge()).Wire()

    loft = BRepOffsetAPI_ThruSections(True, True)
    loft.AddWire(ring(r0, z0))
    loft.AddWire(ring(r1, z1))
    loft.Build()
    return loft.Shape()


def _stacked_cones() -> TopoDS_Shape:
    """Two ruled cones of the same taper, stacked: the fuse is valid, but the kernel's
    face merge raises on it in this version."""
    fuse = BRepAlgoAPI_Fuse(_cone(10, 0, 7.5, 10), _cone(7.5, 10, 5, 20))
    fuse.SetFuzzyValue(1e-5)
    fuse.Build()
    shape = fuse.Shape()
    assert BRepCheck_Analyzer(shape).IsValid()
    return shape


def test_a_merge_that_raises_keeps_the_valid_unmerged_shape() -> None:
    shape = _stacked_cones()
    out, history = unify_faces(shape)
    assert history is None and out.IsSame(shape)
    named = _unify(NamedShape(shape, [("f9/a", f) for f in faces_of(shape)]), "f9")
    assert BRepCheck_Analyzer(named.shape).IsValid()
    assert len(named.faces) == len(faces_of(shape))


def test_a_normal_merge_still_merges() -> None:
    a = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
    b = BRepPrimAPI_MakeBox(gp_Pnt(10, 0, 0), 10, 10, 10).Shape()
    fuse = BRepAlgoAPI_Fuse(a, b)
    fuse.Build()
    out, history = unify_faces(fuse.Shape())
    assert history is not None
    assert measure(out)["faces"] == 6


def test_volume_sanity_bounds() -> None:
    """Spec 2 section 19 item 4 (D705): a boolean of the wrong size is an error."""
    from fdcad.core.features.solids import volume_sane

    a = BRepPrimAPI_MakeBox(10, 10, 10).Shape()  # 1000
    b = BRepPrimAPI_MakeBox(gp_Pnt(5, 0, 0), 10, 10, 10).Shape()  # 1000, half overlapping
    fused = BRepAlgoAPI_Fuse(a, b)
    fused.Build()
    assert volume_sane("boss", a, [b], fused.Shape())  # 1500
    assert not volume_sane("boss", a, [b], BRepPrimAPI_MakeBox(10, 10, 5).Shape())  # lost half
    assert not volume_sane("boss", a, [b], BRepPrimAPI_MakeBox(30, 10, 10).Shape())  # doubled
    small = BRepPrimAPI_MakeBox(10, 10, 9).Shape()
    assert not volume_sane("cut", a, [BRepPrimAPI_MakeBox(1, 1, 1).Shape()], small)
