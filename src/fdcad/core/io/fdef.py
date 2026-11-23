"""Read and write `.fdef` files in canonical form (`FDEF_SPEC.md` sections 2, 14 and 15).

Reading never runs code: the file is parsed as JSON data only.
"""

from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path
from typing import Any

from fdcad import __version__
from fdcad.core import configurations
from fdcad.core.document.model import (
    BASE_SCHEMA_VERSION,
    SCHEMA_VERSION,
    Document,
    Feature,
    Param,
    ParamValue,
    Variable,
)
from fdcad.core.io.migrations import FileFormatError, migrate
from fdcad.core.io.temp_file import make_temp
from fdcad.core.units import Kind, UnitSystem

_TOP_KEYS = (
    "format",
    "schema",
    "app_version",
    "units",
    "next_id",
    "variables",
    "configurations",
    "features",
    "graphs",
    "rollback",
    "appearance",
    "print_setup",
    "views",
    "tree",
    "equations_file",
    "embedded",
    "material",
    "properties",
    "mass_override",
    "solid",
)
_FEATURE_KEYS = ("id", "type", "name", "suppressed", "params", "refs")
_SIGNIFICANT_DIGITS = 12
#: What to do when a part file cannot be read (CLAUDE.md 8.4, bug hunt B5).
#: The file extension parts are saved with (DECISIONS D575).
PART_SUFFIX = ".fdprt"
#: Extensions FDCAD opens as parts: the current one and the one used before v1.0.
PART_SUFFIXES = (PART_SUFFIX, ".fdef")


def is_part_file(path: str | Path) -> bool:
    """True when ``path`` names an FDCAD part file (``.fdprt``, or an older ``.fdef``)."""
    return Path(path).suffix.lower() in PART_SUFFIXES


DAMAGED_NEXT = "Open a backup or an autosave copy of the part."


def _canonical_number(x: float) -> float | int:
    """Round to 12 significant digits. Whole numbers are written without a decimal point."""
    if not math.isfinite(x):
        raise ValueError(f"Cannot save the value {x}. Fix the parameter that produced it.")
    rounded = float(f"{x:.{_SIGNIFICANT_DIGITS}g}")
    if rounded == 0:
        return 0
    if rounded.is_integer() and abs(rounded) < 1e15:
        return int(rounded)
    return rounded


def _canonical(value: Any) -> Any:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, float):
        return _canonical_number(value)
    if isinstance(value, int):
        return value
    if isinstance(value, Param):
        return {"expr": value.expr, "value": _canonical_number(value.value)}
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_canonical(v) for v in value]
    raise TypeError(
        f"Cannot save a value of type {type(value).__name__}. Undo the last change, then save."
    )


def _feature_to_json(f: Feature) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": f.id,
        "type": f.type,
        "name": f.name,
        "suppressed": f.suppressed,
        "params": dict(f.params),
        "refs": f.refs,
    }
    for key, value in f.data.items():
        if key not in out:
            out[key] = value
    return out


def feature_to_json_data(feature: Feature) -> Any:
    """One feature's canonical JSON data, exactly as ``to_json_data`` writes it."""
    return _canonical(_feature_to_json(feature))


def feature_from_json_data(raw: Any) -> Feature:
    """One feature read back from ``feature_to_json_data`` output (for example from the
    clipboard). Raises FileFormatError on damaged data; nothing in it is run."""
    return _feature_from_json(raw)


def _graphs_to_json(doc: Document) -> dict[str, Any]:
    """The ``graphs`` key, only when the part has graphs (schema 2, FDEF_SPEC 12A)."""
    if not doc.graphs:
        return {}
    from fdcad.core.graph.model import graph_to_json

    return {"graphs": [graph_to_json(g) for g in doc.graphs]}


def _graphs_from_json(raw: Any) -> list[Any]:
    from fdcad.core.graph.model import GraphFormatError, graph_from_json

    if raw is None:
        return []
    if not isinstance(raw, list):
        raise _damaged("the graph list is invalid")
    try:
        return [graph_from_json(g) for g in raw]
    except GraphFormatError as exc:
        raise FileFormatError(str(exc)) from exc


