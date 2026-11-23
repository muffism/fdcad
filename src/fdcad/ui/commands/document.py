"""Undoable commands for every document change (CLAUDE.md rule 3).

Each command stores only what it changed (feature, parameter or variable
copies), never solids (PLAN 11.4 item 2), and asks for a rebuild after redo
and undo.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from PySide6.QtGui import QUndoCommand

from fdcad.core.document.model import Document, Feature, ParamValue, Variable
from fdcad.core.units import UnitSystem

if TYPE_CHECKING:
    from fdcad.ui.session import DocumentSession


class DocumentCommand(QUndoCommand):
    """Base class: subclasses implement ``apply`` and ``revert``."""

    def __init__(self, session: DocumentSession, text: str) -> None:
        super().__init__(text)
        self.session = session

    def apply(self) -> None:
        """Make the change."""
        raise NotImplementedError

    def revert(self) -> None:
        """Undo the change."""
        raise NotImplementedError

    def redo(self) -> None:
        """Called by the undo stack, also when the command is first pushed."""
        self.apply()
        self.session.request_rebuild()

    def undo(self) -> None:
        """Called by the undo stack."""
        self.revert()
        self.session.request_rebuild()


class AddFeature(DocumentCommand):
    """Insert a new feature, at the end or before ``index``.

    While the part is rolled back, a new feature goes just above the rollback
    bar and the bar moves below it, so the new feature is built (T14.5.1).
    """

    def __init__(
        self, session: DocumentSession, feature: Feature, index: int | None = None
    ) -> None:
        from fdcad.core.document.rollback import current, insert_index

        super().__init__(session, f"Add {feature.name}")
        doc = session.document
        self.feature = copy.deepcopy(feature)
        self.index = insert_index(doc) if index is None else index
        self.rollback_before = doc.rollback
        rolled = current(doc) is not None and self.index <= len(doc.features) - 1
        self.rollback_after = feature.id if rolled else doc.rollback
        #: While a linked child configuration is active, the new feature is suppressed
        #: in the other configurations (TR195, D868).
        self.configs_before = copy.deepcopy(doc.configurations)

    def apply(self) -> None:
        """Insert the feature."""
        from fdcad.core import configurations as configs

        doc = self.session.document
        doc.features.insert(self.index, copy.deepcopy(self.feature))
        doc.rollback = self.rollback_after
        if doc.configurations:
            configs.suppress_in_others(doc, self.feature.id)

    def revert(self) -> None:
        """Remove it again."""
        del self.session.document.features[self.index]
        self.session.document.rollback = self.rollback_before
        self.session.document.configurations = copy.deepcopy(self.configs_before)


class DeleteFeature(DocumentCommand):
    """Remove a feature. Its id is never reused.

    Deleting the feature just above the rollback bar keeps the bar in place: it
    moves to the feature before, so the rolled back features stay rolled back.
    """

    def __init__(self, session: DocumentSession, fid: str) -> None:
        doc = session.document
        self.index = next(i for i, f in enumerate(doc.features) if f.id == fid)
        self.feature = copy.deepcopy(doc.features[self.index])
        self.rollback_before = doc.rollback
        self.rollback_after = doc.rollback
        if doc.rollback == fid and self.index > 0:
            self.rollback_after = doc.features[self.index - 1].id
        # A graph placed after this feature moves to the feature before it, instead of
        # silently to the end of the tree (audit D3 item 6, D735).
        before = doc.features[self.index - 1].id if self.index > 0 else None
        self.graph_moves = [
            (g.id, before) for g in doc.graphs if getattr(g, "position", None) == fid
        ]
        # The feature leaves its tree folder and its comment goes with it (D2646): a
        # folder whose features were all deleted stayed in the file, unseen, and kept
        # its name taken.
        from fdcad.core.document.tree_info import forget

        self.tree_before = copy.deepcopy(doc.tree)
        self.tree_after = forget(doc.tree, {fid})
        super().__init__(session, f"Delete {self.feature.name}")

    def _place_graphs(self, back: bool) -> None:
        for gid, before in self.graph_moves:
            for graph in self.session.document.graphs:
                if graph.id == gid:
                    graph.position = self.feature.id if back else before

    def apply(self) -> None:
        """Remove the feature."""
        del self.session.document.features[self.index]
        self.session.document.rollback = self.rollback_after
        self._place_graphs(False)
        self.session.document.tree = copy.deepcopy(self.tree_after)

    def revert(self) -> None:
        """Put it back where it was."""
        self.session.document.features.insert(self.index, copy.deepcopy(self.feature))
        self.session.document.rollback = self.rollback_before
        self._place_graphs(True)
        self.session.document.tree = copy.deepcopy(self.tree_before)


class ReplaceFeature(DocumentCommand):
    """Swap a feature for an edited copy (property panel OK, sketch edits).

    When the edit renamed one of its values (a named dimension, TR32), formulas
    elsewhere that used the old name are rewritten in the same undo step."""

    def __init__(self, session: DocumentSession, edited: Feature, text: str | None = None) -> None:
        doc = session.document
        self.index = next(i for i, f in enumerate(doc.features) if f.id == edited.id)
        self.before = copy.deepcopy(doc.features[self.index])
        self.after = copy.deepcopy(edited)
        self.others_before: dict[str, Feature] = {}
        self.others_after: dict[str, Feature] = {}
        self.vars_before: list[Variable] | None = None
        self.vars_after: list[Variable] | None = None
        self.configs_before: dict[str, Any] | None = None
        self.configs_after: dict[str, Any] | None = None
        self.graphs_before: list[Any] | None = None
        self.graphs_after: list[Any] | None = None
        self._renames(doc)
        super().__init__(session, text or f"Edit {edited.name}")

    def _renames(self, doc: Document) -> None:
        from fdcad.core.equations.rename import value_rename_rewrite
        from fdcad.core.equations.value_names import renamed_values

        work = copy.deepcopy(doc)
        changed = False
        for old, new in renamed_values(self.before, self.after):
            rewrite = value_rename_rewrite(work, self.before, old, new)
            for fid, feature in rewrite.features.items():
                if fid == self.after.id:
                    continue
                self.others_before.setdefault(fid, copy.deepcopy(doc.feature(fid)))
                work.features = [feature if f.id == fid else f for f in work.features]
                changed = True
            if rewrite.variables is not None:
                work.variables = rewrite.variables
                changed = True
            if rewrite.configurations is not None:
                work.configurations = rewrite.configurations
                changed = True
            if rewrite.graphs is not None:
                # Node editor formulas follow too (audit D3 item 5, D735).
                work.graphs = rewrite.graphs
                changed = True
        if not changed:
            return
        self.others_after = {fid: copy.deepcopy(work.feature(fid)) for fid in self.others_before}
        if work.variables != doc.variables:
            self.vars_before, self.vars_after = copy.deepcopy(doc.variables), work.variables
        if work.configurations != doc.configurations:
            self.configs_before = copy.deepcopy(doc.configurations)
            self.configs_after = work.configurations
        if work.graphs != doc.graphs:
            self.graphs_before, self.graphs_after = copy.deepcopy(doc.graphs), work.graphs

    def _put(
        self,
        main: Feature,
        others: dict[str, Feature],
        variables: list[Variable] | None,
        configurations: dict[str, Any] | None,
        graphs: list[Any] | None = None,
    ) -> None:
        doc = self.session.document
        doc.features[self.index] = copy.deepcopy(main)
        if graphs is not None:
            doc.graphs = copy.deepcopy(graphs)
        for i, f in enumerate(doc.features):
            if f.id in others:
                doc.features[i] = copy.deepcopy(others[f.id])
        if variables is not None:
            doc.variables = copy.deepcopy(variables)
        if configurations is not None:
            doc.configurations = copy.deepcopy(configurations)

    def apply(self) -> None:
        """Put the edited copy in place."""
        self._put(
            self.after, self.others_after, self.vars_after, self.configs_after, self.graphs_after
        )

    def revert(self) -> None:
        """Restore the original."""
        self._put(
            self.before,
            self.others_before,
            self.vars_before,
            self.configs_before,
            self.graphs_before,
        )


class MoveFeature(DocumentCommand):
    """Move a feature to a new position in the tree.

    The rollback bar stays where it is among the other features: moving the
    feature just above the bar leaves the bar after the feature before it, so
    no other feature is rolled back or forward by the move.
    """

    def __init__(self, session: DocumentSession, fid: str, index: int) -> None:
        doc = session.document
        self.fid = fid
        self.before = next(i for i, f in enumerate(doc.features) if f.id == fid)
        self.after = index
        self.rollback_before = doc.rollback
        self.rollback_after = doc.rollback
        if doc.rollback == fid and self.before > 0:
            self.rollback_after = doc.features[self.before - 1].id
        super().__init__(session, f"Move {doc.feature(fid).name}")

    def _move(self, to: int) -> None:
        features = self.session.document.features
        index = next(i for i, f in enumerate(features) if f.id == self.fid)
        feature = features.pop(index)
        features.insert(to, feature)

    def apply(self) -> None:
        """Move to the new position."""
        self._move(self.after)
        self.session.document.rollback = self.rollback_after

    def revert(self) -> None:
        """Move back."""
        self._move(self.before)
        self.session.document.rollback = self.rollback_before


class SetParam(DocumentCommand):
    """Change one parameter of one feature."""

    def __init__(self, session: DocumentSession, fid: str, name: str, value: ParamValue) -> None:
        feature = session.document.feature(fid)
        self.fid, self.name = fid, name
        self.had = name in feature.params
        self.before = copy.deepcopy(feature.params.get(name))
        self.after = copy.deepcopy(value)
        super().__init__(session, f"Change {name} of {feature.name}")

    def apply(self) -> None:
        """Set the new value."""
        self.session.document.feature(self.fid).params[self.name] = copy.deepcopy(self.after)

    def revert(self) -> None:
        """Restore the old value."""
        params = self.session.document.feature(self.fid).params
        if self.had:
            params[self.name] = copy.deepcopy(self.before)
        else:
            params.pop(self.name, None)


class RenameFeature(DocumentCommand):
    """Change a feature's display name, and the formulas that use it (D527).

    Formulas such as ``"depth@Extrude 1"`` follow the new name; undo puts the
    old name and every rewritten formula back. Only the changed features,
    variables, configurations and graphs are stored.
    """

    def __init__(self, session: DocumentSession, fid: str, name: str) -> None:
        from fdcad.core.equations.rename import rename_rewrite

        doc = session.document
        self.fid = fid
        self.before = doc.feature(fid).name
        self.after = name
        rewrite = rename_rewrite(doc, self.before, name)
        self.new_features = rewrite.features
        self.old_features = {k: copy.deepcopy(doc.feature(k)) for k in rewrite.features}
        self.new_variables = rewrite.variables
        self.old_variables = copy.deepcopy(doc.variables) if rewrite.variables is not None else None
        self.new_configurations = rewrite.configurations
        self.old_configurations = (
            copy.deepcopy(doc.configurations) if rewrite.configurations is not None else None
        )
        self.new_graphs = rewrite.graphs
        self.old_graphs = copy.deepcopy(doc.graphs) if rewrite.graphs is not None else None
        super().__init__(session, f"Rename {self.before}")

    def _set(
        self,
        name: str,
        features: dict[str, Feature],
        variables: list[Variable] | None,
        configurations: dict[str, object] | None,
        graphs: list[Any] | None,
    ) -> None:
        doc = self.session.document
        for i, feature in enumerate(doc.features):
            if feature.id in features:
                doc.features[i] = copy.deepcopy(features[feature.id])
        if variables is not None:
            doc.variables = copy.deepcopy(variables)
        if configurations is not None:
            doc.configurations = copy.deepcopy(configurations)
        if graphs is not None:
            doc.graphs = copy.deepcopy(graphs)
        doc.feature(self.fid).name = name

    def apply(self) -> None:
        """Set the new name and the rewritten formulas."""
        self._set(
            self.after,
            self.new_features,
            self.new_variables,
            self.new_configurations,
            self.new_graphs,
        )

    def revert(self) -> None:
        """Restore the old name and formulas."""
        self._set(
            self.before,
            self.old_features,
            self.old_variables,
            self.old_configurations,
            self.old_graphs,
        )


class SetKeepSeparateBody(DocumentCommand):
    """Keep (or stop keeping) the separate body a feature made (D527).

    Sets or clears the optional ``keep_separate_body`` key; the key is written
    only when true, so clearing it leaves the feature as it was before.
    """

    def __init__(self, session: DocumentSession, fid: str, keep: bool) -> None:
        from fdcad.core.features.base import KEEP_SEPARATE_BODY

        self.key = KEEP_SEPARATE_BODY
        self.fid = fid
        feature = session.document.feature(fid)
        self.before = feature.data.get(self.key)
        self.keep = keep
        label = "Keep Separate Body" if keep else "Warn About Separate Bodies"
        super().__init__(session, f"{label}: {feature.name}")

    def _put(self, value: object) -> None:
        data = self.session.document.feature(self.fid).data
        if value is None:
            data.pop(self.key, None)
        else:
            data[self.key] = value

    def apply(self) -> None:
        """Set the key, or remove it."""
        self._put(True if self.keep else None)

    def revert(self) -> None:
        """Restore the key as it was."""
        self._put(self.before)


class SetSuppressed(DocumentCommand):
    """Suppress or unsuppress a feature."""

    def __init__(self, session: DocumentSession, fid: str, suppressed: bool) -> None:
        self.fid = fid
        self.before = session.document.feature(fid).suppressed
        self.after = suppressed
        name = session.document.feature(fid).name
        super().__init__(session, f"{'Suppress' if suppressed else 'Unsuppress'} {name}")

    def apply(self) -> None:
        """Set the new state."""
        self.session.document.feature(self.fid).suppressed = self.after

    def revert(self) -> None:
        """Restore the old state."""
        self.session.document.feature(self.fid).suppressed = self.before


class SetRollback(DocumentCommand):
    """Move the rollback bar (``None`` means the end of the tree)."""

    def __init__(self, session: DocumentSession, fid: str | None) -> None:
        self.before = session.document.rollback
        self.after = fid
        super().__init__(session, "Move Rollback Bar")

    def apply(self) -> None:
        """Move the bar."""
        self.session.document.rollback = self.after

    def revert(self) -> None:
        """Move it back."""
        self.session.document.rollback = self.before


class SetVariables(DocumentCommand):
    """Replace the global variable list (variables tab edits)."""

    def __init__(self, session: DocumentSession, variables: list[Variable]) -> None:
        self.before = copy.deepcopy(session.document.variables)
        self.after = copy.deepcopy(variables)
        super().__init__(session, "Edit Variables")

    def apply(self) -> None:
        """Set the new list."""
        self.session.document.variables = copy.deepcopy(self.after)

    def revert(self) -> None:
        """Restore the old list."""
        self.session.document.variables = copy.deepcopy(self.before)


class SetUnits(DocumentCommand):
    """Change the part's display units. Stored values are millimetres either way.

    Lengths typed as bare numbers take the part unit, so they are rewritten with the
    old unit first ("25" becomes "25mm") and the geometry never changes (D702).
    """

    def __init__(self, session: DocumentSession, units: UnitSystem) -> None:
        from fdcad.core.equations.rename import Rewrite
        from fdcad.core.equations.unit_change import unit_change_rewrite

        doc = session.document
        self.before = doc.units
        self.after = units
        self.rewrite = unit_change_rewrite(doc, units)
        self.undo_copy = Rewrite(
            {k: copy.deepcopy(doc.feature(k)) for k in self.rewrite.features},
            copy.deepcopy(doc.variables) if self.rewrite.variables is not None else None,
            copy.deepcopy(doc.configurations) if self.rewrite.configurations is not None else None,
            copy.deepcopy(doc.graphs) if self.rewrite.graphs is not None else None,
        )
        super().__init__(session, "Change Units")

    def apply(self) -> None:
        """Use the new units, with the values that depend on the unit rewritten."""
        from fdcad.core.equations.unit_change import apply_rewrite

        apply_rewrite(self.session.document, self.rewrite)
        self.session.document.units = self.after

    def revert(self) -> None:
        """Restore the old units and texts."""
        from fdcad.core.equations.unit_change import apply_rewrite

        apply_rewrite(self.session.document, self.undo_copy)
        self.session.document.units = self.before


class SetHiddenBodies(DocumentCommand):
    """Hide or show bodies on purpose (P3.4 item 6, D410). Saved in the file; needs no
    rebuild, since hiding is display only."""

    def __init__(self, session: DocumentSession, hidden: set[str], text: str) -> None:
        from fdcad.core.body_visibility import hidden_names

        super().__init__(session, text)
        self.before = hidden_names(session.document)
        self.after = set(hidden)

    def apply(self) -> None:
        """Store the new hidden bodies."""
        from fdcad.core.body_visibility import set_hidden_names

        set_hidden_names(self.session.document, self.after)

    def revert(self) -> None:
        """Store the old hidden bodies."""
        from fdcad.core.body_visibility import set_hidden_names

        set_hidden_names(self.session.document, self.before)

    def redo(self) -> None:
        """Change what is drawn; the solid does not change."""
        self.apply()
        self.session.display_changed.emit()

    def undo(self) -> None:
        """Change what is drawn back."""
        self.revert()
        self.session.display_changed.emit()


class SetSeeThroughBodies(DocumentCommand):
    """Make bodies see through, or solid again, on their own (TR21, D753). Saved in the
    file; display only, so it needs no rebuild."""

    def __init__(self, session: DocumentSession, names: set[str], text: str) -> None:
        from fdcad.core.body_visibility import see_through_names

        super().__init__(session, text)
        self.before = see_through_names(session.document)
        self.after = set(names)

    def apply(self) -> None:
        """Store the new see through bodies."""
        from fdcad.core.body_visibility import set_see_through_names

        set_see_through_names(self.session.document, self.after)

    def revert(self) -> None:
        """Store the old ones."""
        from fdcad.core.body_visibility import set_see_through_names

        set_see_through_names(self.session.document, self.before)

    def redo(self) -> None:
        """Change what is drawn; the solid does not change."""
        self.apply()
        self.session.display_changed.emit()

    def undo(self) -> None:
        """Change what is drawn back."""
        self.revert()
        self.session.display_changed.emit()


class SetVisibility(DocumentCommand):
    """Show or hide a sketch or plane on purpose. Saved in the file; needs no rebuild."""

    def __init__(self, session: DocumentSession, fid: str, visible: bool) -> None:
        from fdcad.core.document.display import hidden_ids, shown_ids
        from fdcad.ui.main_window.visibility import toggle

        doc = session.document
        word = "Show" if visible else "Hide"
        super().__init__(session, f"{word} {doc.feature(fid).name}")
        self.before = (hidden_ids(doc), shown_ids(doc))
        hidden, shown = set(self.before[0]), set(self.before[1])
        toggle(fid, doc, hidden, shown, visible)
        self.after = (hidden, shown)

    def apply(self) -> None:
        """Store the new state."""
        from fdcad.core.document.display import set_display

        set_display(self.session.document, *self.after)

    def revert(self) -> None:
        """Store the old state."""
        from fdcad.core.document.display import set_display

        set_display(self.session.document, *self.before)

    def redo(self) -> None:
        """Change what is drawn; the solid does not change."""
        self.apply()
        self.session.display_changed.emit()

    def undo(self) -> None:
        """Change what is drawn back."""
        self.revert()
        self.session.display_changed.emit()


class SetSavedViews(DocumentCommand):
    """Save, update, rename or delete saved views (TR14.2). Saved in the file; the part
    does not change, so there is no rebuild."""

    def __init__(self, session: DocumentSession, views: list[dict[str, Any]], text: str) -> None:
        super().__init__(session, text)
        self.before = copy.deepcopy(session.document.views)
        self.after = copy.deepcopy(views)

    def apply(self) -> None:
        """Store the new list."""
        self.session.document.views = copy.deepcopy(self.after)

    def revert(self) -> None:
        """Store the old list."""
        self.session.document.views = copy.deepcopy(self.before)

    def redo(self) -> None:
        """Change the list only."""
        self.apply()

    def undo(self) -> None:
        """Change the list back."""
        self.revert()


class SetTreeInfo(DocumentCommand):
    """Change tree folders or feature comments (TR23). Saved in the file; no rebuild."""

    def __init__(self, session: DocumentSession, tree: dict[str, Any], text: str) -> None:
        super().__init__(session, text)
        self.before = copy.deepcopy(session.document.tree)
        self.after = copy.deepcopy(tree)

    def apply(self) -> None:
        """Store the new folders and comments."""
        self.session.document.tree = copy.deepcopy(self.after)

    def revert(self) -> None:
        """Store the old ones."""
        self.session.document.tree = copy.deepcopy(self.before)

    def redo(self) -> None:
        """Change the tree rows only."""
        self.apply()
        self.session.display_changed.emit()

    def undo(self) -> None:
        """Change them back."""
        self.revert()
        self.session.display_changed.emit()


class NameValue(DocumentCommand):
    """Name a sketch dimension or feature value, and rewrite the formulas that used its
    old name (TR32, D698). Raises ValueNameError for a name that cannot be used."""

    def __init__(self, session: DocumentSession, fid: str, target: str, name: str) -> None:
        from fdcad.core.equations.value_names import name_value

        doc = session.document
        rewrite = name_value(doc, fid, target, name)
        self.new_features = rewrite.features
        self.old_features = {k: copy.deepcopy(doc.feature(k)) for k in rewrite.features}
        self.new_variables = rewrite.variables
        self.old_variables = copy.deepcopy(doc.variables) if rewrite.variables is not None else None
        self.new_configurations = rewrite.configurations
        self.old_configurations = (
            copy.deepcopy(doc.configurations) if rewrite.configurations is not None else None
        )
        self.new_graphs = rewrite.graphs
        self.old_graphs = copy.deepcopy(doc.graphs) if rewrite.graphs is not None else None
        super().__init__(session, f"Name {name.strip() or target}")

    def _set(
        self,
        features: dict[str, Feature],
        variables: list[Variable] | None,
        configurations: dict[str, object] | None,
        graphs: list[Any] | None,
    ) -> None:
        doc = self.session.document
        for i, feature in enumerate(doc.features):
            if feature.id in features:
                doc.features[i] = copy.deepcopy(features[feature.id])
        if variables is not None:
            doc.variables = copy.deepcopy(variables)
        if configurations is not None:
            doc.configurations = copy.deepcopy(configurations)
        if graphs is not None:
            doc.graphs = copy.deepcopy(graphs)

    def apply(self) -> None:
        """Store the name and the rewritten formulas."""
        self._set(self.new_features, self.new_variables, self.new_configurations, self.new_graphs)

    def revert(self) -> None:
        """Put the old name and formulas back."""
        self._set(self.old_features, self.old_variables, self.old_configurations, self.old_graphs)


class TieValues(DocumentCommand):
    """Replace some features and the variable list in one step: the ``tie_values`` fix,
    which ties two values to a new variable (D2628)."""

    def __init__(
        self,
        session: DocumentSession,
        features: dict[str, Feature],
        variables: list[Variable],
        label: str,
    ) -> None:
        doc = session.document
        self.new_features = copy.deepcopy(features)
        self.old_features = {k: copy.deepcopy(doc.feature(k)) for k in features}
        self.new_variables = copy.deepcopy(variables)
        self.old_variables = copy.deepcopy(doc.variables)
        super().__init__(session, label)

    def _set(self, features: dict[str, Feature], variables: list[Variable]) -> None:
        doc = self.session.document
        for i, feature in enumerate(doc.features):
            if feature.id in features:
                doc.features[i] = copy.deepcopy(features[feature.id])
        doc.variables = copy.deepcopy(variables)

    def apply(self) -> None:
        """Store the tied values and the new variable."""
        self._set(self.new_features, self.new_variables)

    def revert(self) -> None:
        """Put the old values and variables back."""
        self._set(self.old_features, self.old_variables)


class SetLockedBodies(DocumentCommand):
    """Lock or unlock bodies (TR269, D836): the face names that mark them."""

    def __init__(self, session: DocumentSession, after: set[str], text: str) -> None:
        from fdcad.core.body_visibility import locked_names

        super().__init__(session, text)
        self.before = locked_names(session.document)
        self.after = set(after)

    def redo(self) -> None:
        """Store the new marks and redraw."""
        from fdcad.core.body_visibility import set_locked_names

        set_locked_names(self.session.document, self.after)
        self.session.display_changed.emit()

    def undo(self) -> None:
        """Put the old marks back."""
        from fdcad.core.body_visibility import set_locked_names

        set_locked_names(self.session.document, self.before)
        self.session.display_changed.emit()


class SetSketchGrid(DocumentCommand):
    """The part's sketch grid spacing (TR102, D860): major spacing in mm (0 for automatic)
    and minor lines per major line, kept in ``extra.sketch_grid``."""

    def __init__(self, session: DocumentSession, major: float, minor: int, text: str) -> None:
        super().__init__(session, text)
        self.before = session.document.extra.get("sketch_grid")
        self.after = {"major": major, "minor": minor} if major > 0 else None

    def _put(self, value: object) -> None:
        if value is None:
            self.session.document.extra.pop("sketch_grid", None)
        else:
            self.session.document.extra["sketch_grid"] = dict(value)  # type: ignore[call-overload]
        self.session.display_changed.emit()

    def redo(self) -> None:
        """Store the new spacing."""
        self._put(self.after)

    def undo(self) -> None:
        """Put the old spacing back."""
        self._put(self.before)
