"""Undoable change of the print orientation (CLAUDE.md rule 3, DECISIONS D353).

The orientation is saved in the file (``print_setup``) but never changes the
solid, so redo and undo only ask the 3D view to draw again.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from fdcad.ui.commands.document import DocumentCommand

if TYPE_CHECKING:
    from fdcad.ui.session import DocumentSession


class SetPrintSetup(DocumentCommand):
    """Set or clear the face laid flat on the printer bed."""

    def __init__(
        self, session: DocumentSession, down_face: dict[str, Any] | None, text: str
    ) -> None:
        super().__init__(session, text)
        self.before = copy.deepcopy(session.document.print_setup)
        self.after = copy.deepcopy(self.before) if isinstance(self.before, dict) else {}
        self.after["down_face"] = copy.deepcopy(down_face)

    def apply(self) -> None:
        """Store the new orientation."""
        self.session.document.print_setup = copy.deepcopy(self.after)

    def revert(self) -> None:
        """Store the old orientation."""
        self.session.document.print_setup = copy.deepcopy(self.before)

    def redo(self) -> None:
        """Change the orientation; the solid does not change, so no rebuild."""
        self.apply()
        self.session.display_changed.emit()

    def undo(self) -> None:
        """Put the old orientation back."""
        self.revert()
        self.session.display_changed.emit()


class SetMeshExport(DocumentCommand):
    """Keep the STL and 3MF export options in the part (TR182, D776). Saved in the file;
    it changes nothing that is drawn or built."""

    def __init__(self, session: DocumentSession, settings: dict[str, Any], text: str) -> None:
        super().__init__(session, text)
        self.before = copy.deepcopy(session.document.print_setup)
        self.after = copy.deepcopy(self.before) if isinstance(self.before, dict) else {}
        self.after["mesh_export"] = copy.deepcopy(settings)

    def apply(self) -> None:
        """Store the new options."""
        self.session.document.print_setup = copy.deepcopy(self.after)

    def revert(self) -> None:
        """Store the old options."""
        self.session.document.print_setup = copy.deepcopy(self.before)

    def redo(self) -> None:
        """No rebuild and nothing to draw again."""
        self.apply()

    def undo(self) -> None:
        """No rebuild and nothing to draw again."""
        self.revert()


class SetBodyRoles(DocumentCommand):
    """Set the print roles of bodies (TR382, D796). Saved in the file; it changes only
    the export and the tree labels, so no rebuild."""

    def __init__(self, session: DocumentSession, roles: dict[str, str], text: str) -> None:
        from fdcad.core.printing.body_roles import BODY_ROLES

        super().__init__(session, text)
        self.before = copy.deepcopy(session.document.print_setup)
        self.after = copy.deepcopy(self.before) if isinstance(self.before, dict) else {}
        if roles:
            self.after[BODY_ROLES] = copy.deepcopy(roles)
        else:
            self.after.pop(BODY_ROLES, None)

    def apply(self) -> None:
        """Store the new roles."""
        self.session.document.print_setup = copy.deepcopy(self.after)

    def revert(self) -> None:
        """Store the old roles."""
        self.session.document.print_setup = copy.deepcopy(self.before)

    def redo(self) -> None:
        """Store the roles; the tree shows them."""
        self.apply()
        self.session.display_changed.emit()

    def undo(self) -> None:
        """Put the old roles back."""
        self.revert()
        self.session.display_changed.emit()


class SetMaterial(DocumentCommand):
    """Set or take off the part's material (TR78, D803), and with it the part colour
    when asked. Saved in the file; no rebuild: only the tree and colours change."""

    def __init__(
        self, session: DocumentSession, material: dict[str, Any], colour: str | None, text: str
    ) -> None:
        super().__init__(session, text)
        doc = session.document
        self.before = copy.deepcopy(doc.material)
        self.after = copy.deepcopy(material)
        self.colour_before = doc.appearance.get("part_color")
        self.colour_after = colour if colour is not None else self.colour_before

    def apply(self) -> None:
        """Store the new material."""
        doc = self.session.document
        doc.material = copy.deepcopy(self.after)
        if self.colour_after is not None:
            doc.appearance["part_color"] = self.colour_after

    def revert(self) -> None:
        """Store the old material."""
        doc = self.session.document
        doc.material = copy.deepcopy(self.before)
        if self.colour_before is not None:
            doc.appearance["part_color"] = self.colour_before

    def redo(self) -> None:
        """Change the material; the tree and the colour follow."""
        self.apply()
        self.session.display_changed.emit()

    def undo(self) -> None:
        """Put the old material back."""
        self.revert()
        self.session.display_changed.emit()


class SetProperties(DocumentCommand):
    """Set the part's custom properties (TR82, D810). Saved in the file; no rebuild."""

    def __init__(self, session: DocumentSession, rows: list[dict[str, Any]], text: str) -> None:
        super().__init__(session, text)
        self.before = copy.deepcopy(session.document.properties)
        self.after = copy.deepcopy(rows)

    def apply(self) -> None:
        """Store the new rows."""
        self.session.document.properties = copy.deepcopy(self.after)

    def revert(self) -> None:
        """Store the old rows."""
        self.session.document.properties = copy.deepcopy(self.before)

    def redo(self) -> None:
        """Store the rows; nothing is drawn differently."""
        self.apply()
        self.session.display_changed.emit()

    def undo(self) -> None:
        """Put the old rows back."""
        self.revert()
        self.session.display_changed.emit()


class SetMassOverride(DocumentCommand):
    """Set or clear the part's typed mass properties (TR80, D1021). Saved in the file; the
    part rebuilds, since centre of mass points use the typed centre."""

    def __init__(self, session: DocumentSession, data: dict[str, Any], text: str) -> None:
        super().__init__(session, text)
        self.before = copy.deepcopy(session.document.mass_override)
        self.after = copy.deepcopy(data)

    def apply(self) -> None:
        """Store the new override."""
        self.session.document.mass_override = copy.deepcopy(self.after)

    def revert(self) -> None:
        """Store the old override."""
        self.session.document.mass_override = copy.deepcopy(self.before)


class SetPrintSetupKey(DocumentCommand):
    """Set or take off one key of the part's print setup, such as body names (TR183,
    D1201) or per body print settings (TR383). Saved in the file; no rebuild, but the
    tree and the view are told, since labels may change."""

    def __init__(self, session: DocumentSession, key: str, value: Any, text: str) -> None:
        super().__init__(session, text)
        self.before = copy.deepcopy(session.document.print_setup)
        self.after = copy.deepcopy(self.before) if isinstance(self.before, dict) else {}
        if value in (None, {}, []):
            self.after.pop(key, None)
        else:
            self.after[key] = copy.deepcopy(value)

    def apply(self) -> None:
        """Store the new value."""
        self.session.document.print_setup = copy.deepcopy(self.after)

    def revert(self) -> None:
        """Store the old value."""
        self.session.document.print_setup = copy.deepcopy(self.before)

    def redo(self) -> None:
        """Store the value; the tree shows it."""
        self.apply()
        self.session.display_changed.emit()

    def undo(self) -> None:
        """Put the old value back."""
        self.revert()
        self.session.display_changed.emit()
