"""Extrude picks the operation (TR334, D2110).

With ``auto_operation`` the extrusion chooses Boss, Cut or New Body from where its
solid sits against the part: mostly inside the part (more than half of its volume)
is a cut; touching the part or partly inside it is a boss joined to it; apart from
it is a new body. ``auto_alternate`` takes the second choice instead, for when the
first is not what was meant: a cut becomes a boss, a boss becomes a cut and a new
body becomes a cut.
The choice is made on every rebuild, so it follows the part, and is reported in the
result (``extras["operation"]``) for the panel. Kernel work: rebuild thread only.
"""

from __future__ import annotations

import copy
from typing import Any

from fdcad.core.document.model import Feature

#: Share of the extrusion's volume inside the part above which it is a cut.
INSIDE_SHARE = 0.5
#: Gaps up to this (mm) count as touching.
TOUCH = 1e-4
CHOICES = ("boss", "cut", "new_body")


def wanted(feature: Feature) -> bool:
    """True when the feature chooses its own operation."""
    return feature.params.get("auto_operation") is True


def choose(tool_shape: Any, body_shape: Any) -> list[str]:
    """The operations in order of fit for a tool solid against the part."""
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape

    from fdcad.core.features.solids import volume_of
    from fdcad.core.occ import BRepAlgoAPI_Common

    if body_shape is None:
        return ["new_body", "boss"]
    whole = volume_of(tool_shape)
    common = BRepAlgoAPI_Common(tool_shape, body_shape)
    inside = volume_of(common.Shape()) if common.IsDone() else 0.0
    if whole > 0 and inside / whole > INSIDE_SHARE:
        return ["cut", "boss"]
    if inside > 0:
        return ["boss", "cut"]
    gap = BRepExtrema_DistShapeShape(tool_shape, body_shape)
    if gap.IsDone() and gap.Value() <= TOUCH:
        return ["boss", "cut"]
    return ["new_body", "cut"]


def resolved(feature: Feature, tool_shape: Any, body_shape: Any) -> tuple[Feature, str]:
    """A copy of the feature with the chosen operation set, and the choice."""
    order = choose(tool_shape, body_shape)
    pick = order[1] if feature.params.get("auto_alternate") is True else order[0]
    out = copy.deepcopy(feature)
    out.params["operation"] = "cut" if pick == "cut" else "boss"
    if pick == "new_body":
        out.params["merge"] = False
    elif pick == "boss":
        out.params["merge"] = True
    return out, pick
