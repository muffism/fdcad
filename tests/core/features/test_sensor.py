"""Sensor (TR86, D1022)."""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param, Variable
from fdcad.core.equations.engine import measured_names
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.units.expressions import Kind
from tests.core.features.test_multibody import BLOCK, two_blocks


def _sensor(doc: Document, **params: Any) -> str:
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, "sensor", "Sensor 1", params=params))
    return fid


def test_volume_inside_and_outside_the_limits() -> None:
    doc, *_ = two_blocks(gap=10.0)  # two separate 20 x 20 x 10 blocks
    fid = _sensor(doc, source="volume", high=Param("9000", 9000.0))
    result = rebuild(doc)[fid]
    assert result.state is FeatureState.OK
    assert result.extras["value"] == pytest.approx(2 * BLOCK)
    doc.feature(fid).params["high"] = Param("7000", 7000.0)
    result = rebuild(doc)[fid]
    assert result.state is FeatureState.WARNING
    message = result.issues[0].message
    assert "volume 8000 mm^3 is above the high limit 7000" in message
    assert "change the limit" in message
    doc.feature(fid).params.update(low=Param("8500", 8500.0), high=Param("9000", 9000.0))
    assert "below the low limit 8500" in rebuild(doc)[fid].issues[0].message


def test_formula_source_and_reading_the_value() -> None:
    doc, *_ = two_blocks(gap=10.0)
    doc.variables.append(Variable("w", Kind.NUMBER, "12", 12.0))
    fid = _sensor(doc, source="formula", value=Param("=w * 2", 24.0), low=Param("30", 30.0))
    result = rebuild(doc)[fid]
    assert result.extras["value"] == pytest.approx(24)
    assert "value 24 is below the low limit 30" in result.issues[0].message
    assert measured_names(doc)["value@Sensor 1"][1] == pytest.approx(24)


def test_needs_a_limit_and_a_material_for_mass() -> None:
    doc, *_ = two_blocks(gap=10.0)
    fid = _sensor(doc, source="volume")
    assert "Enter a low or a high limit" in rebuild(doc)[fid].issues[0].message
    doc.feature(fid).params.update(source="mass", high=Param("1", 1.0))
    result = rebuild(doc)[fid]
    assert result.state is FeatureState.ERROR
    assert "Use Material on the Tools menu" in result.issues[0].message
    doc.feature(fid).params.update(low=Param("5", 5.0), high=Param("1", 1.0), source="area")
    assert "Enter limits in order" in rebuild(doc)[fid].issues[0].message
