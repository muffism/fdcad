"""Show Sections: one section a sweep or loft would make, by number (TR139 item 2,
D1909), to find where it goes wrong.

``show_section`` (a whole number, 0 for none) picks section ``k`` of ``COUNT``, evenly
spaced from the start (1) to the end (``COUNT``). A sweep's section is its profile
carried along the path with the least turning, worked out without the kernel's
sweep, so it shows even when the sweep fails; a loft's is a slice of the built loft
square to the line from its first profile's centre to its last. The section is drawn
as reference geometry (``extras["reference"]``) with a report line.
"""

from __future__ import annotations

from typing import Any

from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Vec
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import BuildContext, FeatureError

#: How many sections Show Sections steps through, start and end included.
COUNT = 11


def section_number(feature: Feature) -> int:
    """The section to show, 0 for none. Raises FeatureError when it is out of range."""
    value = feature.params.get("show_section")
    if not isinstance(value, Param):
        return 0
    k = round(value.value)
    if abs(k - value.value) > 1e-9 or not 0 <= k <= COUNT:
        raise FeatureError(
            f"{feature.name}: the section to show must be a whole number from 0 to {COUNT}. "
            "Enter a section number, or 0 for none."
        )
    return int(k)


def sweep_section(feature: Feature, ctx: BuildContext, k: int) -> tuple[TopoDS_Shape, str]:
    """Section ``k`` of a sweep: the profile's outlines moved to that station."""
    from fdcad.core.features.solids import compound
    from fdcad.core.features.sweep import (
        Sweep,
        _face_profile,
        _paths_from_plane,
        _sketch_output,
        _wires,
        path_wire,
    )
    from fdcad.core.features.sweep_guides import _carried, _rigid, _stations

    path, _issues = path_wire(feature, ctx)
    kind = feature.params.get("profile_type")
    if kind == "circular":
        profile, _p, _n, up = Sweep._circle(feature, path)
    elif kind == "face":
        profile, point, normal, up = _face_profile(feature, ctx)
        path = _paths_from_plane(feature, path, point, normal)[0]
    else:
        out = _sketch_output(feature, ctx, "profile", "profile")
        if out.profile is None:
            raise FeatureError(f"{feature.name}: {out.profile_error}")
        profile, up = out.profile, gp_Vec(*out.plane.x_dir)
        path = _paths_from_plane(feature, path, out.plane.origin, out.plane.normal)[0]
    stations = _stations(path)
    p0, t0 = stations[0]
    x0 = up.Subtracted(t0.Multiplied(up.Dot(t0)))
    if x0.Magnitude() < 1e-9:
        x0 = t0.Crossed(gp_Vec(0, 0, 1))
    frames = _carried(stations, x0.Normalized())
    index = round((k - 1) * (len(stations) - 1) / (COUNT - 1))
    p, t = stations[index]
    move = _rigid(p0, t0, frames[0], p, t, frames[index])
    wires: list[Any] = []
    for face in profile.faces:
        outer, holes = _wires(face)
        wires += [BRepBuilderAPI_Transform(w, move, True).Shape() for w in [outer, *holes]]
    share = (k - 1) / (COUNT - 1)
    return compound(wires), f"Section {k} of {COUNT}, {share:.0%} along the path."


def loft_section(feature: Feature, body: Any, ctx: BuildContext, k: int) -> tuple[Any, str]:
    """Section ``k`` of a built loft: a slice square to the line through the centres of
    its first and last profiles."""
    from OCP.gp import gp_Dir, gp_Pln, gp_Pnt

    from fdcad.core.features.loft import sections
    from fdcad.core.occ import BRepAlgoAPI_Section

    secs, _issues = sections(feature, ctx)
    a, b = secs[0].centre(), secs[-1].centre()
    axis = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    if sum(c * c for c in axis) < 1e-12:
        raise FeatureError(
            f"{feature.name}: the first and last profiles share a centre, so there is no line "
            "to step along. Set Show section to 0."
        )
    share = (k - 1) / (COUNT - 1)
    at = gp_Pnt(*(a[i] + axis[i] * share for i in range(3)))
    cut = BRepAlgoAPI_Section(body, gp_Pln(at, gp_Dir(*axis)))
    cut.Build()
    return cut.Shape(), f"Section {k} of {COUNT}, {share:.0%} of the way to the last profile."


__all__ = ["COUNT", "loft_section", "section_number", "sweep_section"]
