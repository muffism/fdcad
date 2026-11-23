"""Configurations in the window: the tab, scoped value edits and per configuration
suppression (PHASE4_SPEC P4.10 item 2, D391)."""

from __future__ import annotations

from PySide6.QtWidgets import QMenu
from pytestqt.qtbot import QtBot

from fdcad.core import configurations as configs
from fdcad.core.document.model import Param
from fdcad.core.features.solids import volume_of
from fdcad.ui.equations.config_panel import ConfigurationsPanel
from fdcad.ui.equations.scope import set_scope
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.equations.test_equations import _plate
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def _open(qtbot: QtBot, window: MainWindow) -> DocumentTab:  # noqa: F811
    session = DocumentSession(_plate(), None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = window.add_session(session)
    return tab


def _panel(window: MainWindow) -> ConfigurationsPanel:  # noqa: F811
    panel = window.configurations  # type: ignore[attr-defined]
    assert isinstance(panel, ConfigurationsPanel)
    return panel


def _volume(tab: DocumentTab) -> float:
    report = tab.session.report
    assert report is not None and report.body is not None
    return volume_of(report.body.shape)


def test_commands_and_tab(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    for cid in ("tools.configurations", "tools.design_table"):
        assert cid in BY_ID and cid in window.commands.actions
    _open(qtbot, window)
    panel = _panel(window)
    assert window.left is not None and window.left.indexOf(panel) >= 0
    window.commands.actions["tools.configurations"].trigger()
    assert window.left.currentWidget() is panel
    assert panel.list.count() == 1 and "active" in panel.list.item(0).text()


def test_add_rename_switch_delete_with_undo(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    session = tab.session
    panel = _panel(window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        assert panel.add("Long") == "Long"
    doc = session.document
    assert configs.names(doc) == ["Default", "Long"] and configs.active_name(doc) == "Long"
    assert panel.rename("Long", "Longer")
    assert configs.names(session.document) == ["Default", "Longer"]
    assert not panel.rename("Longer", "Default")  # name in use
    assert "already exists" in panel.message.text()
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        assert panel.activate("Default")
    assert configs.active_name(session.document) == "Default"
    assert panel.delete("Longer")
    assert configs.names(session.document) == ["Default"]
    session.undo.undo()
    assert configs.names(session.document) == ["Default", "Longer"]


def test_value_field_scope_this_configuration(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    session = tab.session
    panel = _panel(window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        panel.add("Long")
    ext = session.document.features[-1].id
    props = window.panel
    assert props is not None
    props.begin(session, session.document.feature(ext), is_new=False)
    field = props.values["depth"]
    menu = field.tools.context_menu()
    assert isinstance(menu, QMenu)
    titles = [a.text() for a in menu.actions()]
    assert "Configurations" in titles
    field.edit.setText("30")
    set_scope(field, "this")
    count = session.undo.count()
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        props.accept()
    assert session.undo.count() == count + 1  # one step
    assert _volume(tab) == 60 * 40 * 30
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        panel.activate("Default")
    assert _volume(tab) == 60 * 40 * 10
    depth = session.document.feature(ext).params["depth"]
    assert depth == Param("10", 10.0)


def test_value_field_scope_all_and_single_configuration_menu(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = _open(qtbot, window)
    session = tab.session
    ext = session.document.features[-1].id
    props = window.panel
    assert props is not None
    props.begin(session, session.document.feature(ext), is_new=False)
    menu = props.values["depth"].tools.context_menu()
    assert "Configurations" not in [a.text() for a in menu.actions()]  # one configuration
    props.reject()
    panel = _panel(window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        panel.add("Long")
    configs_doc = session.document
    configs.set_scoped(configs_doc, f"{ext}.depth", Param("30", 30.0), "this")
    props.begin(session, session.document.feature(ext), is_new=False)
    field = props.values["depth"]
    field.edit.setText("15")
    set_scope(field, "all")
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        props.accept()
    assert configs.configured_paths(session.document) == []
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        panel.activate("Default")
    assert session.document.feature(ext).params["depth"] == Param("15", 15.0)


def test_suppress_in_this_configuration(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    session = tab.session
    panel = _panel(window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        panel.add("Plain")
    ext = session.document.features[-1].id
    tree = window.tree
    assert tree is not None
    item = tree.item_for(ext)
    assert item is not None
    menu = tree._context_menu(session, item)
    assert menu is not None
    action = next(a for a in menu.actions() if a.objectName() == "suppress_this_configuration")
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        action.trigger()
    assert session.document.feature(ext).suppressed
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        panel.activate("Default")
    assert not session.document.feature(ext).suppressed


def test_in_place_rename_messages_clear_when_the_name_is_put_back(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = _open(qtbot, window)
    panel = _panel(window)
    item = panel.list.item(0)
    item.setText("")
    assert "Enter a configuration name" in panel.message.text()
    panel.list.item(0).setText("Default")  # the old name again: nothing to refuse
    assert panel.message.text() == ""
    assert configs.names(tab.session.document) == ["Default"]


def test_add_linked_shows_the_link(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """TR195, D868."""
    tab = _open(qtbot, window)
    panel = _panel(window)
    name = panel.add_linked("Child")
    assert name == "Child"
    texts = [panel.list.item(i).text() for i in range(panel.list.count())]
    assert any("linked to Default" in t for t in texts)
    assert tab.session.document.configurations["items"][-1]["parent"] == "Default"


def test_preview_and_colours_by_configuration(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """TR197 (D2101): Preview builds a copy; Colours by Configuration is one undo step."""
    from fdcad.core import config_preview
    from fdcad.ui import strings_config as text

    tab = _open(qtbot, window)
    panel = _panel(window)
    panel.set_session(tab.session)
    panel.add("Second")
    panel.list.setCurrentRow(0)
    preview = panel.preview_selected()
    assert preview is not None
    qtbot.waitUntil(lambda: preview.built is not None, timeout=20000)
    assert preview.built.name == "Default"
    assert configs.active_name(tab.session.document) == "Second"
    assert preview.message.text() == text.CONFIG_PREVIEW_READY.format(name="Default")
    preview.close()
    assert panel.toggle_colours() is True
    assert config_preview.colours_vary(tab.session.document)
    tab.session.undo.undo()
    assert not config_preview.colours_vary(tab.session.document)
