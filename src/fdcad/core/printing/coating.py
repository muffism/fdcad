"""Coating allowance (TR307, DECISIONS D1214).

A part can keep a coating thickness (paint, powder coat, anodising, a resin dip)
in its print setup under ``coating``. Export of meshes for printing then moves
every face of every body inward by that thickness, so holes come out larger and
pins smaller by the coating, and the coated part ends up at its modelled size.
The model is never changed; Offset Body inward does the same as a feature.
Kernel work: run it off the UI thread.
"""

from __future__ import annotations

from typing import Any

from OCP.TopoDS import TopoDS_Shape

COATING = "coating"
#: The thickest coating allowed, in mm.
LIMIT = 5.0
_TOL = 1e-7


def thickness(print_setup: Any) -> float:
    """The kept coating thickness in mm, 0 for none or a damaged value."""
    raw = print_setup.get(COATING) if isinstance(print_setup, dict) else None
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        return 0.0
    return float(raw) if 0 < raw <= LIMIT else 0.0


def allowed(
    shape: TopoDS_Shape, coat: float, faces: list[tuple[Any, str]] | None = None
) -> tuple[TopoDS_Shape, list[tuple[Any, str]] | None]:
    """``shape`` with every body shrunk by ``coat`` mm, and ``faces`` (face, colour)
    moved onto the new faces. Raises ValueError when a body is thinner than twice the
    coating."""
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepOffset import BRepOffset_MakeOffset, BRepOffset_Skin
    from OCP.GeomAbs import GeomAbs_Intersection
    from OCP.Message import Message_ProgressRange
    from OCP.TopAbs import TopAbs_FACE

    from fdcad.core.features.solids import compound, solids
    from fdcad.core.occ import shape_list

    if coat <= 0:
        return shape, faces
    bodies = solids(shape) or [shape]
    made_bodies = []
    moved: list[tuple[Any, str]] = []
    for body in bodies:
        maker = BRepOffset_MakeOffset()
        maker.Initialize(
            body, -coat, _TOL, BRepOffset_Skin, False, False, GeomAbs_Intersection, False
        )
        try:
            maker.MakeOffsetShape(Message_ProgressRange())
            done = maker.IsDone() and not maker.Shape().IsNull()
        except Exception:  # a kernel failure is a plain error for the export
            done = False
        made = maker.Shape() if done else None
        if made is None or not solids(made) or not BRepCheck_Analyzer(made).IsValid():
            raise ValueError("a body could not take the coating allowance")
        made_bodies.append(solids(made)[0])
        for face, colour in faces or []:
            for new in shape_list(maker.Generated(face)):
                if new.ShapeType() == TopAbs_FACE:
                    moved.append((new, colour))
    out = made_bodies[0] if len(made_bodies) == 1 else compound(made_bodies)
    return out, (moved if faces is not None else None)
