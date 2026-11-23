"""Guards against kernel paths that are broken in the pinned kernel (spec 2 section 19)."""

from __future__ import annotations

import re
from pathlib import Path

import fdcad.core.features as features

FEATURES = Path(features.__file__).parent


def test_fillets_never_use_smooth_law_functions() -> None:
    """Item 5: a fillet radius set through a law function fails in this kernel build.
    Fillets use point tables and the two radius form; keep it that way."""
    for path in FEATURES.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\bLaw_(Function|Interpol|BSpFunc|Composite|S)\b", text), path


def test_twisted_sweeps_use_the_plane_mode() -> None:
    """Item 1 (D703): the curvilinear auxiliary spine mode distorts long sweeps."""
    text = (FEATURES / "sweep.py").read_text(encoding="utf-8")
    calls = re.findall(r"SetMode\(_twist_spine\([^)]*\),\s*(True|False)", text)
    assert calls == ["False"]
