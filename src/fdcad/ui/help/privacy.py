"""Keep the user's name out of problem reports (D2871).

``scrub`` replaces the home folder with ``<home>`` and the login name with
``<user>``. The home folder is matched in every spelling a log or a trace can hold:
with ``\\`` or ``/``, with doubled ``\\`` (as a Python repr shows it), in any case,
and as the short 8.3 name Windows sometimes uses (``C:\\Users\\JOHNSM~1``).
"""

from __future__ import annotations

import contextlib
import getpass
import os
import re
import sys
from collections.abc import Iterable
from pathlib import Path

HOME = "<home>"
USER = "<user>"


def short_path(path: str) -> str:
    """The short 8.3 form of ``path`` on Windows, or "" when there is none."""
    if sys.platform != "win32":
        return ""
    try:
        import ctypes

        buffer = ctypes.create_unicode_buffer(1024)
        kernel32 = getattr(ctypes, "windll").kernel32  # noqa: B009  (mypy off Windows, D2704)
        size = int(kernel32.GetShortPathNameW(path, buffer, len(buffer)))
    except (OSError, AttributeError, ValueError):
        return ""
    if not size or size > len(buffer):
        return ""
    return buffer.value


def last_part(path: str) -> str:
    """The last folder or file name of ``path``, split on ``\\`` and ``/`` on every
    platform, so a Windows path seen on a Mac splits too. A root gives ""."""
    name = re.split(r"[\\/]", path.rstrip("\\/"))[-1]
    return "" if name.endswith(":") else name


def _forms(path: str) -> set[str]:
    path = path.rstrip("\\/")
    if len(path) < 4 or not last_part(path):
        return set()  # a root such as "/" or "C:\" is not a home folder
    return {
        path,
        path.replace("\\", "/"),
        path.replace("/", "\\"),
        path.replace("/", "\\").replace("\\", "\\\\"),
    }


def home_spellings(home: str | None = None) -> list[str]:
    """Every spelling of the home folder, longest first. ``home`` replaces the real one."""
    places = [home] if home is not None else [str(Path.home()), os.environ.get("HOME", "")]
    found: set[str] = set()
    for place in places:
        if not place:
            continue
        found |= _forms(place)
        short = short_path(place)
        if short:
            found |= _forms(short)
    return sorted(found, key=len, reverse=True)


def user_names(home: str | None = None) -> list[str]:
    """The login name in each form FDCAD can find, and the home folder's own name."""
    names: list[str] = []
    with contextlib.suppress(Exception):  # no login name at all: nothing to hide
        names.append(getpass.getuser())
    names += [os.environ.get(key, "") for key in ("USERNAME", "USER", "LOGNAME")]
    place = home if home is not None else str(Path.home())
    names.append(last_part(place))
    short = short_path(place)
    if short:
        names.append(last_part(short))
    out: list[str] = []
    for name in (n.strip() for n in names):
        if len(name) >= 2 and name.casefold() not in {o.casefold() for o in out}:
            out.append(name)
    return sorted(out, key=len, reverse=True)


def scrub(
    text: str,
    home: str | None = None,
    names: Iterable[str] | None = None,
    home_token: str = HOME,
) -> str:
    """``text`` with the home folder replaced by ``home_token`` and the login name, as a
    whole word, by ``<user>``. ``home`` and ``names`` replace the real ones (for tests)."""
    spellings = home_spellings(home)
    if spellings:
        pattern = "|".join(re.escape(s) for s in spellings)
        text = re.sub(f"(?:{pattern})(?!\\w)", lambda _m: home_token, text, flags=re.IGNORECASE)
    words = list(names) if names is not None else user_names(home)
    words = sorted((w for w in words if len(w) >= 2), key=len, reverse=True)
    if words:
        pattern = "|".join(re.escape(w) for w in words)
        text = re.sub(f"(?<![\\w<])(?:{pattern})(?![\\w>])", USER, text, flags=re.IGNORECASE)
    return text


def home_shorthand() -> str:
    """How the user can type their home folder: ``%USERPROFILE%`` on Windows, else ``~``."""
    return "%USERPROFILE%" if sys.platform == "win32" else "~"
