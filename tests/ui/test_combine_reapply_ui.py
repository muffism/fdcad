"""Reapply Fillets in the Combine panel (TR259, D2302)."""

from __future__ import annotations

from fdcad.ui.body_tools.forms import FORMS


def test_combine_has_reapply_fillets_for_add_subtract_and_common() -> None:
    field = next(f for f in FORMS["combine"].fields() if f.name == "reapply_fillets")
    assert field.kind == "flag"
    assert field.when is not None
    for operation in ("add", "subtract", "common"):
        assert field.when({"operation": operation})
    for operation in ("exclusive", "fragments", "at_least"):
        assert not field.when({"operation": operation})
    assert "reapply_fillets" not in FORMS["combine"].defaults
