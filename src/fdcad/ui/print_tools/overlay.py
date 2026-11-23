"""Display only overlays of the print and evaluate tools in the 3D view.

Nothing here changes the part. Each tool owns one named layer of shapes, and
face colours are painted on the shown part and taken off again. Views without
a kernel window (the offscreen platform in tests) only record what was asked.
"""

from __future__ import annotations

from typing import Any


def _store(viewport: Any, name: str) -> dict[str, list[Any]]:
    found = getattr(viewport, name, None)
    if not isinstance(found, dict):
        found = {}
        setattr(viewport, name, found)
    return found


def show_layer(
    viewport: Any,
    name: str,
    shapes: list[Any],
    color: str,
    width: float = 2.0,
    shaded: bool = False,
) -> None:
    """Draw ``shapes`` as the overlay layer ``name``, replacing what it showed before."""
    layers: dict[str, list[Any]] = _store(viewport, "print_layers")
    items: dict[str, list[Any]] = _store(viewport, "print_layer_items")
    layers[name] = list(shapes)
    context = getattr(viewport, "_context", None)
    if context is None:
        return
    from OCP.AIS import AIS_Shape

    from fdcad.ui.viewport import look
    from fdcad.ui.viewport.widget import _hex

    for item in items.pop(name, []):
        context.Remove(item, False)
    made = []
    scale = float(getattr(viewport, "_dpr", 1.0))
    for shape in shapes:
        item = AIS_Shape(shape)
        item.SetColor(_hex(color))
        item.SetWidth(look.line_width(width, scale))  # grows with the screen (D2824)
        look.drop_face_curves(item.Attributes())  # real edges only (D2823)
        if shaded:
            context.Display(item, 1, -1, False)
            context.SetTransparency(item, 0.75, False)
        else:
            context.Display(item, 0, -1, False)
        context.Deactivate(item)
        made.append(item)
    items[name] = made
    context.UpdateCurrentViewer()


def paint_faces(viewport: Any, colors: list[tuple[Any, str]]) -> None:
    """Colour faces of the shown part on top of its own colours; an empty list clears them."""
    viewport.painted_faces = list(colors)
    context = getattr(viewport, "_context", None)
    part = getattr(viewport, "_part", None)
    if context is None or part is None:
        return
    from OCP.AIS import AIS_ColoredShape

    from fdcad.ui.viewport.widget import _hex

    if not isinstance(part, AIS_ColoredShape):
        return
    part.ClearCustomAspects()
    for face, color in [*getattr(viewport, "face_colors", []), *colors]:
        part.SetCustomColor(face, _hex(color))
    context.Redisplay(part, False)
    context.UpdateCurrentViewer()


def show_mesh(viewport: Any, name: str, mesh: Any, color: str | None = None) -> None:
    """Show a triangle mesh (``vertices`` and ``triangles`` arrays, such as an export
    preview, TR336) shaded with its edges as the overlay layer ``name``; None clears it."""
    meshes: dict[str, Any] = _store(viewport, "print_meshes")
    items: dict[str, list[Any]] = _store(viewport, "print_layer_items")
    if mesh is None:
        meshes.pop(name, None)
    else:
        meshes[name] = mesh
    context = getattr(viewport, "_context", None)
    if context is None:
        return
    for item in items.pop(name, []):
        context.Remove(item, False)
    if mesh is not None and len(mesh.triangles):
        from OCP.AIS import AIS_Shape
        from OCP.BRep import BRep_Builder
        from OCP.TopoDS import TopoDS_Face

        from fdcad.core.io.mesh_import import Mesh, triangulation
        from fdcad.ui.viewport.widget import _hex

        face = TopoDS_Face()
        BRep_Builder().MakeFace(face, triangulation(Mesh(mesh.vertices, mesh.triangles)))
        item = AIS_Shape(face)
        from fdcad.ui.themes.theme import DATA

        item.SetColor(_hex(color or DATA["mesh_preview"]))
        aspect = item.Attributes().ShadingAspect().Aspect()
        aspect.SetDrawEdges(True)
        context.Display(item, 1, -1, False)
        context.Deactivate(item)
        items[name] = [item]
    context.UpdateCurrentViewer()
