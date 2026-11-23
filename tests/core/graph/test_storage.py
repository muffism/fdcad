"""Graph storage in the .fdef (FDEF_SPEC 12A): round trips, schema 2, older files."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fdcad.core.cache.disk import document_key
from fdcad.core.document.model import new_document
from fdcad.core.graph.model import (
    Graph,
    GraphFormatError,
    Group,
    Node,
    Wire,
    graph_from_json,
    graph_to_json,
)
from fdcad.core.io import fdef
from fdcad.core.io.migrations import FileFormatError, migrate, migrate_1_to_2
from tests.core.graph.helpers import graph, p

ROOT = Path(__file__).resolve().parents[3]


def _sample_graph() -> Graph:
    g = graph(
        ("n1", "slider", {"min": 2, "max": 10, "step": 0.5, "value": p(4)}),
        ("n2", "cylinder", {"height": p(10)}),
        ("n3", "add_as_feature", {"operation": "subtract"}),
        wires=("n1.out>n2.radius", "n2.body>n3.body"),
    )
    g.position = "f4"
    g.groups.append(Group("k4", "Holes", ["n1", "n2"]))
    g.next_node = 5
    return g


def test_graph_json_round_trip_keeps_everything() -> None:
    g = _sample_graph()
    g.nodes[0].x, g.nodes[0].y = 40.0, 60.0
    data = graph_to_json(g)
    assert list(data) == ["id", "name", "position", "next_node", "nodes", "wires", "groups", "seed"]
    assert data["wires"][0] == {"from": "n1.out", "to": "n2.radius"}
    assert data["nodes"][0]["ui"] == {"x": 40.0, "y": 60.0}
    assert data["nodes"][0]["params"]["value"] == {"expr": "4", "value": 4.0}
    back = graph_from_json(json.loads(json.dumps(data)))
    assert back == g


def test_unknown_graph_keys_survive() -> None:
    data = graph_to_json(_sample_graph())
    data["future"] = {"x": 1}
    assert graph_to_json(graph_from_json(data))["future"] == {"x": 1}


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda d: d.update(nodes="x"), "invalid lists"),
        (lambda d: d["nodes"].append({"id": "n1", "type": "box"}), "same id"),
        (lambda d: d["wires"].append({"from": "n9.out", "to": "n1.x"}), "missing node"),
        (lambda d: d["wires"].append({"from": "n1", "to": "n2.x"}), "invalid end"),
        (lambda d: d.update(seed="1"), "seed"),
        (lambda d: d["nodes"][0].update(ui={"x": "a"}), "position"),
    ],
)
def test_damaged_graphs_are_refused(change: object, message: str) -> None:
    data = graph_to_json(_sample_graph())
    change(data)  # type: ignore[operator]
    with pytest.raises(GraphFormatError, match=message):
        graph_from_json(data)


def test_part_with_graph_saves_as_schema_2_with_graphs_after_features() -> None:
    doc = new_document()
    doc.graphs.append(_sample_graph())
    data = fdef.to_json_data(doc)
    assert data["schema"] == 2
    keys = list(data)
    assert keys.index("graphs") == keys.index("features") + 1
    again = fdef.loads(fdef.dumps(doc))
    assert again.graphs == doc.graphs
    assert fdef.dumps(again) == fdef.dumps(doc)


def test_part_without_graphs_stays_schema_1_and_byte_identical() -> None:
    for path in sorted((ROOT / "samples").glob("*.fdprt")) + sorted(
        (ROOT / "tests" / "fixtures").glob("*.fdef")
    ):
        text = path.read_text(encoding="utf-8")
        doc = fdef.loads(text)
        assert doc.graphs == []
        out = fdef.dumps(doc)
        # Configured values also need schema 2 (D391); only graphs are checked here.
        expected = 2 if json.loads(text)["schema"] == 2 else 1
        assert json.loads(out)["schema"] == expected, path.name
        assert "graphs" not in json.loads(out)
        if json.loads(text).get("app_version") == fdef.__version__:
            assert out == text, path.name


def test_migration_adds_an_empty_graph_list() -> None:
    assert migrate_1_to_2({"schema": 1})["graphs"] == []
    out = migrate({"schema": 1, "features": []})
    assert out["schema"] == 2 and out["graphs"] == []


def test_newer_schema_still_refused() -> None:
    data = fdef.to_json_data(new_document())
    data["schema"] = 3
    with pytest.raises(FileFormatError, match="newer version"):
        fdef.from_json_data(data)


def test_damaged_graph_in_file_is_a_file_error() -> None:
    data = fdef.to_json_data(new_document())
    data["schema"] = 2
    data["graphs"] = [{"id": 5}]
    with pytest.raises(FileFormatError, match="damaged"):
        fdef.from_json_data(data)


def test_cache_key_of_parts_without_graphs_is_unchanged() -> None:
    doc = new_document()
    before = document_key(doc)
    doc.graphs.append(_sample_graph())
    assert document_key(doc) != before
    doc.graphs.clear()
    assert document_key(doc) == before


def test_opening_a_graph_never_runs_code(tmp_path: Path) -> None:
    doc = new_document()
    g = _sample_graph()
    g.nodes.append(Node("n9", "__import__('os').system('x')", {"formula": "__import__('os')"}))
    doc.graphs.append(g)
    path = tmp_path / "g.fdef"
    fdef.save(doc, path)
    loaded = fdef.load(path)
    assert loaded.graphs[0].node("n9").type.startswith("__import__")
    from fdcad.core.graph.engine import Evaluator

    result = Evaluator().evaluate(loaded.graphs[0])
    assert "does not know" in (result.nodes["n9"].error or "")


def test_wire_text_form() -> None:
    assert Wire("n1", "out", "n2", "a").text == ("n1.out", "n2.a")
