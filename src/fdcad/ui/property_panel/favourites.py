"""The Favourites box of the Phase 4 panels (PHASE4_SPEC common rules).

Saves the panel's current settings under a name, applies, updates and deletes
them, and exports or imports them as a file. Stored in the preferences per
feature type. Picks (faces, edges, sketches) are never saved, only settings.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QWidget,
)

from fdcad.ui import strings_phase4 as text
from fdcad.ui.preferences import phase4_settings as prefs

if TYPE_CHECKING:
    from fdcad.ui.property_panel.panel import PropertyPanel


#: Buttons in a row. Three were wider than the left panel's default width (D2790).
COLUMNS = 2
#: The buttons under Apply, in reading order, ``COLUMNS`` a row (D2803).
PAIRS = ("save", "update", "rename", "delete", "export", "import")


class FavouritesBox(QWidget):
    """Name list and buttons for one feature type's favourites."""

    def __init__(
        self, panel: PropertyPanel, ftype: str, report: Callable[[str], None] | None = None
    ) -> None:
        super().__init__()
        self.panel = panel
        self.ftype = ftype
        self.report = report or (lambda _m: None)
        self.names = QComboBox()
        self.names.setObjectName("favourite_names")
        self.names.setToolTip(text.FAVOURITES_TIP)
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.names, 0, 0, 1, COLUMNS)
        self.buttons: dict[str, QPushButton] = {}
        actions = (
            ("save", text.FAV_SAVE, self.ask_save),
            ("apply", text.FAV_APPLY, self.apply_current),
            ("update", text.FAV_UPDATE, self.update_current),
            ("delete", text.FAV_DELETE, self.delete_current),
            ("export", text.FAV_EXPORT, self.ask_export),
            ("import", text.FAV_IMPORT, self.ask_import),
            ("rename", text.FAV_RENAME, self.ask_rename),  # TR326 (D947)
        )
        for key, label, slot in actions:
            button = QPushButton(label)
            button.setToolTip(text.FAVOURITES_TIP)
            button.clicked.connect(slot)
            self.buttons[key] = button
        # Apply acts on the name chosen above it, so it sits under the list at the full
        # width. The other six are three pairs: keep (Save, Update), manage (Rename,
        # Delete) and files (Export, Import). Seven buttons two a row left Rename
        # alone on the last row (D2803).
        layout.addWidget(self.buttons["apply"], 1, 0, 1, COLUMNS)
        for k, key in enumerate(PAIRS):
            layout.addWidget(self.buttons[key], 2 + k // COLUMNS, k % COLUMNS)
        rows = 2 + (len(PAIRS) + COLUMNS - 1) // COLUMNS
        #: What new features of this type start with (TR326, D947).
        self.start_with = QComboBox()
        self.start_with.setObjectName("favourite_default")
        self.start_with.setToolTip(text.FAV_DEFAULT_TIP)
        self.start_with.activated.connect(self._default_chosen)
        # The words sit above their list, and both lists may be narrower than their
        # longest entry, so the box fits a panel as narrow as the tree (D2790).
        words = QLabel(text.FAV_DEFAULT)
        words.setWordWrap(True)
        layout.addWidget(words, rows, 0, 1, COLUMNS)
        layout.addWidget(self.start_with, rows + 1, 0, 1, COLUMNS)
        from fdcad.ui.property_panel.columns import NARROW_LETTERS, let_narrow

        let_narrow(self.names, NARROW_LETTERS)
        let_narrow(self.start_with, NARROW_LETTERS)
        self.refresh()

    def refresh(self, select: str | None = None) -> None:
        """Fill the name list from the preferences."""
        current = select or self.names.currentText()
        self.names.clear()
        found = sorted(prefs.favourites(self.ftype))
        self.names.addItems(found)
        if current in found:
            self.names.setCurrentText(current)
        self.names.setPlaceholderText(text.FAV_NONE)
        for key in ("apply", "update", "delete", "rename"):
            self.buttons[key].setEnabled(bool(found))
        start = getattr(self, "start_with", None)
        if start is not None:
            start.clear()
            start.addItem(text.FAV_FACTORY, prefs.FACTORY)
            start.addItem(text.FAV_LAST_USED, prefs.LAST_USED)
            for name in found:
                start.addItem(name, name)
            index = start.findData(prefs.preset_default(self.ftype))
            start.setCurrentIndex(max(index, 0))

    def _default_chosen(self, index: int) -> None:
        self.set_default(str(self.start_with.itemData(index)))

    def set_default(self, value: str) -> None:
        """Choose what new features of this type start with (TR326)."""
        prefs.set_preset_default(self.ftype, value)
        self.refresh()

    def rename(self, old: str, new: str) -> bool:
        """Rename favourite ``old``; the default follows it."""
        if not prefs.rename_favourite(self.ftype, old, new):
            self.report(text.FAV_RENAME_FAILED)
            return False
        self.refresh(new.strip())
        return True

    def ask_rename(self) -> None:
        """Ask for the new name, then rename."""
        old = self.names.currentText()
        if not old:
            return
        new, ok = QInputDialog.getText(self, text.FAV_RENAME, text.FAV_NAME_PROMPT, text=old)
        if ok:
            self.rename(old, new)

    def _current_params(self) -> dict[str, object] | None:
        settings = getattr(self.panel.form, "settings_params", None)
        if settings is not None:
            found = settings()
            return None if found is None else prefs.params_to_json(found)
        feature = self.panel.current_feature()
        if feature is None:
            return None
        return prefs.params_to_json(feature.params)

    def save(self, name: str) -> bool:
        """Save the panel's settings as ``name``. False when they are not valid yet."""
        params = self._current_params()
        name = name.strip()
        if params is None or not name:
            return False
        stored = prefs.favourites(self.ftype)
        stored[name] = params
        prefs.set_favourites(self.ftype, stored)
        self.refresh(name)
        return True

    def ask_save(self) -> None:
        """Ask for a name, then save."""
        name, ok = QInputDialog.getText(self, text.FAV_NAME_TITLE, text.FAV_NAME_PROMPT)
        if ok:
            self.save(name)

    def update_current(self) -> bool:
        """Overwrite the selected favourite with the panel's settings."""
        name = self.names.currentText()
        return bool(name) and self.save(name)

    def delete_current(self) -> None:
        """Remove the selected favourite."""
        name = self.names.currentText()
        stored = prefs.favourites(self.ftype)
        if stored.pop(name, None) is not None:
            prefs.set_favourites(self.ftype, stored)
        self.refresh()

    def apply(self, name: str) -> bool:
        """Put a favourite's settings into the panel. Picks stay as they are."""
        stored = prefs.favourites(self.ftype).get(name)
        panel = self.panel
        if stored is None or panel.session is None or panel.feature is None:
            return False
        feature = copy.deepcopy(panel.feature)
        form = panel.form
        if form is not None:
            form.apply(feature)  # keep the picks and values made so far
        feature.params.update(prefs.params_from_json(stored))
        panel.begin(panel.session, feature, panel.is_new)
        return True

    def apply_current(self) -> None:
        """Apply the selected favourite."""
        self.apply(self.names.currentText())

    def ask_export(self) -> None:
        """Ask for a file, then export."""
        path, _f = QFileDialog.getSaveFileName(self, text.FAV_EXPORT, "", text.FAV_FILE_FILTER)
        if path:
            prefs.export_favourites(self.ftype, path)

    def ask_import(self) -> None:
        """Ask for a file, then import."""
        path, _f = QFileDialog.getOpenFileName(self, text.FAV_IMPORT, "", text.FAV_FILE_FILTER)
        if path:
            self.import_file(path)

    def import_file(self, path: str) -> int:
        """Import favourites from ``path``; reports the result."""
        try:
            count = prefs.import_favourites(self.ftype, path)
        except ValueError as exc:
            self.report(text.FAV_IMPORT_FAILED.format(error=exc))
            return 0
        self.refresh()
        self.report(text.FAV_IMPORTED.format(count=count))
        return count
