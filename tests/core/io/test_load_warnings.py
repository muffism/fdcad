"""Opening reports what it left out or changed (audit D3 item 21, D5 item 4, D2678, D2679)."""

from __future__ import annotations

import json
from typing import Any

from fdcad.core import configurations
from fdcad.core.document.model import new_document
from fdcad.core.io import fdef


def _saved(**changes: Any) -> dict[str, Any]:
    data = fdef.to_json_data(new_document())
    data.update(changes)
    return data


def _open(data: dict[str, Any]) -> Any:
    return fdef.loads(json.dumps(data))


def _block(*items: Any, active: str = "Default") -> dict[str, Any]:
    return {"active": active, "items": list(items), "design_table": None}


def test_a_sound_part_opens_with_no_warnings() -> None:
    assert _open(_saved()).load_warnings == []


def test_damaged_configuration_entries_are_reported() -> None:
    raw = _saved(
        schema=2,
        configurations=_block(
            {"name": "Default", "overrides": {}},
            "not an entry",
            {"overrides": {"f1.suppressed": True}},
            {"name": "Long", "overrides": [1, 2]},
        ),
    )
    doc = _open(raw)
    assert configurations.names(doc) == ["Default", "Long"]
    notes = doc.load_warnings
    assert len(notes) == 3, notes
    assert "entry 2 of 4" in notes[0] and "left out" in notes[0]
    assert "entry 3 of 4 has no name" in notes[1] and "1 configured value." in notes[1]
    assert '"Long"' in notes[2] and "configurations panel" in notes[2]


def test_damaged_entries_in_an_old_schema_1_file_are_reported() -> None:
    raw = _saved(
        schema=1,
        configurations={
            "active": "Default",
            "items": [{"name": "Default", "suppressed": []}, 7],
        },
    )
    doc = _open(raw)
    assert configurations.names(doc) == ["Default"]
    assert any("entry 2 of 2" in n for n in doc.load_warnings), doc.load_warnings


def test_a_missing_active_configuration_is_reported() -> None:
    raw = _saved(schema=2, configurations=_block({"name": "A", "overrides": {}}, active="Gone"))
    doc = _open(raw)
    assert configurations.active_name(doc) == "A"
    assert any('"Gone"' in n for n in doc.load_warnings)


def test_a_damaged_configurations_block_is_reported() -> None:
    doc = _open(_saved(configurations={"active": "Default", "items": "x"}))
    assert configurations.names(doc) == ["Default"]
    assert "only the Default configuration" in doc.load_warnings[0]


def test_repeated_configuration_names_are_made_unique() -> None:
    raw = _saved(
        schema=2,
        configurations=_block(
            {"name": "Default", "overrides": {}},
            {"name": "Default", "overrides": {}},
            {"name": 'Big, "wide"', "overrides": {}, "parent": None},
            {"name": "Child", "overrides": {}, "parent": 'Big, "wide"'},
            active='Big, "wide"',
        ),
    )
    doc = _open(raw)
    assert configurations.names(doc) == ["Default", "Default 2", "Big wide", "Child"]
    assert configurations.active_name(doc) == "Big wide"  # the link follows the name
    assert doc.configurations["items"][3]["parent"] == "Big wide"
    assert len(doc.load_warnings) == 2, doc.load_warnings
    assert '"Default 2"' in doc.load_warnings[0]


def _view(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "center": [0, 0, 0],
        "direction": [0, 0, -1],
        "up": [0, 1, 0],
        "distance": 100,
        "scale": 1,
    }


def test_saved_view_names_are_checked_on_read() -> None:
    raw = _saved(views=[_view("Top"), _view("top"), _view("  "), _view("x" * 70)])
    doc = _open(raw)
    names = [v["name"] for v in doc.views]
    assert names == ["Top", "top 2", "View 1", "x" * 60]
    assert len(doc.load_warnings) == 3, doc.load_warnings
    assert '"top 2"' in doc.load_warnings[0] and "another saved view" in doc.load_warnings[0]
    # Saving writes the fixed names, so the file is sound the next time.
    assert _open(fdef.to_json_data(doc)).load_warnings == []


def test_folder_names_are_checked_on_read() -> None:
    raw = _saved(
        tree={
            "folders": [
                {"name": "Holes", "features": ["f1"]},
                {"name": "HOLES", "features": ["f2"]},
                {"name": "", "features": ["f3"]},
            ]
        }
    )
    doc = _open(raw)
    assert [f["name"] for f in doc.tree["folders"]] == ["Holes", "HOLES 2", "Folder 1"]
    assert len(doc.load_warnings) == 2, doc.load_warnings
    assert "another folder" in doc.load_warnings[0]
