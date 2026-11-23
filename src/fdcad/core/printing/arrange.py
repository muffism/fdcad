"""Suggest a print orientation and arrange bodies on the bed (TR301, DECISIONS D1210).

``suggest`` tries the face down directions of the part's six largest flat face
directions and ranks them: those that fit the build volume first, then by
overhang area, then by height. Each comes with the flat face to lay on the bed,
so one click can apply Lay Face Flat.

``arrange`` places the bodies' footprints on the bed in rows, largest first,
with a spacing between them and around no print zones (TR413), and returns the
move of each body in model coordinates. Kernel work: run both off the UI thread.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from OCP.TopoDS import TopoDS_Face, TopoDS_Shape

from fdcad.core.printing.profiles import PrinterProfile

Vec3 = tuple[float, float, float]
#: How many face down directions are tried.
DIRECTIONS = 6


@dataclass(frozen=True)
class Candidate:
    """One way to lay the part: the face on the bed, its outward normal, the area that
    overhangs, the height and whether it fits the build volume."""

    face: TopoDS_Face
    down: Vec3
    overhang: float
    height: float
    fits: bool
    #: Floating islands in this orientation (TR409, D1213).
    islands: int = 0


def _flat_directions(shape: TopoDS_Shape) -> list[tuple[Vec3, TopoDS_Face]]:
    """Distinct outward normals of flat faces, the largest total area first, each with
    its largest face."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    from fdcad.core.features.face_picks import outward_normal
    from fdcad.core.naming.names import faces_of

    groups: list[tuple[Vec3, float, TopoDS_Face, float]] = []  # normal, total, face, area
    for face in faces_of(shape):
        n = outward_normal(face)
        if n is None:
            continue
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, props)
        area = props.Mass()
        for k, (m, total, best, best_area) in enumerate(groups):
            if m[0] * n[0] + m[1] * n[1] + m[2] * n[2] > 1 - 1e-6:
                groups[k] = (
                    m,
                    total + area,
                    face if area > best_area else best,
                    max(area, best_area),
                )
                break
        else:
            groups.append((n, area, face, area))
    groups.sort(key=lambda g: -g[1])
    return [(n, face) for n, _t, face, _a in groups[:DIRECTIONS]]


def suggest(shape: TopoDS_Shape, profile: PrinterProfile) -> list[Candidate]:
    """The face down orientations, best first: those that fit, then by overhang area,
    then by floating islands (TR409), then by height."""
    from fdcad.core.printing.islands import find
    from fdcad.core.printing.orientation import lay_flat_rotation, moved
    from fdcad.core.printing.overhang import triangles_by_face

    _faces, corners, _owner = triangles_by_face(shape)
    if len(corners) == 0:
        return []
    cross = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    doubled = np.linalg.norm(cross, axis=1)
    keep = doubled > 1e-15
    normal = np.zeros_like(cross)
    normal[keep] = cross[keep] / doubled[keep, None]
    area = doubled / 2
    points = corners.reshape(-1, 3)
    out = []
    for down, face in _flat_directions(shape):
        up = -np.asarray(down, dtype=np.float64)
        heights = corners @ up
        low = heights.min()
        on_bed = np.all(heights <= low + 1e-3, axis=1)
        steep = (normal @ up) < -math.sin(profile.overhang_angle)
        hanging = float(area[steep & ~on_bed & keep].sum())
        tall = float(heights.max() - low)
        # The footprint: the points seen along up, in two directions square to it.
        a = np.cross(up, [1.0, 0.0, 0.0] if abs(up[0]) < 0.9 else [0.0, 1.0, 0.0])
        a /= np.linalg.norm(a)
        b = np.cross(up, a)
        wide = sorted((float(np.ptp(points @ a)), float(np.ptp(points @ b))))
        bed = sorted((profile.bed_x, profile.bed_y))
        fits = (
            tall <= profile.height + 1e-6 and wide[0] <= bed[0] + 1e-6 and wide[1] <= bed[1] + 1e-6
        )
        islands = len(find(moved(shape, lay_flat_rotation(face)), cells=80).islands)
        out.append(Candidate(face, down, hanging, tall, fits, islands))
    return sorted(out, key=lambda c: (not c.fits, round(c.overhang, 6), c.islands, c.height))


