"""Configurations: named sets of values for one part (PLAN Phase 4, FDEF_SPEC 9, D391).

The document's features and variables always hold the values of the *active*
configuration, so the rebuild, the tree and every panel work unchanged. Each
configuration stores, in ``overrides``, its own value for every *configured
path*: a value that differs between configurations. Paths are

- ``<feature id>.<param>``: a feature parameter (a parameter object, string,
  boolean or number),
- ``<feature id>.<dimension id>``: a sketch dimension (``f5.d1``),
- ``<feature id>.suppressed``: suppression (a boolean),
- ``var.<name>``: a global variable (a parameter object).

Every configuration holds a value for every configured path. A path that no
configuration overrides is shared by all configurations. Switching first
stores the live values of the configured paths in the active configuration,
so an edit made without choosing a scope changes only the active
configuration when the path is configured, and all configurations when it is
not (D391). Pure Python: no Qt, no kernel.
"""

from __future__ import annotations

import copy
from typing import Any

from fdcad.core.document.model import Document, Feature, Param

VAR_PREFIX = "var."
SUPPRESSED = "suppressed"
#: The part colour as a configured value (TR90 item 1, D2100).
PART_COLOR = "part.color"
#: Face, feature and body colours as one configured value (TR197 item 1, D2101).
PART_COLORS = "part.colors"
_COLOR_KEYS = ("faces", "features", "bodies")
#: A sketch's plane reference (TR197 item 1, D2101): "f5.plane".
PLANE = "plane"
#: Path ending for whether a sketch dimension drives (TR197 item 1, D2101): "f5.d1:driving".
DRIVING = ":driving"
SCOPES = ("this", "all", "chosen")
_MISSING = object()


class ConfigurationError(ValueError):
    """A configuration change is not possible. The message is shown to the user."""


def default_block() -> dict[str, Any]:
    """The configurations block of a new part: one configuration named Default."""
    from fdcad.core.document.model import default_configurations

    return default_configurations()


def _block(doc: Document) -> dict[str, Any]:
    block = doc.configurations
    if (
        not isinstance(block, dict)
        or not isinstance(block.get("items"), list)
        or not block["items"]
    ):
        doc.configurations = block = default_block()
    for item in block["items"]:
        if not isinstance(item.get("overrides"), dict):
            item["overrides"] = {}
    if block.get("active") not in [i.get("name") for i in block["items"]]:
        block["active"] = block["items"][0]["name"]
    return block


def items(doc: Document) -> list[dict[str, Any]]:
    """The configuration entries, in order."""
    return list(_block(doc)["items"])


def names(doc: Document) -> list[str]:
    """Configuration names, in order."""
    return [str(i["name"]) for i in _block(doc)["items"]]


def active_name(doc: Document) -> str:
    """The name of the active configuration."""
    return str(_block(doc)["active"])


def _item(doc: Document, name: str) -> dict[str, Any]:
    for item in _block(doc)["items"]:
        if item["name"] == name:
            return item  # type: ignore[no-any-return]
    raise ConfigurationError(
        f'There is no configuration named "{name}". Check the name in the configurations panel.'
    )


def configured_paths(doc: Document) -> list[str]:
    """Every path some configuration overrides, sorted."""
    out: set[str] = set()
    for item in _block(doc)["items"]:
        out.update(item["overrides"])
    return sorted(out)


# Reading and writing live values ------------------------------------------------------


def _split(path: str) -> tuple[str, str]:
    head, _, tail = path.partition(".")
    if not head or not tail:
        raise ConfigurationError(
            f'"{path}" is not a valid parameter path. Pick the value again in the table.'
        )
    return head, tail


def _feature(doc: Document, fid: str) -> Feature | None:
    return next((f for f in doc.features if f.id == fid), None)


def _dimension(feature: Feature, did: str) -> dict[str, Any] | None:
    if feature.type != "sketch":
        return None
    for dim in feature.data.get("dimensions", []):
        if isinstance(dim, dict) and dim.get("id") == did:
            return dim
    return None


#: Path ending for a sketch relation or dimension switched off (TR109, D829): "f5.r2:off"
#: (the third relation, counting from 0) or "f5.d3:off".
OFF = ":off"