def _variable_to_json(v: Variable) -> dict[str, Any]:
    out: dict[str, Any] = {"name": v.name, "kind": v.kind.value, "expr": v.expr, "value": v.value}
    if v.comment:
        out["comment"] = v.comment  # optional, left out when empty (D390)
    if v.allowed:
        out["allowed"] = dict(v.allowed)  # optional (TR274, D906)
    if v.lookup:
        out["lookup"] = dict(v.lookup)  # optional (TR198, D2102)
    if v.type:
        out["type"] = v.type  # optional (TR417, D2104)
    if v.group:
        out["group"] = v.group
    return out


def to_json_data(doc: Document) -> dict[str, Any]:
    """The document as JSON ready data, keys in spec order, unknown keys last."""
    data: dict[str, Any] = {
        "format": "fdef",
        "schema": SCHEMA_VERSION
        if doc.graphs or configurations.needs_schema_2(doc)
        else BASE_SCHEMA_VERSION,
        "app_version": __version__,
        "units": doc.units.value,
        "next_id": doc.next_id,
        "variables": [_variable_to_json(v) for v in doc.variables],
        "configurations": configurations.to_file(doc),
        "features": [_feature_to_json(f) for f in doc.features],
        **_graphs_to_json(doc),
        "rollback": doc.rollback,
        "appearance": doc.appearance,
        "print_setup": doc.print_setup,
        # Written only when the part has saved views, so older parts save unchanged (TR14).
        **({"views": doc.views} if doc.views else {}),
        **({"tree": doc.tree} if doc.tree else {}),
        # Only when linked, so parts without a link save unchanged (TR25).
        **({"equations_file": doc.equations_file} if doc.equations_file else {}),
        # Only when chosen, so parts without a material save unchanged (TR78, D803).
        **({"material": doc.material} if doc.material else {}),
        **({"properties": doc.properties} if doc.properties else {}),  # TR82 (D810)
        **({"mass_override": doc.mass_override} if doc.mass_override else {}),  # TR80
        "embedded": doc.embedded,
        # The finished solid (D1102): only when there is one, so parts saved without it
        # are unchanged; after every key of the spec, before unknown keys.
        **({"solid": doc.solid} if doc.solid else {}),
    }
    for key, value in doc.extra.items():
        if key not in data:
            data[key] = value
    result: dict[str, Any] = _canonical(data)
    return result


def dumps(doc: Document, path: str | os.PathLike[str] | None = None) -> str:
    """Serialize to canonical `.fdef` text: two space indent, newline at the end.

    With ``path``, the text is for a file there: paths to other parts in its folder
    tree are written relative to it (D2625, ``core.io.part_links``).
    """
    data = to_json_data(doc)
    if path is not None:
        from fdcad.core.io import part_links

        data = part_links.for_file(data, Path(path))
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def save(doc: Document, path: str | os.PathLike[str]) -> None:
    """Write ``doc`` to ``path`` atomically, so a crash never leaves a half written file."""
    save_text(dumps(doc, path), path)


def save_text(text: str, path: str | os.PathLike[str]) -> None:
    """Write part text made by ``dumps`` to ``path`` atomically (see ``save``)."""
    target = Path(path)
    fd, tmp = make_temp(target.parent, target)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())  # on the disk before it replaces the old file
        # Read it back: a short or damaged write must never replace a good part
        # (audit D3 item 15, spec 2 section 21 item 10, D723).
        if Path(tmp).read_text(encoding="utf-8") != text:
            raise OSError("the saved file did not read back the same")
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


# Reading ------------------------------------------------------------------


def _damaged(what: str) -> FileFormatError:
    return FileFormatError(f"The file is damaged: {what}. {DAMAGED_NEXT}")


