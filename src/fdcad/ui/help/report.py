"""Problem reports, ready for the user to send (D2871).

FDCAD never sends anything itself (CLAUDE.md rules 5.8 and 5.9). ``send_report``
builds a plain text report, saves it in the log folder, puts it on the clipboard and
opens the user's own mail app with a ``mailto:`` message to ``REPORT_ADDRESS``. The
user reads it and presses Send. The report has the user's name and home folder
replaced (``privacy.scrub``).
"""

from __future__ import annotations

import platform
import re
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QUrl, QUrlQuery
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QMessageBox, QWidget

from fdcad import __version__
from fdcad.ui import strings_feedback as text
from fdcad.ui.help import diagnostics
from fdcad.ui.help.privacy import home_shorthand, scrub

#: Where reports go. The same address is in SOURCE_OFFER.md (D2870).
REPORT_ADDRESS = "FDCAD@proton.me"
#: How many of the newest lines of ``fdcad.log`` a report carries.
LOG_LINES = 300
#: The most lines of one ``crash.log`` session a report carries.
CRASH_LINES = 200
#: How much of the end of ``crash.log`` is read; the file only grows.
CRASH_TAIL_BYTES = 256_000
#: Windows mail handlers cut longer ``mailto:`` links.
MAX_URL = 1800
#: The longest one line summary in the mail.
MAX_SUMMARY = 200
#: The line ``applog`` writes to ``crash.log`` when FDCAD starts.
SESSION_START = re.compile(r"^--- FDCAD .* started ---$")


def _read_tail(path: Path, limit: int | None = None) -> str:
    try:
        with open(path, "rb") as file:
            if limit is not None:
                size = file.seek(0, 2)
                file.seek(max(0, size - limit))
            return file.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def log_tail(folder: Path, count: int = LOG_LINES) -> list[str]:
    """The newest ``count`` lines of ``fdcad.log`` in ``folder``."""
    return _read_tail(folder / "fdcad.log").splitlines()[-count:]


def last_fault(folder: Path) -> str:
    """What faulthandler wrote in the newest FDCAD session of ``crash.log`` that holds
    a fault, looking at the newest two sessions only (the running one never holds one),
    or ""."""
    sessions: list[list[str]] = []
    for line in _read_tail(folder / "crash.log", CRASH_TAIL_BYTES).splitlines():
        if SESSION_START.match(line.strip()):
            sessions.append([line])
        elif sessions:
            sessions[-1].append(line)
    for session in reversed(sessions[-2:]):
        if any(line.strip() for line in session[1:]):
            return "\n".join([session[0], *session[1:][-CRASH_LINES:]]).strip()
    return ""


def _section(title: str, body: str) -> str:
    return f"== {title} ==\n{body.rstrip()}"


def build_report(
    details: str = "", note: str = "", *, theme: str = "", folder: Path | None = None
) -> str:
    """The report: system info, the end of ``fdcad.log``, the last native crash, then
    ``details`` (a traceback) and ``note``, with the user's name and home replaced."""
    from fdcad.applog import log_folder

    folder = folder or log_folder()
    made = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z").strip()
    parts = [text.REPORT_TITLE, text.REPORT_MADE.format(time=made)]
    try:
        info = diagnostics.system_info(theme, folder)
    except Exception as exc:  # a report without system info is still worth sending
        info = f"FDCAD: {__version__}\nOS: {platform.platform()}\n({type(exc).__name__})"
    parts.append(_section(text.REPORT_SYSTEM, info))
    lines = log_tail(folder)
    parts.append(
        _section(text.REPORT_LOG.format(count=len(lines)), "\n".join(lines))
        if lines
        else _section(text.REPORT_LOG.format(count=0), text.REPORT_LOG_EMPTY)
    )
    fault = last_fault(folder)
    if fault:
        parts.append(_section(text.REPORT_CRASH, fault))
    if details.strip():
        parts.append(_section(text.REPORT_DETAILS, details))
    if note.strip():
        parts.append(_section(text.REPORT_NOTE, note))
    return scrub("\n\n".join(parts) + "\n")


def save_report(report: str, folder: Path | None = None) -> Path | None:
    """Write ``FDCAD-report-YYYY-MM-DD-HHMMSS.txt`` in the log folder; None when that failed."""
    from fdcad.applog import log_folder

    folder = folder or log_folder()
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    try:
        folder.mkdir(parents=True, exist_ok=True)
        for n in range(1, 100):
            name = f"FDCAD-report-{stamp}.txt" if n == 1 else f"FDCAD-report-{stamp}-{n}.txt"
            path = folder / name
            try:
                with open(path, "x", encoding="utf-8") as file:
                    file.write(report)
            except FileExistsError:
                continue
            return path
    except OSError:
        return None
    return None


