"""3D edges of a finished sketch, for showing it in the viewport (C1, W5.2).

Run off the UI thread with the rebuild (CLAUDE.md rule 2).
"""

from __future__ import annotations

from OCP.BRep import BRep_Builder
from OCP.Standard import Standard_Failure
from OCP.TopoDS import TopoDS_Compound, TopoDS_Shape

from fdcad.core.sketch.model import Point, Sketch
from fdcad.core.sketch.profiles import ProfileError, SketchPlane, _EdgeMaker


def line_edges(sketch: Sketch, plane: SketchPlane) -> dict[str, TopoDS_Shape]:
    """Each line of ``sketch`` as a 3D edge, by entity id (revolve axis picking, W6.3)."""
    from fdcad.core.sketch.model import Line

    maker = _EdgeMaker(sketch, plane)
    out: dict[str, TopoDS_Shape] = {}
    for ent in sketch.entities.values():
        if isinstance(ent, Line):
            try:
                out[ent.id] = maker.edge(ent.id)
            except (ProfileError, Standard_Failure, KeyError, ValueError):
                continue
    return out


def sketch_edges(
    sketch: Sketch, plane: SketchPlane, construction: bool = True
) -> TopoDS_Shape | None:
    """Every curve of ``sketch`` as one compound of 3D edges, or None when it has none.

    Curves that cannot be made (too small) are left out. With ``construction`` off,
    construction curves are left out too; with it on, construction points are added
    as vertices (TR339, D1703).
    """
    maker = _EdgeMaker(sketch, plane)
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    count = 0
    for ent in sketch.entities.values():
        if isinstance(ent, Point):
            if construction and ent.construction and not _is_handle(sketch, ent.id):
                builder.Add(compound, _vertex(plane, ent))
                count += 1
            continue
        if ent.construction and not construction:
            continue
        try:
            builder.Add(compound, maker.edge(ent.id))
        except (ProfileError, Standard_Failure, KeyError, ValueError):
            continue
        count += 1
    if sketch.texts:  # text outlines (P4.8), display only
        from OCP.TopAbs import TopAbs_EDGE
        from OCP.TopExp import TopExp_Explorer

        from fdcad.core.sketch.text import TextError, text_faces

        try:
            for face in text_faces(sketch, plane):
                explorer = TopExp_Explorer(face, TopAbs_EDGE)
                while explorer.More():
                    builder.Add(compound, explorer.Current())
                    count += 1
                    explorer.Next()
        except (TextError, Standard_Failure):
            pass
    return compound if count else None


def _vertex(plane: SketchPlane, p: Point) -> TopoDS_Shape:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex

    return BRepBuilderAPI_MakeVertex(plane.to_3d(p.x, p.y)).Vertex()


def _is_handle(sketch: Sketch, pid: str) -> bool:
    """True for a spline's tangent handle or a curve's own point (not a free point)."""
    from fdcad.core.sketch.model import entity_points

    return any(
        pid in entity_points(e) for e in sketch.entities.values() if not isinstance(e, Point)
    )


def construction_edges(sketch: Sketch, plane: SketchPlane) -> TopoDS_Shape | None:
    """The construction curves and free construction points of ``sketch`` as one
    compound, or None when it has none (TR339, D1703)."""
    maker = _EdgeMaker(sketch, plane)
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    count = 0
    for ent in sketch.entities.values():
        if not ent.construction:
            continue
        if isinstance(ent, Point):
            if not _is_handle(sketch, ent.id):
                builder.Add(compound, _vertex(plane, ent))
                count += 1
            continue
        try:
            builder.Add(compound, maker.edge(ent.id))
        except (ProfileError, Standard_Failure, KeyError, ValueError):
            continue
        count += 1
    return compound if count else None