def _switch(feature: Feature, key: str) -> dict[str, Any] | None:
    """The stored relation ``r<n>`` or dimension ``d<n>`` of a sketch, or None."""
    if feature.type != "sketch":
        return None
    if key.startswith("r") and key[1:].isdigit():
        relations = feature.data.get("relations", [])
        index = int(key[1:])
        item = relations[index] if index < len(relations) else None
        return item if isinstance(item, dict) else None
    return _dimension(feature, key)


def as_value(raw: Any) -> Any:
    """A stored override as a live value: parameter objects become ``Param``."""
    if isinstance(raw, dict) and set(raw) == {"expr", "value"}:
        return Param(str(raw["expr"]), float(raw["value"]))
    return copy.deepcopy(raw)


def get_value(doc: Document, path: str) -> Any:
    """The live value at ``path``. Raises ConfigurationError when it names nothing."""
    head, tail = _split(path)
    if path == PART_COLOR:
        from fdcad.core.document.model import DEFAULT_PART_COLOR

        return str(doc.appearance.get("part_color") or DEFAULT_PART_COLOR)
    if path == PART_COLORS:
        return {
            key: copy.deepcopy(doc.appearance.get(key) or {})
            for key in _COLOR_KEYS
            if isinstance(doc.appearance.get(key) or {}, dict)
        }
    if head + "." == VAR_PREFIX:
        var = next((v for v in doc.variables if v.name == tail), None)
        if var is None:
            raise ConfigurationError(
                f'There is no variable named "{tail}". '
                "Add it in Global Variables or remove the override."
            )
        return Param(var.expr, var.value)
    feature = _feature(doc, head)
    if feature is None:
        raise ConfigurationError(
            f'There is no feature with id "{head}". Remove the override for the deleted feature.'
        )
    if tail == SUPPRESSED:
        return feature.suppressed
    if tail.endswith(OFF):
        item = _switch(feature, tail[: -len(OFF)])
        if item is not None:
            return item.get("off") is True
    if tail.endswith(DRIVING):
        dim = _dimension(feature, tail[: -len(DRIVING)])
        if dim is not None:
            return dim.get("driving", True) is not False
    if tail in feature.params:
        return copy.deepcopy(feature.params[tail])
    if tail == PLANE and feature.type == "sketch" and isinstance(feature.refs.get(PLANE), dict):
        return copy.deepcopy(feature.refs[PLANE])
    dim = _dimension(feature, tail)
    if dim is not None:
        return as_value(dim.get("param"))
    raise ConfigurationError(
        f'{feature.name} has no value named "{tail}". Pick one of its values instead.'
    )


def set_value(doc: Document, path: str, value: Any) -> None:
    """Write ``value`` at ``path`` in the live document. Paths that name nothing are skipped."""
    try:
        head, tail = _split(path)
    except ConfigurationError:
        return
    value = as_value(value)
    if path == PART_COLOR:
        if isinstance(value, str) and value:
            doc.appearance["part_color"] = value
        return
    if path == PART_COLORS:
        if isinstance(value, dict):
            for key in _COLOR_KEYS:
                colours = value.get(key)
                if isinstance(colours, dict) and (colours or key == "faces"):
                    doc.appearance[key] = copy.deepcopy(colours)
                else:
                    doc.appearance.pop(key, None)
        return
    if head + "." == VAR_PREFIX:
        for var in doc.variables:
            if var.name != tail:
                continue
            if isinstance(value, Param):
                var.expr, var.value = value.expr, value.value
            elif isinstance(value, bool):  # a yes or no variable (TR417)
                var.expr, var.value = ("yes", 1.0) if value else ("no", 0.0)
            elif isinstance(value, str) and var.type == "text":
                var.expr = value
        return
    feature = _feature(doc, head)
    if feature is None:
        return
    if tail == SUPPRESSED:
        feature.suppressed = bool(value)
        return
    if tail.endswith(OFF):
        item = _switch(feature, tail[: -len(OFF)])
        if item is not None:
            if value is True:
                item["off"] = True
            else:
                item.pop("off", None)
        return
    if tail.endswith(DRIVING):
        dim = _dimension(feature, tail[: -len(DRIVING)])
        if dim is not None:
            dim["driving"] = bool(value)
        return
    if tail == PLANE and feature.type == "sketch" and tail not in feature.params:
        if isinstance(value, dict):
            feature.refs[PLANE] = copy.deepcopy(value)
        return
    dim = _dimension(feature, tail)
    if dim is not None and tail not in feature.params:
        if isinstance(value, Param):
            dim["param"] = value
        return
    feature.params[tail] = value


