"""Panels of the Phase 4 shape features: Rib, Dome and Wrap (PHASE4_SPEC P4.5 to P4.7).

Rib (DECISIONS D320): sketch, thickness and side, direction, flip, draft and the
end extension, and the body in parts with several bodies.
"""

from __future__ import annotations

import math
from typing import Any

from fdcad.core.document.model import Feature
from fdcad.core.units import UnitSystem
from fdcad.ui import strings_finish as finish
from fdcad.ui import strings_phase4 as text
from fdcad.ui.property_panel.forms.base import form
from fdcad.ui.property_panel.forms.spec_form import F, G, SpecForm

T = text.SHAPE_TIPS


def _draft_on(v: dict[str, Any]) -> bool:
    return v.get("direction") == "normal" and v.get("use_draft") is True


@form("rib")
class RibForm(SpecForm):
    """Edits a rib."""

    first_param = "thickness"
    remembered_keys = ("side", "direction", "extend")
    layout = (
        G(
            "rib",
            text.GROUP_RIB,
            T["rib_sketch"],
            (
                F("sketch", text.LABEL_SKETCH, "sketch", T["rib_sketch"]),
                F("thickness", text.LABEL_THICKNESS, "length", T["thickness"], 2.0),
                F(
                    "side",
                    text.LABEL_SIDE,
                    "choice",
                    T["side"],
                    "both",
                    tuple(text.RIB_SIDES.items()),
                ),
                F(
                    "direction",
                    text.LABEL_DIRECTION,
                    "choice",
                    T["rib_direction"],
                    "parallel",
                    tuple(text.RIB_DIRECTIONS.items()),
                ),
                F("flip", text.LABEL_FLIP, "bool", T["flip"]),
                F(
                    "extend",
                    text.LABEL_EXTEND,
                    "choice",
                    T["extend"],
                    "linear",
                    tuple(text.RIB_EXTENDS.items()),
                ),
                F(
                    "use_draft",
                    text.LABEL_USE_DRAFT,
                    "bool",
                    T["rib_draft"],
                    when=lambda v: v.get("direction") == "normal",
                ),
                F(
                    "draft_angle",
                    text.LABEL_DRAFT,
                    "angle",
                    T["rib_draft"],
                    math.radians(1),
                    when=_draft_on,
                ),
                F(
                    "draft_outward",
                    text.LABEL_DRAFT_OUTWARD,
                    "bool",
                    T["rib_draft"],
                    when=_draft_on,
                ),
                F(  # TR75 (D2112): keep the thickness at the sketch or at the wall
                    "draft_at",
                    text.LABEL_DRAFT_AT,
                    "choice",
                    T["rib_draft_at"],
                    "sketch",
                    tuple(text.RIB_DRAFT_AT.items()),
                    when=_draft_on,
                ),
                F("body", text.LABEL_BODY, "faces", T["body"], single=True, optional=True),
            ),
        ),
    )

    def build(self) -> None:
        """Tick Draft when the feature has a draft angle."""
        super().build()
        if "draft_angle" in self.feature.params:
            self.checks["use_draft"].setChecked(True)
        from PySide6.QtWidgets import QCheckBox

        from fdcad.ui import strings

        self.detailed = QCheckBox(strings.FIELD_DETAILED_PREVIEW)  # TR164 (D1809)
        self.detailed.setObjectName("rib_detailed_preview")
        self.detailed.setToolTip(strings.FIELD_DETAILED_PREVIEW_TIP)
        self.detailed.setChecked(RibForm.detailed_preview)
        self.detailed.toggled.connect(self._detailed_toggled)
        self.panel.groups["rib"].form.addRow(self.detailed)

    detailed_preview = False  # kept for the session (TR164, D1809)

    def _detailed_toggled(self, on: bool) -> None:
        RibForm.detailed_preview = on
        self.changed.emit()

    def for_preview(self, feature: Feature) -> Feature | None:
        """With Detailed preview the copy sent to the preview carries the flag (never
        saved, D1417)."""
        import copy

        if not RibForm.detailed_preview:
            return feature
        out = copy.deepcopy(feature)
        out.data["preview_detailed"] = True
        return out

    def extra_apply(self, feature: Any) -> str | None:
        """``use_draft`` is a panel switch only; the angle's presence turns draft on."""
        feature.params.pop("use_draft", None)
        if feature.params.get("draft_at") != "wall" or "draft_angle" not in feature.params:
            feature.params.pop("draft_at", None)  # TR75 (D2112): the default is not written
        return None


def rib_defaults(units: UnitSystem) -> dict[str, Any]:
    """A new rib: 2 mm (or 0.08 inch) both sides, parallel to the sketch, Linear."""
    from fdcad.core.document.model import Param
    from fdcad.core.units import Kind
    from fdcad.ui.property_panel.forms.spec_form import number_text

    value = 0.08 * 25.4 if units is UnitSystem.IN else 2.0
    return {
        "thickness": Param(number_text(value, Kind.LENGTH, units), value),
        "side": "both",
        "direction": "parallel",
        "extend": "linear",
    }