def _param_value(raw: Any) -> ParamValue:
    """A stored parameter. Values a newer FDCAD may write open too (audit D5 item 2,
    D726): an ``expr`` and ``value`` object with more keys reads as its value, and
    lists or other objects are kept as they are, so the part still opens."""
    if isinstance(raw, dict) and {"expr", "value"} <= set(raw):
        expr, value = raw["expr"], raw["value"]
        if (
            not isinstance(expr, str)
            or isinstance(value, bool)
            or not isinstance(value, int | float)
        ):
            raise _damaged("a parameter has an invalid expression or value")
        return Param(expr, float(value))
    if raw is None or isinstance(raw, str | bool | int | float):
        return raw
    if isinstance(raw, list | dict):
        kept: list[Any] | dict[str, Any] = copy.deepcopy(raw)
        return kept
    raise _damaged("a parameter has an unsupported value")


def _feature_from_json(raw: Any) -> Feature:
    if not isinstance(raw, dict):
        raise _damaged("a feature is not an object")
    for key in ("id", "type", "name"):
        if not isinstance(raw.get(key), str):
            raise _damaged(f"a feature has no valid '{key}'")
    params = raw.get("params", {})
    refs = raw.get("refs", {})
    if not isinstance(params, dict) or not isinstance(refs, dict):
        raise _damaged(f"feature {raw['id']} has invalid params or refs")
    return Feature(
        id=raw["id"],
        type=raw["type"],
        name=raw["name"],
        suppressed=_flag(raw.get("suppressed", False), raw["id"]),
        params={k: _param_value(v) for k, v in params.items()},
        refs=refs,
        data={k: v for k, v in raw.items() if k not in _FEATURE_KEYS},
    )


