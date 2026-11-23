"""Configurations: create, rename, switch, scoped overrides and the schema 2 file form
(PLAN Phase 4, PHASE4_SPEC P4.10 item 2, FDEF_SPEC 9 and 15, D391)."""

import copy
import json
from pathlib import Path

import pytest

from fdcad.core import configurations as configs
from fdcad.core.document.model import Document, Param, new_document
from fdcad.core.features.solids import volume_of
from fdcad.core.io import fdef
from fdcad.core.io.migrations import migrate
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.samples.make import SAMPLE_DIR
from tests.core.equations.test_equations import _plate

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _two(doc: Document | None = None) -> Document:
    doc = doc or _plate()
    configs.add(doc, "Long")
    return doc


def test_new_part_has_one_default_configuration() -> None:
    doc = new_document()
    assert configs.names(doc) == ["Default"]
    assert configs.active_name(doc) == "Default"
    assert configs.configured_paths(doc) == []


def test_add_rename_delete_and_name_checks() -> None:
    doc = _two()
    assert configs.names(doc) == ["Default", "Long"]
    with pytest.raises(configs.ConfigurationError, match="already exists"):
        configs.add(doc, "Long")
    with pytest.raises(configs.ConfigurationError, match="Enter"):
        configs.add(doc, "  ")
    configs.activate(doc, "Long")
    configs.rename(doc, "Long", "Longer")
    assert configs.names(doc) == ["Default", "Longer"]
    assert configs.active_name(doc) == "Longer"  # renaming keeps it active
    configs.delete(doc, "Longer")  # the active one: Default is shown again
    assert configs.names(doc) == ["Default"] and configs.active_name(doc) == "Default"
    with pytest.raises(configs.ConfigurationError, match="at least one"):
        configs.delete(doc, "Default")


def test_edit_in_this_configuration_only() -> None:
    doc = _two()
    ext = doc.features[-1].id
    configs.activate(doc, "Long")
    configs.set_scoped(doc, f"{ext}.depth", Param("30", 30.0), "this")
    assert doc.feature(ext).params["depth"] == Param("30", 30.0)
    configs.activate(doc, "Default")
    assert doc.feature(ext).params["depth"] == Param("10", 10.0)
    configs.activate(doc, "Long")
    assert doc.feature(ext).params["depth"] == Param("30", 30.0)
    assert configs.configured_paths(doc) == [f"{ext}.depth"]


def test_edit_in_all_configurations_makes_the_value_shared() -> None:
    doc = _two()
    ext = doc.features[-1].id
    configs.set_scoped(doc, f"{ext}.depth", Param("30", 30.0), "this")
    configs.set_scoped(doc, f"{ext}.depth", Param("12", 12.0), "all")
    assert configs.configured_paths(doc) == []
    configs.activate(doc, "Long")
    assert doc.feature(ext).params["depth"] == Param("12", 12.0)


def test_edit_in_chosen_configurations() -> None:
    doc = _two()
    configs.add(doc, "Short")
    ext = doc.features[-1].id
    configs.set_scoped(doc, f"{ext}.depth", Param("5", 5.0), "chosen", ["Long", "Short"])
    assert doc.feature(ext).params["depth"] == Param("10", 10.0)  # Default not chosen
    for name, value in (("Long", 5.0), ("Short", 5.0), ("Default", 10.0)):
        configs.activate(doc, name)
        depth = doc.feature(ext).params["depth"]
        assert isinstance(depth, Param) and depth.value == value


def test_unscoped_edit_follows_the_default_rule() -> None:
    doc = _two()
    ext = doc.feature(doc.features[-1].id)
    ext.params["depth"] = Param("20", 20.0)  # not configured: all configurations
    configs.activate(doc, "Long")
    assert ext.params["depth"] == Param("20", 20.0)
    configs.set_scoped(doc, f"{ext.id}.depth", Param("30", 30.0), "this")
    ext.params["depth"] = Param("35", 35.0)  # configured now: only this configuration
    configs.activate(doc, "Default")
    assert ext.params["depth"] == Param("20", 20.0)
    configs.activate(doc, "Long")
    assert ext.params["depth"] == Param("35", 35.0)


