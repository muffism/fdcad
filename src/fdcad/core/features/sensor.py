"""Sensor (TR86, DECISIONS D1022): a tree row that watches a value and warns when it goes
outside typed limits. It passes the part through unchanged.

Params: ``source`` (``volume``, ``area`` or ``mass`` of the bodies built above the
sensor, or ``formula``); ``value`` (the formula, when ``source`` is ``formula``: a
variable, a dimension, an equation or a measured value); ``low`` and ``high`` (the
limits, either may be left out). The watched value shows in the feature's report and
formulas can read it as ``value@Sensor 1``.
"""

from __future__ import annotations

from typing import Any

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureState,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.units import Kind

SOURCES = ("volume", "area", "mass", "formula")
#: How each part value reads in messages, with its unit.
_NAMES = {
    "volume": ("volume", "mm^3"),
    "area": ("surface area", "mm^2"),
    "mass": ("mass", "g"),
    "formula": ("value", ""),
}


def _number(feature: Feature, name: str) -> float | None:
    p = feature.params.get(name)
    if isinstance(p, Param):
        return p.value
    return None


def watched(feature: Feature, ctx: BuildContext) -> float:
    """The value the sensor watches. Raises FeatureError with what to do."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    from fdcad.core.features.solids import solids
    from fdcad.core.materials import part_material

    source = str(feature.params.get("source", "volume"))
    owner = feature.name
    if source == "formula":
        value = _number(feature, "value")
        if value is None:
            raise FeatureError(f"{owner}: there is no formula to watch. Enter a formula.")
        return value
    if source not in SOURCES:
        raise FeatureError(f"{owner}: unknown value '{source}'. Choose what to watch.")
    bodies = solids(ctx.body.shape) if ctx.body is not None else []
    if not bodies:
        raise FeatureError(
            f"{owner}: there is no body above the sensor to measure. Move the sensor below "
            "a feature that makes a body."
        )
    total = 0.0
    for body in bodies:
        props = GProp_GProps()
        if source == "area":
            BRepGProp.SurfaceProperties_s(body, props)
        else:
            BRepGProp.VolumeProperties_s(body, props)
        total += abs(props.Mass())
    if source == "mass":
        material = part_material(ctx.document)
        if material is None:
            raise FeatureError(
                f"{owner}: the part has no material, so it has no mass. Use Material on the "
                "Tools menu to choose one."
            )
        total *= material.density / 1000.0
    return total


def describe(source: str, value: float) -> str:
    """The value as the sensor's messages name it."""
    name, unit = _NAMES.get(source, ("value", ""))
    return f"{name} {value:.6g}" + (f" {unit}" if unit else "")


@register
class Sensor(FeatureType):
    """Watch a value; warn when it leaves the limits."""

    type_name = "sensor"
    params = (
        ParamSpec("source", choices=SOURCES, default="volume", optional=True),
        ParamSpec("value", kind=Kind.NUMBER, optional=True),
        ParamSpec("low", kind=Kind.NUMBER, optional=True),
        ParamSpec("high", kind=Kind.NUMBER, optional=True),
    )

    def reads_body(self, feature: Feature) -> bool:
        """It reads the part as built so far, so its result is kept for that part only
        (D1064). Without this the result from before a change was shown again."""
        return True

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Read the value and compare it with the limits."""
        source = str(feature.params.get("source", "volume"))
        value = watched(feature, ctx)
        low, high = _number(feature, "low"), _number(feature, "high")
        shown = describe(source, value)
        extras: dict[str, Any] = {"value": value, "report": [f"{feature.name}: {shown}."]}
        issues: list[Issue] = []
        if low is None and high is None:
            issues.append(
                Issue(
                    FeatureState.WARNING,
                    f"{feature.name}: no limit is set. Enter a low or a high limit.",
                    code="sensor_no_limit",
                )
            )
        elif low is not None and high is not None and low > high:
            issues.append(
                Issue(
                    FeatureState.WARNING,
                    f"{feature.name}: the low limit {low:.6g} is above the high limit "
                    f"{high:.6g}. Enter limits in order.",
                    code="sensor_limits",
                )
            )
        elif low is not None and value < low:
            issues.append(
                Issue(
                    FeatureState.WARNING,
                    f"{feature.name}: the {shown} is below the low limit {low:.6g}. Change "
                    "the model, or change the limit.",
                    code="sensor_alert",
                )
            )
        elif high is not None and value > high:
            issues.append(
                Issue(
                    FeatureState.WARNING,
                    f"{feature.name}: the {shown} is above the high limit {high:.6g}. Change "
                    "the model, or change the limit.",
                    code="sensor_alert",
                )
            )
        return FeatureResult(body=ctx.body, issues=issues, extras=extras)
