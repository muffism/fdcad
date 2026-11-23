"""A sweep along a helix refuses a profile wider than the pitch (D2649).

Bug hunt round 10b O6: a profile wider than the helix pitch makes each turn run into
the next, and the sweep reported OK. A full self intersection check took minutes,
so this is the cheap check the hunt asked for: the width of a round profile along
the helix axis against the pitch. It only refuses when the turns surely overlap.
"""

from __future__ import annotations

import math

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GeomAbs import GeomAbs_Circle
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import BuildContext, FeatureError
from fdcad.core.sketch.profiles import Profile


def check_turns(feature: Feature, ctx: BuildContext, profile: Profile) -> None:
    """Raise FeatureError when the swept profile is wider than the helix pitch.

    Only a straight helix of constant pitch is checked, with a round profile (the
    circular profile, or a sketch of one circle) that does not scale along it; every
    other path and profile builds as before.
    """
    from fdcad.core.features.helix import Helix, Placement

    ref = feature.refs.get("path")
    if feature.refs.get("path_edges") or not isinstance(ref, dict) or "feature" not in ref:
        return
    try:
        helix = ctx.document.feature(str(ref["feature"]))
    except KeyError:
        return
    params = helix.params
    taper = params.get("taper_angle")
    if (
        helix.type != "helix"
        or params.get("pitch_type") == "variable"
        or params.get("definition") == "spiral"
        or params.get("ends") == "closed"
        or (isinstance(taper, Param) and abs(taper.value) > 1e-12)
        or feature.params.get("scale_start") is not None
        or feature.params.get("scale_end") is not None
    ):
        return
    try:
        pitch, turns = Helix().sizes(helix)
        place = Placement(helix, ctx)
    except FeatureError:
        return  # the helix reports its own error
    if turns <= 1 + 1e-9 or place.radius <= 0:
        return
    if feature.params.get("profile_type") == "circular":
        diameter = feature.params.get("diameter")
        if not isinstance(diameter, Param):
            return
        # The cut through the axis of a round tube at the helix's lead angle is an
        # ellipse, longer along the axis than the tube is wide.
        lead = math.atan2(pitch, 2 * math.pi * place.radius)
        width = diameter.value / math.cos(lead)
    else:
        found = _circle_width(profile)
        if found is None:
            return
        width = found
    if width > pitch * (1 + 1e-6):
        raise FeatureError(
            f"{feature.name}: the profile is {width:.3g} mm across along the helix, more "
            f"than its pitch of {pitch:g} mm, so each turn runs into the next. Use a "
            "smaller profile or a larger pitch."
        )


def _circle_width(profile: Profile) -> float | None:
    """The diameter of a profile that is one whole circle, or None for any other.

    Only a round section is measured: a long thin profile set at a slant reaches far
    along the axis yet can pass the next turn, so its reach proves nothing. A sketch
    circle's plane may hold the axis or face along the path; either way the section
    of the swept tube through the axis is at least as long as the circle is wide.
    """
    if len(profile.faces) != 1:
        return None
    explorer = TopExp_Explorer(profile.faces[0], TopAbs_EDGE)
    edges = []
    while explorer.More():
        edges.append(TopoDS.Edge(explorer.Current()))
        explorer.Next()
    if len(edges) != 1:
        return None
    curve = BRepAdaptor_Curve(edges[0])
    if curve.GetType() != GeomAbs_Circle:
        return None
    if abs(curve.LastParameter() - curve.FirstParameter() - 2 * math.pi) > 1e-9:
        return None
    return float(2 * curve.Circle().Radius())
