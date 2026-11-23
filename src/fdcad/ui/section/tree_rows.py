"""The Section Planes folder of the feature tree (TR213 item 3, D2501).

While a part's section is on, the tree shows a folder with one row per section
plane. Clicking a row shows that plane's drag arrow and rotation rings; double
clicking opens the section panel; the menu edits or turns the section off.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidgetItem

from fdcad.ui.icons import icon
from fdcad.ui.tree.row_icons import row_icon

#: Item data role of the section rows: -1 for the folder, else the plane index.
SECTION_ROLE = Qt.ItemDataRole.UserRole + 61

FOLDER = "Section Planes"
FOLDER_TIP = "The planes of the section view. Click a plane to drag or turn it in the 3D view."
EDIT = "Edit Section"
TURN_OFF = "Turn Off Section"


def section_folder(names: list[str]) -> QTreeWidgetItem | None:
    """The folder row with one row per plane, or None when the section is off."""
    if not names:
        return None
    folder = QTreeWidgetItem([FOLDER])
    folder.setFlags(Qt.ItemFlag.ItemIsEnabled)
    folder.setData(0, SECTION_ROLE, -1)
    folder.setIcon(0, row_icon("tree.folder"))
    folder.setToolTip(0, FOLDER_TIP)
    for i, name in enumerate(names):
        row = QTreeWidgetItem([name])
        row.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        row.setData(0, SECTION_ROLE, i)
        row.setIcon(0, icon("view.section"))
        folder.addChild(row)
    folder.setExpanded(True)
    return folder
