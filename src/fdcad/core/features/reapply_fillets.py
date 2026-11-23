"""Reapply Fillets: rebuild rounds next to a direct edit (TR259, DECISIONS D1420).

With ``reapply_fillets`` ticked, Move Face and Delete Face first remove the round
faces that touch the picked faces (Remove Fillets, D1410), make their change on
the sharp body, then round the edges between the faces each round joined again,
with the same radius. Combine (D2302) removes the rounds of the picked bodies that
touch or lie inside another picked body (the main body's only, for Subtract). Faces
keep their names through every step (the picked faces are found again by name), so
the change itself runs unchanged.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable

from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Feature
from fdcad.core.features.base import BuildContext, FeatureError, Issue
from fdcad.core.features.modify import edge_faces, edges_of
from fdcad.core.naming.names import NamedShape

PARAM = "reapply_fillets"


def wanted(feature: Feature) -> bool:
    """True when the feature has Reapply Fillets ticked."""
    return feature.params.get(PARAM) is True


def _touching(body: NamedShape, picked: list[TopoDS_Face]) -> list[tuple[str, TopoDS_Face, float]]:
    """Round faces sharing an edge with a picked face."""
    from fdcad.core.features.remove_fillets import find_rounds

    out = []
    for name, face, radius in find_rounds(body):
        if any(f.IsSame(face) for f in picked):
            continue
        near = {
            id(o)
            for e in edges_of(face)
            for o in edge_faces(body.shape, e)
            if any(o.IsSame(p) for p in picked)
        }
        if near:
            out.append((name, face, radius))
    return out


def around(
    feature: Feature,
    ctx: BuildContext,
    picked: list[TopoDS_Face],
    change: Callable[[BuildContext], tuple[NamedShape, list[Issue]]],
) -> tuple[NamedShape, list[Issue]]:
    """Remove the rounds next to ``picked``, run ``change`` on the sharp body, round again."""
    body = ctx.body
    if body is None:
        return change(ctx)
    return redo(feature, ctx, _touching(body, picked), change)


def near_bodies(
    body: NamedShape, own: TopoDS_Shape, others: list[TopoDS_Shape]
) -> list[tuple[str, TopoDS_Face, float]]:
    """Round faces of the solid ``own`` that touch or lie inside one of ``others``
    (Combine, TR259, D2302)."""
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape

    from fdcad.core.features.remove_fillets import find_rounds

    out = []
    for name, face, radius in find_rounds(body):
        if not _inside(own, face):
            continue
        for other in others:
            dist = BRepExtrema_DistShapeShape(face, other)
            if dist.IsDone() and dist.Value() < _TOUCH:
                out.append((name, face, radius))
                break
    return out


#: A round closer than this to another body counts as next to the change (mm).
_TOUCH = 1e-4


def _inside(solid: TopoDS_Shape, face: TopoDS_Face) -> bool:
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer

    explorer = TopExp_Explorer(solid, TopAbs_FACE)
    while explorer.More():
        if explorer.Current().IsSame(face):
            return True
        explorer.Next()
    return False


def redo(
    feature: Feature,
    ctx: BuildContext,
    rounds: list[tuple[str, TopoDS_Face, float]],
    change: Callable[[BuildContext], tuple[NamedShape, list[Issue]]],
) -> tuple[NamedShape, list[Issue]]:
    """Remove ``rounds``, run ``change`` on the sharp body, round the same edges again."""
    from fdcad.core.features.direct import patch
    from fdcad.core.features.fillet import Item, round_edges
    from fdcad.core.features.remove_fillets import _neighbours

    body = ctx.body
    if body is None or not rounds:
        return change(ctx)
    pairs = [(_neighbours(body, face), radius) for _n, face, radius in rounds]
    try:
        sharp = patch(body, [f for _n, f, _r in rounds], feature.id, feature.name,
                      [n for n, _f, _r in rounds])  # fmt: skip
    except FeatureError as exc:
        raise FeatureError(
            f"{feature.name}: the rounds next to the picked faces could not be removed first. "
            "Turn off Reapply Fillets, or remove those rounds yourself.",
            highlight=[n for n, _f, _r in rounds],
        ) from exc
    changed, issues = change(dataclasses.replace(ctx, body=sharp))
    items: list[Item] = []
    radii: dict[str, float] = {}
    for names, radius in pairs:
        for i, a in enumerate(names):
            for b in names[i + 1 :]:
                for edge in _pair_edges(changed, a, b):
                    name = changed.edge_name(edge) or f"edge({a}|{b})"
                    if not any(edge.IsSame(x.edge) for x in items):
                        items.append(Item(name, edge, 0))
                        radii[name] = radius
    if not items:
        return changed, issues
    remade = round_edges(
        feature.id, changed, items, lambda i: [(0.0, radii[i.name]), (1.0, radii[i.name])]
    )
    if remade is None:
        raise FeatureError(
            f"{feature.name}: the rounds could not be made again after the change. "
            "Turn off Reapply Fillets, or make the change smaller.",
            highlight=[n for n, _f, _r in rounds],
        )
    return remade, issues


def _base(name: str) -> str:
    """``name`` without the ``#k`` a split adds (``f6/side/e5#2`` is ``f6/side/e5``)."""
    head, sep, tail = name.rpartition("#")
    return head if sep and tail.isdigit() else name


def _pair_edges(shape: NamedShape, a: str, b: str) -> list[TopoDS_Edge]:
    """Edges between face ``a`` and face ``b``, or between pieces of them a boolean split
    (Combine, D2302)."""
    exact = shape.edges(f"edge({'|'.join(sorted([a, b]))})")
    if exact:
        return exact
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer

    from fdcad.core.occ import ShapeMap

    want = sorted([a, b])
    out: list[TopoDS_Edge] = []
    seen = ShapeMap()
    explorer = TopExp_Explorer(shape.shape, TopAbs_EDGE)
    while explorer.More():
        edge = TopoDS.Edge(explorer.Current())
        explorer.Next()
        if seen.Contains(edge):
            continue
        seen.Add(edge)
        faces = edge_faces(shape.shape, edge)
        if len(faces) != 2:
            continue
        names = sorted(_base(shape.primary_name(f) or "") for f in faces)
        if names == want:
            out.append(edge)
    return out
