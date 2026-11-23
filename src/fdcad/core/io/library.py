"""Library feature files (TR72 item 1, D2115).

A library feature file (``.fdlib``) holds one feature made from a sketch, or one
sketch, in FDCAD's own feature form, the same data Copy puts on the clipboard (TR9,
D685)::

    {"format": "fdlib", "version": 1, "name": "Slot",
     "feature": {...}, "sketch": {...} or null}

Reading never runs code (CLAUDE.md 5.10): the file is JSON read as data, size
limited, and the features are checked like a part file's. No Qt.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fdcad.core.document.model import Feature
from fdcad.core.io.fdef import (
    feature_from_json_data,
    feature_to_json_data,
    finite_float,
    no_constant,
)
from fdcad.core.io.migrations import FileFormatError

SUFFIX = ".fdlib"
FORMAT = "fdlib"
VERSION = 1
#: Larger files are refused (hostile file limits, audit D12).
MAX_BYTES = 20_000_000


class LibraryError(ValueError):
    """The library file cannot be written or read. The message says what to do."""


def to_data(feature: Feature, sketch: Feature | None) -> dict[str, Any]:
    """The file form of a feature and its sketch."""
    return {
        "format": FORMAT,
        "version": VERSION,
        "name": feature.name,
        "feature": feature_to_json_data(feature),
        "sketch": feature_to_json_data(sketch) if sketch is not None else None,
    }


def save(path: str | Path, feature: Feature, sketch: Feature | None) -> Path:
    """Write a library file. Raises OSError."""
    target = Path(path)
    if target.suffix.lower() != SUFFIX:
        target = target.with_suffix(SUFFIX)
    target.write_text(json.dumps(to_data(feature, sketch), indent=1), encoding="utf-8")
    return target


def from_data(raw: Any) -> tuple[Feature, Feature | None]:
    """The feature and its sketch from the file form. Raises LibraryError."""
    if not isinstance(raw, dict) or raw.get("format") != FORMAT:
        raise LibraryError("This is not an FDCAD library feature file. Choose a .fdlib file.")
    if not isinstance(raw.get("version"), int) or raw["version"] > VERSION:
        raise LibraryError("The library file was made by a newer FDCAD. Update FDCAD to insert it.")
    try:
        feature = feature_from_json_data(raw["feature"])
        sketch = feature_from_json_data(raw["sketch"]) if raw.get("sketch") else None
    except (KeyError, TypeError, ValueError, FileFormatError) as exc:
        raise LibraryError("The library file is damaged. Save the library feature again.") from exc
    if feature.type != "sketch" and (sketch is None or sketch.type != "sketch"):
        raise LibraryError("The library file is damaged. Save the library feature again.")
    return feature, sketch


def load(path: str | Path) -> tuple[Feature, Feature | None]:
    """Read a library file. Raises LibraryError or OSError."""
    source = Path(path)
    if source.stat().st_size > MAX_BYTES:
        raise LibraryError(
            f"{source.name} is larger than {MAX_BYTES // 1_000_000} MB. "
            "Choose a library feature file."
        )
    try:
        raw = json.loads(
            source.read_text(encoding="utf-8"), parse_constant=no_constant, parse_float=finite_float
        )
    except ValueError as exc:  # not UTF-8, not JSON, or NaN and Infinity (D2671)
        raise LibraryError(
            f"{source.name} cannot be read. Choose a library feature file saved by FDCAD."
        ) from exc
    return from_data(raw)
