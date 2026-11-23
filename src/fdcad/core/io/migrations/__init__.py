"""Schema migrations for `.fdef` files (FDEF_SPEC 15).

Each step upgrades raw JSON data by one schema version. Add the next step
here with tests for every new schema.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fdcad.core.document.model import SCHEMA_VERSION
from fdcad.core.io.migrations.v1_to_v2 import migrate_1_to_2

Migration = Callable[[dict[str, Any]], dict[str, Any]]


#: Maps a schema version to the function that upgrades it to the next version.
MIGRATIONS: dict[int, Migration] = {1: migrate_1_to_2}

NEWER_FILE_MESSAGE = (
    "This file was made with a newer version of FDCAD. Please update FDCAD to open it."
)


class FileFormatError(ValueError):
    """The file cannot be opened. The message is shown to the user as is."""


def migrate(
    data: dict[str, Any],
    target: int = SCHEMA_VERSION,
    steps: dict[int, Migration] | None = None,
) -> dict[str, Any]:
    """Upgrade raw file data to ``target`` in memory. The file on disk is not touched."""
    chain = MIGRATIONS if steps is None else steps
    schema = data.get("schema")
    if not isinstance(schema, int) or isinstance(schema, bool) or schema < 1:
        raise FileFormatError(
            "The file has no valid schema version. It may be damaged. "
            "Open a backup or an autosave copy of the part."
        )
    if schema > target:
        raise FileFormatError(NEWER_FILE_MESSAGE)
    while schema < target:
        step = chain.get(schema)
        if step is None:
            raise FileFormatError(
                f"No upgrade from schema {schema} is available. Update FDCAD to open this file."
            )
        data = step(data)
        schema += 1
        data["schema"] = schema
    return data
