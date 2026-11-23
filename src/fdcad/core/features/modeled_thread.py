"""Modelled thread (PHASE4_SPEC P4.3, DECISIONS D315).

Real helical thread geometry that prints, cut into or added onto a hole or a
shaft. The profile is the nominal 60 degree V of ISO 68 and ANSI B1.1 (basic
profile with sharp roots); the panel warns that it is nominal.

Params (FDEF_SPEC 5.3.23):

- ``standard``, ``size``: what the values were filled from (display only).
- ``diameter``: length, the major diameter (an override is just another value).
- ``pitch``: length. ``method``: ``cut`` or ``extrude``. ``hand``: ``right`` or
  ``left``. ``starts``: number of starts (1 to 4).
- ``end_condition``: ``blind`` (with ``length``), ``revolutions`` (with
  ``revolutions``) or ``up_to`` (with ``refs.up_to``).
- ``offset``: optional length, moves the start along the axis; ``keep_length``
  (default true) keeps the length when the start moves, else the end stays.
- ``start_angle``: optional angle where the thread starts around the axis.
- ``reverse``: optional boolean, run the other way along the axis.

Printing (TR178, D782):

- ``form``: optional, ``iso`` (default, the 60 degree V), ``printable`` (a 90
  degree V: flanks at 45 degrees, so the thread prints upright without supports)
  or ``round`` (a coarse round groove for caps and jars, half the pitch wide).
- ``clearance``: optional length per side: a hole's thread grows and a shaft's
  shrinks by it. Without it, ``print_fit`` and ``fit_tolerance`` give it as for
  the Hole Tool (half the fit's diameter change).
- ``thread_class`` (TR393, D1507): optional tolerance class such as ``6H``, ``6g``
  or ``2A``; half its allowance is added to the clearance per side when no
  clearance is typed. "none" or left out: no class.
- ``taper_angle`` (TR145, D1917): optional half angle of a tapered thread (1.7899
  degrees for NPT and Rc, 1 in 16 on the diameter): the helix runs on a cone, so a
  hole's thread narrows going in and a shaft's widens away from its end.
- ``form`` "sketch" (TR254, D1918): the section from ``refs.profile_sketch``, one
  closed region whose X runs along the axis and Y is the depth into the material.
- ``end_finish`` (TR254, D1918): optional, ``square`` (default), ``chamfer`` (the
  depth runs out at 45 degrees) or ``fade`` (it runs out over the last pitch).
- ``relief`` (TR256, D1922): optional boolean: a run out groove (undercut) where the
  thread ends, sized from the pitch after DIN 76-1. ``lead_in`` is the end chamfer.
- ``lead_in``: optional boolean: a 45 degree cone at the start removes the thin
  start of the thread (on a shaft down to the root, in a hole out to the major
  diameter).

Refs: ``edge`` (one round edge of a hole or shaft), ``up_to`` (a vertex, a flat
face, or a plane feature).

Face roles: ``thread/face#k`` (the thread's faces, ordered by position).

Tapped holes with ``modeled_thread`` cut the same thread in every hole.
"""

from __future__ import annotations

import math
from typing import Any

from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakePolygon,
    BRepBuilderAPI_MakeWire,
)
from OCP.BRepLib import BRepLib
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
from OCP.Geom import Geom_CylindricalSurface
from OCP.Geom2d import Geom2d_Line
from OCP.gp import gp_Ax3, gp_Dir, gp_Dir2d, gp_Pnt, gp_Pnt2d
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    Vec3,
    register,
)
from fdcad.core.features.cosmetic_thread import cylinder_at
from fdcad.core.features.modify import require_body, resolve_edges
from fdcad.core.features.solids import (
    check_result,
    combine,
    compound,
    right_side_out,
    solids,
    volume_of,
)
from fdcad.core.naming.names import NamedShape, restrict
from fdcad.core.units import Kind

#: Height of the fundamental 60 degree triangle per pitch (ISO 68).
H_PER_PITCH = math.sqrt(3.0) / 2.0
_TAN30 = math.tan(math.radians(30.0))
#: How far a profile reaches past the face, as a share of the pitch.
_OVERLAP = 0.05
#: Most turns one thread may have, to keep the rebuild reasonable (D315).
MAX_TURNS = 400


def _add(a: Vec3, b: Vec3, s: float = 1.0) -> Vec3:
    return (a[0] + b[0] * s, a[1] + b[1] * s, a[2] + b[2] * s)


FORMS = (
    "iso",
    "printable",
    "round",
    "trapezoidal",
    "acme",
    "square",
    "buttress",
    "pipe",
    "sketch",  # TR254 (D1918): the user's own profile from a sketch
)
#: How a thread ends (TR254, D1918): a square end, a 45 degree run out, or a run out
#: over the last turn.
END_FINISHES = ("square", "chamfer", "fade")
#: Points on a round thread's half circle.
_ARC_STEPS = 8

