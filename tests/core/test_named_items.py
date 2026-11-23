"""Named faces and edges (TR152, D2105)."""

import pytest
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp_Explorer

from fdcad.core import named_items, properties
from fdcad.core.graph.nodes.base import GraphEnv
from fdcad.core.io import fdef
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.engine import RebuildEngine
from tests.core.equations.test_equations import _plate


def _first(shape, kind):  # type: ignore[no-untyped-def]
    explorer = TopExp_Explorer(shape, kind)
    return explorer.Current()


def test_name_measure_and_use_in_a_property() -> None:
    doc = _plate()
    body = RebuildEngine().rebuild(doc).body
    assert body is not None
    face_ref = reference_for(body, _first(body.shape, TopAbs_FACE))
    edge_ref = reference_for(body, _first(body.shape, TopAbs_EDGE))
    assert face_ref is not None and edge_ref is not None
    assert named_items.add(doc, " Lid  face ", face_ref) == "Lid face"
    named_items.add(doc, "Rim", edge_ref)
    with pytest.raises(named_items.ItemNameError, match="already names"):
        named_items.add(doc, "rim", face_ref)
    with pytest.raises(named_items.ItemNameError, match="Start the name"):
        named_items.add(doc, "1st", face_ref)
    assert named_items.name_of(doc, face_ref) == "Lid face"
    named_items.add(doc, "Top", face_ref)  # a new name replaces the old one
    assert [i["name"] for i in named_items.items(doc)] == ["Rim", "Top"]
    doc.properties = [{"name": "TopArea", "kind": "number", "value": '="area@Top"'}]
    RebuildEngine().rebuild(doc)
    measured = doc.measured[named_items.MEASURED_KEY]
    assert measured["area@Top"] > 0 and measured["length@Rim"] > 0
    shown = properties.shown(doc)[0]
    assert shown.error == "" and shown.number == pytest.approx(measured["area@Top"])
    again = fdef.loads(fdef.dumps(doc))
    assert named_items.items(again) == named_items.items(doc)
    named_items.rename(again, "top", "Lid")
    named_items.remove(again, "Rim")
    assert [i["name"] for i in named_items.items(again)] == ["Lid"]


def test_a_model_reference_follows_a_name() -> None:
    from fdcad.core.graph import modelrefs
    from fdcad.core.graph.nodes.base import NodeContext

    doc = _plate()
    body = RebuildEngine().rebuild(doc).body
    face_ref = reference_for(body, _first(body.shape, TopAbs_FACE))
    named_items.add(doc, "Lid", face_ref)
    env = GraphEnv(body=body, named={"lid": face_ref})
    ctx = NodeContext.__new__(NodeContext)
    ctx.env, ctx.warnings = env, []
    out = modelrefs.resolve("face", {"named": "Lid"}, ctx)
    assert out["curve"] is not None
    from fdcad.core.graph.nodes.base import NodeError

    with pytest.raises(NodeError, match="no item named"):
        modelrefs.resolve("face", {"named": "Gone"}, ctx)
