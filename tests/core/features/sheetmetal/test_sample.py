"""The sheet metal bracket sample and its flat pattern (PLAN Phase 5, PLAN 10 items 2 and 9)."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

from fdcad.core.features.sheetmetal.export import dxf_text, flat_drawing, svg_text
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.samples.make import SAMPLE_DIR
from fdcad.samples.sheet_metal import DEPTH, FLANGE, RADIUS, THICKNESS, WIDTH

GOLDEN = Path(__file__).resolve().parents[3] / "golden"


def _flat() -> FlatResult:
    doc = fdef.load(SAMPLE_DIR / "sheet_metal_bracket_flat.fdprt")
    report = RebuildEngine().rebuild(doc)
    result = report.results[doc.features[-1].id]
    assert isinstance(result, FlatResult)
    return result


def test_flat_length_matches_the_bend_allowance_formula() -> None:
    result = _flat()
    angle = 90.0
    allowance = math.pi * (RADIUS + 0.44 * THICKNESS) * angle / 180
    setback = RADIUS + THICKNESS  # outer virtual sharp to tangent at 90 degrees
    want = (DEPTH - setback) + allowance + (FLANGE - setback)
    assert result.size == pytest.approx((WIDTH, want), abs=1e-9)
    assert want == pytest.approx(66.523893421169, abs=1e-9)


def _rounded(text: str) -> list[str]:
    """Lines with every number rounded to 4 places, sorted, so the order of edges and the
    last digits of the kernel do not matter."""

    def fix(m: re.Match[str]) -> str:
        value = round(float(m.group(0)), 4)
        return f"{value + 0.0:.4f}"

    return sorted(re.sub(r"-?\d+\.?\d*", fix, line) for line in text.splitlines())


@pytest.mark.parametrize("fmt", ["dxf", "svg"])
def test_flat_pattern_files_match_golden(fmt: str) -> None:
    drawing = flat_drawing(_flat())
    text = dxf_text(drawing) if fmt == "dxf" else svg_text(drawing)
    golden = GOLDEN / f"sheet_metal_bracket_flat.{fmt}"
    assert _rounded(text) == _rounded(golden.read_text(encoding="utf-8"))


def test_sheet_metal_files_round_trip_byte_for_byte() -> None:
    text = (SAMPLE_DIR / "sheet_metal_bracket.fdprt").read_text(encoding="utf-8")
    doc = fdef.loads(text)
    next(f for f in doc.features if f.type == "sheet_metal").data["bend_table"] = "2,2,90,4.5\n"
    again = fdef.dumps(doc)
    assert fdef.dumps(fdef.loads(again)) == again
    assert '"bend_table": "2,2,90,4.5\\n"' in again
