"""Short names for OCP collection classes, the kernel's booleans in their safe mode, and a
point test that is right for parts of several bodies.

OCP 8 exposes OpenCascade's templated collections under generated names in
``OCP.collections``. Import them from here, so a later OCP rename touches one file.
"""

from typing import TYPE_CHECKING, Any

from OCP.BRepAlgoAPI import BRepAlgoAPI_BooleanOperation
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common as _Common
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut as _Cut
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse as _Fuse
from OCP.BRepAlgoAPI import BRepAlgoAPI_Section as _Section
from OCP.BRepAlgoAPI import BRepAlgoAPI_Splitter as _Splitter
from OCP.collections import (
    IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeListMap,
)
from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
from OCP.collections import List_TopoDS_Shape as ShapeList
from OCP.collections import Map_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeSet
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopoDS import TopoDS_Shape

__all__ = [
    "BRepAlgoAPI_BooleanOperation",
    "BRepAlgoAPI_Common",
    "BRepAlgoAPI_Cut",
    "BRepAlgoAPI_Fuse",
    "BRepAlgoAPI_Section",
    "BRepAlgoAPI_Splitter",
    "ShapeList",
    "ShapeListMap",
    "ShapeMap",
    "ShapeSet",
    "point_inside",
    "shape_list",
]


def shape_list(shapes: ShapeList) -> list[TopoDS_Shape]:
    """A Python list of an OpenCascade shape list.

    ``list(shapes)`` works but takes about 1 ms per call in OCP 8, which made
    naming the slowest part of a rebuild. Reading the ends directly is about
    50 times faster; most history lists hold one or two shapes.
    """
    n = shapes.Size()
    if n == 0:
        return []
    if n == 1:
        return [shapes.First()]
    if n == 2:
        return [shapes.First(), shapes.Last()]
    rest = ShapeList()
    rest.Assign(shapes)
    out = []
    while not rest.IsEmpty():
        out.append(rest.First())
        rest.RemoveFirst()
    return out


# Booleans that leave their inputs alone (D1067) -----------------------------------------
#
# The kernel's boolean operations may write into the shapes they are given: they add
# curves to faces and loosen edges and corners where the two shapes meet. A body shares
# almost all of its faces with the results of the features before it, and the rebuild
# keeps those results. So a later cut could leave an earlier result not valid (found on a
# gearbox: three faces of the housing after a grille was cut in the cover lying on it),
# and a rebuild that starts from a kept result then starts from a spoiled body. The
# kernel has a safe mode for this, off by default. The classes below are the
# kernel's own with the safe mode on, under the same names: import the booleans from
# here, never from ``OCP.BRepAlgoAPI`` (``tests/core/test_safe_booleans.py`` checks).
#
# One exception, decided at every ``Build`` (D1076): when a shape on one side shares a
# face with a shape on the other (the part before and after a cut, which Fold compares),
# the safe mode can give a wrong answer: on a sheet metal tray with two gussets the cut
# of the part after a slot by the part before it came back as the whole part, where
# nothing should be left. The kernel's own mode is right there, and so is the safe mode
# on copies that share nothing. So shapes that share a face are built in the kernel's
# own mode, as all booleans were before D1067.


def share_a_face(first: ShapeList, second: ShapeList) -> bool:
    """True when a shape of ``first`` and a shape of ``second`` have a face in common."""
    one, other = ShapeMap(), ShapeMap()
    for shape in shape_list(first):
        TopExp.MapShapes_s(shape, TopAbs_FACE, one)
    for shape in shape_list(second):
        TopExp.MapShapes_s(shape, TopAbs_FACE, other)
    if one.Extent() > other.Extent():
        one, other = other, one
    return any(other.Contains(one.FindKey(i)) for i in range(1, one.Extent() + 1))


# Tools made of crossing pieces (D2623) ---------------------------------------------------
#
# The kernel never intersects the pieces of one compound with each other. A tool that is
# a compound of solids sharing material is taken badly: a cross of two boxes cut from a
# plate left the plate whole, and the rooms and pin hole of a pin hinge cut as one tool
# left the rooms uncut (D1085, and the pieces of D1055). So before a cut, join or
# intersection, each such tool is replaced by its pieces: passed as separate tools the
# kernel intersects them with each other, which is the same as fusing them first, and
# the history still covers every face of the tool. An intersection takes its tool's
# pieces as several tools, so for it the pieces are fused first.


