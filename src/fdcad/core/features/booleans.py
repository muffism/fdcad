"""Booleans for the Phase 3 features, with the fuzzy tolerance of DECISIONS D47.

``boolean_shape`` works on plain shapes (volumes found while planning),
``boolean_named`` carries face names through the operation. Both run in
parallel mode and never let a kernel exception escape.
"""

from __future__ import annotations

from typing import Any

from OCP.TopAbs import TopAbs_COMPOUND, TopAbs_FACE
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.features.base import FeatureError
from fdcad.core.features.solids import (
    FUZZY_TOLERANCE,
    WholeBodyCutError,
    _unify,
    compound,
    each_body,
    needs_merge,
    reached_bodies,
    solids,
)
from fdcad.core.naming.names import NamedShape, carry, restrict
from fdcad.core.occ import (
    BRepAlgoAPI_BooleanOperation,
    BRepAlgoAPI_Common,
    BRepAlgoAPI_Cut,
    BRepAlgoAPI_Fuse,
    ShapeList,
    ShapeMap,
)

_OPERATIONS: dict[str, type[BRepAlgoAPI_BooleanOperation]] = {
    "fuse": BRepAlgoAPI_Fuse,
    "cut": BRepAlgoAPI_Cut,
    "common": BRepAlgoAPI_Common,
}


def _run(
    operation: str, a: TopoDS_Shape, b: TopoDS_Shape, fuzzy: float | None = None
) -> BRepAlgoAPI_BooleanOperation | None:
    op = _OPERATIONS[operation]()
    args, tools = ShapeList(), ShapeList()
    args.Append(a)
    # Each solid of a compound tool is its own tool, so copies that touch each
    # other (a pattern with spacing equal to the width) are joined cleanly.
    parts = solids(b) if b.ShapeType() == TopAbs_COMPOUND else []
    for part in parts or [b]:
        tools.Append(part)
    op.SetArguments(args)
    op.SetTools(tools)
    # A larger fuzzy value treats faces that nearly touch as touching (TR261).
    op.SetFuzzyValue(max(FUZZY_TOLERANCE, fuzzy) if fuzzy is not None else FUZZY_TOLERANCE)
    op.SetRunParallel(True)
    op.SetToFillHistory(True)
    try:
        op.Build()
    except Exception:
        return None
    if not op.IsDone():
        return None
    return op


def result_shape(op: Any) -> TopoDS_Shape | None:
    """``op.Shape()``, or None when the kernel produced nothing.

    A null shape must never reach another kernel call: some of them crash the
    process on it instead of raising an exception.
    """
    try:
        shape = op.Shape()
    except Exception:
        return None
    if shape is None or shape.IsNull():
        return None
    return shape


def boolean_shape(operation: str, a: TopoDS_Shape, b: TopoDS_Shape) -> TopoDS_Shape | None:
    """``a`` fused with, cut by or in common with ``b``; None when the kernel fails."""
    op = _run(operation, a, b)
    return result_shape(op) if op is not None else None


def _on_some_bodies(
    operation: str,
    body: NamedShape,
    tool: NamedShape,
    fid: str,
    owner: str,
    unify: bool,
    fuzzy: float | None,
) -> NamedShape | None:
    """``boolean_named`` on a part of several bodies, or None to run it on the whole part
    (a fuse whose tool reaches every body)."""

    def alone(sub: NamedShape) -> NamedShape:
        return boolean_named(operation, sub, tool, fid, owner, unify, fuzzy)

    if operation == "cut":
        return each_body(
            fid, body, [tool.shape], alone, f"{owner} removes the whole body. Change the values."
        )
    pieces = solids(body.shape)
    reached = reached_bodies(body.shape, tool.shape)
    if len(reached) == len(pieces):
        return None
    if not reached:  # it touches nothing: new bodies beside the others
        apart = compound(pieces + solids(tool.shape))
        return NamedShape(apart, restrict(body.faces + tool.faces, apart, fid))
    picked = [pieces[i] for i in reached]
    inside = ShapeMap()
    for piece in picked:
        TopExp.MapShapes_s(piece, TopAbs_FACE, inside)
    part = picked[0] if len(picked) == 1 else compound(picked)
    fused = alone(NamedShape(part, [(n, f) for n, f in body.faces if inside.Contains(f)]))
    shapes: list[TopoDS_Shape] = []
    for i, piece in enumerate(pieces):  # the bodies keep their order
        if i == reached[0]:
            shapes.extend(solids(fused.shape))
        elif i not in reached:
            shapes.append(piece)
    shape = compound(shapes)
    others = [(n, f) for n, f in body.faces if not inside.Contains(f)]
    return NamedShape(shape, restrict(others + fused.faces, shape, fid))


def boolean_named(
    operation: str,
    body: NamedShape,
    tool: NamedShape,
    fid: str,
    owner: str,
    unify: bool = True,
    fuzzy: float | None = None,
) -> NamedShape:
    """A boolean that carries the face names of both shapes. Raises FeatureError.
    ``fuzzy`` (mm) treats faces closer than it as touching (TR261).

    On a part of several bodies a fuse joins the tool to the bodies it reaches, and a
    cut cuts each body it reaches on its own (D1055, D1056). The other bodies are not
    given to the kernel: handed the whole part, it joined bodies that only touched each
    other (a table pattern of studs on one plate joined two interlocked blocks
    elsewhere), and a cut could leave the plug of a hole behind as a body.
    """
    if operation in ("fuse", "cut") and len(solids(body.shape)) > 1:
        some = _on_some_bodies(operation, body, tool, fid, owner, unify, fuzzy)
        if some is not None:
            return some
    op = _run(operation, body.shape, tool.shape, fuzzy)
    if op is None:
        raise FeatureError(
            f"{owner} failed: the kernel could not combine the shapes. "
            "Change a value slightly so faces do not almost touch."
        )
    shape = result_shape(op)
    if shape is None:
        raise FeatureError(
            f"{owner} failed: the kernel could not combine the shapes. "
            "Change a value slightly so faces do not almost touch."
        )
    names = carry(body.faces + tool.faces, op.History())
    result = NamedShape(shape, restrict(names, shape, fid))
    if operation != "fuse" and not solids(shape):
        raise WholeBodyCutError(f"{owner} removes the whole body. Change the values.")
    if unify and needs_merge(body, result):
        return _unify(result, fid)
    return result