def path_exists(doc: Document, path: str) -> bool:
    """True when ``path`` names a value of this part."""
    try:
        get_value(doc, path)
    except ConfigurationError:
        return False
    return True


# Keeping configurations in step -------------------------------------------------------


def sync_active(doc: Document) -> None:
    """Store the live values of the configured paths in the active configuration. A
    linked child marks the values it changed as its own (TR195); the others follow
    its parent."""
    active = _item(doc, active_name(doc))
    for path in configured_paths(doc):
        if path_exists(doc, path):
            active["overrides"][path] = get_value(doc, path)
    parent = _parent_of(doc, active)
    if parent is not None:
        own = set(active.get("own") or [])
        for path, value in active["overrides"].items():
            if parent["overrides"].get(path, _MISSING) != value:
                own.add(path)
            else:
                own.discard(path)
        active["own"] = sorted(own)
    follow_parents(doc)


# Linked child configurations (TR195, D868) ----------------------------------------------


def _parent_of(doc: Document, item: dict[str, Any]) -> dict[str, Any] | None:
    name = item.get("parent")
    if not isinstance(name, str):
        return None
    return next((i for i in _block(doc)["items"] if i["name"] == name), None)


def follow_parents(doc: Document) -> None:
    """Give every linked child its parent's value for each path it did not change
    itself, parents first (a chain of children follows all the way down)."""
    done: set[str] = set()
    items = _block(doc)["items"]

    def follow(item: dict[str, Any], depth: int = 0) -> None:
        if item["name"] in done or depth > len(items):
            return
        parent = _parent_of(doc, item)
        if parent is not None:
            follow(parent, depth + 1)
            own = set(item.get("own") or [])
            for path, value in parent["overrides"].items():
                if path not in own:
                    item["overrides"][path] = copy.deepcopy(value)
        done.add(item["name"])

    for item in items:
        follow(item)


def own_paths(doc: Document, name: str) -> list[str]:
    """The paths a linked child sets itself (empty for other configurations)."""
    item = _item(doc, name)
    return list(item.get("own") or []) if isinstance(item.get("parent"), str) else []


def add_linked(doc: Document, name: str) -> str:
    """Add a configuration linked to the active one: it follows the active one's values
    until it changes them (TR195). Returns its name."""
    clean = add(doc, name)
    child = _item(doc, clean)
    child["parent"] = active_name(doc)
    child["own"] = []
    return clean


def unlink(doc: Document, name: str) -> None:
    """Make a linked child an ordinary configuration with its current values."""
    item = _item(doc, name)
    item.pop("parent", None)
    item.pop("own", None)


def suppress_in_others(doc: Document, fid: str) -> None:
    """A feature added while a linked child is active is suppressed in the other
    configurations (TR195)."""
    active = _item(doc, active_name(doc))
    if not isinstance(active.get("parent"), str):
        return
    path = f"{fid}.{SUPPRESSED}"
    for item in _block(doc)["items"]:
        item["overrides"][path] = item is not active
    own = set(active.get("own") or [])
    own.add(path)
    active["own"] = sorted(own)
    for item in _block(doc)["items"]:
        if isinstance(item.get("parent"), str) and item is not active:
            item.setdefault("own", [])
            if path not in item["own"]:
                item["own"] = sorted([*item["own"], path])


def normalize(doc: Document) -> None:
    """Give every configuration a value for every configured path (the live value)."""
    paths = configured_paths(doc)
    for item in _block(doc)["items"]:
        overrides = item["overrides"]
        for path in paths:
            if path not in overrides and path_exists(doc, path):
                overrides[path] = get_value(doc, path)
        item["overrides"] = {k: as_value(overrides[k]) for k in sorted(overrides)}


def apply_active(doc: Document) -> None:
    """Write the active configuration's values into the live document (after loading)."""
    normalize(doc)
    for path, value in _item(doc, active_name(doc))["overrides"].items():
        set_value(doc, path, value)


def activate(doc: Document, name: str) -> None:
    """Make ``name`` the active configuration and show its values."""
    target = _item(doc, name)
    sync_active(doc)
    normalize(doc)
    for path, value in target["overrides"].items():
        set_value(doc, path, value)
    _block(doc)["active"] = name