def _crossing_pieces(shape: TopoDS_Shape) -> list[TopoDS_Shape] | None:
    """The solids of a compound when two of them share material, else None."""
    from OCP.TopAbs import TopAbs_COMPOUND, TopAbs_SOLID

    if shape.IsNull() or shape.ShapeType() != TopAbs_COMPOUND:
        return None
    pieces: list[TopoDS_Shape] = []
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        pieces.append(explorer.Current())
        explorer.Next()
    if len(pieces) < 2:
        return None
    import numpy as np
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    corners = np.empty((len(pieces), 6))
    for i, piece in enumerate(pieces):
        box = Bnd_Box()
        BRepBndLib.Add_s(piece, box)
        low, high = box.CornerMin(), box.CornerMax()
        corners[i] = (low.X(), low.Y(), low.Z(), high.X(), high.Y(), high.Z())
    lo, hi = corners[:, :3], corners[:, 3:]
    # Boxes that overlap by more than a hair on every axis; touching pieces do not count.
    meet = np.all(
        (lo[:, None, :] < hi[None, :, :] - _HAIR) & (lo[None, :, :] < hi[:, None, :] - _HAIR),
        axis=2,
    )
    pairs = list(zip(*np.nonzero(np.triu(meet, 1)), strict=True))
    if len(pairs) > _MOST_PAIRS:
        # One fuse of the pieces whose boxes meet, against the sum of their volumes
        # (D2658): a boolean of each pair took 255 s for the 102 pairs of a gyroid's 71
        # pieces, the one fuse 18 s.
        near = [pieces[int(k)] for k in sorted({int(k) for pair in pairs for k in pair})]
        alone = sum(_volume(p) for p in near)
        return pieces if alone - _volume(_fused(near)) > max(_HAIR**3, 1e-6 * alone) else None
    for i, j in pairs:
        if _shared_volume(pieces[int(i)], pieces[int(j)]) > _HAIR**3:
            return pieces
    return None


#: Less than this (mm) is a touch, not an overlap.
_HAIR = 1e-4
#: More pairs of pieces with meeting boxes than this are tested with one fuse (D2658).
_MOST_PAIRS = 4


def _volume(shape: TopoDS_Shape) -> float:
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props, 1e-7)
    return abs(float(props.Mass()))


def _shared_volume(a: TopoDS_Shape, b: TopoDS_Shape) -> float:
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    op = _Common()
    op.SetNonDestructive(True)
    first, second = ShapeList(), ShapeList()
    first.Append(a)
    second.Append(b)
    op.SetArguments(first)
    op.SetTools(second)
    op.Build()
    if not op.IsDone():
        return 1.0  # the kernel cannot say: treat the pieces as crossing
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(op.Shape(), props)
    return abs(float(props.Mass()))


def _fused(pieces: list[TopoDS_Shape]) -> TopoDS_Shape:
    """The pieces fused into one shape."""
    op = _Fuse()
    op.SetNonDestructive(True)
    first, rest = ShapeList(), ShapeList()
    first.Append(pieces[0])
    for piece in pieces[1:]:
        rest.Append(piece)
    op.SetArguments(first)
    op.SetTools(rest)
    op.Build()
    return op.Shape() if op.IsDone() else pieces[0]


def _tools_apart(op: Any, fuse_first: bool) -> None:
    """Replace each tool made of crossing pieces by its pieces (or by their fuse).
    Skipped when the boolean was made with ``pieces_apart=True`` (D2658)."""
    if op.__dict__.get("_apart"):
        return
    tools = shape_list(op.Tools())
    found = [_crossing_pieces(t) for t in tools]
    if not any(found):
        return
    out = ShapeList()
    for tool, pieces in zip(tools, found, strict=True):
        if pieces is None:
            out.Append(tool)
        elif fuse_first:
            out.Append(_fused(pieces))
        else:
            for piece in pieces:
                out.Append(piece)
    op.SetTools(out)


def _build(op: Any, base: Any, args: tuple[Any, ...]) -> Any:
    """``Build`` in the safe mode, or in the kernel's own when the sides share a face."""
    op.SetNonDestructive(not share_a_face(op.Arguments(), op.Tools()))
    return base.Build(op, *args)


def _two_shapes(args: tuple[Any, ...]) -> bool:
    return len(args) == 2 and all(isinstance(a, TopoDS_Shape) for a in args)


