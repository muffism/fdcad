"""Named faces and edges (TR152, D2105).

A face or edge of the part can be given a name. Names are kept in the part's tree
block under ``named_items``: a list of ``{"name", "kind", "ref"}``, where ``ref`` is
the usual lasting reference of the picked face or edge (the one features store), so
a name follows the face when features above it change. Bodies have names already
(TR183, ``core.body_titles``).

After each rebuild the named items are measured (``Document.measured``, never
saved): ``"area@<name>"`` for a face and ``"length@<name>"`` for an edge, in mm2 and
mm. Custom property formulas read them, as they read ``"volume@Part"``; feature
formulas cannot, since the values come from the finished part (a loop). A node
editor Model Reference made from a named item stores ``{"named": name}`` and follows
the name. No Qt; kernel calls only in ``resolve`` and ``measure``.
"""

from __future__ import annotations

import copy
import re
from typing import Any

from fdcad.core.document.model import Document

KEY = "named_items"
KINDS = ("face", "edge")
#: Where the measures are kept in ``Document.measured``.
MEASURED_KEY = "__named__"
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_ ]*\Z")


class ItemNameError(ValueError):
    """A name cannot be used. The message says what to fix."""


def items(doc: Document) -> list[dict[str, Any]]:
    """The named items, in order; damaged entries are left out."""
    raw = doc.tree.get(KEY) if isinstance(doc.tree, dict) else None
    return [
        i
        for i in (raw if isinstance(raw, list) else [])
        if isinstance(i, dict)
        and isinstance(i.get("name"), str)
        and i.get("kind") in KINDS
        and isinstance(i.get("ref"), dict)
    ]


def find(doc: Document, name: str) -> dict[str, Any] | None:
    """The named item called ``name`` (ignoring case), or None."""
    wanted = name.strip().casefold()
    return next((i for i in items(doc) if i["name"].casefold() == wanted), None)


def check_name(doc: Document, name: str, ignore: str | None = None) -> str:
    """A cleaned up name. Raises ItemNameError when it cannot be used."""
    clean = " ".join(name.split())
    if not _NAME.match(clean):
        raise ItemNameError(
            "Start the name with a letter and use letters, digits, spaces and underscores."
        )
    found = find(doc, clean)
    if found is not None and found["name"] != ignore:
        raise ItemNameError(f'"{clean}" already names an item. Choose another name.')
    return clean


def _store(doc: Document, new: list[dict[str, Any]]) -> None:
    if not isinstance(doc.tree, dict):
        doc.tree = {}
    if new:
        doc.tree[KEY] = new
    else:
        doc.tree.pop(KEY, None)


def add(doc: Document, name: str, ref: dict[str, Any]) -> str:
    """Name the face or edge ``ref`` points at. A face or edge that already has a name
    gets the new one. Returns the name. Raises ItemNameError."""
    kind = ref.get("kind")
    if kind not in KINDS:
        raise ItemNameError("Only faces and edges take a name here. Pick a face or an edge.")
    clean = check_name(doc, name, ignore=name_of(doc, ref))
    kept = [i for i in items(doc) if i["ref"].get("name") != ref.get("name")]
    kept.append({"name": clean, "kind": kind, "ref": copy.deepcopy(ref)})
    _store(doc, kept)
    return clean


def rename(doc: Document, old: str, new: str) -> str:
    """Rename a named item. Returns the new name. Raises ItemNameError."""
    item = find(doc, old)
    if item is None:
        raise ItemNameError(f'There is no item named "{old}". Pick one in the list.')
    clean = check_name(doc, new, ignore=item["name"])
    out = []
    for i in items(doc):
        entry = copy.deepcopy(i)
        if i["name"] == item["name"]:
            entry["name"] = clean
        out.append(entry)
    _store(doc, out)
    return clean


def remove(doc: Document, name: str) -> None:
    """Take the name off an item (the face or edge stays)."""
    _store(doc, [copy.deepcopy(i) for i in items(doc) if i["name"].casefold() != name.casefold()])


def name_of(doc: Document, ref: dict[str, Any] | None) -> str | None:
    """The name of the item ``ref`` points at, or None."""
    if not isinstance(ref, dict):
        return None
    found = next((i for i in items(doc) if i["ref"].get("name") == ref.get("name")), None)
    return str(found["name"]) if found is not None else None


def resolve(body: Any, item: dict[str, Any]) -> Any:
    """The face or edge of ``body`` the item names. Raises FeatureError."""
    from fdcad.core.features.lookup import resolve_edge, resolve_face

    owner = f'Named item "{item["name"]}"'
    if item["kind"] == "edge":
        return resolve_edge(body, item["ref"], owner)[0]
    return resolve_face(body, item["ref"], owner)[0]


def measure(doc: Document, body: Any) -> None:
    """Measure every named item of the finished part into ``Document.measured``. Items
    that no longer resolve are left out."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    found = items(doc)
    if not found or body is None:
        doc.measured.pop(MEASURED_KEY, None)
        return
    values: dict[str, float] = {}
    for item in found:
        try:
            shape = resolve(body, item)
            props = GProp_GProps()
            if item["kind"] == "edge":
                BRepGProp.LinearProperties_s(shape, props)
                values[f"length@{item['name']}"] = props.Mass()
            else:
                BRepGProp.SurfaceProperties_s(shape, props)
                values[f"area@{item['name']}"] = props.Mass()
        except Exception:  # a name that no longer resolves has no value
            continue
    doc.measured[MEASURED_KEY] = values