#: Flat sided thread forms (TR254, D1510), from their published basic profiles, as
#: (leading flank angle, trailing flank angle, depth): the angles from the radial in
#: degrees, the depth as a share of the pitch. The crest and root flats are equal and
#: take what is left: crest + root + depth x (tan a1 + tan a2) = 1.
#: Metric trapezoidal (ISO 2904): 30 degrees included, depth 0.5P.
#: ACME (ASME B1.5): 29 degrees included, depth 0.5P.
#: Square: straight flanks, depth 0.5P, half the pitch each for groove and land.
#: Buttress (ASME B1.9): a 7 degree load flank and a 45 degree back, depth 0.6P.
#: Pipe (ISO 228 and ISO 7, the 55 degree Whitworth form): depth 0.640327P; the round
#: crests and roots are flats at the same depth.
_FLAT_FORMS: dict[str, tuple[float, float, float]] = {
    "trapezoidal": (15.0, 15.0, 0.5),
    "acme": (14.5, 14.5, 0.5),
    "square": (0.0, 0.0, 0.5),
    "buttress": (7.0, 45.0, 0.6),
    "pipe": (27.5, 27.5, 0.640327),
}


def _flat_form(
    face_radius: float, major: float, pitch: float, internal: bool, method: str, form: str
) -> list[tuple[float, float]]:
    """The section of a flat sided form (TR254, D1510), as ``thread_profile``.

    The crest and root flats share what the flanks leave of the pitch equally."""
    a1, a2, share = _FLAT_FORMS[form]
    t1, t2 = math.tan(math.radians(a1)), math.tan(math.radians(a2))
    depth = share * pitch
    flat = (pitch - depth * (t1 + t2)) / 2.0  # crest = root
    half = major / 2.0
    root = half - depth  # the minor radius
    e = _OVERLAP * pitch

    def side(r0: float, r: float, w: float) -> tuple[tuple[float, float], tuple[float, float]]:
        """The two flank points at radius ``r`` of a flat ``w`` wide at radius ``r0``."""
        run = abs(r - r0)
        return (r, -(w / 2.0 + run * t1)), (r, w / 2.0 + run * t2)

    if method == "cut" and not internal:  # a groove into the shaft
        if face_radius <= root:
            raise FeatureError("the shaft is smaller than the thread root. Use a smaller size.")
        base = max(face_radius, half) + e
        lo, hi = side(root, base, flat)
        pts = [(root, -flat / 2.0), (root, flat / 2.0), hi, lo]
    elif method == "cut":  # a groove into the hole wall out to the major
        if face_radius >= half:
            raise FeatureError("the hole is larger than the thread. Use a larger size.")
        base = min(face_radius, root) - e
        lo, hi = side(half, base, flat)
        pts = [(half, -flat / 2.0), (half, flat / 2.0), hi, lo]
    elif not internal:  # a ridge on the shaft out to the major
        if face_radius >= half:
            raise FeatureError(
                "the shaft is as large as the thread. Use Cut Thread or a larger size."
            )
        base = face_radius - e
        lo, hi = side(half, base, flat)
        pts = [lo, (half, -flat / 2.0), (half, flat / 2.0), hi]
    else:  # a ridge in the hole in to the minor
        if face_radius <= root:
            raise FeatureError(
                "the hole is smaller than the thread crest. Use Cut Thread or a smaller size."
            )
        base = face_radius + e
        lo, hi = side(root, base, flat)
        pts = [lo, (root, -flat / 2.0), (root, flat / 2.0), hi]
    if max(z for _r, z in pts) - min(z for _r, z in pts) >= pitch * 0.999:
        raise FeatureError(
            "the thread profile is wider than the pitch, because the face is far from the "
            "thread. Choose the size that matches the face."
        )
    return pts


def _round_profile(
    face_radius: float, major: float, pitch: float, internal: bool, method: str
) -> list[tuple[float, float]]:
    """A half circle groove or ridge of radius a quarter pitch (TR178)."""
    rho = pitch / 4.0
    half = major / 2.0
    e = _OVERLAP * pitch

    def arc(centre: float, outward: bool) -> list[tuple[float, float]]:
        sign = 1.0 if outward else -1.0
        return [
            (
                centre + sign * rho * math.sin(math.pi * k / _ARC_STEPS),
                -rho * math.cos(math.pi * k / _ARC_STEPS),
            )
            for k in range(_ARC_STEPS + 1)
        ]

    if method == "cut" and not internal:  # a groove into the shaft from the major
        if face_radius <= half - rho:
            raise FeatureError("the shaft is smaller than the thread root. Use a smaller size.")
        base = max(face_radius, half) + e
        return [(base, -rho), *arc(half, False), (base, rho)]
    if method == "cut":  # a groove into the hole wall out to the major
        if face_radius >= half:
            raise FeatureError("the hole is larger than the thread. Use a larger size.")
        base = min(face_radius, half - rho) - e
        return [(base, -rho), *arc(half - rho, True), (base, rho)]
    if not internal:  # a ridge on the shaft out to the major
        if face_radius >= half:
            raise FeatureError(
                "the shaft is as large as the thread. Use Cut Thread or a larger size."
            )
        base = face_radius - e
        return [(base, -rho), *arc(half - rho, True), (base, rho)]
    if face_radius <= half - rho:
        raise FeatureError(
            "the hole is smaller than the thread crest. Use Cut Thread or a smaller size."
        )
    base = face_radius + e
    return [(base, -rho), *arc(half, False), (base, rho)]


