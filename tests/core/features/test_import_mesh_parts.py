"""Slicer 3MF parts as named bodies with roles (TR386, D1205)."""

from __future__ import annotations

from pathlib import Path

from fdcad.core.body_titles import report_marks, titles_of
from fdcad.core.features.base import FeatureState
from fdcad.core.features.import_mesh import part_from_mesh
from fdcad.core.features.solids import solids
from fdcad.core.io.export import export_3mf
from fdcad.core.printing import body_roles as br
from fdcad.core.rebuild.runner import rebuild
from tests.core.io.test_3mf_conformance import _two_boxes


def _doc(tmp_path: Path, keep: bool):  # type: ignore[no-untyped-def]
    out = tmp_path / "parts.3mf"
    export_3mf(
        _two_boxes(), out, name="Box", roles=[br.PART, br.MODIFIER], titles=["Shell", "Infill"]
    )
    doc = part_from_mesh("parts.3mf", out.read_bytes())
    feature = doc.features[-1]
    feature.params.update(
        {"convert": True, "parts": True, **({"keep_roles": True} if keep else {})}
    )
    return doc, feature


def test_parts_become_named_bodies_with_roles(tmp_path: Path) -> None:
    doc, feature = _doc(tmp_path, keep=True)
    results = rebuild(doc)
    res = results[feature.id]
    assert res.state is not FeatureState.ERROR, res.issues
    assert res.body is not None and len(solids(res.body.shape)) == 2
    report = type("R", (), {"results": results})()
    titles = titles_of(doc, res.body, report_marks(report, "body_titles"))
    assert titles == ["Shell", "Infill"]
    roles = br.roles_of(doc, res.body, report_marks(report, "body_roles"))
    assert roles == [br.PART, br.MODIFIER]
    # Setting the modifier back to Part is kept over the file's role.
    given = report_marks(report, "body_roles")
    doc.print_setup[br.BODY_ROLES] = br.with_roles(doc, res.body, [1], br.PART, given)
    assert br.roles_of(doc, res.body, given) == [br.PART, br.PART]


def test_roles_left_out_unless_kept(tmp_path: Path) -> None:
    doc, feature = _doc(tmp_path, keep=False)
    res = rebuild(doc)[feature.id]
    assert res.body is not None and len(solids(res.body.shape)) == 1
    assert res.extras["body_titles"] and "body_roles" not in res.extras


def test_without_parts_one_body(tmp_path: Path) -> None:
    doc, feature = _doc(tmp_path, keep=False)
    feature.params.pop("parts")
    res = rebuild(doc)[feature.id]
    assert res.body is not None
    assert "body_titles" not in res.extras
