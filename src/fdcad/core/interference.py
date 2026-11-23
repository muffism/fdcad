"""Interference and gap check between the bodies of a part (TR150, DECISIONS D771).

Every pair of bodies is checked: a pair whose bounding boxes are further apart
than the gap is skipped at once; otherwise the shared volume of the two (a
boolean common) gives an overlap, and the smallest distance between them gives
a gap or a touch. Kernel work, run in a kernel job (CLAUDE.md 5.2); a pair the
kernel cannot check is reported as such, never raised (CLAUDE.md 5.7).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.features.booleans import boolean_shape
from fdcad.core.features.solids import solids, volume_of

Vec3 = tuple[float, float, float]
#: Closer than this (mm) counts as touching; overlaps smaller than this (mm3) as none.
TOUCH = 1e-4
VOLUME_NOISE = 1e-6


@dataclass
class PairResult:
    """One pair of bodies (0 based indices) and what was found."""

    first: int
    second: int
    kind: str  # "overlap", "touch", "gap" or "failed"
    volume: float = 0.0  # mm3, for an overlap
    distance: float = 0.0  # mm, the smallest gap (0 for an overlap or a touch)
    points: tuple[Vec3, Vec3] | None = None  # the closest points, for a gap
    shape: TopoDS_Shape | None = field(default=None, repr=False)  # the shared volume


def _box(shape: TopoDS_Shape) -> Bnd_Box:
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    return box


def _apart(a: Bnd_Box, b: Bnd_Box, gap: float) -> bool:
    return bool(a.Distance(b) > gap + TOUCH)


def check_pair(i: int, a: TopoDS_Shape, j: int, b: TopoDS_Shape, gap: float) -> PairResult | None:
    """The result for one pair, or None when they are further apart than ``gap``."""
    try:
        common = boolean_shape("common", a, b)
        volume = volume_of(common) if common is not None and solids(common) else 0.0
        if volume > VOLUME_NOISE:
            return PairResult(i, j, "overlap", volume=volume, shape=common)
        dist = BRepExtrema_DistShapeShape(a, b)
        if not dist.IsDone():
            return PairResult(i, j, "failed")
        d = dist.Value()
        if d <= TOUCH:
            return PairResult(i, j, "touch")
        if d < gap:
            p, q = dist.PointOnShape1(1), dist.PointOnShape2(1)
            return PairResult(
                i, j, "gap", distance=d, points=((p.X(), p.Y(), p.Z()), (q.X(), q.Y(), q.Z()))
            )
        return None
    except Exception:  # a pair the kernel cannot check is said, never raised
        return PairResult(i, j, "failed")


def check(
    bodies: Sequence[TopoDS_Shape],
    gap: float = 0.0,
    touching: bool = False,
    exclude: Sequence[int] = (),
    ignore: Sequence[tuple[int, int]] = (),
) -> list[PairResult]:
    """Overlaps, gaps under ``gap`` mm and, with ``touching``, touching pairs."""
    skip = set(exclude)
    ignored = {tuple(sorted(p)) for p in ignore}
    boxes = [_box(b) for b in bodies]
    out: list[PairResult] = []
    for i in range(len(bodies)):
        if i in skip:
            continue
        for j in range(i + 1, len(bodies)):
            if j in skip or (i, j) in ignored or _apart(boxes[i], boxes[j], gap):
                continue
            result = check_pair(i, bodies[i], j, bodies[j], gap)
            if result is None or (result.kind == "touch" and not touching):
                continue
            out.append(result)
    return out
