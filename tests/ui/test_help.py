"""Help menu and first run welcome (D551 to D554)."""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, QUrl
from PySide6.QtWidgets import QDialog
from pytestqt.qtbot import QtBot

from fdcad import __version__
from fdcad.ui import strings_help as text
from fdcad.ui.help.dialogs import AboutDialog, GuideWindow, ShortcutsDialog, shortcut_rows
from fdcad.ui.help.paths import guide_dir, license_files
from fdcad.ui.help.welcome import WelcomeDialog
from fdcad.ui.input.commands import COMMANDS, ShortcutMap
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.preferences.settings import Settings

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("FDCAD_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))


@pytest.fixture
def window(qtbot: QtBot, settings: Settings) -> Iterator[MainWindow]:
    win = MainWindow(settings)
    win.show()
    win.finish_setup()
    yield win
    while win.tabs.count():
        tab = win.tabs.widget(0)
        assert isinstance(tab, DocumentTab)
        tab.session.cancel_rebuild()
        tab.session.wait()
        tab.autosaver.discard()
        win.tabs.removeTab(0)
    win.close()
    win.deleteLater()


def test_help_menu_lists_the_four_commands(window: MainWindow) -> None:
    labels = [a.text() for a in window.help.actions.values()]
    from fdcad.ui.help.lessons import MENU as LESSONS  # TR291 item 2 (D2505)

    assert labels == [
        text.WELCOME,
        LESSONS,
        text.USER_GUIDE,
        text.SHORTCUTS,
        text.WHATS_NEW,
        text.ABOUT,
    ]


def test_welcome_shows_once_and_reopens_from_help(window: MainWindow, settings: Settings) -> None:
    assert settings.welcome_seen is False
    dialog = window.help.first_run()
    assert dialog is not None and dialog.isVisible()
    assert not dialog.isModal()
    dialog.reject()  # dismiss
    assert settings.welcome_seen is True
    assert window.help.first_run() is None  # never shown again on start
    window.help.actions["welcome"].trigger()
    assert window.help.welcome is not None and window.help.welcome.isVisible()
    window.help.welcome.close()


def test_closing_the_welcome_window_also_counts(qtbot: QtBot, settings: Settings) -> None:
    dialog = WelcomeDialog(settings)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.close()
    assert settings.welcome_seen is True


def test_welcome_covers_the_five_topics(qtbot: QtBot, settings: Settings) -> None:
    dialog = WelcomeDialog(settings, open_guide=lambda: None)
    qtbot.addWidget(dialog)
    headings = [h for h, _ in text.WELCOME_SECTIONS]
    assert headings == [
        "Start a sketch",
        "The command tabs",
        "The left panel",
        "Preferences and themes",
        "The user guide",
    ]
    body = " ".join(b for _, b in text.WELCOME_SECTIONS)
    for word in ("Sketch", "Features", "Feature Tree", "Preferences", "theme", "Help"):
        assert word in body


@pytest.mark.parametrize("point_size", [9.0, 13.0, 16.0])
def test_welcome_text_is_never_cut_off(qtbot: QtBot, settings: Settings, point_size: float) -> None:
    """Bug hunt F6: at the macOS system font size (13 pt) or larger, or in a small
    window, the welcome squeezed its paragraphs and cut off their lines."""
    from PySide6.QtWidgets import QApplication, QLabel, QScrollArea

    app = QApplication.instance()
    assert isinstance(app, QApplication)
    old = app.font()
    font = app.font()
    font.setPointSizeF(point_size)
    app.setFont(font)
    try:
        dialog = WelcomeDialog(settings, open_guide=lambda: None)
        qtbot.addWidget(dialog)
        for size in (None, (420, 300)):
            if size is None:
                dialog.show()
            else:
                dialog.resize(*size)
            qtbot.wait(10)
            labels = [lab for lab in dialog.findChildren(QLabel) if lab.wordWrap()]
            assert labels
            for label in labels:
                assert label.height() >= label.heightForWidth(label.width()), label.text()
        area = dialog.findChild(QScrollArea)
        assert area is not None
        if point_size == 9.0:  # opens big enough to need no scrolling at the usual size
            fresh = WelcomeDialog(settings, open_guide=lambda: None)
            qtbot.addWidget(fresh)
            fresh.show()
            qtbot.wait(10)
            bar = fresh.findChild(QScrollArea).verticalScrollBar()
            assert not bar.isVisible()
    finally:
        app.setFont(old)


def test_welcome_guide_button_opens_the_guide(window: MainWindow) -> None:
    dialog = window.help.show_welcome()
    dialog.guide_button.click()
    assert window.help.guide is not None and window.help.guide.isVisible()
    assert window.help.welcome is not None and not window.help.welcome.isVisible()
    window.help.guide.close()


def test_about_box_has_version_license_and_notices(qtbot: QtBot) -> None:
    dialog = AboutDialog()
    qtbot.addWidget(dialog)
    shown = " ".join(label.text() for label in dialog.labels)
    assert "GPL v3" in shown
    assert text.NOT_AFFILIATED in shown
    assert __version__ in text.ABOUT_HEADING.format(version=__version__)
    for row in range(dialog.documents.count()):
        dialog.show_document(row)
        assert "not in this installation" not in dialog.viewer.toPlainText()
    dialog.show_document(1)
    assert "FDCAD THIRD PARTY NOTICES" in dialog.viewer.toPlainText()
    assert text.ABOUT_COPYRIGHT in shown
    assert text.ABOUT_COPYRIGHT == "Copyright (C) 2026 the FDCAD contributors"


def test_about_link_opens_the_notices_and_the_source_offer(qtbot: QtBot) -> None:
    """D2867: Help, About links to the notices and the source offer."""
    dialog = AboutDialog()
    qtbot.addWidget(dialog)
    assert 'href="notices"' in dialog.notices_link.text()
    dialog.notices_link.linkActivated.emit("notices")
    assert dialog.tabs.currentIndex() == 1
    assert dialog.documents.currentItem().text() == text.LICENSE_DOCS["notices"]
    assert "PART 1. REQUIRED CREDITS" in dialog.viewer.toPlainText()
    dialog.notices_link.linkActivated.emit("offer")
    assert dialog.documents.currentItem().text() == text.LICENSE_DOCS["offer"]
    assert "Written offer" in dialog.viewer.toPlainText()


def test_not_affiliated_sentence_matches_the_readme() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert text.NOT_AFFILIATED in readme


def test_about_from_the_window_uses_the_new_box(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []
    monkeypatch.setattr(QDialog, "exec", lambda self: seen.append(self.objectName()) or 0)
    window.help.actions["about"].trigger()
    window.about()
    assert seen == ["aboutDialog", "aboutDialog"]


def test_license_files_exist_in_source_and_build_layouts(tmp_path: Path) -> None:
    for path in license_files().values():
        assert path.is_file(), path
    built = license_files(tmp_path)
    assert built["lgpl3"] == tmp_path / "licenses" / "LGPL-3.0.txt"
    assert built["license"] == tmp_path / "LICENSE"
    assert built["notices"] == tmp_path / "THIRD_PARTY_NOTICES.txt"
    assert built["offer"] == tmp_path / "SOURCE_OFFER.md"


def test_guide_opens_locally_and_follows_links(qtbot: QtBot) -> None:
    guide = GuideWindow()
    qtbot.addWidget(guide)
    assert guide.page() == guide_dir() / "README.md"
    assert "FDCAD User Guide" in guide.browser.toPlainText()
    target = guide_dir() / "getting-started.md"
    guide.browser.setSource(QUrl.fromLocalFile(str(target)))
    assert guide.page() == target
    assert guide.back.isEnabled()
    guide.home()
    assert guide.page() == guide_dir() / "README.md"


@pytest.mark.parametrize(
    ("page", "link"),
    [
        ("sketching.md", "#tool-values-in-the-sketch"),
        ("typing-values.md", "sketching.md#typing-sizes-while-you-draw"),
    ],
)
def test_guide_links_to_a_heading_scroll_to_it(qtbot: QtBot, page: str, link: str) -> None:
    """Bug hunt F12: links to a heading ("page.md#heading") opened the top of the page."""
    guide = GuideWindow()
    qtbot.addWidget(guide)
    guide.resize(600, 300)
    guide.show()
    guide.browser.setSource(QUrl.fromLocalFile(str(guide_dir() / page)))
    qtbot.wait(10)
    guide.browser.setSource(guide.browser.source().resolved(QUrl(link)))
    qtbot.wait(10)
    assert guide.page() == guide_dir() / (link.split("#")[0] or page)
    assert guide.browser.verticalScrollBar().value() > 0


def test_guide_never_opens_web_pages(qtbot: QtBot) -> None:
    guide = GuideWindow()
    qtbot.addWidget(guide)
    before = guide.page()
    guide.browser.setSource(QUrl("https://example.org/page"))
    assert guide.page() == before
    assert guide.browser.blocked == "https://example.org/page"


def test_guide_says_when_it_is_missing(qtbot: QtBot, tmp_path: Path) -> None:
    guide = GuideWindow(folder=tmp_path)
    qtbot.addWidget(guide)
    assert guide.browser.toPlainText() == text.GUIDE_MISSING


def test_shortcuts_list_every_command_with_current_keys(qtbot: QtBot) -> None:
    keys = ShortcutMap({"file.new": ["Ctrl+Alt+N"]})
    rows = shortcut_rows(keys)
    assert len(rows) == len(COMMANDS)
    assert ("New Part", "File", "Ctrl+Alt+N") in rows
    dialog = ShortcutsDialog(keys)
    qtbot.addWidget(dialog)
    assert dialog.visible_rows() == len(COMMANDS)
    dialog.filter.setText("new part")
    assert dialog.visible_rows() >= 1
    dialog.filter.setText("Ctrl+Alt+N")
    assert dialog.visible_rows() == 1


def test_spec_bundles_the_user_guide_and_licenses() -> None:
    spec = (ROOT / "packaging" / "fdcad.spec").read_text(encoding="utf-8")
    assert "docs/user_guide" in spec
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.txt", "SOURCE_OFFER.md", "LGPL-2.1.txt"):
        assert name in spec


def test_help_text_has_no_dashes_or_protected_names() -> None:
    tree = ast.parse((ROOT / "src/fdcad/ui/strings_help.py").read_text(encoding="utf-8"))
    values = [
        n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]
    for value in values:
        assert chr(0x2013) not in value and chr(0x2014) not in value
        if value != text.NOT_AFFILIATED:  # the one sentence CLAUDE.md 7.5 allows
            assert re.search(r"SOLIDWORKS|Rhinoceros|Grasshopper", value) is None