def check_name(doc: Document, name: str, ignore: str | None = None) -> str:
    """A cleaned up new configuration name. Raises ConfigurationError when it cannot be used."""
    clean = " ".join(name.split())
    if not clean:
        raise ConfigurationError("Enter a configuration name.")
    if any(c in clean for c in ',"\n'):
        raise ConfigurationError(
            "Configuration names cannot hold commas or quotes. Remove them from the name."
        )
    if clean != ignore and clean in names(doc):
        raise ConfigurationError(
            f'A configuration named "{clean}" already exists. Choose another name.'
        )
    return clean


def add(doc: Document, name: str) -> str:
    """Add a configuration with the active configuration's values. Returns its name."""
    clean = check_name(doc, name)
    sync_active(doc)
    overrides = copy.deepcopy(_item(doc, active_name(doc))["overrides"])
    _block(doc)["items"].append({"name": clean, "overrides": overrides})
    return clean


def rename(doc: Document, old: str, new: str) -> str:
    """Rename a configuration (and its design table row). Returns the new name."""
    item = _item(doc, old)
    clean = check_name(doc, new, ignore=old)
    block = _block(doc)
    if block["active"] == old:
        block["active"] = clean
    item["name"] = clean
    for other in block["items"]:
        if other.get("parent") == old:
            other["parent"] = clean
    table = block.get("design_table")
    if isinstance(table, dict):
        for row in table.get("rows", []):
            if row.get("config") == old:
                row["config"] = clean
    return clean


def delete(doc: Document, name: str) -> None:
    """Delete a configuration. The last one cannot be deleted; deleting the active one
    shows the first of the others."""
    block = _block(doc)
    if len(block["items"]) == 1:
        raise ConfigurationError(
            "A part needs at least one configuration. Add another one before deleting this one."
        )
    _item(doc, name)
    if block["active"] == name:
        activate(doc, next(n for n in names(doc) if n != name))
    block["items"] = [i for i in block["items"] if i["name"] != name]
    for item in block["items"]:  # children of a deleted parent stand on their own
        if item.get("parent") == name:
            unlink(doc, item["name"])
    table = block.get("design_table")
    if isinstance(table, dict):
        table["rows"] = [r for r in table.get("rows", []) if r.get("config") != name]


def unconfigure(doc: Document, path: str) -> None:
    """Make ``path`` shared again: every configuration uses the live value."""
    for item in _block(doc)["items"]:
        item["overrides"].pop(path, None)


def set_scoped(
    doc: Document,
    path: str,
    value: Any,
    scope: str,
    chosen: list[str] | None = None,
    old: Any = _MISSING,
) -> None:
    """Set ``path`` to ``value`` in this, all or the chosen configurations (P4.10 item 2).

    ``old`` is the value before the edit, when the live document already holds
    the new value (the property panel applies the edit first). Configurations
    that do not take the new value keep ``old``.
    """
    if scope not in SCOPES:
        raise ConfigurationError(f"Unknown scope {scope}. Use one of {', '.join(SCOPES)}.")
    previous = get_value(doc, path) if old is _MISSING else as_value(old)
    sync_active(doc)
    active = active_name(doc)
    if scope == "all":
        unconfigure(doc, path)
        set_value(doc, path, value)
        return
    targets = {active} if scope == "this" else set(chosen or [])
    unknown = targets - set(names(doc))
    if unknown:
        raise ConfigurationError(
            f'There is no configuration named "{sorted(unknown)[0]}". '
            "Check the name in the configurations panel."
        )
    for item in _block(doc)["items"]:
        overrides = item["overrides"]
        if item["name"] in targets:
            overrides[path] = as_value(value)
        elif path not in overrides or item["name"] == active:
            overrides[path] = as_value(previous)
        item["overrides"] = dict(sorted(overrides.items()))
    set_value(doc, path, value if active in targets else previous)
    _drop_if_shared(doc, path)


def _drop_if_shared(doc: Document, path: str) -> None:
    """A path with the same value in every configuration is shared again."""
    values = [i["overrides"].get(path, _MISSING) for i in _block(doc)["items"]]
    if values and all(v == values[0] for v in values) and values[0] is not _MISSING:
        unconfigure(doc, path)


