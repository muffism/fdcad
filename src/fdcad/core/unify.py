"""Merging faces that lie on the same surface, with a fallback (spec 2 section 19
item 2, audit E item 2, DECISIONS D704).

After a boolean the kernel's face merge removes needless seams. In this kernel
version it can raise on a valid shape (two stacked cones of the same taper) or,
rarely, give an invalid one. Either way the unmerged shape is kept: it is valid,
only with extra seams. The check covers only the faces and edges the merge made,
so it stays cheap on large parts (PLAN.md section 11). No Qt.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.occ import ShapeMap


def _made(before: TopoDS_Shape, after: TopoDS_Shape) -> list[TopoDS_Shape]:
    """Faces and edges of ``after`` that are not in ``before``."""
    out: list[TopoDS_Shape] = []
    for kind in (TopAbs_FACE, TopAbs_EDGE):
        old = ShapeMap()
        TopExp.MapShapes_s(before, kind, old)
        explorer = TopExp_Explorer(after, kind)
        while explorer.More():
            item = explorer.Current()
            if not old.Contains(item):
                out.append(item)
            explorer.Next()
    return out


def _compound(shapes: list[TopoDS_Shape]) -> TopoDS_Shape:
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    builder, out = BRep_Builder(), TopoDS_Compound()
    builder.MakeCompound(out)
    for s in shapes:
        builder.Add(out, s)
    return out


def unify_faces(
    shape: TopoDS_Shape,
    keep: Iterable[TopoDS_Shape] = (),
    linear: float | None = None,
    angular: float | None = None,
    keep_map: Any | None = None,
) -> tuple[TopoDS_Shape, Any | None]:
    """``shape`` with faces on the same surface merged, and the merge history.

    ``keep`` lists edges and vertices the merge must leave; ``keep_map`` is a kernel
    map of more of them, for many at once (D2624). When the merge raises,
    gives nothing, or makes a face or edge that fails the kernel check, ``shape``
    comes back as it is with no history (names then need no carrying). ``linear`` (mm)
    and ``angular`` (radians) loosen what counts as the same surface (TR261).
    """
    try:
        maker = ShapeUpgrade_UnifySameDomain(shape, True, True, False)
        if linear is not None:
            maker.SetLinearTolerance(linear)
        if angular is not None:
            maker.SetAngularTolerance(angular)
        for item in keep:
            maker.KeepShape(item)
        if keep_map is not None:
            maker.KeepShapes(keep_map)
        maker.Build()
        merged = maker.Shape()
    except Exception:
        return shape, None
    if merged is None or merged.IsNull():
        return shape, None
    made = _made(shape, merged)
    if made:
        try:
            if not BRepCheck_Analyzer(_compound(made), True, True).IsValid():
                return shape, None
        except Exception:
            return shape, None
    return merged, maker.History()
