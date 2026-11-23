"""Configuration rules, themes and trial values (TR331, D2103)."""

import pytest

from fdcad.core import config_rules
from fdcad.core import configurations as configs
from fdcad.core import design_table as dt
from fdcad.core.document.model import Param
from fdcad.core.equations.allowed import problems
from fdcad.core.io import fdef
from tests.core.equations.test_equations import _plate


def _rule(ext: str, **extra: object) -> dict[str, object]:
    rule: dict[str, object] = {
        "if": "var.Width",
        "test": ">",
        "value": "70",
        "then": f"{ext}.depth",
        "choices": ["20", "30"],
    }
    rule.update(extra)
    return rule


def test_rules_apply_in_the_design_table_top_to_bottom() -> None:
    doc = _plate()
    ext = doc.features[-1].id
    later = {"if": f"{ext}.depth", "test": "=", "value": "20", "then": f"{ext}.suppressed",
             "choices": ["S"]}  # fmt: skip
    config_rules.set_rules(doc, [_rule(ext), later])
    table = dt.Table(["var.Width"], [("Small", ["60"]), ("Wide", ["90"])])
    dt.apply(doc, table, delete_missing=True)
    configs.activate(doc, "Wide")
    assert doc.feature(ext).params["depth"] == Param("20", 20.0)
    assert doc.feature(ext).suppressed  # the second rule saw the first one's value
    configs.activate(doc, "Small")
    assert doc.feature(ext).params["depth"].value == 10.0
    assert not doc.feature(ext).suppressed


def test_unmet_rules_warn_after_an_edit_and_off_rules_do_not() -> None:
    doc = _plate()
    ext = doc.features[-1].id
    config_rules.set_rules(doc, [_rule(ext)])
    assert problems(doc) == []
    doc.variables[0].expr, doc.variables[0].value = "80", 80.0
    assert any("Rule 1" in m for m in problems(doc))
    assert dt.run_rules(doc) == 1
    assert doc.feature(ext).params["depth"].value == 20.0
    assert problems(doc) == []
    doc.feature(ext).params["depth"] = Param("5", 5.0)
    config_rules.set_rules(doc, [_rule(ext, off=True)])
    assert problems(doc) == []
    again = fdef.loads(fdef.dumps(doc))
    assert config_rules.rules(again)[0]["off"] is True


def test_broken_rules_are_refused() -> None:
    doc = _plate()
    ext = doc.features[-1].id
    with pytest.raises(config_rules.RuleError, match="Rule 1"):
        config_rules.set_rules(doc, [_rule(ext, then="f99.depth")])
    with pytest.raises(config_rules.RuleError, match="no choices"):
        config_rules.set_rules(doc, [_rule(ext, choices=[])])
    with pytest.raises(config_rules.RuleError):
        config_rules.set_rules(doc, [_rule(ext, choices=["abc"])])


def test_a_theme_fills_several_columns() -> None:
    doc = _plate()
    ext = doc.features[-1].id
    config_rules.set_themes(doc, {"Heavy": {f"{ext}.depth": "25", configs.PART_COLOR: "#445566"}})
    table = dt.Table(
        ["var.Width", dt.THEME, f"{ext}.depth"],
        [("Plain", ["60", "", ""]), ("Thick", ["60", "heavy", ""]), ("Own", ["60", "Heavy", "7"])],
    )
    dt.apply(doc, table, delete_missing=True)
    configs.activate(doc, "Thick")
    assert doc.feature(ext).params["depth"].value == 25.0
    assert doc.appearance["part_color"] == "#445566"
    configs.activate(doc, "Own")
    assert doc.feature(ext).params["depth"].value == 7.0  # a typed cell wins
    stored = dt.stored(doc)
    assert stored is not None and configs.PART_COLOR in stored.columns
    assert dict(stored.rows)["Thick"][stored.columns.index(dt.THEME)] == "heavy"
    with pytest.raises(dt.DesignTableError, match="no theme"):
        dt.apply(doc, dt.Table([dt.THEME], [("Plain", ["Light"])]))
    with pytest.raises(config_rules.RuleError):
        config_rules.set_themes(doc, {"Bad": {"var.Nope": "1"}})


def test_trial_values_build_a_copy() -> None:
    doc = _plate()
    ext = doc.features[-1].id
    config_rules.set_rules(doc, [_rule(ext)])
    before = fdef.dumps(doc)
    work = config_rules.trial(doc, ["var.Width"], ["95"])
    assert work.variables[0].value == 95.0
    assert work.feature(ext).params["depth"].value == 20.0
    assert fdef.dumps(doc) == before
    assert configs.names(work) == configs.names(doc)