def test_suppression_variables_dimensions_and_settings_per_configuration() -> None:
    doc = _two()
    sketch, ext = doc.features[-2].id, doc.features[-1].id
    configs.activate(doc, "Long")
    configs.set_scoped(doc, f"{ext}.suppressed", True, "this")
    configs.set_scoped(doc, "var.Width", Param("80", 80.0), "this")
    configs.set_scoped(doc, f"{sketch}.d2", Param("50", 50.0), "this")
    configs.set_scoped(doc, f"{ext}.reverse", True, "this")
    assert doc.feature(ext).suppressed and doc.variables[0].expr == "80"
    configs.activate(doc, "Default")
    assert not doc.feature(ext).suppressed
    assert doc.variables[0].expr == "60" and doc.feature(ext).params["reverse"] is False
    dim = next(d for d in doc.feature(sketch).data["dimensions"] if d["id"] == "d2")
    assert configs.as_value(dim["param"]).expr == "40"


def test_unknown_paths_and_configurations_are_refused() -> None:
    doc = _two()
    with pytest.raises(configs.ConfigurationError):
        configs.get_value(doc, "f99.depth")
    with pytest.raises(configs.ConfigurationError):
        configs.get_value(doc, "var.Nope")
    with pytest.raises(configs.ConfigurationError, match="no configuration"):
        configs.set_scoped(doc, f"{doc.features[-1].id}.depth", Param("1", 1.0), "chosen", ["X"])


def test_rebuild_follows_the_active_configuration() -> None:
    doc = _two()
    ext = doc.features[-1].id
    configs.activate(doc, "Long")
    configs.set_scoped(doc, f"{ext}.depth", Param("30", 30.0), "this")
    engine = RebuildEngine()
    body = engine.rebuild(doc).body
    assert body is not None and volume_of(body.shape) == pytest.approx(60 * 40 * 30)
    configs.activate(doc, "Default")
    body = engine.rebuild(doc).body
    assert body is not None and volume_of(body.shape) == pytest.approx(60 * 40 * 10)


def test_schema_2_round_trip() -> None:
    doc = _two()
    ext = doc.features[-1].id
    configs.activate(doc, "Long")
    configs.set_scoped(doc, f"{ext}.depth", Param("30", 30.0), "this")
    configs.set_scoped(doc, f"{ext}.suppressed", True, "chosen", ["Default"])
    text = fdef.dumps(doc)
    data = json.loads(text)
    assert data["schema"] == 2
    long_item = data["configurations"]["items"][1]
    assert long_item == {
        "name": "Long",
        "overrides": {f"{ext}.depth": {"expr": "30", "value": 30}, f"{ext}.suppressed": False},
    }
    again = fdef.loads(text)
    assert configs.active_name(again) == "Long"
    assert again.feature(ext).params["depth"] == Param("30", 30.0)
    assert fdef.dumps(again) == text
    configs.activate(again, "Default")
    assert again.feature(ext).suppressed


def test_parts_without_configured_values_stay_schema_1() -> None:
    doc = _two()  # two configurations, nothing configured
    data = json.loads(fdef.dumps(doc))
    assert data["schema"] == 1
    assert data["configurations"]["items"][0] == {
        "name": "Default",
        "overrides": {},
        "suppressed": [],
    }


def test_migration_turns_suppressed_lists_into_overrides() -> None:
    raw = json.loads(fdef.dumps(_plate()))
    raw["configurations"] = {
        "active": "Default",
        "items": [
            {"name": "Default", "overrides": {}, "suppressed": []},
            {"name": "Lite", "overrides": {"f6.depth": {"expr": "5", "value": 5}},
             "suppressed": ["f6"]},
        ],
        "design_table": None,
    }  # fmt: skip
    out = migrate(copy.deepcopy(raw))
    assert out["schema"] == 2
    items = out["configurations"]["items"]
    assert items[0]["overrides"] == {"f6.suppressed": False}
    assert items[1]["overrides"] == {
        "f6.depth": {"expr": "5", "value": 5},
        "f6.suppressed": True,
    }
    doc = fdef.from_json_data(raw)
    configs.activate(doc, "Lite")
    assert doc.feature("f6").suppressed
    assert doc.feature("f6").params["depth"] == Param("5", 5.0)
    configs.activate(doc, "Default")
    assert doc.feature("f6").params["depth"] == Param("10", 10.0)  # filled from the file


