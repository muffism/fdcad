"""Change a fillet to a chamfer and back (TR134, D994).

A constant size fillet becomes an equal distance chamfer of the same size on the
same edges, and an equal distance chamfer becomes a fillet of that radius. The
picks (edges, faces of edges, features' edges) stay; options only one kind has are
dropped. Other kinds (variable fillets, face fillets, angle or vertex chamfers)
are refused with a message. No Qt.
"""

from __future__ import annotations

import copy
import re

from fdcad.core.document.model import Feature, Param

#: The picks both kinds read the same way.
SHARED_REFS = ("edges", "faces", "features")


class SwapError(ValueError):
    """The feature cannot change kind; the message says why and what to do."""


def can_swap(feature: Feature) -> bool:
    """True for a constant fillet or an equal distance chamfer on edges."""
    try:
        swapped(feature)
    except SwapError:
        return False
    return True


def _renamed(name: str, old: str, new: str) -> str:
    match = re.fullmatch(rf"{old}( \d+)?", name)
    return f"{new}{match.group(1) or ''}" if match else name


def swapped(feature: Feature) -> Feature:
    """The other kind of feature, same id, edges and size."""
    refs = {k: copy.deepcopy(v) for k, v in feature.refs.items() if k in SHARED_REFS}
    if not refs:
        raise SwapError(
            f"{feature.name} rounds or bevels no picked edges, so it cannot change kind. "
            "Edit it instead."
        )
    params = feature.params
    out = copy.deepcopy(feature)
    out.refs = refs
    if feature.type == "fillet":
        radius = params.get("radius")
        constant = params.get("fillet_type", "constant") == "constant"
        shaped = params.get("method", "radius") != "radius" or (
            params.get("profile", "circular") != "circular"
        )  # TR62 (D1402)
        if (
            not constant
            or shaped
            or params.get("multiple_radius") is True
            or not isinstance(radius, Param)
        ):
            raise SwapError(
                f"{feature.name} is not one constant size, so it cannot become a chamfer. "
                "Make it a constant size fillet first."
            )
        out.type = "chamfer"
        out.params = {
            "chamfer_type": "distance_distance",
            "method": "symmetric",
            "distance": copy.deepcopy(radius),
        }
        out.name = _renamed(feature.name, "Fillet", "Chamfer")
        return out
    if feature.type == "chamfer":
        distance = params.get("distance")
        equal = params.get("chamfer_type", "distance_distance") == "distance_distance" and (
            params.get("method", "symmetric") == "symmetric"
        )
        if not equal or not isinstance(distance, Param):
            raise SwapError(
                f"{feature.name} is not an equal distance chamfer, so it cannot become a "
                "fillet. Make both distances one value first."
            )
        out.type = "fillet"
        out.params = {"fillet_type": "constant", "radius": copy.deepcopy(distance)}
        out.name = _renamed(feature.name, "Chamfer", "Fillet")
        return out
    raise SwapError(f"{feature.name} is not a fillet or a chamfer. Pick one of those.")