def _with_clearance(
    face_radius: float,
    major: float,
    pitch: float,
    internal: bool,
    method: str,
    form: str,
    clearance: float,
) -> list[tuple[float, float]]:
    """The profile moved by ``clearance`` (see thread_profile)."""
    pts = thread_profile(face_radius, major, pitch, internal, method, form)
    # Cut: the points away from the overlap edge move further into the material.
    # Extruded: the crest points move back toward the face.
    edge = max(r for r, _z in pts) if (method == "cut") != internal else min(r for r, _z in pts)
    sign = 1.0 if internal else -1.0  # a hole's thread grows outward, a shaft's inward
    moved = [(r if abs(r - edge) < 1e-9 else r + sign * clearance, z) for r, z in pts]
    limit = 0.475 * pitch
    out: list[tuple[float, float]] = []
    for i, (r, z) in enumerate(moved):
        if abs(z) <= limit:
            out.append((r, z))
            continue
        # Trim the flank square where it reaches the limit width.
        z_cap = math.copysign(limit, z)

        def crossing(other: tuple[float, float], r: float = r, z: float = z) -> float:
            t = (limit - abs(other[1])) / (abs(z) - abs(other[1]))
            return other[0] + (r - other[0]) * t

        prv, nxt = moved[i - 1], moved[(i + 1) % len(moved)]
        if abs(prv[1]) < limit:
            out.append((crossing(prv), z_cap))
        out.append((r, z_cap))
        if abs(nxt[1]) < limit:
            out.append((crossing(nxt), z_cap))
    clean: list[tuple[float, float]] = []
    for p in out:
        if not clean or abs(clean[-1][0] - p[0]) > 1e-9 or abs(clean[-1][1] - p[1]) > 1e-9:
            clean.append(p)
    return clean


def thread_profile(
    face_radius: float,
    major: float,
    pitch: float,
    internal: bool,
    method: str,
    form: str = "iso",
    clearance: float = 0.0,
) -> list[tuple[float, float]]:
    """The thread section as (radius, axial offset) points, centred on offset 0.

    Cut threads are V grooves into the material; extruded threads are ridges with
    a flat crest standing off the face. ``form`` "printable" uses 45 degree flanks
    and "round" a half circle (TR178). Raises FeatureError when the face does not
    suit the thread. ``clearance`` moves the thread's surface by that much into the
    material (cut) or back from it (extruded); a groove that would get wider than
    the pitch is trimmed square at 95 percent of it.
    """
    if clearance > 0:
        return _with_clearance(face_radius, major, pitch, internal, method, form, clearance)
    if form == "round":
        return _round_profile(face_radius, major, pitch, internal, method)
    if form in _FLAT_FORMS:  # TR254 (D1510)
        return _flat_form(face_radius, major, pitch, internal, method, form)
    tan_half = 1.0 if form == "printable" else _TAN30
    h = pitch / (2.0 * tan_half)
    half = major / 2.0
    e = _OVERLAP * pitch
    if method == "cut" and not internal:
        apex = half - 7.0 * h / 8.0
        base = max(face_radius, half) + e
        w = (base - apex) * tan_half
        if face_radius <= apex:
            raise FeatureError("the shaft is smaller than the thread root. Use a smaller size.")
        pts = [(apex, 0.0), (base, w), (base, -w)]
    elif method == "cut":
        apex = half + h / 8.0
        base = min(face_radius, half - 5.0 * h / 8.0) - e
        w = (apex - base) * tan_half
        if face_radius >= apex:
            raise FeatureError("the hole is larger than the thread. Use a larger size.")
        pts = [(apex, 0.0), (base, w), (base, -w)]
    elif not internal:
        apex = half + h / 8.0
        base = face_radius - e
        if face_radius >= half:
            raise FeatureError(
                "the shaft is as large as the thread. Use Cut Thread or a larger size."
            )
        w_base, w_top = (apex - base) * tan_half, (apex - half) * tan_half
        pts = [(base, -w_base), (half, -w_top), (half, w_top), (base, w_base)]
    else:
        apex = half - 7.0 * h / 8.0
        crest = half - 5.0 * h / 8.0
        base = face_radius + e
        if face_radius <= crest:
            raise FeatureError(
                "the hole is smaller than the thread crest. Use Cut Thread or a smaller size."
            )
        w_base, w_top = (base - apex) * tan_half, (crest - apex) * tan_half
        pts = [(base, -w_base), (crest, -w_top), (crest, w_top), (base, w_base)]
    widest = 2.0 * max(abs(z) for _r, z in pts)
    if widest >= pitch * 0.999:
        if not internal and face_radius > half:
            # The usual cause: a size much smaller than the shaft (D589).
            raise FeatureError(
                f"the shaft ({2 * face_radius:.2f} mm across) is larger than the thread "
                f"({major:.2f} mm). Choose the size that matches the shaft."
            )
        if internal and face_radius < half - 5.0 * h / 8.0:
            raise FeatureError(
                f"the hole ({2 * face_radius:.2f} mm across) is too small for the thread "
                f"({major:.2f} mm). Choose the size that matches the hole."
            )
        raise FeatureError("the thread profile is wider than the pitch. Check the size and pitch.")
    return pts


