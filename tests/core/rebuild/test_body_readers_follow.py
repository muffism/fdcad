"""Features that read the part follow a change to it (D1063, D1064).

Found on a gearbox (2026-11-12). Sensor, Contour and Parting Line read the whole part
but did not say so, so the rebuild kept their old result when a feature before them
changed: the sensor went on reporting the old volume.
"""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.curves import edges_in
from fdcad.core.rebuild.engine import RebuildEngine
from tests.core.features.test_features import plate


def test_sensor_contour_and_parting_line_are_made_again_when_the_part_changes() -> None:
    doc, ext = plate()  # 50 by 50 by 10

    def add(ftype: str, refs: dict | None = None, **params: object) -> str:
        fid = doc.new_feature_id()
        doc.features.append(Feature(fid, ftype, f"{ftype} 1", params=dict(params), refs=refs or {}))
        return fid

    sensor = add("sensor", source="volume")
    contour = add("contour", {"direction": {"feature": "f2"}}, spacing=Param("4", 4.0))
    parting = add("parting_line", {"direction": {"feature": "f2"}})
    engine = RebuildEngine()
    first = engine.rebuild(doc)
    assert first.results[sensor].extras["value"] == pytest.approx(25000.0)
    levels = len(edges_in(first.results[contour].extras["curve"]))
    doc.feature(ext).params["depth"] = Param("30", 30.0)
    second = engine.rebuild(doc)
    assert not {sensor, contour, parting} & set(second.reused)
    assert second.results[sensor].extras["value"] == pytest.approx(75000.0)
    assert len(edges_in(second.results[contour].extras["curve"])) > levels
