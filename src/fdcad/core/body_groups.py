"""Identical bodies in a multibody part (TR308, D958).

Two bodies count as identical when their volume, surface area, principal moments
of inertia and face, edge and vertex counts match within a small relative
tolerance, wherever they sit and however they are turned: a pattern of the same
bracket is one group. The feature tree shows each group of two or more in a folder
with a count. Kernel work: run it in the rebuild worker. No Qt.
"""

from __future__ import annotations

from collections import Counter

from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.occ import ShapeMap

#: Relative tolerance for the measured values.
TOLERANCE = 1e-6
#: Above this many bodies the tree does not group them (the check costs time).
MAX_BODIES = 500

Signature = tuple[int, int, int, float, float, float, float, float]


def _count(shape: TopoDS_Shape, kind: object) -> int:
    found = ShapeMap()
    TopExp.MapShapes_s(shape, kind, found)
    return int(found.Extent())


def _counts(solid: TopoDS_Shape) -> tuple[int, int, int]:
    return (
        _count(solid, TopAbs_FACE),
        _count(solid, TopAbs_EDGE),
        _count(solid, TopAbs_VERTEX),
    )


def signature(solid: TopoDS_Shape) -> Signature:
    """Counts and measures of one body that do not change when it moves or turns."""
    volume = GProp_GProps()
    BRepGProp.VolumeProperties_s(solid, volume)
    area = GProp_GProps()
    BRepGProp.SurfaceProperties_s(solid, area)
    moments = volume.PrincipalProperties().Moments()
    m = sorted(abs(float(x)) for x in moments)
    return (
        _count(solid, TopAbs_FACE),
        _count(solid, TopAbs_EDGE),
        _count(solid, TopAbs_VERTEX),
        abs(float(volume.Mass())),
        float(area.Mass()),
        m[0],
        m[1],
        m[2],
    )


def _same(a: Signature, b: Signature) -> bool:
    if a[:3] != b[:3]:
        return False
    for x, y in zip(a[3:], b[3:], strict=True):
        scale = max(abs(x), abs(y), 1e-9)
        if abs(x - y) > TOLERANCE * scale:
            return False
    return True


def groups_of(signatures: list[Signature]) -> list[list[int]]:
    """Body indexes grouped by identical signatures, groups of two or more only, each
    in body order, ordered by their first body."""
    groups: list[list[int]] = []
    keys: list[Signature] = []
    for i, sig in enumerate(signatures):
        for k, key in enumerate(keys):
            if _same(sig, key):
                groups[k].append(i)
                break
        else:
            keys.append(sig)
            groups.append([i])
    return [g for g in groups if len(g) > 1]


def identical_groups(bodies: list[TopoDS_Shape]) -> list[list[int]]:
    """Groups of identical bodies; none for one body or more than ``MAX_BODIES``."""
    if len(bodies) < 2 or len(bodies) > MAX_BODIES:
        return []
    try:
        # Bodies match only when their face, edge and vertex counts do, so a body whose
        # counts no other body has is not measured (D2661): on the nut and bolt, whose
        # two bodies differ, that was 0.4 s of thread faces measured for nothing.
        counts = [_counts(b) for b in bodies]
        seen = Counter(counts)
        alike = [i for i, c in enumerate(counts) if seen[c] > 1]
        if not alike:
            return []
        groups = groups_of([signature(bodies[i]) for i in alike])
    except Exception:  # a body the kernel cannot measure is never grouped
        return []
    return [[alike[k] for k in group] for group in groups]
