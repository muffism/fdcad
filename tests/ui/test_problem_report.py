"""Problem reports ready for the user to send (D2871). FDCAD itself sends nothing."""

from __future__ import annotations

import functools
import getpass
import re
from pathlib import Path, PurePosixPath
from typing import Any

import pytest
from PySide6.QtCore import QUrl, QUrlQuery
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QMessageBox, QWidget
from pytestqt.qtbot import QtBot

from fdcad import __version__, applog
from fdcad.ui import strings_feedback as text
from fdcad.ui.errors.handler import ErrorHandler
from fdcad.ui.errors.message import ErrorMessage, details_text
from fdcad.ui.help import diagnostics, privacy, report
from fdcad.ui.help.privacy import home_spellings, scrub, user_names
from fdcad.ui.main_window import crash_guard
from fdcad.ui.main_window.crash_guard import Suspect
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_workflow import _folders, window

__all__ = ["_folders", "window"]

ROOT = Path(__file__).resolve().parents[2]
FAKE_HOME = "C:\\Users\\Jane Q Doe"
FAKE_USER = "jdoe"


def _trace() -> str:
    try:
        raise ValueError("bad thing in C:\\Users\\Jane Q Doe\\part.fdprt")
    except ValueError as exc:
        return details_text(exc, "Opening part.fdprt")


def _query(url: QUrl, key: str) -> str:
    return QUrlQuery(url).queryItemValue(key, QUrl.ComponentFormattingOption.FullyDecoded)


@pytest.fixture
def logs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A log folder of the test's own, so no report lands in the real one."""
    folder = tmp_path / "logs"
    folder.mkdir()
    monkeypatch.setattr(applog, "log_folder", lambda: folder)
    return folder


@pytest.fixture
def mails(monkeypatch: pytest.MonkeyPatch) -> list[QUrl]:
    """The mailto links that would have gone to the mail app."""
    sent: list[QUrl] = []
    monkeypatch.setattr(report, "open_mail", lambda url: sent.append(url) or True)
    return sent


# The address --------------------------------------------------------------------------


def test_the_address_is_the_one_in_the_source_offer() -> None:
    offer = (ROOT / "SOURCE_OFFER.md").read_text(encoding="utf-8")
    assert report.REPORT_ADDRESS == "FDCAD@proton.me"
    assert report.REPORT_ADDRESS in offer


# Privacy ------------------------------------------------------------------------------


def test_the_home_folder_is_replaced_in_every_spelling() -> None:
    clean = functools.partial(scrub, home=FAKE_HOME, names=[FAKE_USER])
    assert clean("Opened C:\\Users\\Jane Q Doe\\Documents\\a.fdprt") == (
        "Opened <home>\\Documents\\a.fdprt"
    )
    assert clean("file:///C:/Users/Jane Q Doe/a.step") == "file:///<home>/a.step"
    assert clean("c:\\users\\JANE Q DOE\\x") == "<home>\\x"  # any case on Windows
    assert clean("'C:\\\\Users\\\\Jane Q Doe\\\\a.fdprt'") == "'<home>\\\\a.fdprt'"  # a repr
    assert clean("C:\\Users\\Jane Q Doe") == "<home>"
    # Another folder that only starts the same is not the home folder.
    assert clean("C:\\Users\\Jane Q Doer\\x") == "C:\\Users\\Jane Q Doer\\x"


def test_the_short_name_of_the_home_folder_is_replaced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(privacy, "short_path", lambda p: "C:\\Users\\JANEQD~1" if p else "")
    assert "C:\\Users\\JANEQD~1" in home_spellings(FAKE_HOME)
    temp = "C:\\Users\\JANEQD~1\\AppData\\Local\\Temp\\x.log"
    assert scrub(temp, home=FAKE_HOME, names=[]) == "<home>\\AppData\\Local\\Temp\\x.log"
    assert "JANEQD~1" in user_names(FAKE_HOME)


