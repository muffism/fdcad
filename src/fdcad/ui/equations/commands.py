"""Undoable commands for equations (CLAUDE.md rule 3).

They store copies of the variables and of the features they change, never solids.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from fdcad.core.document.model import Document, Feature, Variable
from fdcad.ui.commands.document import DocumentCommand

if TYPE_CHECKING:
    from fdcad.ui.session import DocumentSession


class SetEquations(DocumentCommand):
    """Replace the global variables and some features in one step (equations manager OK)."""

    def __init__(
        self,
        session: DocumentSession,
        variables: list[Variable],
        features: dict[str, Feature],
        text: str,
        configurations: dict[str, Any] | None = None,
        link: str | None = None,
    ) -> None:
        super().__init__(session, text)
        doc = session.document
        # The linked equations file (TR25); None leaves it as it is.
        self.link_before = doc.equations_file
        self.link_after = doc.equations_file if link is None else link
        self.vars_before = copy.deepcopy(doc.variables)
        self.vars_after = copy.deepcopy(variables)
        self.before = {fid: copy.deepcopy(doc.feature(fid)) for fid in features}
        self.after = copy.deepcopy(features)
        # Configured values of renamed or deleted variables (None: unchanged).
        self.cfg_before = copy.deepcopy(doc.configurations) if configurations is not None else None
        self.cfg_after = copy.deepcopy(configurations)

    def _put(
        self,
        variables: list[Variable],
        features: dict[str, Feature],
        configurations: dict[str, Any] | None,
        link: str,
    ) -> None:
        doc = self.session.document
        doc.variables = copy.deepcopy(variables)
        for i, f in enumerate(doc.features):
            if f.id in features:
                doc.features[i] = copy.deepcopy(features[f.id])
        if configurations is not None:
            doc.configurations = copy.deepcopy(configurations)
        doc.equations_file = link

    def apply(self) -> None:
        """Use the edited variables and features."""
        self._put(self.vars_after, self.after, self.cfg_after, self.link_after)

    def revert(self) -> None:
        """Restore the old ones."""
        self._put(self.vars_before, self.before, self.cfg_before, self.link_before)


class DocumentChange(DocumentCommand):
    """A configurations or design table change, made by a core function on a copy.

    Only what changed is kept: the configurations block, the variables when they
    changed, and copies of the changed features (never solids). Raises the core
    function's error before anything is pushed, so the caller can show it.
    """

    def __init__(
        self,
        session: DocumentSession,
        text: str,
        change: Callable[[Document], None],
    ) -> None:
        super().__init__(session, text)
        doc = session.document
        work = copy.deepcopy(doc)
        change(work)
        self.cfg_before = copy.deepcopy(doc.configurations)
        self.cfg_after = copy.deepcopy(work.configurations)
        self.vars_before = copy.deepcopy(doc.variables)
        self.vars_after = copy.deepcopy(work.variables)
        # The part colour and custom properties can vary by configuration (TR90, D2100).
        self.extra_before = (copy.deepcopy(doc.appearance), copy.deepcopy(doc.properties))
        self.extra_after = (copy.deepcopy(work.appearance), copy.deepcopy(work.properties))
        after = {f.id: f for f in work.features}
        self.before = {f.id: copy.deepcopy(f) for f in doc.features if after.get(f.id) != f}
        self.after = {fid: copy.deepcopy(after[fid]) for fid in self.before if fid in after}

    @property
    def changes_anything(self) -> bool:
        """False when the change left the part as it was."""
        return bool(
            self.before
            or self.cfg_before != self.cfg_after
            or self.vars_before != self.vars_after
            or self.extra_before != self.extra_after
        )

    def _put(
        self,
        configurations: dict[str, Any],
        variables: list[Variable],
        features: dict[str, Feature],
        extra: tuple[dict[str, Any], list[dict[str, Any]]] | None = None,
    ) -> None:
        doc = self.session.document
        if extra is not None and extra != (doc.appearance, doc.properties):
            doc.appearance = copy.deepcopy(extra[0])
            doc.properties = copy.deepcopy(extra[1])
        doc.configurations = copy.deepcopy(configurations)
        doc.variables = copy.deepcopy(variables)
        for i, f in enumerate(doc.features):
            if f.id in features:
                doc.features[i] = copy.deepcopy(features[f.id])

    def apply(self) -> None:
        """Use the changed configurations, variables and features."""
        self._put(self.cfg_after, self.vars_after, self.after, self.extra_after)

    def revert(self) -> None:
        """Restore them."""
        self._put(self.cfg_before, self.vars_before, self.before, self.extra_before)
