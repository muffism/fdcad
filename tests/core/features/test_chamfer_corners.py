"""Chamfer corners: Patch or Mitre where three bevels meet (TR321, D1812)."""

from __future__ import annotations

from typing import Any

from OCP.BRepAdaptor import BRepAdaptor_Curve

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, plate, volume


def _corner_chamfer(corner: str | None) -> tuple[Any, str]:
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    from fdcad.core.features.modify import edges_of
    from fdcad.core.naming.names import faces_of

    refs: list[dict[str, Any]] = []
    seen: list[Any] = []
    for face in faces_of(b.shape):
        for edge in edges_of(face):
            c = BRepAdaptor_Curve(edge)
            ends = [c.Value(c.FirstParameter()), c.Value(c.LastParameter())]
            at_corner = any(p.X() < 1e-6 and p.Y() < 1e-6 and p.Z() > 10 - 1e-6 for p in ends)
            if at_corner and not any(edge.IsSame(s) for s in seen):
                seen.append(edge)
                ref = reference_for(b, edge)
                assert ref is not None
                refs.append(ref)
    assert len(refs) == 3
    params: dict[str, Any] = {"distance": Param("2", 2.0)}
    if corner:
        params["corner"] = corner
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, "chamfer", "Chamfer 1", params=params, refs={"edges": refs}))
    return rebuild(doc)[fid], fid


def test_mitre_leaves_no_corner_face() -> None:
    patch, fid = _corner_chamfer(None)
    mitred, fid2 = _corner_chamfer("mitre")
    assert patch.state is FeatureState.OK, messages(patch)
    assert mitred.state is FeatureState.OK, messages(mitred)
    assert any(n.startswith(f"{fid}/corner") for n, _f in patch.body.faces)
    names = [n for n, _f in mitred.body.faces]
    assert not any(n.startswith(f"{fid2}/corner") or n.startswith(f"{fid2}/mitre") for n in names)
    assert len([n for n in names if n.startswith(f"{fid2}/chamfer/")]) == 3
    assert len(mitred.body.faces) == len(patch.body.faces) - 1
    assert volume(mitred.body.shape) != volume(patch.body.shape)


def test_blend_replaces_the_corner_with_a_curved_face() -> None:
    """TR321 (D2304)."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Plane

    patch, _fid = _corner_chamfer(None)
    blended, fid2 = _corner_chamfer("blend")
    assert blended.state is FeatureState.OK, messages(blended)
    assert len(blended.body.faces) == len(patch.body.faces)
    assert len([n for n, _f in blended.body.faces if n.startswith(f"{fid2}/chamfer/")]) == 3
    corner = [f for n, f in blended.body.faces if n.startswith(f"{fid2}/corner")]
    assert len(corner) == 1
    assert BRepAdaptor_Surface(corner[0]).GetType() != GeomAbs_Plane
    # The curved face bulges out of the flat triangle, toward the mitre point.
    mitred, _fid3 = _corner_chamfer("mitre")
    v_patch, v_blend = volume(patch.body.shape), volume(blended.body.shape)
    assert v_patch < v_blend < volume(mitred.body.shape)
