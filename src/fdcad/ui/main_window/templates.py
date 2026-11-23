"""File, Save as Template and New Part from a template (TR217, D833)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QInputDialog

from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow


def folder() -> Path:
    """Where templates are kept: a folder of FDCAD's data folder."""
    from fdcad.ui.main_window.recovery import data_dir

    return data_dir() / "templates"


def templates() -> list[tuple[str, Path]]:
    """The saved templates as (name, file)."""
    from fdcad.core.templates import list_templates

    return list_templates(folder())


def save_as_template(window: MainWindow, name: str | None = None) -> Path | None:
    """Save the current part's settings as a template, asking for its name."""
    from fdcad.core.templates import clean_name, save_template
    from fdcad.ui.preferences.print_settings import active_profile

    tab = window.current
    if tab is None:
        return None
    if name is None:
        typed, ok = QInputDialog.getText(window, strings.TEMPLATE_SAVE, strings.TEMPLATE_ASK)
        if not ok:
            return None
        name = typed
    try:
        clean = clean_name(name)
        path = save_template(
            tab.session.document, folder(), clean, active_profile(window.settings).name
        )
    except (ValueError, OSError) as exc:
        window.status.setText(strings.TEMPLATE_FAILED.format(reason=strings.clause(exc)))
        return None
    window.status.setText(strings.TEMPLATE_SAVED.format(name=clean))
    return path


def new_from_template(window: MainWindow, path: Path) -> bool:
    """Open a new part from a template; its printer becomes the active one when it is
    one of the printer profiles."""
    from fdcad.core.io.migrations import FileFormatError
    from fdcad.core.templates import new_from_template as make
    from fdcad.ui.preferences import print_settings
    from fdcad.ui.session import DocumentSession

    try:
        doc, printer = make(path)
    except (FileFormatError, OSError) as exc:
        window.status.setText(strings.TEMPLATE_FAILED.format(reason=strings.clause(exc)))
        return False
    window.add_session(DocumentSession(doc, None, window))
    found = print_settings.profiles(window.settings)
    if printer and any(p.name == printer for p in found):
        print_settings.set_profiles(window.settings, found, printer)
    return True
