"""Print roles on body rows and in Export 3MF (TR382, D796)."""

from __future__ import annotations

import zipfile
from pathlib import Path

from pytestqt.qtbot import QtBot

from fdcad.core.printing.body_roles import roles_of
from fdcad.ui import strings_phase3 as text3
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_display import _body_row, _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def _role_actions(window: MainWindow, index: int) -> dict[str, object]:  # noqa: F811
    assert window.tree is not None
    menu = window.tree._body_menu(index)
    sub = next(a.menu() for a in menu.actions() if a.text() == text3.PRINT_ROLE)
    return {a.text(): a for a in sub.actions()}


def test_set_a_role_label_it_undo_and_export(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    tab = _open(qtbot, window)
    session = tab.session
    actions = _role_actions(window, 1)
    assert set(actions) == set(text3.PRINT_ROLES.values())
    assert actions["Part"].isChecked()  # type: ignore[attr-defined]
    actions["Negative Volume"].trigger()  # type: ignore[attr-defined]
    report = session.report
    assert report is not None
    assert roles_of(session.document, report.body)[1] == "negative"
    assert session.undo.undoText() == text3.PRINT_ROLE_UNDO
    assert _role_actions(window, 1)["Negative Volume"].isChecked()  # type: ignore[attr-defined]
    tree = window.tree
    assert tree is not None
    qtbot.waitUntil(
        lambda: _body_row(window, 1).text(0).endswith("(Negative Volume)"), timeout=10000
    )
    target = tmp_path / "roles.3mf"
    window.export("3mf", target)
    qtbot.waitUntil(lambda: target.exists(), timeout=30000)
    qtbot.waitUntil(lambda: "Bambu Studio" in window.status.text(), timeout=30000)
    with zipfile.ZipFile(target) as package:
        config = package.read("Metadata/model_settings.config").decode()
    assert 'subtype="negative_part"' in config
    session.undo.undo()
    assert roles_of(session.document, report.body)[1] == "part"