def follow_variables(doc: Document, renamed: dict[str, str | None]) -> None:
    """Move ``var.<old>`` overrides and design table columns to ``var.<new>``.

    ``renamed`` maps old variable names to new ones; None means the variable
    was deleted, so its overrides and its column go too. Every rename is done
    at once, so swapping two names works.
    """
    moves = {
        f"{VAR_PREFIX}{old}": (f"{VAR_PREFIX}{new}" if new is not None else None)
        for old, new in renamed.items()
        if old != new
    }
    if not moves:
        return
    block = _block(doc)

    def moved(path: str) -> str | None:
        return moves.get(path, path)

    for item in block["items"]:
        old = item["overrides"]
        kept = {p: v for p, v in old.items() if p not in moves}
        for path, target in moves.items():
            if path in old and target is not None:
                kept[target] = old[path]
        item["overrides"] = dict(sorted(kept.items()))
    table = block.get("design_table")
    if isinstance(table, dict) and isinstance(table.get("columns"), list):
        columns = [str(c) for c in table["columns"]]
        keep = [i for i, c in enumerate(columns) if moved(c) is not None]
        table["columns"] = [str(moved(columns[i])) for i in keep]
        for row in table.get("rows") or []:
            values = row.get("values") if isinstance(row, dict) else None
            if isinstance(values, list):
                row["values"] = [values[i] for i in keep if i < len(values)]


def changed_paths(before: Feature, after: Feature) -> list[str]:
    """Paths of the values that differ between two copies of one feature."""
    out = []
    for name in sorted(set(before.params) | set(after.params)):
        if before.params.get(name, _MISSING) != after.params.get(name, _MISSING):
            out.append(f"{after.id}.{name}")
    if before.suppressed != after.suppressed:
        out.append(f"{after.id}.{SUPPRESSED}")
    return out


# File form ----------------------------------------------------------------------------


def owner_exists(doc: Document, path: str) -> bool:
    """False when the feature or variable a path belongs to was deleted.

    Such overrides stay in memory, so undoing the delete brings the values back,
    but they are left out of the saved file and the configured value count.
    """
    head, _, tail = path.partition(".")
    if path in (PART_COLOR, PART_COLORS):
        return True
    if head + "." == VAR_PREFIX:
        return any(v.name == tail for v in doc.variables)
    return _feature(doc, head) is not None


def kept_paths(doc: Document) -> list[str]:
    """The configured paths whose feature or variable still exists, sorted."""
    return [p for p in configured_paths(doc) if owner_exists(doc, p)]


def needs_schema_2(doc: Document) -> bool:
    """True when the configurations need schema 2: a configured value or a design table."""
    block = _block(doc)
    return bool(block.get("design_table")) or bool(kept_paths(doc))


def to_file(doc: Document) -> dict[str, Any]:
    """The configurations block as saved, without changing the document.

    Schema 1 form (``suppressed`` lists, D391) when nothing is configured, so
    older parts save exactly as before; schema 2 form otherwise, with the
    active configuration's live values.
    """
    block = _block(doc)
    schema_2 = needs_schema_2(doc)
    live = {p: get_value(doc, p) for p in configured_paths(doc) if path_exists(doc, p)}
    out_items = []
    for item in block["items"]:
        overrides = {p: v for p, v in item["overrides"].items() if owner_exists(doc, p)}
        if item["name"] == block["active"]:
            overrides.update({p: v for p, v in live.items() if p in overrides})
        entry: dict[str, Any] = {"name": item["name"], "overrides": dict(sorted(overrides.items()))}
        if not schema_2:
            entry["suppressed"] = []
        for key, value in item.items():
            if key not in entry and key != "suppressed":
                entry[key] = value
        out_items.append(entry)
    from fdcad.core.design_table import sync_rows

    out: dict[str, Any] = {
        "active": block["active"],
        "items": out_items,
        "design_table": sync_rows(doc),
    }
    for key, value in block.items():
        if key not in out:
            out[key] = value
    return out


