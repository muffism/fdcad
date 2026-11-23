"""Printing and moulding checks for the Manufacturing Check (TR298, TR299, DECISIONS D805).

Printing (FDM, resin and powder share the checks; their profiles hold the values,
seeded from the printer in use, D801):

- ``slender_pin``: a round post taller than ``pin_ratio`` times its diameter.
- ``thin_wall``: a wall thinner than ``min_wall`` plus 0.2 percent of the part's
  size (big parts need thicker walls, they warp more).
- ``small_hole``: a round hole under ``min_round_hole``.
- ``small_text``: sketch text lower than ``text_nozzles`` nozzle widths.
- ``long_bridge``: a flat face looking straight down, above the bed, wider in
  both directions than ``max_bridge``.
- ``fine_thread``: a modelled thread whose pitch is under ``thread_layers``
  layers: print a pilot hole and tap it, or use an insert.

Moulding (TR298):

- ``thick_wall`` and ``thin_wall``: walls over ``max_wall`` or under ``min_wall``.
- ``wall_change``: two walls of one part that differ by more than
  ``wall_change`` times (uneven cooling).
- ``sharp_inside``: an inside corner between two flat faces with no round.
- ``no_draft``: a flat face along the pull direction (Z), which drags in the mould.
- ``rib_thick``: a rib (a thin wall standing on the part) thicker than
  ``rib_ratio`` of the thickest wall (sink marks).

FDCAD's own general values; advisory only. No Qt; geometry work, so ``check``
runs in a kernel job.
"""

from __future__ import annotations

import math
from typing import Any

from fdcad.core.document.model import Document, Param
from fdcad.core.manufacturing import Finding, _cylinder, _facing_pairs, _flat, _hole_diameters
from fdcad.core.naming.names import NamedShape

PRINT_PROCESSES = ("fdm", "resin", "powder")
#: Extra print rule values every print profile starts with.
PRINT_EXTRA: dict[str, float] = {
    "pin_ratio": 8.0,
    "text_nozzles": 8.0,
    "thread_layers": 4.0,
}
MOULD_EXTRA: dict[str, float] = {"wall_change": 2.0, "rib_ratio": 0.6}


def _value(profile: dict[str, float | str], key: str, default: float) -> float:
    found = profile.get(key, default)
    return float(found) if isinstance(found, (int, float)) else default


def _size(body: NamedShape) -> tuple[float, float]:
    """The part's largest size and its lowest Z."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(body.shape, box, False, False)
    lo, hi = box.CornerMin(), box.CornerMax()
    return max(hi.X() - lo.X(), hi.Y() - lo.Y(), hi.Z() - lo.Z()), lo.Z()


def _convex_posts(body: NamedShape) -> list[tuple[str, float, float]]:
    """Whole round outside faces (posts and pins): (name, diameter, height)."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepTools import BRepTools
    from OCP.GeomAbs import GeomAbs_Cylinder

    out = []
    for name, face in body.faces:
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Cylinder or _cylinder(face) is not None:
            continue  # not a cylinder, or a hole (concave)
        u0, u1, v0, v1 = BRepTools.UVBounds_s(face)
        if u1 - u0 < 2 * math.pi - 1e-6:
            continue
        out.append((name, 2 * surface.Cylinder().Radius(), v1 - v0))
    return out


def printing(doc: Document, body: NamedShape, profile: dict[str, float | str]) -> list[Finding]:
    """The print findings (TR299)."""
    out: list[Finding] = []
    size, floor = _size(body)
    pin_ratio = _value(profile, "pin_ratio", PRINT_EXTRA["pin_ratio"])
    for name, diameter, height in _convex_posts(body):
        if diameter > 0 and height > pin_ratio * diameter + 1e-9:
            out.append(
                Finding(
                    "slender_pin",
                    f"The post {name} is {height:g} mm tall and {diameter:g} mm across, more "
                    f"than {pin_ratio:g} times its width: it may snap or wobble while printing. "
                    "Make it thicker or shorter, or print it lying down.",
                    faces=[name],
                )
            )
    min_wall = _value(profile, "min_wall", 0.8) + 0.002 * size
    for a, b, gap, facing in _facing_pairs(body):
        if not facing and gap < min_wall - 1e-9:
            out.append(
                Finding(
                    "thin_wall",
                    f"The wall between {a} and {b} is {gap:g} mm thick, under {min_wall:.3g} mm "
                    "for a part this size. Make it thicker.",
                    faces=[a, b],
                )
            )
    smallest = _value(profile, "min_round_hole", 1.0)
    for name, _face, diameter, _depth in _hole_diameters(body):
        if diameter < smallest - 1e-9:
            out.append(
                Finding(
                    "small_hole",
                    f"The hole {name} is {diameter:g} mm across, under the {smallest:g} mm this "
                    "printer makes round. Make it larger, or drill it after printing.",
                    faces=[name],
                )
            )
    bridge = _value(profile, "max_bridge", 10.0)
    for name, face in body.faces:
        flat = _flat(face)
        if flat is None or flat[0][2] > -0.999 or flat[1][2] <= floor + 1e-6:
            continue
        width = _narrow_width(face)
        if width > bridge + 1e-9:
            out.append(
                Finding(
                    "long_bridge",
                    f"{name} faces straight down and spans {width:g} mm, more than the "
                    f"{bridge:g} mm this printer bridges. Add a chamfer or supports, or turn "
                    "the part.",
                    faces=[name],
                )
            )
    nozzle = _value(profile, "nozzle", 0.4)
    least_text = _value(profile, "text_nozzles", PRINT_EXTRA["text_nozzles"]) * nozzle
    layers = _value(profile, "thread_layers", PRINT_EXTRA["thread_layers"]) * _value(
        profile, "layer_height", 0.2
    )
    for feature in doc.features:
        if feature.suppressed:
            continue
        if feature.type == "modeled_thread":
            pitch = feature.params.get("pitch")
            if isinstance(pitch, Param) and pitch.value < layers - 1e-9:
                out.append(
                    Finding(
                        "fine_thread",
                        f"{feature.name}: a {pitch.value:g} mm pitch is finer than "
                        f"{layers:g} mm, which these layers print cleanly. Print a pilot hole "
                        "and tap it, or use a threaded insert.",
                        fid=feature.id,
                    )
                )
        if feature.type == "sketch" and isinstance(feature.data, dict):
            heights = [
                float(t.get("height", 5.0))
                for t in feature.data.get("texts", [])
                if isinstance(t, dict)
            ]
            if heights and min(heights) < least_text - 1e-9:
                out.append(
                    Finding(
                        "small_text",
                        f"{feature.name}: text {min(heights):g} mm high is under "
                        f"{least_text:g} mm, too small for the nozzle to draw. Make it larger.",
                        fid=feature.id,
                    )
                )
    return out


