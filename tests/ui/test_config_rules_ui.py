"""Rules and Themes, Apply Rules and Try Row in the design table (TR331, D2103)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core import config_rules
from fdcad.ui import strings_config as text
from fdcad.ui.equations.rules_dialog import CHOICES, IF, THEN, VALUE, RulesDialog
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_design_table_ui import _dialog, _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def test_rules_dialog_apply_rules_and_try_row(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = _open(qtbot, window)
    session = tab.session
    ext = session.document.features[-1].id
    table = _dialog(window)

    def fill(dialog: RulesDialog) -> bool:
        r = dialog.add_rule()
        dialog.set_rule_cell(r, IF, "var.Width")
        dialog.set_rule_cell(r, VALUE, "50")
        dialog.set_rule_cell(r, THEN, f"{ext}.depth")
        dialog.set_rule_cell(r, CHOICES, "20, 30")
        dialog.add_theme_value("Deep", f"{ext}.depth", "30")
        dialog.accept()
        return True

    table.run_dialog = fill  # type: ignore[method-assign, assignment]
    assert table.edit_rules()
    doc = session.document
    assert config_rules.rules(doc)[0]["choices"] == ["20", "30"]
    assert config_rules.themes(doc) == {"Deep": {f"{ext}.depth": "30"}}
    assert table.apply_rules() == 1  # Width is 60, over 50: depth becomes 20
    assert session.document.feature(ext).params["depth"].value == 20.0
    assert table.message.text() == text.TABLE_RULES_APPLIED.format(count=1)
    trial = table.try_row()
    assert trial is not None
    qtbot.waitUntil(lambda: trial.built is not None, timeout=20000)
    table.reject()


def test_a_broken_rule_is_refused(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    dialog = RulesDialog(tab.session, window)
    r = dialog.add_rule()
    dialog.set_rule_cell(r, CHOICES, "")
    dialog.accept()
    assert "Rule 1" in dialog.message.text()
    assert config_rules.rules(tab.session.document) == []
    dialog.reject()