def from_file(raw: Any, warnings: list[str] | None = None) -> dict[str, Any]:
    """A configurations block read from a schema 2 file (overrides as live values).

    Damaged entries are left out so the part still opens, and each adds a sentence
    to ``warnings`` saying what was left out (audit D3 item 21, D2678). A name that is
    repeated or breaks the name rules is made usable and reported (audit D5 item 4,
    D2679).
    """
    notes: list[str] = [] if warnings is None else warnings
    if raw is None:
        return default_block()
    if not isinstance(raw, dict) or not isinstance(raw.get("items"), list) or not raw["items"]:
        notes.append(
            "The configurations in the file are damaged and were left out, so the part has "
            "only the Default configuration. Open another copy of the file to get them back."
        )
        return default_block()
    block = dict(raw)
    block["items"] = []
    total = len(raw["items"])
    cleaned: dict[str, str] = {}
    for number, entry in enumerate(raw["items"], start=1):
        where = f"Configuration entry {number} of {total}"
        if not isinstance(entry, dict):
            notes.append(f"{where} is damaged (it is not a configuration) and was left out.")
            continue
        overrides = entry.get("overrides")
        name = entry.get("name")
        if not isinstance(name, str) or not _clean_name(name):
            count = len(overrides) if isinstance(overrides, dict) else 0
            notes.append(
                f"{where} has no name and was left out, with its {count} configured "
                f"value{'' if count == 1 else 's'}."
            )
            continue
        if overrides is not None and not isinstance(overrides, dict):
            notes.append(
                f'The values of configuration "{name}" are damaged and were left out, so it '
                "uses the part's values. Set them again in the configurations panel."
            )
        item = dict(entry)
        item["overrides"] = (
            {str(k): as_value(v) for k, v in overrides.items()}
            if isinstance(overrides, dict)
            else {}
        )
        item.pop("suppressed", None)
        taken = [str(i["name"]) for i in block["items"]]
        clean = _clean_name(name)
        if clean in taken:
            n = 2
            while f"{clean} {n}" in taken:
                n += 1
            item["name"] = f"{clean} {n}"
            notes.append(
                f'A second configuration named "{clean}" is now called "{item["name"]}". '
                "Rename it in the configurations panel if you like."
            )
        elif clean != name:
            item["name"] = cleaned.setdefault(name, clean)
            notes.append(
                f'The configuration "{name.strip()}" is now called "{clean}": names cannot '
                "hold commas, quotes, line breaks or extra spaces."
            )
        block["items"].append(item)
    if not block["items"]:
        notes.append("The part has only the Default configuration now.")
        return default_block()
    _follow_names(block, cleaned)
    found = [str(i["name"]) for i in block["items"]]
    active = block.get("active")
    if active not in found:
        notes.append(
            f'The active configuration "{active}" is not in the file, so "{found[0]}" is active.'
            if isinstance(active, str)
            else f'The file does not say which configuration is active, so "{found[0]}" is.'
        )
        block["active"] = found[0]
    block.setdefault("design_table", None)
    return block


def _clean_name(name: str) -> str:
    """``name`` as ``check_name`` would keep it: no commas, quotes or extra spaces."""
    return " ".join(name.replace(",", " ").replace('"', " ").split())


def _follow_names(block: dict[str, Any], cleaned: dict[str, str]) -> None:
    """Links to a configuration whose name was cleaned on read follow it: the active
    name, a child's parent and design table rows. A repeated name is not followed,
    since links to it always meant the first configuration of that name."""
    if not cleaned:
        return
    active = block.get("active")
    if isinstance(active, str) and active in cleaned:
        block["active"] = cleaned[active]
    for item in block["items"]:
        parent = item.get("parent")
        if isinstance(parent, str) and parent in cleaned:
            item["parent"] = cleaned[parent]
    table = block.get("design_table")
    if isinstance(table, dict) and isinstance(table.get("rows"), list):
        for row in table["rows"]:
            config = row.get("config") if isinstance(row, dict) else None
            if isinstance(config, str) and config in cleaned:
                row["config"] = cleaned[config]


def migrate_suppressed_lists(block: Any) -> Any:
    """Schema 1 to 2: each configuration's ``suppressed`` list becomes overrides.

    A feature listed by any configuration gets ``<id>.suppressed`` in every
    configuration: true where it was listed, false elsewhere.
    """
    if not isinstance(block, dict) or not isinstance(block.get("items"), list):
        return block
    listed: set[str] = set()
    for item in block["items"]:
        if isinstance(item, dict) and isinstance(item.get("suppressed"), list):
            listed.update(str(fid) for fid in item["suppressed"])
    out = dict(block)
    out["items"] = []
    for item in block["items"]:
        if not isinstance(item, dict):
            out["items"].append(item)  # left out and reported when the block is read (D2678)
            continue
        new = dict(item)
        suppressed = {str(f) for f in new.pop("suppressed", None) or []}
        overrides = dict(new.get("overrides") or {})
        for fid in sorted(listed):
            overrides[f"{fid}.{SUPPRESSED}"] = fid in suppressed
        new["overrides"] = overrides
        out["items"].append(new)
    return out
