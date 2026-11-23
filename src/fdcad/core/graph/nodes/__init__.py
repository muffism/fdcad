"""Node types. Importing this package registers every type in ``NODE_TYPES``.

Every node type is listed in FDEF_SPEC 12A.
"""

from fdcad.core.graph.nodes import (  # noqa: F401  (registers the node types)
    curves,
    inputs,
    lists,
    math_nodes,
    outputs,
    patterns,
    points,
    solids,
)
from fdcad.core.graph.nodes.base import NODE_TYPES, NodeType

__all__ = ["NODE_TYPES", "NodeType"]


def catalog() -> list[NodeType]:
    """Every node type, by category then title, for the add node list."""
    return sorted(NODE_TYPES.values(), key=lambda t: (t.category, t.title))
