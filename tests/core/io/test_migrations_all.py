"""Migration tests from every earlier schema version (PLAN Phase 6, PLAN 10 item 5, D430).

Schema 1 is the only earlier schema. Covered here:

1. Hand made schema 1 fixtures in ``tests/fixtures/schema1``, one per optional key
   group: each opens, rebuilds without errors and saves byte for byte the same,
   and loading it through ``migrate_1_to_2`` gives the same document.
2. A schema 1 form of every sample part: graphs and graph bodies left out and
   configured values reduced to the schema 1 ``suppressed`` lists. Each opens and
   saves as schema 1; samples that are schema 1 already save byte for byte.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from fdcad.core.document.model import BASE_SCHEMA_VERSION, SCHEMA_VERSION
from fdcad.core.features.base import FeatureState
from fdcad.core.io import fdef
from fdcad.core.io.migrations import migrate
from fdcad.core.io.migrations.v1_to_v2 import migrate_1_to_2
from fdcad.core.rebuild.runner import rebuild
from fdcad.samples.graphs import SAMPLE_DIR as GRAPH_SAMPLE_DIR
from fdcad.samples.make import SAMPLE_DIR

FIXTURES = Path(__file__).parents[2] / "fixtures" / "schema1"
SCHEMA1 = sorted(FIXTURES.glob("*.fdef"))
#: Fixtures that stay schema 1 when saved (the suppressed lists need schema 2, D391).
UNCHANGED = [p for p in SCHEMA1 if p.stem != "configurations_suppressed_lists"]
SAMPLES = sorted([*SAMPLE_DIR.glob("*.fdprt"), *GRAPH_SAMPLE_DIR.glob("*.fdprt")])

#: Each optional schema 1 key and the fixture that holds it.
OPTIONAL_KEYS = {
    "comment": "variable_comment",
    "suppression": "feature_suppression_and_comments",
    "comments": "feature_suppression_and_comments",
    "hidden": "appearance_lists",
    "shown": "appearance_lists",
    "features": "appearance_lists",
    "bodies": "appearance_lists",
    "down_face": "print_setup_down_face",
    "label": "dimension_label_measure_to_supplement",
    "measure_to": "dimension_label_measure_to_supplement",
    "supplement": "dimension_label_measure_to_supplement",
    "doubled_distance": "dimension_label_measure_to_supplement",
    "offset": "relation_offset_value",
    "value": "relation_offset_value",
    "source": "sketch_source",
    "texts": "sketch_texts",
    "pictures": "sketch_pictures",
    "image": "sketch_pictures",
    "merge": "extrude_options",
    "start_condition": "extrude_options",
    "start_offset": "extrude_options",
    "start_reverse": "extrude_options",
    "cut_outside": "extrude_options",
    "regions": "selected_regions",
    "skip": "pattern_skip",
    "x_future_block": "unknown_keys",
    "x_future_key": "unknown_keys",
    "suppressed": "configurations_suppressed_lists",
    "keep_separate_body": "keep_separate_body",
}


def test_every_optional_key_has_a_fixture() -> None:
    names = {p.stem for p in SCHEMA1}
    for key, name in OPTIONAL_KEYS.items():
        assert name in names, name
        assert f'"{key}"' in (FIXTURES / f"{name}.fdef").read_text(encoding="utf-8"), key


@pytest.mark.parametrize("path", UNCHANGED, ids=lambda p: p.stem)
def test_schema_1_fixture_opens_rebuilds_and_saves_unchanged(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert json.loads(text)["schema"] == BASE_SCHEMA_VERSION
    doc = fdef.loads(text)
    results = rebuild(doc)
    errors = {k: r.issues for k, r in results.items() if r.state is FeatureState.ERROR}
    assert errors == {}
    assert fdef.dumps(doc) == text


@pytest.mark.parametrize("path", SCHEMA1, ids=lambda p: p.stem)
def test_migrated_data_gives_the_same_document(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    direct = fdef.from_json_data(copy.deepcopy(data))
    upgraded = migrate(copy.deepcopy(data))
    assert upgraded["schema"] == SCHEMA_VERSION
    assert upgraded["graphs"] == []
    for item in upgraded["configurations"]["items"]:
        assert "suppressed" not in item
    assert fdef.from_json_data(upgraded) == direct
    # The migration works on a copy and never changes its input.
    assert data == json.loads(path.read_text(encoding="utf-8"))
    assert migrate_1_to_2(copy.deepcopy(data))["schema"] == BASE_SCHEMA_VERSION


def test_suppressed_lists_become_overrides_and_save_as_schema_2() -> None:
    text = (FIXTURES / "configurations_suppressed_lists.fdef").read_text(encoding="utf-8")
    doc = fdef.loads(text)
    assert not doc.feature("f6").suppressed  # "Default" is active
    saved = json.loads(fdef.dumps(doc))
    assert saved["schema"] == SCHEMA_VERSION
    assert [i["overrides"] for i in saved["configurations"]["items"]] == [
        {"f6.suppressed": False},
        {"f6.suppressed": True},
    ]
    again = fdef.loads(fdef.dumps(doc))
    assert again == doc
    assert fdef.dumps(again) == fdef.dumps(doc)


def _schema_1_form(data: dict[str, Any]) -> dict[str, Any]:
    """The closest schema 1 file to ``data``: no graphs, suppression lists only."""
    out = copy.deepcopy(data)
    out["schema"] = BASE_SCHEMA_VERSION
    graphs = out.pop("graphs", None)
    if graphs:
        out["features"] = [f for f in out["features"] if f["type"] != "graph_body"]
    block = out["configurations"]
    for item in block["items"]:
        overrides = item.get("overrides", {})
        item["suppressed"] = sorted(
            (
                p.removesuffix(".suppressed")
                for p, v in overrides.items()
                if p.endswith(".suppressed") and v
            ),
            key=lambda fid: int(fid[1:]),
        )
        item["overrides"] = {}
    block["design_table"] = None
    return out


@pytest.mark.parametrize("path", SAMPLES, ids=lambda p: p.stem)
def test_schema_1_form_of_every_sample_opens(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    old = _schema_1_form(data)
    doc = fdef.from_json_data(copy.deepcopy(old))
    assert doc.graphs == []
    assert len(doc.features) == len(old["features"])
    if not any(item["suppressed"] for item in old["configurations"]["items"]):
        assert json.loads(fdef.dumps(doc))["schema"] == BASE_SCHEMA_VERSION
    if data["schema"] == BASE_SCHEMA_VERSION:
        assert old == data
        assert fdef.dumps(doc) == text
        assert fdef.from_json_data(migrate(copy.deepcopy(data))) == doc
