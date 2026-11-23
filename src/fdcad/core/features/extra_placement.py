"""An extra offset in a reference's own axes, after its method (TR149, D980).

Every reference plane, axis and coordinate system method can be followed by three
distances along its own X, Y and Z (Z is the plane normal, the axis direction or
the frame's Z), three turns about those axes (X first, then the turned Y, then the
turned Z), and a flip of Z. With none set nothing changes. No Qt.
"""

from __future__ import annotations

import math

from fdcad.core.document.model import Feature, Param

Vec3 = tuple[float, float, float]
LENGTHS = ("extra_dx", "extra_dy", "extra_dz")
ANGLES = ("extra_rx", "extra_ry", "extra_rz")
FLIP = "extra_flip"


def _value(feature: Feature, name: str) -> float:
    value = feature.params.get(name)
    return float(value.value) if isinstance(value, Param) else 0.0


def _unit(v: Vec3) -> Vec3:
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _turn(v: Vec3, axis: Vec3, angle: float) -> Vec3:
    """``v`` turned by ``angle`` about the unit ``axis`` (Rodrigues)."""
    c, s = math.cos(angle), math.sin(angle)
    k = axis
    dot = k[0] * v[0] + k[1] * v[1] + k[2] * v[2]
    kv = _cross(k, v)
    return tuple(v[i] * c + kv[i] * s + k[i] * dot * (1 - c) for i in range(3))  # type: ignore[return-value]


def perpendicular(z: Vec3) -> Vec3:
    """A fixed unit direction square to ``z``, for an axis's own X."""
    helper = (1.0, 0.0, 0.0) if abs(z[0]) < 0.9 else (0.0, 1.0, 0.0)
    return _unit(_cross(_cross(z, helper), z))


def has_extra(feature: Feature) -> bool:
    """True when any extra offset, turn or the flip is set."""
    return feature.params.get(FLIP) is True or any(
        abs(_value(feature, n)) > 1e-12 for n in (*LENGTHS, *ANGLES)
    )


def apply(feature: Feature, origin: Vec3, z: Vec3, x: Vec3 | None) -> tuple[Vec3, Vec3, Vec3]:
    """The placement after the extra offset: origin, Z and X."""
    z = _unit(z)
    x = perpendicular(z) if x is None else _unit(x)
    if not has_extra(feature):
        return origin, z, x
    y = _cross(z, x)
    dx, dy, dz = (_value(feature, n) for n in LENGTHS)
    origin = tuple(origin[i] + dx * x[i] + dy * y[i] + dz * z[i] for i in range(3))  # type: ignore[assignment]
    for name, axis_index in zip(ANGLES, range(3), strict=True):
        angle = _value(feature, name)
        if abs(angle) < 1e-15:
            continue
        axis = (x, y, z)[axis_index]
        x, y, z = (_turn(v, axis, angle) for v in (x, y, z))
    if feature.params.get(FLIP) is True:
        z = (-z[0], -z[1], -z[2])
    return origin, z, x