def _start(op: Any, base: Any, args: tuple[Any, ...], apart: bool = False) -> None:
    """Make ``op`` as the kernel's ``base(*args)`` does, with the safe mode on first.
    ``apart`` skips the crossing pieces check (D2658)."""
    if not args:
        base.__init__(op)
        op.SetNonDestructive(True)
        op.__dict__["_apart"] = apart
        return
    if not _two_shapes(args):
        raise TypeError("give two shapes, or nothing and then SetArguments and SetTools")
    base.__init__(op)
    op.SetNonDestructive(True)
    op.__dict__["_apart"] = apart
    first, second = ShapeList(), ShapeList()
    first.Append(args[0])
    second.Append(args[1])
    op.SetArguments(first)
    op.SetTools(second)
    op.Build()  # the kernel's two shape form builds at once


class LocalMismatchError(AssertionError):
    """A local boolean gave another result than the kernel's (check mode, D2601)."""


def _try_local(op: Any, base: Any, kind: str, args: tuple[Any, ...]) -> bool:
    """Make a cut or join of a large body locally (``local_boolean``, D2601); True when
    done. Otherwise the kernel's own boolean runs."""
    from OCP.BOPAlgo import BOPAlgo_GlueEnum

    from fdcad.core import local_boolean

    op.__dict__.pop("_local", None)
    if args or not local_boolean.enabled():
        return False
    bodies, tools = shape_list(op.Arguments()), shape_list(op.Tools())
    if len(bodies) != 1 or len(tools) != 1:
        if bodies and len(bodies) + len(tools) > 2:
            local_boolean.STATS["several shapes"] = local_boolean.STATS.get("several shapes", 0) + 1
        return False
    if op.Glue() != BOPAlgo_GlueEnum.BOPAlgo_GlueOff:
        return False
    made = local_boolean.run(kind, bodies[0], tools[0], float(op.FuzzyValue()))
    if made is None:
        return False
    if local_boolean.checking():
        _build(op, base, args)
        _compare(kind, made.shape, op.Shape())
    op.__dict__["_local"] = made
    return True


def _compare(kind: str, mine: TopoDS_Shape, kernel: TopoDS_Shape) -> None:
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    def volume(shape: TopoDS_Shape) -> float:
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(shape, props, 1e-7)
        return float(props.Mass())

    def faces(shape: TopoDS_Shape) -> int:
        found = ShapeMap()
        TopExp.MapShapes_s(shape, TopAbs_FACE, found)
        return int(found.Extent())

    a, b = volume(mine), volume(kernel)
    if abs(a - b) > 1e-7 * max(abs(b), 1.0) or faces(mine) != faces(kernel):
        raise LocalMismatchError(
            f"local {kind}: volume {a!r} against {b!r}, faces {faces(mine)} against {faces(kernel)}"
        )
    if not BRepCheck_Analyzer(mine).IsValid():
        raise LocalMismatchError(f"local {kind}: the result is not valid")


class _LocalAnswers:
    """What a boolean made by ``local_boolean`` answers (D2601); the kernel's otherwise."""

    def _made(self) -> Any:
        return self.__dict__.get("_local")

    def Shape(self) -> Any:  # noqa: N802 (the kernel's names, here and below)
        made = self._made()
        return made.shape if made is not None else super().Shape()  # type: ignore[misc]

    def History(self) -> Any:  # noqa: N802
        made = self._made()
        return made.history if made is not None else super().History()  # type: ignore[misc]

    def Modified(self, shape: Any) -> Any:  # noqa: N802
        made = self._made()
        if made is None:
            return super().Modified(shape)  # type: ignore[misc]
        return made.history.Modified(shape)

    def Generated(self, shape: Any) -> Any:  # noqa: N802
        made = self._made()
        if made is None:
            return super().Generated(shape)  # type: ignore[misc]
        return ShapeList()  # a boolean makes no faces from edges

    def IsDeleted(self, shape: Any) -> Any:  # noqa: N802
        made = self._made()
        if made is None:
            return super().IsDeleted(shape)  # type: ignore[misc]
        return made.history.IsRemoved(shape)

    def IsDone(self) -> Any:  # noqa: N802
        return True if self._made() is not None else super().IsDone()  # type: ignore[misc]

    def HasErrors(self) -> Any:  # noqa: N802
        return False if self._made() is not None else super().HasErrors()  # type: ignore[misc]

    def HasWarnings(self) -> Any:  # noqa: N802
        made = self._made()
        return False if made is not None else super().HasWarnings()  # type: ignore[misc]


