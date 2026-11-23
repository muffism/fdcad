"""Reading and writing `.fdef` files (FDEF_SPEC 2, 14, 15, 16)."""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from fdcad.core.document.model import Param, Variable, new_document
from fdcad.core.io import fdef
from fdcad.core.io.migrations import NEWER_FILE_MESSAGE, FileFormatError, migrate
from fdcad.core.units import Kind, UnitSystem

SPEC = Path(__file__).resolve().parents[3] / "FDEF_SPEC.md"


def _spec_example() -> str:
    """The complete minimal example from FDEF_SPEC section 16."""
    section = SPEC.read_text(encoding="utf-8").split("## 16. Complete minimal example", 1)[1]
    match = re.search(r"```json\n(.*?)```", section, re.S)
    assert match is not None
    return match.group(1)


def test_spec_example_loads() -> None:
    doc = fdef.loads(_spec_example())
    assert doc.units is UnitSystem.MM
    assert doc.next_id == 7
    assert doc.variables == [Variable("Size", Kind.LENGTH, "50", 50.0)]
    extrude = doc.feature("f6")
    assert extrude.params["depth"] == Param("10", 10.0)
    assert extrude.params["operation"] == "boss"
    assert extrude.refs == {"sketch": {"feature": "f5"}}
    sketch = doc.feature("f5")
    assert sketch.data["next_entity"] == 9
    assert len(sketch.data["entities"]) == 8
    assert doc.appearance["faces"] == {"f6/cap/end": "#2E6FD8"}


def test_round_trip_is_identical() -> None:
    doc = fdef.loads(_spec_example())
    text = fdef.dumps(doc)
    again = fdef.loads(text)
    assert again == doc
    assert fdef.dumps(again) == text


def test_canonical_form() -> None:
    doc = new_document()
    doc.variables.append(Variable("W", Kind.LENGTH, "1/3in", 25.4 / 3))
    text = fdef.dumps(doc)
    assert text.endswith("}\n")
    assert '\n  "format": "fdef",' in text  # two space indent
    data = json.loads(text)
    assert list(data) == [
        "format", "schema", "app_version", "units", "next_id", "variables",
        "configurations", "features", "rollback", "appearance", "print_setup", "embedded",
    ]  # fmt: skip
    assert list(data["features"][0]) == ["id", "type", "name", "suppressed", "params", "refs"]
    assert data["variables"][0]["value"] == 8.46666666667  # 12 significant digits
    assert data["schema"] == 1


def test_whole_numbers_have_no_decimal_point() -> None:
    doc = new_document()
    doc.variables.append(Variable("W", Kind.LENGTH, "50", 50.0))
    assert '"value": 50\n' in fdef.dumps(doc)


def test_unknown_keys_are_preserved() -> None:
    data: dict[str, Any] = json.loads(_spec_example())
    data["future_top"] = {"x": 1}
    data["features"][5]["future_feature_key"] = [1, 2]
    text = fdef.dumps(fdef.from_json_data(data))
    out = json.loads(text)
    assert out["future_top"] == {"x": 1}
    assert out["features"][5]["future_feature_key"] == [1, 2]


def test_save_and_load_file(tmp_path: Path) -> None:
    doc = new_document(UnitSystem.IN)
    path = tmp_path / "part.fdef"
    fdef.save(doc, path)
    assert fdef.load(path) == doc
    assert list(tmp_path.iterdir()) == [path]  # no temporary files left behind


def test_newer_schema_is_refused_with_spec_message() -> None:
    data = json.loads(_spec_example())
    data["schema"] = 99
    with pytest.raises(FileFormatError) as err:
        fdef.from_json_data(data)
    assert str(err.value) == NEWER_FILE_MESSAGE


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("not json", "not valid JSON"),
        ("[]", "not an FDCAD part file"),
        ('{"format": "other"}', "not an FDCAD part file"),
        ('{"format": "fdef"}', "schema"),
        ('{"format": "fdef", "schema": 1, "next_id": 5}', "feature list"),
        ('{"format": "fdef", "schema": 1, "features": []}', "next_id"),
        (
            '{"format": "fdef", "schema": 1, "next_id": 5, "units": "furlong", "features": []}',
            "unit system",
        ),
    ],
)
def test_bad_files_give_clear_errors(text: str, message: str) -> None:
    with pytest.raises(FileFormatError, match=message):
        fdef.loads(text)


@pytest.mark.parametrize(
    ("schema", "configurations"),
    [
        (1, {"items": [{"name": "A", "overrides": 5}]}),
        (2, {"items": [{"name": "A", "overrides": {"var.D": {"expr": "1", "value": None}}}]}),
        (2, {"items": [{"name": "A", "overrides": {"var.D": {"expr": "1", "value": "x"}}}]}),
    ],
)
def test_damaged_configurations_give_a_file_error(schema: int, configurations: Any) -> None:
    """Bug hunt F1: a damaged configurations block raised TypeError and broke Open."""
    data = {
        "format": "fdef",
        "schema": schema,
        "units": "mm",
        "next_id": 3,
        "features": [],
        "configurations": configurations,
    }
    with pytest.raises(FileFormatError, match=r"damaged.*Open a backup"):
        fdef.from_json_data(data)


def test_migrations_run_in_order() -> None:
    def one_to_two(data: dict[str, Any]) -> dict[str, Any]:
        data["log"] = [*data.get("log", []), "1->2"]
        return data

    def two_to_three(data: dict[str, Any]) -> dict[str, Any]:
        data["log"] = [*data["log"], "2->3"]
        return data

    out = migrate({"schema": 1}, target=3, steps={1: one_to_two, 2: two_to_three})
    assert out == {"schema": 3, "log": ["1->2", "2->3"]}


def test_missing_migration_step_is_an_error() -> None:
    with pytest.raises(FileFormatError, match="No upgrade from schema 1"):
        migrate({"schema": 1}, target=2, steps={})


def test_non_finite_values_cannot_be_saved() -> None:
    doc = new_document()
    doc.variables.append(Variable("W", Kind.LENGTH, "x", float("nan")))
    with pytest.raises(ValueError, match="Cannot save"):
        fdef.dumps(doc)