def test_the_real_short_name_is_found_on_windows() -> None:
    import sys

    found = privacy.short_path(str(Path.home()))
    if sys.platform != "win32":
        assert found == ""
    else:
        assert found == "" or found.casefold().startswith(str(Path.home())[:3].casefold())


def test_the_login_name_is_replaced_as_a_whole_word() -> None:
    clean = functools.partial(scrub, home=FAKE_HOME, names=[FAKE_USER, "Jane Q Doe"])
    assert clean("Signed in as jdoe.") == "Signed in as <user>."
    assert clean("JDOE and Jane Q Doe") == "<user> and <user>"
    assert clean("jdoes and xjdoe") == "jdoes and xjdoe"
    assert clean("C:\\Users\\Jane Q Doe\\x by jdoe") == "<home>\\x by <user>"


def test_a_login_name_like_a_token_leaves_the_tokens_alone() -> None:
    assert scrub("<home>\\x <user> user", home=FAKE_HOME, names=["user", "home"]) == (
        "<home>\\x <user> <user>"
    )


def test_user_names_come_from_the_login_and_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(privacy.getpass, "getuser", lambda: FAKE_USER)
    monkeypatch.setattr(privacy, "short_path", lambda _p: "")
    monkeypatch.setenv("USERNAME", "Jane")
    monkeypatch.setenv("USER", "jdoe")
    monkeypatch.delenv("LOGNAME", raising=False)
    names = user_names(FAKE_HOME)
    assert set(names) == {FAKE_USER, "Jane", "Jane Q Doe"}
    assert names[0] == "Jane Q Doe"  # longest first, so it is replaced whole


def test_a_windows_home_is_split_on_a_mac_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """On macOS and Linux a path does not split on a backslash (D2871)."""
    monkeypatch.setattr(privacy, "PurePath", PurePosixPath, raising=False)
    monkeypatch.setattr(privacy.getpass, "getuser", lambda: FAKE_USER)
    monkeypatch.setattr(privacy, "short_path", lambda p: "C:\\Users\\JANEQD~1" if p else "")
    for key in ("USERNAME", "USER", "LOGNAME"):
        monkeypatch.delenv(key, raising=False)
    assert set(user_names(FAKE_HOME)) == {FAKE_USER, "Jane Q Doe", "JANEQD~1"}
    assert set(user_names("/Users/jane/")) == {FAKE_USER, "jane", "JANEQD~1"}
    monkeypatch.setattr(privacy, "short_path", lambda _p: "")
    assert home_spellings("C:\\") == home_spellings("/") == []


def test_last_part_splits_on_both_slashes() -> None:
    assert privacy.last_part("C:\\Users\\Jane Q Doe") == "Jane Q Doe"
    assert privacy.last_part("C:/Users/jane/") == "jane"
    assert privacy.last_part("/Users/jane") == "jane"
    assert privacy.last_part("C:\\Users\\JANEQD~1\\") == "JANEQD~1"
    assert privacy.last_part("C:\\") == privacy.last_part("/") == privacy.last_part("C:") == ""


def test_a_unix_home_and_a_root_home(monkeypatch: pytest.MonkeyPatch) -> None:
    assert scrub("/home/jane/parts/a.fdprt", home="/home/jane", names=[]) == "<home>/parts/a.fdprt"
    assert scrub("/home/janet/a", home="/home/jane", names=[]) == "/home/janet/a"
    monkeypatch.setattr(privacy, "short_path", lambda _p: "")
    assert home_spellings("/") == []
    assert home_spellings("C:\\") == []


def test_the_log_folder_line_of_system_info_has_no_user_name(qtbot: QtBot) -> None:
    folder = Path.home() / "AppData" / "Roaming" / "FDCAD" / "logs"
    info = diagnostics.system_info("light", folder)
    line = next(row for row in info.splitlines() if row.startswith("Log folder:"))
    assert "<home>" in line
    assert str(Path.home()).casefold() not in line.casefold()
    assert not re.search(rf"(?<!\w){re.escape(getpass.getuser())}(?!\w)", line, re.IGNORECASE)