class _SafeCut(_LocalAnswers, _Cut):  # type: ignore[misc]
    """The kernel's cut, in the mode that does not change its inputs; on a large body,
    made locally (D2601)."""

    def __init__(self, *args: Any, pieces_apart: bool = False) -> None:
        _start(self, _Cut, args, pieces_apart)

    def Build(self, *args: Any) -> Any:  # noqa: N802 (the kernel's name)
        _tools_apart(self, False)
        if _try_local(self, _Cut, "cut", args):
            return None
        return _build(self, _Cut, args)


class _SafeFuse(_LocalAnswers, _Fuse):  # type: ignore[misc]
    """The kernel's fuse, in the mode that does not change its inputs; on a large body,
    made locally (D2601)."""

    def __init__(self, *args: Any, pieces_apart: bool = False) -> None:
        _start(self, _Fuse, args, pieces_apart)

    def Build(self, *args: Any) -> Any:  # noqa: N802 (the kernel's name)
        _tools_apart(self, False)
        if _try_local(self, _Fuse, "fuse", args):
            return None
        return _build(self, _Fuse, args)


class _SafeCommon(_Common):  # type: ignore[misc]
    """The kernel's intersection, in the mode that does not change its inputs."""

    def __init__(self, *args: Any, pieces_apart: bool = False) -> None:
        _start(self, _Common, args, pieces_apart)

    def Build(self, *args: Any) -> Any:  # noqa: N802 (the kernel's name)
        _tools_apart(self, True)
        return _build(self, _Common, args)


class _SafeSplitter(_Splitter):  # type: ignore[misc]
    """The kernel's splitter, in the mode that does not change its inputs."""

    def __init__(self) -> None:
        _Splitter.__init__(self)
        self.SetNonDestructive(True)

    def Build(self, *args: Any) -> Any:  # noqa: N802
        return _build(self, _Splitter, args)


class _SafeSection(_Section):  # type: ignore[misc]
    """The kernel's section, in the mode that does not change its inputs.

    Made with nothing, or with a shape and a second shape or plane, and then an
    optional ``False`` to build later (as the kernel's own).
    """

    def __init__(self, *args: Any) -> None:
        perform = True
        if args and isinstance(args[-1], bool):
            perform, args = args[-1], args[:-1]
        if len(args) not in (0, 2):
            raise TypeError("give a shape and a second shape or plane, or nothing")
        _Section.__init__(self)
        self.SetNonDestructive(True)
        if args:
            self.Init1(args[0])
            self.Init2(args[1])
            if perform:
                self.Build()

    def Build(self, *args: Any) -> Any:  # noqa: N802
        return _build(self, _Section, args)


if TYPE_CHECKING:  # to the type checker these are the kernel's own classes
    from OCP.BRepAlgoAPI import (
        BRepAlgoAPI_Common,
        BRepAlgoAPI_Cut,
        BRepAlgoAPI_Fuse,
        BRepAlgoAPI_Section,
        BRepAlgoAPI_Splitter,
    )
else:
    BRepAlgoAPI_Common = _SafeCommon
    BRepAlgoAPI_Cut = _SafeCut
    BRepAlgoAPI_Fuse = _SafeFuse
    BRepAlgoAPI_Section = _SafeSection
    BRepAlgoAPI_Splitter = _SafeSplitter


# Points inside a part of several bodies (D1082) -----------------------------------------
#
# The kernel's point classifier counts the faces a ray from the point crosses. Given a
# compound of two bodies that share a face, it counts the shared face twice, and a point
# inside the upper of two stacked blocks comes back as outside. A part's shape is such a
# compound whenever one body sits on another (a cover on its housing). Ask about each
# body on its own instead, here.


def point_inside(shape: TopoDS_Shape, point: tuple[float, float, float], tol: float) -> bool:
    """True when ``point`` is inside one of the solids of ``shape``."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN, TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer

    p = gp_Pnt(*point)
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        solid = explorer.Current()
        explorer.Next()
        box = Bnd_Box()
        BRepBndLib.Add_s(solid, box)
        box.Enlarge(tol)
        if box.IsOut(p):
            continue
        if BRepClass3d_SolidClassifier(solid, p, tol).State() == TopAbs_IN:
            return True
    return False
