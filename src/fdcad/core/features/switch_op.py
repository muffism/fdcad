"""Switch a feature between boss and cut, or to and from thin (TUTORIAL_REVIEW_SPEC_2
TR387, DECISIONS D890).

Extrude, revolve, sweep and loft keep their sketch, end conditions and references;
only ``operation`` changes. Extrude and revolve can also turn Thin on (one direction,
1 mm) or off (every ``thin_`` value removed). A name still in the default form
("Extrude 3") follows the new operation ("Cut 4"); a name the user chose stays. No Qt.
"""

from __future__ import annotations

import copy
import re

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.names import default_name, name_prefix

SWITCHABLE = ("extrude", "revolve", "sweep", "loft")
THIN_TYPES = ("extrude", "revolve")


def can_switch(feature: Feature) -> bool:
    """True for a feature whose boss or cut can be switched."""
    return feature.type in SWITCHABLE


def _renamed(doc: Document, feature: Feature, old_op: str, new_op: str) -> str:
    prefix = name_prefix(feature.type, old_op)
    if re.fullmatch(rf"{re.escape(prefix)} \d+", feature.name):
        return default_name(doc, feature.type, new_op)
    return feature.name


def switched_operation(doc: Document, feature: Feature) -> Feature:
    """A copy of ``feature`` with Boss and Cut swapped."""
    old = str(feature.params.get("operation", "boss"))
    new = "cut" if old == "boss" else "boss"
    out = copy.deepcopy(feature)
    out.params["operation"] = new
    out.name = _renamed(doc, feature, old, new)
    return out


def switched_thin(feature: Feature) -> Feature:
    """A copy of ``feature`` with Thin turned on (one direction, 1 mm) or off."""
    out = copy.deepcopy(feature)
    if isinstance(out.params.get("thin_type"), str):
        for key in [k for k in out.params if k.startswith("thin_")]:
            out.params.pop(key)
    else:
        out.params["thin_type"] = "one_direction"
        out.params["thin_thickness"] = Param("1", 1.0)
    return out
