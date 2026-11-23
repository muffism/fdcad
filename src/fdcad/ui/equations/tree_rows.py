"""The Equations folder in the feature tree: one row per global variable (P4.10 item 1)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidgetItem

from fdcad.core.document.model import Document
from fdcad.ui import strings_config as text

#: Item data role that marks the Equations folder and its rows.
EQUATIONS_ROLE = int(Qt.ItemDataRole.UserRole) + 21
FOLDER = "equations"


def equations_row(doc: Document) -> QTreeWidgetItem | None:
    """The Equations folder, or None while the part has no global variables."""
    if not doc.variables:
        return None
    from fdcad.ui.icons import icon
    from fdcad.ui.property_panel.panel import format_value

    folder = QTreeWidgetItem([text.EQ_FOLDER])
    folder.setFlags(Qt.ItemFlag.ItemIsEnabled)
    folder.setData(0, EQUATIONS_ROLE, FOLDER)
    folder.setIcon(0, icon("tools.equations"))
    folder.setToolTip(0, text.EQ_FOLDER_TIP)
    for var in doc.variables:
        shown = format_value(var.value, var.kind, doc.units)
        child = QTreeWidgetItem([text.EQ_FOLDER_ROW.format(name=f'"{var.name}"', value=shown)])
        child.setFlags(Qt.ItemFlag.ItemIsEnabled)
        child.setData(0, EQUATIONS_ROLE, var.name)
        child.setToolTip(0, f"{var.expr}\n{var.comment}".strip())
        folder.addChild(child)
    return folder