# The report ---------------------------------------------------------------------------


def _crash_log(folder: Path, sessions: list[str]) -> None:
    lines = []
    for body in sessions:
        lines.append(f"\n--- FDCAD {__version__} started ---\n{body}")
    (folder / "crash.log").write_text("".join(lines), encoding="utf-8")


FAULT = (
    "Windows fatal exception: access violation\n\nCurrent thread 0x1 (most recent call first):\n"
)


def test_the_report_holds_system_info_log_crash_details_and_note(
    qtbot: QtBot, logs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        report, "scrub", functools.partial(scrub, home=FAKE_HOME, names=[FAKE_USER])
    )
    log_lines = [f"line {n:03} C:\\Users\\Jane Q Doe\\a.fdprt jdoe" for n in range(400)]
    (logs / "fdcad.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    _crash_log(logs, ["", FAULT, ""])  # the last session is the running one
    out = report.build_report(_trace(), "It closed while I saved.", theme="dark")
    order = [
        text.REPORT_TITLE,
        f"== {text.REPORT_SYSTEM} ==",
        f"== {text.REPORT_LOG.format(count=300)} ==",
        f"== {text.REPORT_CRASH} ==",
        f"== {text.REPORT_DETAILS} ==",
        f"== {text.REPORT_NOTE} ==",
    ]
    places = [out.index(heading) for heading in order]
    assert places == sorted(places)
    assert "line 099" not in out and "line 100" in out and "line 399" in out
    assert "access violation" in out
    assert "ValueError: bad thing in <home>\\part.fdprt" in out
    assert "It closed while I saved." in out and "Theme:" in out
    assert "Jane Q Doe" not in out and not re.search(r"\bjdoe\b", out)
    assert "<home>\\a.fdprt <user>" in out


def test_the_report_has_the_real_home_and_login_removed(qtbot: QtBot, tmp_path: Path) -> None:
    # tmp_path is in the user's temp folder, under the home folder (often its short name).
    folder = tmp_path / "logs"
    folder.mkdir()
    (folder / "fdcad.log").write_text(f"Opened {tmp_path / 'a.fdprt'}\n", encoding="utf-8")
    out = report.build_report(_trace(), folder=folder)
    assert str(Path.home()).casefold() not in out.casefold()
    short = privacy.short_path(str(Path.home()))
    assert not short or short.casefold() not in out.casefold()
    for name in user_names():
        assert not re.search(rf"(?<![\w<]){re.escape(name)}(?![\w>])", out, re.IGNORECASE)


def test_a_report_without_a_log_or_details(qtbot: QtBot, logs: Path) -> None:
    out = report.build_report()
    assert text.REPORT_LOG_EMPTY in out
    assert text.REPORT_CRASH not in out and text.REPORT_DETAILS not in out
    assert text.REPORT_NOTE not in out


def test_only_a_fault_of_the_last_session_is_included(tmp_path: Path) -> None:
    assert report.last_fault(tmp_path) == ""  # no crash.log
    _crash_log(tmp_path, [FAULT, "", ""])  # an old fault, then two clean sessions
    assert report.last_fault(tmp_path) == ""
    _crash_log(tmp_path, ["", FAULT, ""])
    assert "access violation" in report.last_fault(tmp_path)
    _crash_log(tmp_path, [FAULT])  # a fault in the newest session
    assert report.last_fault(tmp_path).startswith("--- FDCAD")


def test_save_report_names_the_file_by_date(tmp_path: Path) -> None:
    first = report.save_report("one", tmp_path)
    second = report.save_report("two", tmp_path)
    assert first is not None and second is not None and first != second
    assert re.fullmatch(r"FDCAD-report-\d{4}-\d{2}-\d{2}-\d{6}\.txt", first.name)
    assert first.read_text(encoding="utf-8") == "one"
    assert second.read_text(encoding="utf-8") == "two"
    blocked = tmp_path / "a file"
    blocked.write_text("x", encoding="utf-8")
    assert report.save_report("three", blocked) is None  # a file where the folder goes


def test_the_last_error_line_of_a_trace() -> None:
    assert report.last_error_line(_trace()).startswith("ValueError: bad thing")
    assert report.last_error_line("FDCAD 1.0\nWindows 11") == ""


# The mail -----------------------------------------------------------------------------


def test_the_mailto_link_is_fully_encoded(qtbot: QtBot) -> None:
    path = Path.home() / "AppData" / "Roaming" / "FDCAD" / "logs" / "FDCAD-report-x.txt"
    url = report.mailto_url(path, "KeyError: 'a+b & c=d; e#f'")
    assert url.scheme() == "mailto" and url.path() == report.REPORT_ADDRESS
    assert _query(url, "subject") == f"FDCAD {__version__} problem report"
    body = _query(url, "body")
    assert body.startswith(text.REPORT_MAIL_ASK)
    assert f"FDCAD: {__version__}" in body and "OS: " in body
    assert "Problem: KeyError: 'a+b & c=d; e#f'" in body
    shown = privacy.scrub(str(path), home_token=privacy.home_shorthand())
    assert text.REPORT_MAIL_SAVED.format(path=shown) in body
    assert str(Path.home()) not in body
    encoded = url.toString(QUrl.ComponentFormattingOption.FullyEncoded)
    assert "%20" in encoded and "+" not in encoded
    assert "%2B" in encoded and "%26" in encoded and "%3D" in encoded and "%3B" in encoded
    assert "%0D%0A" in encoded
    assert encoded.count("&") == 1  # only between subject and body
    assert len(encoded) < report.MAX_URL


def test_a_long_summary_and_path_keep_the_link_short(qtbot: QtBot) -> None:
    path = Path("D:/") / ("very long folder name " * 40) / "FDCAD-report-x.txt"
    url = report.mailto_url(path, "RuntimeError: " + "\u00fc" * 5000)
    assert report.url_length(url) < report.MAX_URL
    body = _query(url, "body")
    assert "Problem: RuntimeError:" in body and "FDCAD-report-x.txt" in body
    assert _query(url, "subject") == f"FDCAD {__version__} problem report"


def test_without_a_saved_file_the_mail_says_it_is_on_the_clipboard(qtbot: QtBot) -> None:
    body = _query(report.mailto_url(None, ""), "body")
    assert text.REPORT_MAIL_CLIPBOARD in body
    assert f"Problem: {text.REPORT_CLOSED}" in body


def test_tests_never_open_a_mail_app() -> None:
    # tests/conftest.py puts a stand in for open_mail in every test.
    assert report.open_mail.__module__ != report.__name__
    assert report.open_mail(QUrl(f"mailto:{report.REPORT_ADDRESS}")) is True


def test_send_report_saves_copies_and_opens_the_mail(
    qtbot: QtBot, logs: Path, mails: list[QUrl]
) -> None:
    details = _trace()
    assert report.send_report(None, details=details, note="note")
    files = list(logs.glob("FDCAD-report-*.txt"))
    assert len(files) == 1
    saved = files[0].read_text(encoding="utf-8")
    assert QGuiApplication.clipboard().text() == saved
    assert "ValueError: bad thing" in saved and "note" in saved
    assert len(mails) == 1
    assert "Problem: ValueError: bad thing" in _query(mails[0], "body")
    assert files[0].name in _query(mails[0], "body")


def test_without_a_mail_app_it_says_where_the_report_is(
    qtbot: QtBot, logs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(report, "open_mail", lambda _url: False)
    boxes: list[str] = []
    opened: list[Path] = []

    def fake_exec(box: QMessageBox) -> int:
        boxes.append(box.text())
        folder = next(b for b in box.buttons() if b.text() == text.REPORT_OPEN_FOLDER)
        folder.click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    monkeypatch.setattr(diagnostics, "open_folder", lambda f: opened.append(f) or True)
    assert not report.send_report(None, details=_trace())
    saved = next(logs.glob("FDCAD-report-*.txt"))
    assert boxes == [text.REPORT_NO_MAIL.format(path=saved, address=report.REPORT_ADDRESS)]
    assert opened == [logs]


def test_send_report_never_raises(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*_a: Any, **_k: Any) -> str:
        raise RuntimeError("no")

    shown: list[str] = []
    monkeypatch.setattr(report, "build_report", broken)
    monkeypatch.setattr(QMessageBox, "exec", lambda box: shown.append(box.text()) or 0)
    assert report.send_report(None) is False
    assert shown and report.REPORT_ADDRESS in shown[0]
    monkeypatch.setattr(report, "_no_mail", broken)
    assert report.send_report(None) is False


# Where the user gets it ---------------------------------------------------------------


@pytest.fixture
def reports(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Calls of send_report, without making a report."""
    calls: list[dict[str, Any]] = []

    def fake(parent: QWidget | None, **kwargs: Any) -> bool:
        calls.append({"parent": parent, **kwargs})
        return True

    monkeypatch.setattr(report, "send_report", fake)
    return calls


def test_the_error_box_has_report_problem_and_stays_open(
    qtbot: QtBot, reports: list[dict[str, Any]]
) -> None:
    details = _trace()
    box = ErrorMessage("Could not open part.fdprt: it is damaged. Open a backup.", details)
    qtbot.addWidget(box)
    box.show()
    button = box.report_button
    assert button is not None and button.text() == text.REPORT_PROBLEM
    assert button.toolTip() == text.REPORT_PROBLEM_TIP
    button.click()
    assert box.isVisible()  # like Copy Details, it does not close the box
    assert reports == [
        {"parent": box, "details": details, "summary": report.last_error_line(details)}
    ]


def test_an_error_box_without_a_trace_sums_up_with_its_message(
    qtbot: QtBot, reports: list[dict[str, Any]]
) -> None:
    box = ErrorMessage("Could not save a.fdprt. Save it somewhere else.", details_text())
    qtbot.addWidget(box)
    assert box.report_button is not None
    box.report_button.click()
    assert reports[0]["summary"] == "Could not save a.fdprt"


def test_an_error_box_without_details_has_no_report_button(qtbot: QtBot) -> None:
    box = ErrorMessage("Something failed. Try again.")
    qtbot.addWidget(box)
    assert box.report_button is None


def test_the_uncaught_error_box_offers_report_problem(qtbot: QtBot) -> None:
    parent = QWidget()
    qtbot.addWidget(parent)
    handler = ErrorHandler(lambda: parent)
    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        handler.handle(RuntimeError, exc, exc.__traceback__)
    box = handler.box
    assert box is not None and box.report_button is not None
    assert text.REPORT_PROBLEM in text.UNEXPECTED
    box.close()
    qtbot.waitUntil(lambda: handler.box is None, timeout=2000)


def test_help_report_a_problem(window: MainWindow, reports: list[dict[str, Any]]) -> None:
    help_menu = window.help
    action = help_menu.diagnostic_actions["report"]
    assert action.text() == text.REPORT_A_PROBLEM
    action.trigger()
    assert reports == [{"parent": window, "summary": text.REPORT_FROM_HELP}]
    assert window.status.text() == text.REPORT_READY


def test_a_crash_last_time_offers_report_problem_in_the_status_bar(
    window: MainWindow, reports: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(crash_guard, "leftovers", lambda: [Suspect(None, "f1", "Fillet 1")])
    crash_guard.collect(window)
    found = crash_guard.FOUND.format(name="Fillet 1")
    assert window.status.text() == found
    button = window.crash_report
    assert button is not None and button.isVisible()
    assert button.text() == text.REPORT_PROBLEM and button.parent() is window.statusBar()
    button.click()
    assert reports == [{"parent": window, "note": found, "summary": text.REPORT_CLOSED}]
    assert window.crash_report is None and not button.isVisible()


def test_no_crash_last_time_no_report_button(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(crash_guard, "leftovers", lambda: [])
    crash_guard.collect(window)
    assert window.crash_report is None