def _variable_from_json(raw: Any) -> Variable:
    try:
        return Variable(
            name=str(raw["name"]),
            kind=Kind(raw["kind"]),
            expr=str(raw["expr"]),
            value=float(raw["value"]),
            comment=str(raw.get("comment", "")),
            allowed=dict(raw["allowed"]) if isinstance(raw.get("allowed"), dict) else None,
            lookup=dict(raw["lookup"]) if isinstance(raw.get("lookup"), dict) else None,
            type=str(raw["type"]) if raw.get("type") in ("text", "yes_no") else "",
            group=str(raw.get("group") or ""),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise _damaged("a variable is invalid") from exc


def from_json_data(data: Any) -> Document:
    """Build a document from parsed JSON data, migrating older schemas in memory.

    Raises FileFormatError only: a value of the wrong type anywhere in the data
    (bug hunt F1) is reported as a damaged file, never as a Python error.
    """
    try:
        return _from_json_data(data)
    except FileFormatError:
        raise
    except (TypeError, ValueError, KeyError, AttributeError, IndexError) as exc:
        raise _damaged("a value has the wrong type") from exc


def _from_json_data(data: Any) -> Document:
    if not isinstance(data, dict) or data.get("format") != "fdef":
        raise FileFormatError("This is not an FDCAD part file. Choose a .fdprt file.")
    try:
        return _document_from_json(data)
    except FileFormatError:
        raise
    except (KeyError, IndexError, TypeError, AttributeError, ValueError) as exc:
        # A value of the wrong type that no check above caught (round 10e, D634).
        raise _damaged("an entry has a value of the wrong type") from exc


def _document_from_json(data: dict[str, Any]) -> Document:
    data = migrate(dict(data))
    try:
        units = UnitSystem(data.get("units", "mm"))
    except ValueError as exc:
        raise _damaged("unknown unit system") from exc
    features = data.get("features")
    if not isinstance(features, list):
        raise _damaged("the feature list is missing")
    next_id = data.get("next_id")
    if not isinstance(next_id, int) or isinstance(next_id, bool) or next_id < 1:
        raise _damaged("'next_id' is missing or invalid")
    variables = data.get("variables", [])
    if not isinstance(variables, list):
        raise _damaged("the variable list is invalid")
    rollback = data.get("rollback")
    link = data.get("equations_file", "")
    if not isinstance(link, str):
        raise _damaged("'equations_file' is not text")
    for key in ("appearance", "print_setup", "embedded"):
        if data.get(key) is not None and not isinstance(data[key], dict):
            raise _damaged(f"'{key}' is not an object")
    notes: list[str] = []  # what opening left out or changed (D2678)
    doc = Document(
        units=units,
        next_id=next_id,
        variables=[_variable_from_json(v) for v in variables],
        configurations=configurations.from_file(data.get("configurations"), notes),
        features=[_feature_from_json(f) for f in features],
        rollback=rollback if isinstance(rollback, str) else None,
        appearance=data.get("appearance") or {"part_color": "#B4BCC4", "faces": {}},
        print_setup=data.get("print_setup") or {"down_face": None},
        views=_views_from_json(data.get("views"), notes),
        tree=_tree_from_json(data.get("tree"), notes),
        equations_file=link,
        material=_material_from_json(data.get("material")),
        properties=_properties_from_json(data.get("properties")),
        mass_override=_override_from_json(data.get("mass_override")),
        embedded=data.get("embedded") or {},
        app_version=str(data.get("app_version", "")),
        solid=data["solid"] if isinstance(data.get("solid"), dict) else {},
        extra={k: v for k, v in data.items() if k not in _TOP_KEYS},
        graphs=_graphs_from_json(data.get("graphs")),
        load_warnings=notes,
    )
    _check_ids(doc)
    configurations.apply_active(doc)  # the live values are the active configuration's
    return doc


def _flag(value: object, fid: str) -> bool:
    """A true or false key. Text "false" was read as true, so the feature came out
    suppressed (audit D5 item 4, D744)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    raise _damaged(f"feature {fid} has a 'suppressed' value that is not true or false")


def _check_ids(doc: Document) -> None:
    """Feature ids are unique, the next id is above every used one, and the rollback bar
    names a feature (audit D3 item 7, D5 item 4, D723). Repeated ids make the file
    damaged; a low next id is raised and a rollback naming nothing is cleared, so ids
    never repeat later."""
    seen: set[str] = set()
    for f in doc.features:
        if f.id in seen:
            raise _damaged(f"the feature id '{f.id}' is used twice")
        seen.add(f.id)
    used = [int(f.id[1:]) for f in doc.features if f.id[:1] == "f" and f.id[1:].isdigit()]
    if used and doc.next_id <= max(used):
        doc.next_id = max(used) + 1
    if doc.rollback is not None and doc.rollback not in seen:
        doc.rollback = None


def _views_from_json(raw: Any, notes: list[str]) -> list[dict[str, Any]]:
    """The saved views (TR14). Damaged entries make the file damaged, as elsewhere; a
    name that is empty, too long or repeated is changed and noted (D2679)."""
    from fdcad.core.document.saved_views import (
        SavedViewError,
        usable_names,
        view_from_json,
        view_to_json,
    )

    if raw is None:
        return []
    if not isinstance(raw, list):
        raise _damaged("'views' is not a list")
    try:
        # Keys a newer FDCAD added to a view stay (FDEF_SPEC 14.4, audit D5 item 1, D726).
        views = [{**v, **view_to_json(view_from_json(v))} for v in raw]
    except SavedViewError as exc:
        raise _damaged(str(exc)) from exc
    return usable_names(views, notes)


def _tree_from_json(raw: Any, notes: list[str]) -> dict[str, Any]:
    """Tree folders and comments (TR23); folder names are made usable and noted (D2679)."""
    from fdcad.core.document.tree_info import TreeInfoError, checked, usable_names

    if raw is None:
        return {}
    try:
        tree = checked(raw)
    except TreeInfoError as exc:
        raise _damaged(str(exc)) from exc
    return usable_names(tree, notes)


#: The largest part file FDCAD opens (audit D12 item 7, D709).
MAX_FILE = 2 << 30


class _RepeatedKeyError(ValueError):
    """A JSON object names one key twice (audit D5 item 5, D738)."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


def _no_repeats(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build a JSON object, refusing a key that appears twice (the last one used to win)."""
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise _RepeatedKeyError(key)
        out[key] = value
    return out


class _NotANumberError(ValueError):
    """NaN, Infinity, or a number too large for a float, in a part file (D2671). FDCAD
    never writes them, and a feature holding one could not be rebuilt or saved."""

    def __init__(self, word: str) -> None:
        super().__init__(f"{word} is too large or not a number")
        self.word = word


def finite_float(text: str) -> float:
    """A JSON number as a float, refusing one too large to hold, such as 1e400, which
    would read as an infinite number (D2671). Raises ValueError."""
    value = float(text)
    if not math.isfinite(value):
        raise _NotANumberError(text)
    return value


def no_constant(word: str) -> Any:
    """For ``json.loads(parse_constant=...)``: refuse NaN and Infinity. Raises ValueError."""
    raise _NotANumberError(word)


def loads(text: str) -> Document:
    """Parse `.fdef` text. Raises FileFormatError with a user facing message."""
    if text.startswith(chr(0xFEFF)):
        text = text[1:]  # a byte order mark added by an editor (audit D5 item 5, D738)
    try:
        data = json.loads(
            text,
            object_pairs_hook=_no_repeats,
            parse_constant=no_constant,
            parse_float=finite_float,
        )
    except _NotANumberError as exc:
        raise FileFormatError(
            f"The file is damaged: it has a value that is too large or not a number "
            f"({exc.word}). {DAMAGED_NEXT}"
        ) from None
    except _RepeatedKeyError as exc:
        raise FileFormatError(
            f"The file is damaged: the key {exc.key!r} appears twice in one object, so it is "
            f"not clear which value to use. {DAMAGED_NEXT}"
        ) from None
    except json.JSONDecodeError as exc:
        raise FileFormatError(
            f"The file is damaged: it is not valid JSON (line {exc.lineno}). {DAMAGED_NEXT}"
        ) from exc
    except (RecursionError, ValueError) as exc:
        # Nesting too deep for the reader, or a number with thousands of digits
        # (audit D12 item 7, D709).
        raise FileFormatError(
            f"The file is damaged: it nests too deeply or has a number too long to read. "
            f"{DAMAGED_NEXT}"
        ) from exc
    try:
        return from_json_data(data)
    except FileFormatError:
        raise
    except (RecursionError, ValueError, TypeError, KeyError, AttributeError, IndexError) as exc:
        raise FileFormatError(
            f"The file is damaged: a value has the wrong form ({type(exc).__name__}). "
            f"{DAMAGED_NEXT}"
        ) from exc


def load(path: str | os.PathLike[str]) -> Document:
    """Read a `.fdef` file. Raises FileFormatError or OSError."""
    if Path(path).stat().st_size > MAX_FILE:
        raise FileFormatError(
            "The file is larger than FDCAD opens (2 GB), so it is damaged or not a part. "
            "Open another copy of the part."
        )
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise FileFormatError(f"The file is damaged: it is not UTF-8 text. {DAMAGED_NEXT}") from exc
    from fdcad.core.io import part_links

    return part_links.opened(loads(text), Path(path))  # other parts' paths absolute (D2625)


def _material_from_json(raw: Any) -> dict[str, Any]:
    """The saved material (TR78); a damaged one is dropped, so the part still opens."""
    from fdcad.core.materials import from_data

    found = from_data(raw)
    return found.to_data() if found is not None else {}


def _override_from_json(raw: Any) -> dict[str, Any]:
    """The saved mass override (TR80, D1021); a damaged one is dropped, so the part opens."""
    from fdcad.core.mass import override_from_data

    found = override_from_data(raw)
    return found.to_data() if found is not None else {}


def _properties_from_json(raw: Any) -> list[dict[str, Any]]:
    """The saved custom properties (TR82); damaged rows are dropped, so the part opens."""
    from fdcad.core.document.model import Document
    from fdcad.core.properties import rows

    if not isinstance(raw, list):
        return []
    holder = Document(properties=[r for r in raw if isinstance(r, dict)])
    return [row.to_data() for row in rows(holder)]