@form("dome")
class DomeForm(SpecForm):
    """Edits a dome (PHASE4_SPEC P4.6, DECISIONS D321)."""

    first_param = "distance"
    remembered_keys = ("elliptical", "continuous")
    layout = (
        G(
            "dome",
            text.GROUP_DOME,
            T["dome_faces"],
            (
                F("faces", text.LABEL_FACES, "faces", T["dome_faces"]),
                F("distance", text.LABEL_DISTANCE, "length", T["distance"], 5.0),
                F("reverse", text.LABEL_REVERSE, "bool", T["dome_reverse"]),
                F("elliptical", text.LABEL_ELLIPTICAL, "bool", T["elliptical"]),
                F("continuous", text.LABEL_CONTINUOUS, "bool", T["continuous"]),
                F(  # TR147 (D1805)
                    "direction",
                    finish.DOME_DIRECTION,
                    "any",
                    finish.DOME_DIRECTION_TIP,
                    single=True,
                    optional=True,
                ),
                F(  # TR147 (D2301)
                    "profile_sketch",
                    finish.DOME_PROFILE,
                    "sketch",
                    finish.DOME_PROFILE_TIP,
                    finish.DOME_PROFILE_NONE,
                    optional=True,
                ),
            ),
        ),
    )


def dome_defaults(units: UnitSystem) -> dict[str, Any]:
    """A new dome: 5 mm (or 0.2 inch) high."""
    from fdcad.core.document.model import Param
    from fdcad.core.units import Kind
    from fdcad.ui.property_panel.forms.spec_form import number_text

    value = 0.2 * 25.4 if units is UnitSystem.IN else 5.0
    return {"distance": Param(number_text(value, Kind.LENGTH, units), value)}


@form("corner_relief")
class CornerReliefForm(SpecForm):
    """Edits a corner relief (TR244, DECISIONS D785)."""

    first_param = "tool_diameter"
    remembered_keys = ("relief_type",)
    layout = (
        G(
            "relief",
            text.GROUP_RELIEF,
            text.RELIEF_TIPS["relief_type"],
            (
                F(
                    "relief_type",
                    text.LABEL_RELIEF_TYPE,
                    "choice",
                    text.RELIEF_TIPS["relief_type"],
                    "dogbone",
                    tuple(text.RELIEF_TYPES.items()),
                ),
                F(
                    "tool_diameter",
                    text.LABEL_TOOL_DIAMETER,
                    "length",
                    text.RELIEF_TIPS["tool_diameter"],
                    6.0,
                ),
                F(
                    "clearance",
                    text.LABEL_RELIEF_CLEARANCE,
                    "length",
                    text.RELIEF_TIPS["clearance"],
                    0.0,
                ),
                F(
                    "flip",
                    text.LABEL_RELIEF_FLIP,
                    "bool",
                    text.RELIEF_TIPS["flip"],
                    when=lambda v: v.get("relief_type") == "t_bone",
                ),
                F(
                    "edges",
                    text.LABEL_RELIEF_EDGES,
                    "edges",
                    text.RELIEF_TIPS["edges"],
                    optional=True,
                ),
                F(
                    "feature",
                    text.LABEL_RELIEF_FEATURE,
                    "feature",
                    text.RELIEF_TIPS["feature"],
                    "extrude",
                    optional=True,
                ),
            ),
        ),
    )


def relief_defaults(units: UnitSystem) -> dict[str, Any]:
    """A new corner relief: a dogbone for a 6 mm (or 1/4 inch) tool."""
    from fdcad.core.document.model import Param
    from fdcad.core.units import Kind
    from fdcad.ui.property_panel.forms.spec_form import number_text

    value = 0.25 * 25.4 if units is UnitSystem.IN else 6.0
    return {
        "relief_type": "dogbone",
        "tool_diameter": Param(number_text(value, Kind.LENGTH, units), value),
    }


@form("wrap")
class WrapForm(SpecForm):
    """Edits a wrap (PHASE4_SPEC P4.7, DECISIONS D322)."""

    first_param = "thickness"
    remembered_keys = ("wrap_type",)
    layout = (
        G(
            "wrap",
            text.GROUP_WRAP,
            T["wrap_sketch"],
            (
                F("sketch", text.LABEL_SKETCH, "sketch", T["wrap_sketch"]),
                F(
                    "method",
                    text.LABEL_WRAP_METHOD,
                    "choice",
                    T["wrap_method"],
                    "analytical",
                    tuple(text.WRAP_METHODS.items()),
                ),
                F("face", text.LABEL_FACE_TO_WRAP, "faces", T["wrap_face"], single=True),
                F(
                    "wrap_type",
                    text.LABEL_TYPE,
                    "choice",
                    T["wrap_type"],
                    "emboss",
                    tuple(text.WRAP_TYPES.items()),
                ),
                F(
                    "thickness",
                    text.LABEL_THICKNESS,
                    "length",
                    T["wrap_thickness"],
                    1.0,
                    when=lambda v: v.get("wrap_type") != "scribe",
                ),
                F(
                    "reverse",
                    text.LABEL_REVERSE,
                    "bool",
                    T["wrap_reverse"],
                    when=lambda v: v.get("method") not in ("spline", "project"),
                ),
                F(  # TR75 item 2 (D2112)
                    "pull",
                    text.LABEL_PULL,
                    "any",
                    T["wrap_pull"],
                    single=True,
                    optional=True,
                    when=lambda v: v.get("method") != "spline" and v.get("wrap_type") != "scribe",
                ),
            ),
        ),
    )

    def apply(self, feature: Feature) -> str | None:
        """Write the fields; the default Analytical method is not written (D528)."""
        problem = super().apply(feature)
        if feature.params.get("method") == "analytical":
            feature.params.pop("method")
        return problem


def wrap_defaults(units: UnitSystem) -> dict[str, Any]:
    """A new wrap: emboss 1 mm (or 0.04 inch)."""
    from fdcad.core.document.model import Param
    from fdcad.core.units import Kind
    from fdcad.ui.property_panel.forms.spec_form import number_text

    value = 0.04 * 25.4 if units is UnitSystem.IN else 1.0
    return {
        "wrap_type": "emboss",
        "thickness": Param(number_text(value, Kind.LENGTH, units), value),
    }