def _frame_x(direction: Vec3, angle: float) -> Vec3:
    """A unit vector square to ``direction``, turned by ``angle`` about it."""
    d = direction
    other = (1.0, 0.0, 0.0) if abs(d[0]) < 0.9 else (0.0, 1.0, 0.0)
    along = sum(o * dd for o, dd in zip(other, d, strict=True))
    x = _add(other, d, -along)
    n = math.sqrt(sum(c * c for c in x))
    x = (x[0] / n, x[1] / n, x[2] / n)
    y = (d[1] * x[2] - d[2] * x[1], d[2] * x[0] - d[0] * x[2], d[0] * x[1] - d[1] * x[0])
    c, s = math.cos(angle), math.sin(angle)
    return (x[0] * c + y[0] * s, x[1] * c + y[1] * s, x[2] * c + y[2] * s)


def helical_solid(
    origin: Vec3,
    direction: Vec3,
    x_dir: Vec3,
    profile: list[tuple[float, float]],
    radius: float,
    lead: float,
    length: float,
    left: bool,
    taper: float = 0.0,
) -> TopoDS_Shape:
    """Sweep ``profile`` along a helix about the axis (origin, direction).

    The helix is exact (a line on a cylinder) and the sweep uses the kernel's
    corrected Frenet frame, which keeps the section square to a helix (D315).
    ``taper`` (TR145, D1917) is the half angle of a cone the helix runs on instead,
    positive when the radius grows along ``direction``.
    """
    ax3 = gp_Ax3(gp_Pnt(*origin), gp_Dir(*direction), gp_Dir(*x_dir))
    turn = 2.0 * math.pi
    if abs(taper) > 1e-9:
        from OCP.Geom import Geom_ConicalSurface

        # v runs along the cone's side: each turn rises one lead along the axis.
        surface: Any = Geom_ConicalSurface(ax3, taper, radius)
        rise = lead / math.cos(taper)
    else:
        surface = Geom_CylindricalSurface(ax3, radius)
        rise = lead
    line = Geom2d_Line(gp_Pnt2d(0.0, 0.0), gp_Dir2d(-turn if left else turn, rise))
    end = length / lead * math.hypot(turn, rise)
    edge = BRepBuilderAPI_MakeEdge(line, surface, 0.0, end).Edge()
    BRepLib.BuildCurves3d_s(edge, 1e-6)
    pipe = BRepOffsetAPI_MakePipeShell(BRepBuilderAPI_MakeWire(edge).Wire())
    pipe.SetMode(True)
    poly = BRepBuilderAPI_MakePolygon()
    for r, z in profile:
        poly.Add(gp_Pnt(*_add(_add(origin, x_dir, r), direction, z)))
    poly.Close()
    pipe.Add(poly.Wire(), False, False)
    pipe.Build()
    if not pipe.IsDone() or not pipe.MakeSolid():
        raise FeatureError("the thread could not be swept. Check the size and pitch.")
    return right_side_out(pipe.Shape())  # inside out (D607), turned, not flagged (D1049)


def _removed_volume(body: TopoDS_Shape, result: TopoDS_Shape) -> float:
    """The volume a cut took from ``body``: the bodies it changed, before less after.

    Bodies the cut left as they were (the nut beside a bolt) count the same on both
    sides, so they are not measured (D2661); nor is a body measured again that the
    rebuild measured already (``volume_of`` inside ``measured_volumes``).
    """
    before, after = solids(body), solids(result)
    if not before or not after:
        return volume_of(body) - volume_of(result)
    gone = [s for s in before if not any(s.IsSame(t) for t in after)]
    made = [t for t in after if not any(t.IsSame(s) for s in before)]
    return sum(volume_of(s) for s in gone) - sum(volume_of(t) for t in made)


def check_thread_cut(
    owner: str, body: TopoDS_Shape, tool: TopoDS_Shape, result: TopoDS_Shape, strict: bool = True
) -> None:
    """Raise when a thread cut did not remove what the thread overlaps (D607).

    The kernel can report success for a helical cut that removed nothing or
    the wrong material, for example when the thread runs out of the far end.
    """
    from fdcad.core.occ import BRepAlgoAPI_Common

    removed = _removed_volume(body, result)
    common = BRepAlgoAPI_Common(body, tool)
    overlap = volume_of(common.Shape()) if common.IsDone() else 0.0
    if overlap <= 0.0:
        # The kernel's common of a helix can come back empty on some builds (Windows,
        # turned shaft) although the cut is right; then only the removal is checked.
        overlap = removed
    least = 0.01 * abs(volume_of(tool))  # the tool is built to overlap the part
    # A thread with a run out is two helical solids that touch, whose common the kernel
    # measures loosely, so only the removal itself is checked then (TR254, D1918).
    mismatch = strict and abs(removed - overlap) > 1e-2 * max(overlap, 1.0)
    if removed <= least or mismatch:
        raise FeatureError(
            f"{owner} failed: the kernel could not cut the thread cleanly. Change the length "
            "slightly, or end the thread before the far end of the face."
        )


