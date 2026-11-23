"""The part's own view directions (TR333, D955).

"Set Current View as Front" (or any standard view) turns every standard view so the
chosen one looks the way the camera looks now; the geometry does not move. "Set
Current View as Home" keeps the camera direction Home turns to. Both live in the
part under ``extra["view_frame"]``; Reset removes them. Pure Python, no Qt.

A frame is a rotation, stored as three rows of a 3 by 3 matrix, that takes a
standard view direction and up vector to the part's own.
"""

from __future__ import annotations

import math
from typing import Any

Vec3 = tuple[float, float, float]
Matrix = tuple[Vec3, Vec3, Vec3]

KEY = "view_frame"
IDENTITY: Matrix = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


class ViewFrameError(ValueError):
    """The camera cannot set a view; the message says why."""


def _unit(v: Vec3) -> Vec3:
    n = math.sqrt(sum(c * c for c in v))
    if n < 1e-12:
        raise ViewFrameError("The view has no direction. Turn the view and try again.")
    return (v[0] / n, v[1] / n, v[2] / n)


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _basis(eye: Vec3, up: Vec3) -> Matrix:
    """An orthonormal basis (eye, up, side) with up made square to eye."""
    e = _unit(eye)
    along = _dot(up, e)
    u = _unit((up[0] - along * e[0], up[1] - along * e[1], up[2] - along * e[2]))
    return e, u, _cross(e, u)


def frame_for(standard: tuple[Vec3, Vec3], eye: Vec3, up: Vec3) -> Matrix:
    """The rotation that takes the standard view (eye, up) to the camera's."""
    s, c = _basis(*standard), _basis(eye, up)
    # R = C^T S as columns: R x = sum_k c_k (s_k . x)
    return tuple(  # type: ignore[return-value]
        tuple(sum(c[k][i] * s[k][j] for k in range(3)) for j in range(3)) for i in range(3)
    )


def turn(frame: Matrix, v: Vec3) -> Vec3:
    """``v`` turned by ``frame``."""
    return (_dot(frame[0], v), _dot(frame[1], v), _dot(frame[2], v))


def frame_of(extra: dict[str, Any]) -> Matrix:
    """The part's frame, the identity when none is set or it is damaged."""
    raw: Any = (extra.get(KEY) or {}).get("frame")
    try:
        rows = tuple(tuple(float(x) for x in row) for row in raw)
    except (TypeError, ValueError):
        return IDENTITY
    if len(rows) != 3 or any(len(r) != 3 for r in rows):
        return IDENTITY
    return rows  # type: ignore[return-value]


def home_of(extra: dict[str, Any]) -> tuple[Vec3, Vec3] | None:
    """The part's Home camera direction (eye, up), or None for the standard one."""
    raw: Any = (extra.get(KEY) or {}).get("home")
    try:
        eye, up = (tuple(float(x) for x in raw[k]) for k in ("eye", "up"))
    except (TypeError, ValueError, KeyError):
        return None
    if len(eye) != 3 or len(up) != 3:
        return None
    return (eye[0], eye[1], eye[2]), (up[0], up[1], up[2])


def with_frame(extra: dict[str, Any], frame: Matrix | None) -> dict[str, Any] | None:
    """The ``view_frame`` value after setting (or, with None, removing) the frame."""
    out = dict(extra.get(KEY) or {})
    if frame is None:
        out.pop("frame", None)
    else:
        out["frame"] = [list(row) for row in frame]
    return out or None


def with_home(extra: dict[str, Any], home: tuple[Vec3, Vec3] | None) -> dict[str, Any] | None:
    """The ``view_frame`` value after setting (or, with None, removing) Home."""
    out = dict(extra.get(KEY) or {})
    if home is None:
        out.pop("home", None)
    else:
        e, u = _basis(*home)[:2]
        out["home"] = {"eye": list(e), "up": list(u)}
    return out or None
