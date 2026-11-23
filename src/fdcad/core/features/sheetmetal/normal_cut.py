"""Normal cut (TUTORIAL_REVIEW_SPEC TR12.2, DECISIONS D700): an extruded cut in a sheet
metal part cuts square to the sheet.

For each wall, the cut tool is met with the wall's middle plane; that outline is cut
straight through the wall's thickness. The cut faces are then square to the sheet
when folded and flat, and the holes are part of the sheet model, so the flat pattern
and later sheet metal features see them. A tool that reaches a bend is left to the
plain cut, which the flat pattern takes in by wrapping it round the bend. No Qt.
"""

from __future__ import annotations

from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.gp import gp_Ax3, gp_Dir, gp_Pln, gp_Pnt, gp_Trsf, gp_Vec
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.features.sheetmetal.locate import bounds
from fdcad.core.features.sheetmetal.model import SheetModel, folded_bend, volume
from fdcad.core.features.solids import compound, transform
from fdcad.core.naming.names import NamedShape, faces_of
from fdcad.core.occ import BRepAlgoAPI_Common

#: How far past both faces of the sheet the square cut reaches, in mm.
_PAST = 1.0


def _wall_section(
    local_tool: NamedShape, lo: tuple[float, ...], hi: tuple[float, ...], t: float
) -> list[TopoDS_Shape]:
    """Faces where the tool meets the wall's middle plane (z = t / 2), in its frame."""
    margin = 1.0
    # The wall's own x and y, so the face limits below are the wall's coordinates.
    plane = gp_Pln(gp_Ax3(gp_Pnt(0.0, 0.0, t / 2), gp_Dir(0.0, 0.0, 1.0), gp_Dir(1.0, 0.0, 0.0)))
    face = BRepBuilderAPI_MakeFace(
        plane, lo[0] - margin, hi[0] + margin, lo[1] - margin, hi[1] + margin
    ).Face()
    common = BRepAlgoAPI_Common(local_tool.shape, face)
    common.Build()
    if not common.IsDone():
        return []
    out = []
    explorer = TopExp_Explorer(common.Shape(), TopAbs_FACE)
    while explorer.More():
        out.append(explorer.Current())
        explorer.Next()
    return out


def normal_cut(
    model: SheetModel, tool: NamedShape, fid: str
) -> tuple[SheetModel, NamedShape | None]:
    """The model with square cuts through the walls the tool meets, and the part of the
    tool that meets bends (cut as it is by the caller), or None."""
    t = model.thickness
    places = model.placements(False)
    made = 0
    for wid, wall in model.walls.items():
        if wid not in places:
            continue
        local = transform(tool, places[wid].Inverted())
        lo, hi = bounds(model.piece(wid))
        sections = _wall_section(local, lo, hi, t)
        for section in sections:
            down = gp_Trsf()
            down.SetTranslation(gp_Vec(0.0, 0.0, -t / 2 - _PAST))
            moved = BRepBuilderAPI_Transform(section, down, True).Shape()
            prism = BRepPrimAPI_MakePrism(moved, gp_Vec(0.0, 0.0, t + 2 * _PAST))
            prism.Build()
            if not prism.IsDone():
                continue
            made += 1
            shape = prism.Shape()
            names = [(f"{fid}/normal{made}/face{i}", f) for i, f in enumerate(faces_of(shape))]
            wall.cuts.append(NamedShape(shape, names))
    bends = []
    for bend in model.bends.values():
        if bend.parent in places and bend.bid not in model.unfolded:
            bends.append(transform(folded_bend(bend, t), places[bend.parent]).shape)
    leftover = None
    if bends:
        common = BRepAlgoAPI_Common(tool.shape, compound(bends))
        common.Build()
        if common.IsDone() and volume(common.Shape()) > 1e-9:
            leftover = NamedShape(common.Shape(), [])
    return model, leftover