def thread_tools(
    start: Vec3,
    direction: Vec3,
    face_radius: float,
    major: float,
    pitch: float,
    length: float,
    internal: bool,
    method: str = "cut",
    starts: int = 1,
    left: bool = False,
    start_angle: float = 0.0,
    form: str = "iso",
    clearance: float = 0.0,
    taper: float = 0.0,
    profile: list[tuple[float, float]] | None = None,
    finish: str = "square",
) -> list[TopoDS_Shape]:
    """One helical solid per start. Cut threads begin a pitch before ``start`` so the
    groove runs out of the open end cleanly. ``taper`` (TR145, D1917): the half angle
    of a tapered thread, the radius growing along ``direction`` when positive."""
    if length <= 0:
        raise FeatureError("the thread length must be greater than zero. Enter a longer length.")
    lead = pitch * starts
    if length / lead > MAX_TURNS:
        raise FeatureError(
            f"the thread has more than {MAX_TURNS} turns. Make it shorter or use a cosmetic thread."
        )
    if profile is None:
        profile = thread_profile(face_radius, major, pitch, internal, method, form, clearance)
    run_in = pitch if method == "cut" else 0.0
    origin = _add(start, direction, -run_in)
    # A tapered thread's helix starts where the cone is, a run in before the start.
    shift = -run_in * math.tan(taper)
    profile = [(r + shift, z) for r, z in profile]
    run = 0.0
    if finish != "square" and abs(taper) < 1e-9:  # TR254 (D1918): the last part runs out
        radii = [r for r, _z in profile]
        near, far = min(radii), max(radii)
        deep = near if abs(near - face_radius) > abs(far - face_radius) else far
        depth = abs(deep - face_radius)
        run = min(depth if finish == "chamfer" else pitch, 0.9 * length)
    out = []
    for k in range(starts):
        angle = start_angle + 2.0 * math.pi * k / starts
        x_dir = _frame_x(direction, angle)
        out.append(
            helical_solid(
                origin,
                direction,
                x_dir,
                profile,
                face_radius + shift,
                lead,
                length - run + run_in,
                left,
                taper,
            )
        )
        if run > 0 and abs(taper) < 1e-9:
            # The run out: the same section on a cone that takes it out of the material.
            turned = 2.0 * math.pi * (length - run + run_in) / lead
            x_end = _frame_x(direction, angle + (-turned if left else turned))
            out_angle = math.atan2(depth, run) * (1.0 if deep < face_radius else -1.0)
            out.append(
                helical_solid(
                    _add(origin, direction, length - run + run_in),
                    direction,
                    x_end,
                    profile,
                    face_radius,
                    lead,
                    run,
                    left,
                    out_angle,
                )
            )
    return out


def sketch_profile(
    feature: Feature, ctx: BuildContext, face_radius: float, internal: bool, method: str
) -> list[tuple[float, float]]:
    """The thread section from a sketch (TR254, D1918): ``refs.profile_sketch`` holds one
    closed region; its X runs along the axis and its Y is the depth into the material
    (cut) or the height off the face (extruded). The region is centred along the axis."""
    from OCP.BRepAdaptor import BRepAdaptor_CompCurve
    from OCP.BRepTools import BRepTools
    from OCP.GCPnts import GCPnts_QuasiUniformDeflection

    ref = feature.refs.get("profile_sketch")
    fid = ref.get("feature") if isinstance(ref, dict) else None
    out = ctx.result(fid).sketch if isinstance(fid, str) else None
    if out is None or out.profile is None or len(out.profile.faces) != 1:
        raise FeatureError(
            f"{feature.name}: a sketch profile needs a sketch with one closed region. Choose "
            "the sketch, or close it."
        )
    wire = BRepTools.OuterWire_s(out.profile.faces[0])
    sampler = GCPnts_QuasiUniformDeflection(BRepAdaptor_CompCurve(wire), 0.005)
    flat = []
    for i in range(1, sampler.NbPoints()):
        p = sampler.Value(i)
        u, v, _w = out.plane.to_2d(p.X(), p.Y(), p.Z())
        flat.append((u, v))
    if len(flat) < 3:
        raise FeatureError(f"{feature.name}: the profile sketch is too small. Draw it larger.")
    mid = (min(u for u, _v in flat) + max(u for u, _v in flat)) / 2
    low = min(v for _u, v in flat)
    # Into the material: inward on a shaft cut or a hole's ridge, outward otherwise.
    inward = (method == "cut") != internal
    sign = -1.0 if inward else 1.0
    # Points on the face line reach a little past it, so the cut opens cleanly.
    over = 0.02 + 0.05 * (max(v for _u, v in flat) - low)
    return [
        (face_radius + sign * ((v - low) if v - low > 1e-6 else -over), u - mid) for u, v in flat
    ]


def _value(feature: Feature, name: str, default: float) -> float:
    value = feature.params.get(name)
    return value.value if isinstance(value, Param) else default


