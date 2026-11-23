"""List nodes: item, length, reverse, sort, shift, cull by pattern and flatten.
Lists may be nested up to two levels (PLAN Phase 7)."""

from __future__ import annotations

from typing import Any

from fdcad.core.graph.nodes.base import (
    NodeContext,
    NodeError,
    NodeType,
    Port,
    Setting,
    count_of,
    number_of,
    register,
)
from fdcad.core.graph.types import PortType

LISTS = "List"
L = PortType.LIST


def as_list(value: Any) -> list[Any]:
    """``value`` as a list: a single value becomes a list of one, nothing an empty list."""
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


@register
class ListItem(NodeType):
    """The item at an index. Indexes past the end wrap around when Wrap is on."""

    type_name = "list_item"
    title = "List Item"
    category = LISTS
    words = "index get pick element"
    inputs = (Port("list", L, "List"), Port("index", PortType.NUMBER, "Index", 0.0))
    outputs = (Port("out", L, "Item"),)
    settings = (Setting("wrap", "bool", True),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        items = as_list(args.get("list"))
        if not items:
            raise NodeError("The list is empty. Connect a list with items.")
        index = round(number_of(args.get("index"), "Index"))
        if ctx.setting("wrap", True):
            index %= len(items)
        elif not -len(items) <= index < len(items):
            raise NodeError(f"Index {index} is outside the list of {len(items)}. Turn on Wrap.")
        return {"out": items[index]}


@register
class ListLength(NodeType):
    """How many items a list has."""

    type_name = "list_length"
    title = "List Length"
    category = LISTS
    words = "count size number of items"
    inputs = (Port("list", L, "List"),)
    outputs = (Port("out", PortType.NUMBER, "Length"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        return {"out": float(len(as_list(args.get("list"))))}


@register
class ListReverse(NodeType):
    """The list in the opposite order."""

    type_name = "list_reverse"
    title = "Reverse List"
    category = LISTS
    words = "flip backwards order"
    inputs = (Port("list", L, "List"),)
    outputs = (Port("out", L, "List"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        return {"out": list(reversed(as_list(args.get("list"))))}


@register
class ListSort(NodeType):
    """Numbers sorted from small to large, or any list sorted by a list of number keys."""

    type_name = "list_sort"
    title = "Sort List"
    category = LISTS
    words = "order ascending smallest largest"
    inputs = (Port("list", L, "List"), Port("keys", L, "Keys", optional=True))
    outputs = (Port("out", L, "List"), Port("indices", L, "Indices"))

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        items = as_list(args.get("list"))
        keys_in = args.get("keys")
        keys = as_list(keys_in) if keys_in is not None else items
        if len(keys) != len(items):
            raise NodeError("Keys and list have different lengths. Connect one key per item.")
        numbers = [number_of(k, "Sort key") for k in keys]
        order = sorted(range(len(items)), key=lambda i: (numbers[i], i))
        return {"out": [items[i] for i in order], "indices": [float(i) for i in order]}


@register
class ListShift(NodeType):
    """Items moved along the list by an offset; with Wrap they come round to the start."""

    type_name = "list_shift"
    title = "Shift List"
    category = LISTS
    words = "rotate offset cycle"
    inputs = (Port("list", L, "List"), Port("offset", PortType.NUMBER, "Offset", 1.0))
    outputs = (Port("out", L, "List"),)
    settings = (Setting("wrap", "bool", True),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        items = as_list(args.get("list"))
        if not items:
            return {"out": []}
        k = round(number_of(args.get("offset"), "Offset"))
        if ctx.setting("wrap", True):
            k %= len(items)
            return {"out": items[k:] + items[:k]}
        return {"out": items[k:] if k >= 0 else items[: len(items) + k]}


@register
class ListCull(NodeType):
    """Items kept where a repeating true and false pattern is true."""

    type_name = "list_cull"
    title = "Cull by Pattern"
    category = LISTS
    words = "filter remove skip every other mask"
    inputs = (Port("list", L, "List"), Port("pattern", L, "Pattern", [True, False]))
    outputs = (Port("out", L, "List"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        items = as_list(args.get("list"))
        pattern = [bool(p) for p in as_list(args.get("pattern"))]
        if not pattern:
            raise NodeError("The pattern is empty. Connect true and false values.")
        return {"out": [v for i, v in enumerate(items) if pattern[i % len(pattern)]]}


@register
class ListFlatten(NodeType):
    """Nested lists joined into one plain list."""

    type_name = "list_flatten"
    title = "Flatten List"
    category = LISTS
    words = "join merge nested unnest"
    inputs = (Port("list", L, "List"),)
    outputs = (Port("out", L, "List"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        out: list[Any] = []

        def walk(value: Any) -> None:
            if isinstance(value, list):
                for v in value:
                    walk(v)
            else:
                out.append(value)

        walk(as_list(args.get("list")))
        return {"out": out}


def counted(value: Any, what: str) -> int:
    """A whole number of items."""
    return count_of(value, what, 0, 100000)
