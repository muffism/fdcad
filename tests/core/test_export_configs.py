"""Export each configuration (TR196, D827)."""

from __future__ import annotations

from pathlib import Path

from fdcad.core import configurations as configs
from fdcad.core.document.model import Param
from fdcad.core.io import fdef
from fdcad.core.io.export_configs import LOG_NAME, export_configurations, file_name
from tests.core.equations.test_equations import _plate


def test_each_configuration_gets_its_own_file(tmp_path: Path) -> None:
    doc = _plate()
    ext = doc.features[-1].id
    configs.add(doc, "Long")
    configs.activate(doc, "Long")
    configs.set_scoped(doc, f"{ext}.depth", Param("30", 30.0), "this")
    configs.activate(doc, "Default")
    before = doc.feature(ext).params["depth"]
    found = export_configurations(doc, ["Default", "Long", "Gone"], tmp_path, "step", "Plate")
    assert [o.ok for o in found] == [True, True, False]
    assert doc.feature(ext).params["depth"] == before  # the open part is unchanged
    assert configs.active_name(doc) == "Default"
    log = (tmp_path / LOG_NAME).read_text(encoding="utf-8")
    assert "Gone: Failed" in log and "Long: Exported." in log
    assert found[0].path is not None and found[1].path is not None
    assert found[1].path.name == "Plate Long.step"
    assert found[1].path.stat().st_size > found[0].path.stat().st_size * 0.5
    saved = export_configurations(doc, ["Long"], tmp_path, "fdprt", "Plate")
    assert saved[0].ok and saved[0].path is not None
    assert configs.active_name(fdef.load(saved[0].path)) == "Long"
    assert file_name("A/B", "x:y", "stl") == "A_B x_y.stl"