def clearance_of(feature: Feature, internal: bool | None = None) -> float:
    """The clearance per side in mm: typed, else from the fit preset (TR178) plus half
    the thread class's allowance (TR393, D1507). ``internal`` checks the class fits."""
    typed = feature.params.get("clearance")
    if isinstance(typed, Param):
        return typed.value
    from fdcad.core.features.hole import fit_extra

    return fit_extra(feature) / 2.0 + class_allowance(
        feature, _value(feature, "pitch", 0.0), _value(feature, "diameter", 0.0), internal
    )


def class_allowance(
    feature: Feature, pitch: float, major: float, internal: bool | None = None
) -> float:
    """Half the diameter allowance of ``thread_class`` (TR393, D1507), 0 without one."""
    from fdcad.core.features import thread_class

    name = str(feature.params.get("thread_class", "none") or "none")
    if name == "none":
        return 0.0
    if name not in thread_class.CLASSES:
        raise FeatureError(
            f"{feature.name}: '{name}' is not a thread class. Choose one from the list."
        )
    if internal is not None and thread_class.is_internal(name) != internal:
        if internal:
            raise FeatureError(
                f"{feature.name}: {name} is a class for external threads, but this thread "
                "is in a hole. Choose a class for internal threads, such as 6H or 2B."
            )
        raise FeatureError(
            f"{feature.name}: {name} is a class for internal threads, but this thread is "
            "on a shaft. Choose a class for external threads, such as 6g or 2A."
        )
    return thread_class.allowance(name, pitch, major) / 2.0


