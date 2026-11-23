"""Out of date results are flagged (TR352, D881)."""

from __future__ import annotations

from types import SimpleNamespace

from fdcad.core.document.model import Feature, new_document
from fdcad.ui import strings
from fdcad.ui.main_window.mass_properties import stale_name


def _tab(failed: str | None) -> object:
    doc = new_document()
    doc.features.append(Feature("f9", "extrude", "Boss 3"))
    report = SimpleNamespace(failed_at=failed)
    return SimpleNamespace(session=SimpleNamespace(report=report, document=doc))


def test_stale_name_and_text() -> None:
    assert stale_name(_tab("f9")) == "Boss 3"  # type: ignore[arg-type]
    assert stale_name(_tab(None)) == ""  # type: ignore[arg-type]
    assert stale_name(_tab("f99")) == ""  # type: ignore[arg-type]
    assert "Boss 3 failed" in strings.STALE_RESULTS.format(name="Boss 3")
