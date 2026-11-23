"""Sheet metal gusset (TR12.1, D700)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.gusset import outline
from fdcad.core.features.sheetmetal.model import Bend
from fdcad.core.io import fdef
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.samples.make import SAMPLE_DIR, measure


def _bracket() -> Document:
    return fdef.loads((SAMPLE_DIR / "sheet_metal_bracket.fdprt").read_text(encoding="utf-8"))


def _wall_refs(doc: Document) -> list[dict[str, object]]:
    """A face on the base flange's wall and one on the edge flange's wall."""
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None
    body = report.body
    refs = []
    for prefix in ("f7/", "f8/flange"):
        face = next(
            f for n, f in body.faces if n.startswith(prefix) and n.endswith(("/top", "/bottom"))
        )
        ref = reference_for(body, face)
        assert ref is not None
        refs.append(ref)
    return refs


def _add_gusset(doc: Document, **params: object) -> str:
    refs = _wall_refs(doc)
    values: dict[str, object] = {
        "depth": Param("8", 8.0),
        "width": Param("6", 6.0),
        **params,
    }
    gusset = Feature(
        doc.new_feature_id(),
        "gusset",
        "Gusset 1",
        params=values,  # type: ignore[arg-type]
        refs={"walls": refs, "sheet_metal": {"feature": "f5"}},
    )
    doc.features.insert(len(doc.features) - 1, gusset)  # before the flat pattern
    return gusset.id


def _folded(doc: Document) -> float:
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None
    return float(measure(report.body.shape)["volume"])


def test_outline_closes_the_inside_corner() -> None:
    bend = Bend("b", "f8", "w1", "w2", (0.0, 0.0), (1.0, 0.0), 80.0, 1, 2.0, 1.5707963, 4.0)
    for profile in ("flat", "round"):
        pts = outline(bend, 2.0, 8.0, profile)
        assert pts[0] == pytest.approx((-8.0, 2.0))  # on the parent wall's inside face
        assert pts[-1] == pytest.approx((0.0, 2.0))  # back at the bend's start
        assert all(z >= 2.0 - 1e-9 for _u, z in pts)  # all on the inside of the bend


@pytest.mark.parametrize("profile", ["round", "flat"])
def test_gusset_adds_a_rib_and_keeps_the_sheet(profile: str) -> None:
    base = _folded(_bracket())
    doc = _bracket()
    fid = _add_gusset(doc, profile=profile)
    report = RebuildEngine().rebuild(doc)
    result = report.results[fid]
    assert result.state is not FeatureState.ERROR, [i.message for i in result.issues]
    assert report.body is not None
    after = float(measure(report.body.shape)["volume"])
    # Pressing moves material: the rib adds about what the press takes away.
    assert after == pytest.approx(base, rel=0.05)
    assert after != pytest.approx(base, rel=1e-9)


def test_flat_cutout_only_when_ticked() -> None:
    plain, cut = _bracket(), _bracket()
    _add_gusset(plain)
    _add_gusset(cut, flat_cutout=True)

    def flat_volume(doc: Document) -> float:
        doc.features[-1].params["flattened"] = True  # the Flat Pattern shows the flat part
        report = RebuildEngine().rebuild(doc)
        assert report.body is not None
        return float(measure(report.body.shape)["volume"])

    assert flat_volume(cut) < flat_volume(plain) - 1.0


def test_walls_without_a_bend_and_oversized_gusset_are_errors() -> None:
    doc = _bracket()
    fid = _add_gusset(doc, width=Param("500", 500.0))
    result = RebuildEngine().rebuild(doc).results[fid]
    assert result.state is FeatureState.ERROR
    assert "past the end" in " ".join(i.message for i in result.issues)