def lead_in_tool(
    start: Vec3, direction: Vec3, major: float, root: float, internal: bool
) -> TopoDS_Shape:
    """The 45 degree cone that trims the start of a thread (TR178)."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeRevol
    from OCP.gp import gp_Ax1

    from fdcad.core.features.hole import _wire_face

    half = major / 2.0
    big = half + 1.0
    if internal:  # a countersink out to the major
        section = [(0.0, -1.0), (big, -1.0), (root, half - root), (0.0, half - root)]
    else:  # a chamfer down to the root
        section = [(root, -1.0), (big + 1.0, -1.0), (big + 1.0, big + 1.0 - root), (root, 0.0)]
    x = _frame_x(direction, 0.0)
    pts = [_add(_add(start, x, r), direction, z) for r, z in section]
    face, _edges = _wire_face(pts)
    maker = BRepPrimAPI_MakeRevol(face, gp_Ax1(gp_Pnt(*start), gp_Dir(*direction)), 2 * math.pi)
    maker.Build()
    if not maker.IsDone():
        raise FeatureError("the lead in could not be made. Untick Lead In.")
    return maker.Shape()


@register
class ModeledThread(FeatureType):
    """A real helical thread on a hole or shaft."""

    type_name = "modeled_thread"
    makes_solid = True
    params = (
        ParamSpec("diameter", kind=Kind.LENGTH),
        ParamSpec("pitch", kind=Kind.LENGTH),
        ParamSpec("method", choices=("cut", "extrude"), default="cut"),
        ParamSpec("hand", choices=("right", "left"), default="right"),
        ParamSpec("end_condition", choices=("blind", "revolutions", "up_to"), default="blind"),
        ParamSpec("form", choices=FORMS, optional=True),  # TR178
        ParamSpec("end_finish", choices=END_FINISHES, optional=True),  # TR254 (D1918)
        ParamSpec("relief", default=False, optional=True),  # TR256 (D1922)
    )

    def kind_of(self, name: str) -> Kind | None:
        """Lengths, the start angle and the two counts."""
        if name in ("length", "offset", "clearance", "fit_tolerance"):
            return Kind.LENGTH
        if name in ("start_angle", "taper_angle"):  # TR145 (D1917)
            return Kind.ANGLE
        if name in ("revolutions", "starts"):
            return Kind.NUMBER
        return super().kind_of(name)

    def _length(
        self, feature: Feature, ctx: BuildContext, start: Vec3, direction: Vec3
    ) -> tuple[float, list[Issue]]:
        end = feature.params.get("end_condition", "blind")
        pitch = self.number(feature, "pitch")
        starts = max(1, round(_value(feature, "starts", 1.0)))
        if end == "revolutions":
            turns = _value(feature, "revolutions", 0.0)
            if turns <= 0:
                raise FeatureError(
                    f"{feature.name}: the number of turns must be above zero. Enter more turns."
                )
            return turns * pitch * starts, []
        if end == "up_to":
            point, issues = self._up_to_point(feature, ctx)
            rel = (point[0] - start[0], point[1] - start[1], point[2] - start[2])
            length = sum(r * d for r, d in zip(rel, direction, strict=True))
            if length <= 1e-6:
                raise FeatureError(
                    f"{feature.name}: the Up to item is behind the start edge. "
                    "Pick an item along the thread or use Reverse."
                )
            return length, issues
        length = _value(feature, "length", 0.0)
        if length <= 0:
            raise FeatureError(
                f"{feature.name}: the thread length must be greater than zero. "
                "Enter a longer length."
            )
        return length, []

    def _up_to_point(self, feature: Feature, ctx: BuildContext) -> tuple[Vec3, list[Issue]]:
        ref = feature.refs.get("up_to")
        if isinstance(ref, list) and ref:
            ref = ref[0]
        if not isinstance(ref, dict):
            raise FeatureError(f"{feature.name}: Up to Selection needs an item. Pick one.")
        if "feature" in ref and "kind" not in ref:
            plane = ctx.result(str(ref["feature"])).plane
            if plane is None:
                raise FeatureError(
                    f"{feature.name}: the Up to item is not a plane. Pick a plane or flat face."
                )
            return plane.origin, []
        from fdcad.core.naming.names import centroid
        from fdcad.core.naming.resolve import resolve_face, resolve_vertex

        body = require_body(feature, ctx)
        if ref.get("kind") == "vertex":
            from OCP.BRep import BRep_Tool

            vertex, issues = resolve_vertex(body, ref, feature.name)
            p = BRep_Tool.Pnt_s(vertex)
            return (p.X(), p.Y(), p.Z()), issues
        face, issues = resolve_face(body, ref, feature.name)
        return centroid(face), issues

    def _tools(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[NamedShape, list[Issue], TopoDS_Shape | None]:
        body = require_body(feature, ctx)
        picked, issues = resolve_edges(feature, ctx, "edge")
        found = cylinder_at(body.shape, picked[0][1])
        if found is None:
            raise FeatureError(
                f"{feature.name}: the picked edge is not the round end of a hole or shaft. "
                "Pick a round edge of a cylindrical face."
            )
        _face, start, direction, radius, internal, _face_length = found
        if feature.params.get("reverse") is True:
            direction = (-direction[0], -direction[1], -direction[2])
        offset = _value(feature, "offset", 0.0)
        start = _add(start, direction, offset)
        length, more = self._length(feature, ctx, start, direction)
        if feature.params.get("keep_length", True) is False:
            length -= offset
        major = self.number(feature, "diameter")
        pitch = self.number(feature, "pitch")
        if major <= 0 or pitch <= 0:
            raise FeatureError(
                f"{feature.name}: the diameter and pitch must be greater than zero. "
                "Enter larger values."
            )
        starts = round(_value(feature, "starts", 1.0))
        if not 1 <= starts <= 4:
            raise FeatureError(f"{feature.name}: use 1 to 4 starts.")
        clearance = clearance_of(feature, internal)
        if clearance < 0 or 2 * clearance >= pitch:
            raise FeatureError(
                f"{feature.name}: the clearance must be from 0 to less than half the pitch. "
                "Type a smaller clearance."
            )
        form = str(feature.params.get("form", "iso"))
        method = str(feature.params.get("method", "cut"))
        taper = _value(feature, "taper_angle", 0.0)  # TR145 (D1917)
        if not 0.0 <= taper < math.radians(10.0):
            raise FeatureError(
                f"{feature.name}: the taper must be from 0 to less than 10 degrees. Enter a "
                "smaller taper, such as 1.79 degrees for NPT."
            )
        # A hole narrows going in and a shaft widens away from its end, as pipe threads do.
        taper = -taper if internal else taper
        finish = str(feature.params.get("end_finish", "square"))  # TR254 (D1918)
        own = None
        try:
            if form == "sketch":
                own = sketch_profile(feature, ctx, radius, internal, method)
            shapes = thread_tools(
                start,
                direction,
                radius,
                major,
                pitch,
                length,
                internal,
                method,
                starts,
                feature.params.get("hand") == "left",
                _value(feature, "start_angle", 0.0),
                form,
                clearance,
                taper,
                own,
                finish,
            )
            lead = None
            if feature.params.get("lead_in") is True:
                profile = own or thread_profile(
                    radius, major, pitch, internal, method, form, clearance
                )
                radii = [r for r, _z in profile]
                if internal:
                    root = min(radius, min(radii))
                else:
                    root = max(min(radii), 0.0) if method == "cut" else radius
                lead = lead_in_tool(start, direction, major, root, internal)
        except FeatureError as exc:
            raise FeatureError(f"{feature.name}: {exc}") from exc
        shape = shapes[0] if len(shapes) == 1 else compound(shapes)
        named = NamedShape(shape, restrict([], shape, f"{feature.id}/thread"))
        return named, issues + more, lead

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Cut the thread into the part or add it."""
        if ctx.simplify_threads:  # TR347 (D1921): a cosmetic mark while editing
            return self._simplified(feature, ctx)
        tool, issues, lead = self._tools(feature, ctx)
        operation = "cut" if feature.params.get("method", "cut") == "cut" else "boss"
        start_body = ctx.body
        if lead is not None and ctx.body is not None:
            # The cone goes first: cutting it after the thread leaves invalid faces.
            cone = NamedShape(lead, restrict([], lead, f"{feature.id}/lead_in"))
            start_body = combine(feature.id, feature.name, ctx.body, cone, "cut")
        try:
            # A cut is checked below against what the thread overlaps, with its own
            # message (D607), so the point check of D2619 is left to bosses.
            result = combine(
                feature.id, feature.name, start_body, tool, operation,
                check_tools=operation != "cut",
            )  # fmt: skip
        except FeatureError:
            raise
        except Exception as exc:
            raise FeatureError(
                f"{feature.name} failed: the kernel could not join the thread to the part. "
                "Change the length or start slightly."
            ) from exc
        if operation == "cut" and start_body is not None:
            strict = feature.params.get("end_finish", "square") == "square"
            check_thread_cut(feature.name, start_body.shape, tool.shape, result.shape, strict)
        if feature.params.get("relief") is True:  # TR256 (D1922): a run out groove
            groove = self._relief(feature, ctx)
            named = NamedShape(groove, restrict([], groove, f"{feature.id}/relief"))
            result = combine(feature.id, feature.name, result, named, "cut")
        issues = issues + check_result(feature.id, feature.name, ctx.body, result, None)
        return FeatureResult(body=result, issues=issues)

    def _relief(self, feature: Feature, ctx: BuildContext) -> TopoDS_Shape:
        """The thread run out groove (undercut) at the thread's end (TR256, D1922),
        sized from the pitch (``thread_relief``). Its far side is where the thread ends."""
        body = require_body(feature, ctx)
        picked, _issues = resolve_edges(feature, ctx, "edge")
        found = cylinder_at(body.shape, picked[0][1])
        if found is None:
            raise FeatureError(
                f"{feature.name}: the picked edge is not the round end of a hole or shaft. "
                "Pick a round edge of a cylindrical face."
            )
        _face, start, direction, radius, internal, _face_length = found
        if feature.params.get("reverse") is True:
            direction = (-direction[0], -direction[1], -direction[2])
        start = _add(start, direction, _value(feature, "offset", 0.0))
        length, _more = self._length(feature, ctx, start, direction)
        major, pitch = self.number(feature, "diameter"), self.number(feature, "pitch")
        from fdcad.core.features.thread_relief import groove_ring, groove_size

        across, width = groove_size(major, pitch, internal)
        if width >= length:
            raise FeatureError(
                f"{feature.name}: the run out groove ({width:g} mm) is as long as the thread. "
                "Make the thread longer, or turn off Thread Relief."
            )
        inner, outer = (radius - 1.0, across / 2.0) if internal else (across / 2.0, radius + 1.0)
        if inner <= 0:
            raise FeatureError(
                f"{feature.name}: the run out groove would reach the axis. Use a finer pitch, or "
                "turn off Thread Relief."
            )
        return groove_ring(start, direction, inner, outer, length - width, length)

    def _simplified(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """The part unchanged, with the thread drawn as a cosmetic mark (TR347, D1921)."""
        from fdcad.core.features.base import ThreadMark
        from fdcad.core.features.cosmetic_thread import thread_label

        body = require_body(feature, ctx)
        picked, issues = resolve_edges(feature, ctx, "edge")
        found = cylinder_at(body.shape, picked[0][1])
        if found is None:
            raise FeatureError(
                f"{feature.name}: the picked edge is not the round end of a hole or shaft. "
                "Pick a round edge of a cylindrical face."
            )
        _face, start, direction, radius, internal, _face_length = found
        if feature.params.get("reverse") is True:
            direction = (-direction[0], -direction[1], -direction[2])
        start = _add(start, direction, _value(feature, "offset", 0.0))
        length, more = self._length(feature, ctx, start, direction)
        major, pitch = self.number(feature, "diameter"), self.number(feature, "pitch")
        size = str(feature.params.get("size", ""))
        mark = ThreadMark(
            start,
            direction,
            major,
            pitch,
            length,
            2 * radius,
            internal,
            thread_label(size, major, pitch),
        )
        return FeatureResult(body=body, issues=issues + more, threads=[mark])

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The thread solid, for the preview."""
        tool, _issues, _lead = self._tools(feature, ctx)
        return tool


def hole_threads(
    feature: Feature, body: NamedShape, places: list[Any], wall_diameter: float
) -> NamedShape:
    """Cut a modelled thread into every tapped hole, in one boolean (P4.3, PLAN 5A.5)."""
    from fdcad.core.features.hole import cut_all

    pitch = _value(feature, "pitch", 0.0)
    major = _value(feature, "thread_diameter", wall_diameter + 1.0825 * pitch)
    length = _value(feature, "thread_depth", 0.0)
    extra = class_allowance(feature, pitch, major, True)  # TR393 (D1507)
    tools: list[NamedShape] = []
    for place in places:
        try:
            for shape in thread_tools(
                place.origin,
                place.direction,
                wall_diameter / 2,
                major,
                pitch,
                length,
                True,
                clearance=extra,
            ):
                prefix = f"{feature.id}/hole/{place.point}/thread"
                tools.append(NamedShape(shape, restrict([], shape, prefix)))
        except FeatureError as exc:
            raise FeatureError(f"{feature.name}: {exc}") from exc
    if not tools:
        return body
    result = cut_all(feature, body, tools)
    if solids(result.shape):
        whole = compound([t.shape for t in tools]) if len(tools) > 1 else tools[0].shape
        check_thread_cut(feature.name, body.shape, whole, result.shape)
    if not solids(result.shape):
        raise FeatureError(
            f"{feature.name}: the threads remove the whole part. "
            "Reduce the thread depth or pick another face."
        )
    return result