Rect = tuple[float, float, float, float]


def _overlaps(r: Rect, others: list[Rect]) -> bool:
    return any(r[0] < o[2] and o[0] < r[2] and r[1] < o[3] and o[1] < r[3] for o in others)


def pack(
    sizes: list[tuple[float, float]],
    width: float,
    depth: float,
    spacing: float,
    blocked: list[Rect],
) -> list[tuple[float, float]] | None:
    """Lower left corners for rectangles of ``sizes`` on a bed ``width`` by ``depth``: rows
    from the front, the deepest first, ``spacing`` apart and clear of ``blocked`` (grown
    by the spacing). None when they do not all fit."""
    order = sorted(range(len(sizes)), key=lambda i: (-sizes[i][1], -sizes[i][0]))
    walls = [(b[0] - spacing, b[1] - spacing, b[2] + spacing, b[3] + spacing) for b in blocked]
    placed: list[Rect] = []
    out: list[tuple[float, float] | None] = [None] * len(sizes)
    for i in order:
        w, d = sizes[i]
        # Bottom left first: try the corners next to what is already there.
        xs = sorted({0.0, *(r[2] for r in placed + walls if r[2] >= 0)})
        ys = sorted({0.0, *(r[3] for r in placed + walls if r[3] >= 0)})
        spot = None
        for y in ys:
            for x in xs:
                r = (x, y, x + w, y + d)
                if r[2] > width + 1e-9 or r[3] > depth + 1e-9:
                    continue
                if not _overlaps(r, walls) and not _overlaps(r, placed):
                    spot = (x, y)
                    break
            if spot is not None:
                break
        if spot is None:
            return None
        out[i] = spot
        placed.append((spot[0], spot[1], spot[0] + w + spacing, spot[1] + d + spacing))
    return [p for p in out if p is not None]


def _box(shape: TopoDS_Shape) -> tuple[float, float, float, float, float, float]:
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    lo, hi = box.CornerMin(), box.CornerMax()
    return lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()


def arrange(
    bodies: list[TopoDS_Shape], turn: object, profile: PrinterProfile, spacing: float
) -> list[Vec3] | None:
    """The move of each body, in model coordinates, that lays the bodies out on the bed
    ``spacing`` apart. ``turn`` is the print orientation's rotation (a gp_Trsf). The
    bed is filled from its front left corner, so no print zones are avoided where the
    printer has them. None when the bodies do not fit."""
    from OCP.gp import gp_Vec

    from fdcad.core.printing.orientation import moved

    boxes = [_box(moved(b, turn)) for b in bodies]
    sizes = [(b[3] - b[0], b[4] - b[1]) for b in boxes]
    spots = pack(sizes, profile.bed_x, profile.bed_y, spacing, list(profile.no_zones))
    if spots is None:
        return None
    # Print placement centres the whole layout on the bed again: keep the layout's
    # centre where the bed's centre is, so the zones stay clear.
    x0 = min(x for x, _y in spots)
    y0 = min(y for _x, y in spots)
    x1 = max(x + w for (x, _y), (w, _d) in zip(spots, sizes, strict=True))
    y1 = max(y + d for (_x, y), (_w, d) in zip(spots, sizes, strict=True))
    shift = (profile.bed_x / 2 - (x0 + x1) / 2, profile.bed_y / 2 - (y0 + y1) / 2)
    blocked_after = [
        (z[0] - shift[0], z[1] - shift[1], z[2] - shift[0], z[3] - shift[1])
        for z in profile.no_zones
    ]
    if shift != (0.0, 0.0) and profile.no_zones:
        # Pack again with the zones where they fall once the layout is centred.
        again = pack(sizes, profile.bed_x, profile.bed_y, spacing, blocked_after)
        if again is not None:
            spots = again
    back = turn.Inverted()  # type: ignore[attr-defined]
    out: list[Vec3] = []
    for (x, y), b in zip(spots, boxes, strict=True):
        v = gp_Vec(x - b[0], y - b[1], 0.0)
        v.Transform(back)
        out.append((v.X(), v.Y(), v.Z()))
    return out
