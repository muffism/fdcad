"""Bodies of a multibody part (PHASE3_SPEC P3.4, DECISIONS D233).

The part is one shape: a solid, or a compound of solids when it has several
bodies. A feature refers to a body by a face reference to any face of it, so
the body is found by the same name and snapshot rules as faces (PLAN 6).
Bodies are numbered in the order of the part's solids.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.features.base import BuildContext, FeatureError, Issue
from fdcad.core.features.lookup import resolve_face
from fdcad.core.features.solids import compound, solids
from fdcad.core.naming.names import NamedFace, NamedShape, restrict
from fdcad.core.occ import ShapeMap


def solid_of_face(body: TopoDS_Shape, face: TopoDS_Shape) -> int:
    """Index of the solid holding ``face`` in ``solids(body)``, or -1."""
    for i, solid in enumerate(solids(body)):
        fmap = ShapeMap()
        TopExp.MapShapes_s(solid, TopAbs_FACE, fmap)
        if fmap.Contains(face):
            return i
    return -1


def body_of_ref(ctx: BuildContext, ref: Any, owner: str) -> tuple[TopoDS_Shape, list[Issue]]:
    """The solid a body reference (a face reference) points at."""
    index, issues = body_index(ctx, ref, owner)
    assert ctx.body is not None
    return solids(ctx.body.shape)[index], issues


def body_index(ctx: BuildContext, ref: Any, owner: str) -> tuple[int, list[Issue]]:
    """Index of the solid a body reference points at."""
    if not isinstance(ref, dict) or ref.get("kind") != "face":
        raise FeatureError(f"{owner}: pick a body in the view.")
    face, issues = resolve_face(ctx.body, ref, owner)
    assert ctx.body is not None
    index = solid_of_face(ctx.body.shape, face)
    if index < 0:
        raise FeatureError(f"{owner}: a picked body was lost. Pick it again.")
    return index, issues


def body_indices(ctx: BuildContext, refs: Any, owner: str) -> tuple[list[int], list[Issue]]:
    """Distinct solid indices for a list of body references, in pick order."""
    if not isinstance(refs, list) or not refs:
        raise FeatureError(f"{owner}: pick one or more bodies in the view.")
    out: list[int] = []
    issues: list[Issue] = []
    for ref in refs:
        index, found = body_index(ctx, ref, owner)
        issues.extend(found)
        if index not in out:
            out.append(index)
    return out, issues


def names_on(named: NamedShape, shape: TopoDS_Shape) -> list[NamedFace]:
    """The names of ``named`` whose faces belong to ``shape``."""
    fmap = ShapeMap()
    TopExp.MapShapes_s(shape, TopAbs_FACE, fmap)
    return [(n, f) for n, f in named.faces if fmap.Contains(f)]


def sub_body(named: NamedShape, indices: Sequence[int], fid: str) -> NamedShape:
    """The bodies at ``indices`` as one named shape."""
    all_solids = solids(named.shape)
    picked = [all_solids[i] for i in indices]
    shape = picked[0] if len(picked) == 1 else compound(picked)
    return NamedShape(shape, restrict(names_on(named, shape), shape, fid))


def rest_of(named: NamedShape, indices: Sequence[int], fid: str) -> NamedShape | None:
    """Every body except those at ``indices``, or None when nothing is left."""
    others = [i for i in range(len(solids(named.shape))) if i not in indices]
    return sub_body(named, others, fid) if others else None


def join(parts: Sequence[NamedShape | None], fid: str) -> NamedShape | None:
    """Put bodies side by side in one part (no boolean)."""
    found = [p for p in parts if p is not None]
    if not found:
        return None
    shapes: list[TopoDS_Shape] = []
    names: list[NamedFace] = []
    for p in found:
        shapes.extend(solids(p.shape))
        names.extend(p.faces)
    shape = shapes[0] if len(shapes) == 1 else compound(shapes)
    return NamedShape(shape, restrict(names, shape, fid))


def sketch_face(feature: Any, ctx: BuildContext) -> TopoDS_Shape | None:
    """The face of the part that the feature's sketch was drawn on, or None when the
    sketch is on a plane or the face is gone. With ``in_body_of`` it gives a sketched
    feature the body it was drawn on (D1077)."""
    ref = feature.refs.get("sketch")
    sid = ref.get("feature") if isinstance(ref, dict) else None
    if not isinstance(sid, str) or ctx.body is None:
        return None
    try:
        plane = ctx.document.feature(sid).refs.get("plane")
    except KeyError:
        return None
    if not isinstance(plane, dict) or plane.get("kind") != "face":
        return None
    try:
        face, _issues = resolve_face(ctx.body, plane, feature.name)
    except FeatureError:
        return None
    return face


def in_body_of(
    body: NamedShape, face: TopoDS_Shape, fid: str, run: Callable[[NamedShape], NamedShape]
) -> NamedShape:
    """Run ``run`` on the body that has ``face`` only; the other bodies stay as they are.

    Features placed on a face (snap hooks, mounting bosses) join only that body,
    so they never join the pieces of a split that touch it (D622).
    """
    index = solid_of_face(body.shape, face) if len(solids(body.shape)) > 1 else -1
    return in_body_at(body, index, fid, run)


def in_body_at(
    body: NamedShape, index: int, fid: str, run: Callable[[NamedShape], NamedShape]
) -> NamedShape:
    """Run ``run`` on the body at ``index`` only, as ``in_body_of`` does; with an index
    below zero or a part of one body, ``run`` gets the whole part."""
    pieces = solids(body.shape)
    if index < 0 or len(pieces) < 2:
        return run(body)
    done = run(sub_body(body, [index], fid))
    shapes: list[TopoDS_Shape] = []
    for i, piece in enumerate(pieces):
        shapes.extend(solids(done.shape) if i == index else [piece])
    shape = compound(shapes)
    rest = rest_of(body, [index], fid)
    names = (rest.faces if rest is not None else []) + done.faces
    return NamedShape(shape, restrict(names, shape, fid))


def body_count(named: NamedShape | None) -> int:
    """How many bodies the part has."""
    return len(solids(named.shape)) if named is not None else 0


def on_own_bodies(
    named: NamedShape,
    faces: Sequence[TopoDS_Shape],
    fid: str,
    edit: Callable[[NamedShape], NamedShape],
) -> NamedShape:
    """Run ``edit`` on only the bodies that hold ``faces``; the other bodies stay as they are.

    Direct edits work on one body at a time, so a face moved into another body
    never fails or joins the bodies. The edited bodies keep their place in the
    body order.
    """
    count = len(solids(named.shape))
    picked = sorted({solid_of_face(named.shape, f) for f in faces} - {-1})
    if count < 2 or not picked or len(picked) == count:
        return edit(named)
    result = edit(sub_body(named, picked, fid))
    rest = rest_of(named, picked, fid)
    assert rest is not None
    all_solids = solids(named.shape)
    shapes: list[TopoDS_Shape] = []
    for i, solid in enumerate(all_solids):
        if i == picked[0]:
            shapes.extend(solids(result.shape))
        elif i not in picked:
            shapes.append(solid)
    shape = compound(shapes)
    return NamedShape(shape, restrict([*rest.faces, *result.faces], shape, fid))


def scope_body(feature: Any, ctx: BuildContext) -> NamedShape | None:
    """The bodies a feature acts on: the picked ones with Selected bodies, else the
    whole part. Up to Next and Through All look only at these (audit B item 12, D731)."""
    if ctx.body is None or feature.params.get("bodies_scope", "all") != "selected":
        return ctx.body
    indices, _issues = body_indices(ctx, feature.refs.get("bodies"), feature.name)
    if not indices:
        return ctx.body
    return sub_body(ctx.body, indices, feature.id)


def scoped(
    feature: Any, ctx: BuildContext, change: Callable[[NamedShape], NamedShape]
) -> tuple[NamedShape, list[Issue]]:
    """Apply ``change`` to the bodies the feature acts on (TR33, D697).

    With ``bodies_scope`` "selected" (refs ``bodies``: one face reference per body)
    only the picked bodies are changed; the others are added back as they are. With
    "all" (the default) the whole part is changed, as before.
    """
    assert ctx.body is not None
    if feature.params.get("bodies_scope", "all") != "selected":
        return change(ctx.body), []
    indices, issues = body_indices(ctx, feature.refs.get("bodies"), feature.name)
    count = len(solids(ctx.body.shape))
    if len(indices) == count:
        return change(ctx.body), issues
    picked = sub_body(ctx.body, indices, feature.id)
    rest = sub_body(ctx.body, [i for i in range(count) if i not in indices], feature.id)
    done = change(picked)
    shape = compound([done.shape, rest.shape])
    return NamedShape(shape, restrict(done.faces + rest.faces, shape, feature.id)), issues
