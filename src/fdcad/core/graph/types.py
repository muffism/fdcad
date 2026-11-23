"""Port types of the node graph and the rules for wiring them (PLAN Phase 7).

Values travel between nodes as plain Python data:

- number, length, angle: ``float`` (lengths in millimetres, angles in radians)
- boolean: ``bool``
- point, vector: ``(x, y, z)`` tuples of floats
- plane: ``Plane``
- curve, body: OpenCascade shapes (a wire or edge, a solid or compound)
- list: a Python ``list`` of any of these, nested at most two levels deep
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

Vec3 = tuple[float, float, float]


class PortType(Enum):
    """What a port carries."""

    NUMBER = "number"
    LENGTH = "length"
    ANGLE = "angle"
    BOOLEAN = "boolean"
    POINT = "point"
    VECTOR = "vector"
    PLANE = "plane"
    CURVE = "curve"
    BODY = "body"
    LIST = "list"


NUMERIC = frozenset({PortType.NUMBER, PortType.LENGTH, PortType.ANGLE})
GEOMETRY = frozenset({PortType.CURVE, PortType.BODY})
#: Deepest list nesting a value may have (PLAN Phase 7, list nodes).
MAX_LIST_DEPTH = 2


def can_connect(source: PortType, target: PortType) -> bool:
    """True when an output of type ``source`` may feed an input of type ``target``.

    Numbers, lengths and angles mix freely (the value is passed as is). Points
    and vectors are both three numbers. Curves and bodies are both shapes, so
    move, rotate and the like take either; a node that needs one kind says so
    when it runs. A list may feed any input: the node then
    runs once per item. Anything may feed a list input.
    """
    if source is target or target is PortType.LIST or source is PortType.LIST:
        return True
    if source in NUMERIC and target in NUMERIC:
        return True
    pair = {source, target}
    if pair == {PortType.POINT, PortType.VECTOR}:
        return True
    if pair <= GEOMETRY:  # curves and bodies are both shapes; the node checks which
        return True
    return source is PortType.BOOLEAN and target in NUMERIC


@dataclass(frozen=True)
class Plane:
    """A plane: an origin, a unit normal and a unit X direction in the plane."""

    origin: Vec3 = (0.0, 0.0, 0.0)
    normal: Vec3 = (0.0, 0.0, 1.0)
    x_dir: Vec3 = (1.0, 0.0, 0.0)

    @property
    def y_dir(self) -> Vec3:
        """The in plane Y direction (normal cross X)."""
        return cross(self.normal, self.x_dir)

    def at(self, u: float, v: float) -> Vec3:
        """The point at plane coordinates ``(u, v)``."""
        o, x, y = self.origin, self.x_dir, self.y_dir
        return (o[0] + x[0] * u + y[0] * v, o[1] + x[1] * u + y[1] * v, o[2] + x[2] * u + y[2] * v)

    def coords(self, p: Vec3) -> tuple[float, float]:
        """Plane coordinates of ``p`` (its projection onto the plane)."""
        d = sub(p, self.origin)
        return (dot(d, self.x_dir), dot(d, self.y_dir))


XY_PLANE = Plane()


def make_plane(origin: Vec3, normal: Vec3) -> Plane:
    """A plane through ``origin`` square to ``normal`` with a stable X direction."""
    n = unit(normal)
    if n == (0.0, 0.0, 0.0):
        raise ValueError("The plane normal has zero length. Give it a direction.")
    helper: Vec3 = (1.0, 0.0, 0.0) if abs(n[0]) < 0.9 else (0.0, 1.0, 0.0)
    x = unit(sub(helper, scale(n, dot(helper, n))))
    return Plane(origin, n, x)


def dot(a: Vec3, b: Vec3) -> float:
    """Dot product."""
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vec3, b: Vec3) -> Vec3:
    """Cross product."""
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def sub(a: Vec3, b: Vec3) -> Vec3:
    """``a`` minus ``b``."""
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a: Vec3, b: Vec3) -> Vec3:
    """``a`` plus ``b``."""
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def scale(a: Vec3, k: float) -> Vec3:
    """``a`` times ``k``."""
    return (a[0] * k, a[1] * k, a[2] * k)


def length(a: Vec3) -> float:
    """Length of a vector."""
    return math.sqrt(dot(a, a))


def unit(a: Vec3) -> Vec3:
    """``a`` scaled to length 1, or zero when it has no length."""
    n = length(a)
    return (a[0] / n, a[1] / n, a[2] / n) if n > 0 else (0.0, 0.0, 0.0)


def list_depth(value: object) -> int:
    """How deeply ``value`` is nested in lists (0 for a single value)."""
    if not isinstance(value, list):
        return 0
    return 1 + max((list_depth(v) for v in value), default=0)
