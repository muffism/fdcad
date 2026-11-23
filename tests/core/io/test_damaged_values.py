"""Damaged values in a part file give the "damaged" message, never a raw error (D634).

Found in round 10e by changing one value at a time in sample files and opening
them in the app.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from fdcad.core.io import fdef
from fdcad.core.io.fdef import FileFormatError
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.rebuild.values import refresh_values
from fdcad.samples.make import SAMPLE_DIR


def _sample() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (SAMPLE_DIR / "plate_with_holes.fdprt").read_text(encoding="utf-8")
    )
    return data


def _write(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "damaged.fdprt"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.mark.parametrize("key", ["suppressed", "overrides"])
def test_configuration_entry_of_the_wrong_type(tmp_path: Path, key: str) -> None:
    data = _sample()
    data["configurations"]["items"][0][key] = 1.5  # was a TypeError
    with pytest.raises(FileFormatError, match="The file is damaged"):
        fdef.load(_write(tmp_path, data))


@pytest.mark.parametrize("key", ["appearance", "print_setup", "embedded"])
def test_top_block_that_is_not_an_object(tmp_path: Path, key: str) -> None:
    data = _sample()
    data[key] = "x"  # loaded, then broke the feature tree
    with pytest.raises(FileFormatError, match=f"'{key}' is not an object"):
        fdef.load(_write(tmp_path, data))


def test_sketch_dimension_value_of_the_wrong_type(tmp_path: Path) -> None:
    data = _sample()
    sketch = next(f for f in data["features"] if f["type"] == "sketch")
    sketch["dimensions"][0]["param"]["value"] = {"a": 1}  # was a TypeError on open
    doc = fdef.load(_write(tmp_path, data))
    refresh_values(doc)  # must not raise
    report = RebuildEngine().rebuild(doc)  # the sketch reports it as a feature error
    assert report.results