def last_error_line(details: str) -> str:
    """The last line of a traceback in ``details`` (``ValueError: bad``), or ""."""
    if "Traceback (most recent call last)" not in details:
        return ""
    lines = [line.strip() for line in details.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _encode(value: str) -> str:
    return bytes(QUrl.toPercentEncoding(value).data()).decode("ascii")


def _url(subject: str, body: list[str]) -> QUrl:
    url = QUrl(f"mailto:{REPORT_ADDRESS}")
    query = QUrlQuery()
    # Fully encoded here, so "&", "+", ";" and the rest are never read as delimiters
    # and a space is %20, not "+". Line breaks are CR LF, as RFC 6068 asks.
    query.setQueryItems([("subject", _encode(subject)), ("body", _encode("\r\n".join(body)))])
    url.setQuery(query)
    return url


def url_length(url: QUrl) -> int:
    """The length of ``url`` as the mail app gets it."""
    return len(url.toString(QUrl.ComponentFormattingOption.FullyEncoded))


def mailto_url(path: Path | None, summary: str) -> QUrl:
    """A ``mailto:`` link to ``REPORT_ADDRESS``: the subject, a question, the version,
    the OS, the one line ``summary`` and where the full report is. Shorter than
    ``MAX_URL`` when encoded; the home folder is shown as the user can type it."""
    subject = text.REPORT_SUBJECT.format(version=__version__)
    summary = " ".join(scrub(summary).split())
    if len(summary) > MAX_SUMMARY:
        summary = summary[: MAX_SUMMARY - 3].rstrip() + "..."
    where = scrub(str(path), home_token=home_shorthand()) if path is not None else ""
    while True:
        saved = text.REPORT_MAIL_SAVED.format(path=where) if where else ""
        body = [
            text.REPORT_MAIL_ASK,
            "",
            "",
            text.REPORT_MAIL_VERSION.format(version=__version__),
            text.REPORT_MAIL_OS.format(os=f"{platform.system()} {platform.release()}"),
            text.REPORT_MAIL_PROBLEM.format(summary=summary or text.REPORT_CLOSED),
            "",
            saved or text.REPORT_MAIL_CLIPBOARD,
        ]
        url = _url(subject, body)
        if url_length(url) < MAX_URL:
            return url
        if len(summary) > 20:
            summary = summary[: len(summary) // 2].rstrip() + "..."
        elif where and path is not None and where != path.name:
            where = path.name  # a very long folder: the file name is enough to find it
        elif where:
            where = ""
        else:
            return url


def open_mail(url: QUrl) -> bool:
    """Hand ``url`` to the user's mail app. Tests replace this (tests/conftest.py)."""
    return bool(QDesktopServices.openUrl(url))


def _no_mail(parent: QWidget | None, path: Path | None) -> None:
    """Say where the report is when no mail app opened, with a button to its folder."""
    box = QMessageBox(parent)
    box.setObjectName("reportNoMail")
    box.setWindowTitle(text.ERROR_TITLE)
    box.setIcon(QMessageBox.Icon.Information)
    if path is None:
        box.setText(text.REPORT_NO_MAIL_NO_FILE.format(address=REPORT_ADDRESS))
        folder = None
    else:
        box.setText(text.REPORT_NO_MAIL.format(path=path, address=REPORT_ADDRESS))
        folder = box.addButton(text.REPORT_OPEN_FOLDER, QMessageBox.ButtonRole.ActionRole)
    ok = box.addButton(QMessageBox.StandardButton.Ok)
    box.setDefaultButton(ok)
    box.exec()
    if folder is not None and path is not None and box.clickedButton() is folder:
        diagnostics.open_folder(path.parent)
    box.deleteLater()


def send_report(
    parent: QWidget | None, details: str = "", note: str = "", summary: str = ""
) -> bool:
    """Build, save and copy the report, then open the mail app with a message to
    ``REPORT_ADDRESS``. True when the mail app opened. Never raises."""
    from fdcad.applog import log

    path: Path | None = None
    try:
        try:
            from fdcad.ui.themes.theme import current

            theme = current().value
        except Exception:
            theme = ""
        report = build_report(details, note, theme=theme)
        path = save_report(report)
        QGuiApplication.clipboard().setText(report)
        log.info("Problem report saved at %s", path)
        line = summary or last_error_line(details) or text.REPORT_CLOSED
        if open_mail(mailto_url(path, line)):
            return True
        log.warning("No mail app opened for the problem report")
    except Exception:
        log.exception("Could not make the problem report")
    try:
        _no_mail(parent, path)
    except Exception:
        log.exception("Could not show where the problem report is")
    return False
