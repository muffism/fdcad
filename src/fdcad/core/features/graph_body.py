"""Graph body: a body made by a node graph, added to the tree (PLAN Phase 7, D23).

``refs.graph`` names the graph and its Add as Feature node:
``{"graph": "g1", "output": "n3"}``. The node's ``operation`` says whether the
body is a new body, added to the part or subtracted from it. Faces are named
``<feature>/face/<k>`` in the order of the graph body's faces.
"""

from __future__ import annotations

from typing import Any

from fdcad.core.document.model import Document, Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    register,
)
from fdcad.core.features.solids import check_result, combine, compound
from fdcad.core.naming.names import NamedShape, faces_of, restrict


def _target(feature: Feature) -> tuple[str, str]:
    ref = feature.refs.get("graph")
    if not isinstance(ref, dict) or not isinstance(ref.get("graph"), str):
        raise FeatureError(f"{feature.name} has no graph. Delete it and add it again from a graph.")
    return str(ref["graph"]), str(ref.get("output", ""))


@register
class GraphBody(FeatureType):
    """The body from a graph's Add as Feature node."""

    type_name = "graph_body"
    makes_solid = True

    def key_data(self, feature: Feature, doc: Document, results: dict[str, FeatureResult]) -> Any:
        from fdcad.core.graph.drive import graph_of, position_index
        from fdcad.core.graph.model import graph_to_json

        try:
            gid, _node = _target(feature)
        except FeatureError:
            return None
        graph = graph_of(doc, gid)
        if graph is None:
            return None
        last = position_index(doc, graph)
        above = [(f.id, results[f.id].key) for f in doc.features[: last + 1] if f.id in results]
        variables = [(v.name, v.value) for v in doc.variables]
        data = graph_to_json(graph)
        for node in data["nodes"]:
            node.pop("ui", None)  # where nodes sit in the editor does not change the body
        data.pop("groups", None)
        data.pop("name", None)
        return [data, above, variables]

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        from fdcad.core.graph.drive import graph_of, make_env
        from fdcad.core.graph.engine import SHARED

        gid, nid = _target(feature)
        graph = graph_of(ctx.document, gid)
        if graph is None:
            raise FeatureError(f"{feature.name}: its graph is missing. Delete {feature.name}.")
        node = graph.find(nid)
        if node is None or node.type != "add_as_feature":
            raise FeatureError(
                f"{feature.name}: the Add as Feature node of {graph.name} is missing. "
                f"Add it again or delete {feature.name}."
            )
        env = make_env(ctx.document, graph, ctx.results, ctx.variables)
        outcome = SHARED.evaluate(graph, env, ctx.cancelled, targets=[nid])
        res = outcome.nodes.get(nid)
        if res is None or outcome.cancelled:
            raise FeatureError(f"{feature.name}: the graph did not finish. Rebuild.")
        failed = outcome.first_error(nid)
        if failed is not None:
            from fdcad.core.graph.nodes.base import NODE_TYPES

            bad = graph.find(failed[0])
            ntype = NODE_TYPES.get(bad.type) if bad is not None else None
            title = ntype.title if ntype is not None else (bad.type if bad is not None else "")
            # The editor shows node titles, not ids or type names.
            where = f" in its {title} node ({failed[0]})" if bad is not None else ""
            raise FeatureError(f"{feature.name}: {graph.name} has an error{where}: {failed[1]}")
        shape = res.outputs.get("out")
        if shape is None:
            raise FeatureError(f"{feature.name}: {graph.name} made no body. Connect a body.")
        faces = [(f"{feature.id}/face/{k}", f) for k, f in enumerate(faces_of(shape), start=1)]
        tool = NamedShape(shape, faces)
        operation = str(node.params.get("operation", "new"))
        body = ctx.body
        if operation == "add":
            result = combine(feature.id, feature.name, body, tool, "boss")
            # A graph body added to the part gets the body count check other bosses get,
            # so a lattice that comes apart from its base says so (audit E item 9.2, D746).
            issues = check_result(feature.id, feature.name, body, result, None)
            return FeatureResult(body=result, issues=issues)
        elif operation == "subtract":
            if body is None:
                raise FeatureError(
                    f"{feature.name} has nothing to subtract from. Add a body first."
                )
            result = combine(feature.id, feature.name, body, tool, "cut")
        elif body is None:
            result = tool
        else:
            joined = compound([body.shape, tool.shape])
            result = NamedShape(joined, restrict(body.faces + tool.faces, joined, feature.id))
        return FeatureResult(body=result)
