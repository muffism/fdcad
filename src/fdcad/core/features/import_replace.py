"""Replace an imported body with a new file (TUTORIAL_REVIEW_SPEC TR11, D694).

The import feature keeps its id, name and place in the tree; only the embedded
file it reads changes, so later features rebuild on the new body. References
that do not fit the new body show as the usual lost reference errors on those
features. A STEP import takes a STEP file and a mesh import a mesh file. No Qt.
"""

from __future__ import annotations

from pathlib import PurePath
from typing import Any

from fdcad.core.document.model import Document, Feature
from fdcad.core.io.embedded import make_block, new_block_id

#: Import feature types and the file suffixes each one reads.
SUFFIXES = {
    "import_step": (".step", ".stp", ".igs", ".iges"),
    "import_mesh": (".stl", ".3mf", ".obj"),
}


class ReplaceError(ValueError):
    """The file cannot replace this import; the message says why."""


def can_replace(feature: Feature) -> bool:
    """True for import features that read an embedded file."""
    source = feature.refs.get("source")
    return feature.type in SUFFIXES and isinstance(source, dict) and "embedded" in source


def new_source(
    doc: Document, feature: Feature, filename: str, data: bytes
) -> tuple[str, dict[str, Any]]:
    """The block id and block for a file that replaces ``feature``'s file."""
    if not can_replace(feature):
        raise ReplaceError(f"{feature.name} is not an imported file.")
    suffix = PurePath(filename).suffix.lower()
    if suffix not in SUFFIXES[feature.type]:
        wanted = ", ".join(SUFFIXES[feature.type])
        raise ReplaceError(
            f"{feature.name} needs a file of the same kind ({wanted}). Choose another file."
        )
    if not data:
        raise ReplaceError(f"{filename} is empty. Choose another file.")
    bid = new_block_id(doc)
    if feature.type == "import_step":
        if suffix in (".igs", ".iges"):  # STEP and IGES replace each other (TR31)
            return bid, make_block("step", filename, data, format="iges")
        return bid, make_block("step", filename, data)
    from fdcad.core.io.mesh_import import format_of

    return bid, make_block("mesh", filename, data, format=format_of(filename))


def block_users(doc: Document, bid: str) -> list[str]:
    """Ids of features that read embedded block ``bid``."""
    out = []
    for f in doc.features:
        source = f.refs.get("source")
        if isinstance(source, dict) and source.get("embedded") == bid:
            out.append(f.id)
    return out