def _narrow_width(face: Any) -> float:
    """The smaller of a flat face's two sizes across X and Y (its bounding box)."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(face, box, False, False)
    lo, hi = box.CornerMin(), box.CornerMax()
    return float(min(hi.X() - lo.X(), hi.Y() - lo.Y()))


def moulding(body: NamedShape, profile: dict[str, float | str]) -> list[Finding]:
    """The moulding findings (TR298)."""
    from fdcad.core.features.corner_relief import inside_corner

    out: list[Finding] = []
    least = _value(profile, "min_wall", 1.0)
    most = _value(profile, "max_wall", 4.0)
    walls = [(a, b, gap) for a, b, gap, facing in _facing_pairs(body) if not facing]
    for a, b, gap in walls:
        if gap > most + 1e-9:
            out.append(
                Finding(
                    "thick_wall",
                    f"The wall between {a} and {b} is {gap:g} mm thick, over {most:g} mm: it "
                    "may sink as it cools. Core it out or make it thinner.",
                    faces=[a, b],
                )
            )
        elif gap < least - 1e-9:
            out.append(
                Finding(
                    "thin_wall",
                    f"The wall between {a} and {b} is {gap:g} mm thick, under {least:g} mm: "
                    "the plastic may not fill it. Make it thicker.",
                    faces=[a, b],
                )
            )
    if walls:
        thin = min(walls, key=lambda w: w[2])
        thick = max(walls, key=lambda w: w[2])
        change = _value(profile, "wall_change", MOULD_EXTRA["wall_change"])
        if thin[2] > 0 and thick[2] > change * thin[2] + 1e-9:
            out.append(
                Finding(
                    "wall_change",
                    f"Walls range from {thin[2]:g} to {thick[2]:g} mm, more than {change:g} "
                    "times: they cool unevenly and warp. Keep the walls closer in thickness.",
                    faces=[thin[0], thin[1], thick[0], thick[1]],
                )
            )
        ratio = _value(profile, "rib_ratio", MOULD_EXTRA["rib_ratio"])
        for a, b, gap in walls:
            if gap < thick[2] - 1e-9 and gap > ratio * thick[2] + 1e-9 and _rib(body, a, b):
                out.append(
                    Finding(
                        "rib_thick",
                        f"The rib between {a} and {b} is {gap:g} mm thick, more than "
                        f"{ratio:g} of the {thick[2]:g} mm wall it stands on: it leaves a sink "
                        "mark. Make it thinner.",
                        faces=[a, b],
                    )
                )
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    sharp: list[Any] = []
    ex = TopExp_Explorer(body.shape, TopAbs_EDGE)
    while ex.More():
        edge = TopoDS.Edge(ex.Current())
        ex.Next()
        if inside_corner(body, edge) is not None and not any(edge.IsSame(e) for e in sharp):
            sharp.append(edge)
    if sharp:
        out.append(
            Finding(
                "sharp_inside",
                f"{len(sharp)} inside corners have no round: plastic flows badly round them and "
                "they crack. Round them (half the wall thickness is a good start).",
                edges=sharp,
            )
        )
    upright = []
    for name, face in body.faces:
        flat = _flat(face)
        if flat is not None and abs(flat[0][2]) < 1e-9:
            upright.append(name)
    draft = _value(profile, "min_draft_deg", 1.0)
    if upright:
        out.append(
            Finding(
                "no_draft",
                f"{len(upright)} faces run straight along the pull direction (Z) with no "
                f"draft: they drag in the mould. Add at least {draft:g} "
                "degrees of draft.",
                faces=upright,
            )
        )
    return out


def _rib(body: NamedShape, a: str, b: str) -> bool:
    """True when the wall between faces ``a`` and ``b`` is narrow compared to the part:
    a rib standing on it rather than an outside wall."""
    from fdcad.core.manufacturing import _extent

    faces = dict(body.faces)
    size, _floor = _size(body)
    reach = max(_extent(faces[a], (1.0, 0.0, 0.0)), _extent(faces[a], (0.0, 1.0, 0.0)))
    return reach < 0.9 * size and b in faces
