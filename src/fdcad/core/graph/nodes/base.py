"""The node interface and the node registry (PLAN Phase 7).

A node type lists its input and output ports and its settings, and computes
its outputs from its inputs. Nodes never run code from the file: the type
string picks one of the classes registered here, and settings are plain data.
"""

from __future__ import annotations

import math
import zlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from fdcad.core.document.model import Param
from fdcad.core.graph.types import PortType
from fdcad.core.units import Kind, UnitSystem

if TYPE_CHECKING:
    import numpy as np

    from fdcad.core.graph.model import Node


class NodeError(Exception):
    """A node cannot compute. The message is shown on the node."""


class NeedsConfirmationError(NodeError):
    """A node waits for the user to confirm a slow step (performance guard)."""


@dataclass(frozen=True)
class Port:
    """An input or output of a node.

    ``default`` is used when an input has no wire and no stored value.
    ``whole_list`` inputs take a list as one value; other inputs given a list
    make the node run once per item.
    """

    name: str
    type: PortType
    label: str = ""
    default: Any = None
    whole_list: bool = False
    optional: bool = False

    @property
    def title(self) -> str:
        """The label shown on the node."""
        return self.label or self.name.replace("_", " ").capitalize()


@dataclass(frozen=True)
class Setting:
    """A value set on the node itself, not through a wire.

    ``kind`` is one of ``number``, ``length``, ``angle`` (stored as parameter
    objects), ``int``, ``bool``, ``choice``, ``text``, ``variable`` (a
    variable name), ``feature`` (a feature id), ``param`` (a parameter name)
    and ``ref`` (a model reference).
    """

    name: str
    kind: str
    default: Any = None
    choices: tuple[str, ...] = ()
    label: str = ""

    @property
    def title(self) -> str:
        """The label shown on the node."""
        return self.label or self.name.replace("_", " ").capitalize()


@dataclass
class GraphEnv:
    """What nodes may read from the part: only data from features at or above the
    graph's position (DECISIONS D26)."""

    units: UnitSystem = UnitSystem.MM
    variables: dict[str, tuple[Kind, float]] = field(default_factory=dict)
    #: Feature id to (type, name, params) for features at or above the position.
    features: dict[str, Any] = field(default_factory=dict)
    #: Feature id to its rebuild result, for model references.
    results: dict[str, Any] = field(default_factory=dict)
    #: The part body at the graph position (a NamedShape), or None.
    body: Any = None
    #: Content key of the part at the position: changes when the model above changes.
    body_key: str = ""
    #: Named faces and edges (TR152): name in lower case to its lasting reference.
    named: dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeContext:
    """Passed to ``compute``: the node, its environment and helpers."""

    node: Node
    env: GraphEnv
    seed: int
    input_types: dict[str, PortType] = field(default_factory=dict)
    cancelled: Callable[[], bool] = lambda: False
    warnings: list[str] = field(default_factory=list)

    def rng(self, extra: int = 0) -> np.random.Generator:
        """A random generator seeded from the graph seed, the node id and ``extra``."""
        import numpy as np

        number = zlib.crc32(self.node.id.encode("utf-8"))
        return np.random.default_rng([self.seed & 0xFFFFFFFF, number, extra & 0xFFFFFFFF])

    def setting(self, name: str, default: Any = None) -> Any:
        """A setting's stored value; parameter objects give their internal value."""
        value = self.node.params.get(name, default)
        return value.value if isinstance(value, Param) else value


class NodeType:
    """Base class of node types. Subclasses set the class attributes and ``compute``."""

    type_name: ClassVar[str]
    title: ClassVar[str]
    category: ClassVar[str]
    inputs: ClassVar[tuple[Port, ...]] = ()
    outputs: ClassVar[tuple[Port, ...]] = ()
    settings: ClassVar[tuple[Setting, ...]] = ()
    #: Extra words the add node search matches.
    words: ClassVar[str] = ""
    #: True for nodes that write to the part (set variable, set parameter, add as feature).
    is_output: ClassVar[bool] = False

    def input(self, name: str) -> Port | None:
        """The input port called ``name``."""
        return next((p for p in self.inputs if p.name == name), None)

    def output(self, name: str) -> Port | None:
        """The output port called ``name``."""
        return next((p for p in self.outputs if p.name == name), None)

    def env_key(self, node: Node, env: GraphEnv) -> Any:
        """Data from the part this node reads, so its result is redone when it changes."""
        return None

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        """Outputs by port name. Raises NodeError."""
        raise NotImplementedError


NODE_TYPES: dict[str, NodeType] = {}


def register(cls: type[NodeType]) -> type[NodeType]:
    """Class decorator: make a node type available by its ``type_name``."""
    NODE_TYPES[cls.type_name] = cls()
    return cls


def number_of(value: Any, what: str) -> float:
    """``value`` as a float. Raises NodeError naming ``what``."""
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, int | float):
        return float(value)
    raise NodeError(f"{what} needs a number. Connect a number.")


def finite_of(value: Any, what: str) -> float:
    """``value`` as a float that the part file can keep: not nan or infinite (D2671).
    Raises NodeError naming ``what``."""
    number = number_of(value, what)
    if not math.isfinite(number):
        raise NodeError(f"{what} is too large or not a number. Check the nodes that feed it.")
    return number


def vec_of(value: Any, what: str) -> tuple[float, float, float]:
    """``value`` as a 3D point or vector. Raises NodeError naming ``what``."""
    if isinstance(value, tuple) and len(value) == 3:
        return (float(value[0]), float(value[1]), float(value[2]))
    raise NodeError(f"{what} needs a point or vector. Connect a point.")


def count_of(value: Any, what: str, low: int = 0, high: int = 100000) -> int:
    """``value`` as a whole number in ``[low, high]``. Raises NodeError."""
    n = number_of(value, what)
    k = round(n)
    if k < low or k > high:
        raise NodeError(f"{what} must be from {low} to {high}. Change the value.")
    return k