OLDER = [p for p in sorted(SAMPLE_DIR.glob("*.fdprt")) if p.stem != "configured_bolt_family"]


@pytest.mark.parametrize("path", [*OLDER, *sorted(FIXTURES.glob("*.fdef"))], ids=lambda p: p.stem)
def test_every_older_file_opens_and_saves_unchanged(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert json.loads(text)["schema"] == 1
    doc = fdef.loads(text)
    assert configs.names(doc) == ["Default"]
    assert fdef.dumps(doc) == text


def test_follow_variables_moves_swaps_and_drops_overrides_and_columns() -> None:
    from fdcad.core import design_table as dt
    from fdcad.core.document.model import Variable
    from fdcad.core.units import Kind

    doc = _two()
    doc.variables += [Variable("A", Kind.LENGTH, "1", 1.0), Variable("B", Kind.LENGTH, "2", 2.0)]
    for name in ("Width", "A", "B"):
        configs.set_scoped(doc, f"var.{name}", Param("9", 9.0), "this")
    rows = [("Default", ["9", "9"]), ("Long", ["", ""])]
    dt.apply(doc, dt.Table(["var.A", "var.Width"], rows))
    configs.follow_variables(doc, {"A": "B", "B": "A", "Width": None})
    assert configs.configured_paths(doc) == ["var.A", "var.B"]
    table = doc.configurations["design_table"]
    assert table["columns"] == ["var.B"]
    assert all(len(row["values"]) == 1 for row in table["rows"])
    configs.follow_variables(doc, {"A": "A"})  # no change
    assert configs.configured_paths(doc) == ["var.A", "var.B"]


def test_values_of_a_deleted_feature_are_left_out_of_the_file() -> None:
    doc = _two()
    ext = doc.features[-1]
    configs.set_scoped(doc, f"{ext.id}.suppressed", True, "this")
    doc.features.remove(ext)
    assert configs.configured_paths(doc) == [f"{ext.id}.suppressed"]  # kept for undo
    assert configs.kept_paths(doc) == []
    saved = json.loads(fdef.dumps(doc))
    assert saved["schema"] == 1
    assert all(item["overrides"] == {} for item in saved["configurations"]["items"])


def test_linked_child_follows_the_parent_until_it_changes_a_value() -> None:
    """TR195, D868."""
    doc = _plate()
    ext = doc.features[-1].id
    path = f"{ext}.depth"
    configs.set_scoped(doc, path, Param("10", 10.0), "this")  # make depth configured
    configs.add(doc, "Other")
    configs.activate(doc, "Default")
    child = configs.add_linked(doc, "Child")
    assert child == "Child" and configs.own_paths(doc, "Child") == []
    # The parent changes: the child follows.
    configs.set_scoped(doc, path, Param("15", 15.0), "this")
    configs.activate(doc, "Child")
    assert doc.feature(ext).params["depth"].value == 15.0
    # The child changes the value itself: now its own.
    configs.set_scoped(doc, path, Param("30", 30.0), "this")
    configs.activate(doc, "Default")
    assert configs.own_paths(doc, "Child") == [path]
    configs.set_scoped(doc, path, Param("20", 20.0), "this")
    configs.activate(doc, "Child")
    assert doc.feature(ext).params["depth"].value == 30.0  # kept its own value
    # A feature added while the child is active is suppressed in the others.
    fid = doc.new_feature_id()
    from fdcad.core.document.model import Feature

    doc.features.append(Feature(fid, "sketch", "Late", refs={"plane": {"feature": "f2"}}))
    configs.suppress_in_others(doc, fid)
    configs.activate(doc, "Other")
    assert doc.feature(fid).suppressed
    configs.activate(doc, "Child")
    assert not doc.feature(fid).suppressed
    configs.delete(doc, "Default")  # the parent goes: the child stands alone
    assert configs.own_paths(doc, "Child") == []
