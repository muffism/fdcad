"""Print, Suggest Orientation and Arrange on Bed (TR301, DECISIONS D1210).

Suggest Orientation ranks the part's face down directions in the background and
lists them; Apply lays the chosen face flat (Lay Face Flat, one undo step).
Arrange on Bed asks for a spacing, works out a layout of the bodies on the bed in
the background, and adds one Move and Copy Body feature per moved body, all as
one undo step.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QInputDialog,
    QLabel,
    QListWidget,
    QVBoxLayout,
    QWidget,
)

from fdcad.ui import strings_print as text
from fdcad.ui.print_tools import jobs

if TYPE_CHECKING:
    from fdcad.core.printing.arrange import Candidate
    from fdcad.ui.main_window.window import MainWindow


def _direction(down: tuple[float, float, float]) -> str:
    names = {(1, 0, 0): "+X", (-1, 0, 0): "-X", (0, 1, 0): "+Y", (0, -1, 0): "-Y"}
    names.update({(0, 0, 1): "+Z", (0, 0, -1): "-Z"})
    key = tuple(round(v) for v in down)
    if key in names and all(abs(v - round(v)) < 1e-6 for v in down):
        return names[key]
    return "({:.2f}, {:.2f}, {:.2f})".format(*down)


class OrientationDialog(QDialog):
    """The ranked orientations; ``chosen`` is the picked row after OK."""

    def __init__(self, found: list[Candidate], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("orientation_dialog")
        self.setWindowTitle(text.SUGGEST_TITLE)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(text.SUGGEST_PROMPT))
        self.list = QListWidget()
        self.list.setObjectName("orientation_list")
        for c in found:
            row = text.SUGGEST_ROW.format(
                down=_direction(c.down),
                overhang=f"{c.overhang:.0f}",
                height=f"{c.height:.1f}",
                fits=text.SUGGEST_FITS if c.fits else text.SUGGEST_TOO_BIG,
                islands=c.islands,
            )
            self.list.addItem(row)
        self.list.setCurrentRow(0)
        layout.addWidget(self.list)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel
        )
        apply = buttons.button(QDialogButtonBox.StandardButton.Apply)
        apply.clicked.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        # Once the buttons are in the window: Apply is the main button and Enter, and
        # the list has the keys. Cancel was drawn as the main button (D1034).
        cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel.setAutoDefault(False)
        apply.setDefault(True)
        self.list.setFocus()

    @property
    def chosen(self) -> int:
        """The picked row."""
        return max(self.list.currentRow(), 0)


def run(dialog: QDialog) -> bool:
    """Show a dialog and wait; True on OK (a seam for tests, which cannot click it)."""
    return bool(dialog.exec())


def suggest_orientation(window: MainWindow) -> jobs.Job | None:
    """Rank the face down directions and lay the chosen face flat."""
    from fdcad.core.printing.arrange import suggest
    from fdcad.ui.preferences.print_settings import active_profile

    tab = window.current
    report = tab.session.report if tab is not None else None
    if tab is None or report is None or report.body is None:
        window.status.setText(text.SUGGEST_NOTHING)
        return None
    shape = report.body.shape
    profile = active_profile(window.settings)

    def done(found: Any) -> None:
        if window.current is not tab:
            return
        if not found:
            window.status.setText(text.SUGGEST_NO_FLAT)
            return
        dialog = OrientationDialog(found, window)
        accepted = run(dialog)
        pick = dialog.chosen
        dialog.deleteLater()
        if accepted:
            window.print_orientation.take(tab, found[pick].face)

    return jobs.start(
        lambda: suggest(shape, profile),
        done,
        lambda reason: window.status.setText(text.SUGGEST_FAILED.format(reason=reason)),
    )


def arrange_bodies(window: MainWindow, spacing: float | None = None) -> jobs.Job | None:
    """Lay the bodies out on the bed ``spacing`` apart (asked when None)."""
    from fdcad.core.features.solids import solids
    from fdcad.core.printing import orientation
    from fdcad.core.printing.arrange import arrange
    from fdcad.ui.preferences.print_settings import active_profile

    tab = window.current
    report = tab.session.report if tab is not None else None
    if tab is None or report is None or report.body is None:
        window.status.setText(text.SUGGEST_NOTHING)
        return None
    body = report.body
    parts = solids(body.shape)
    if len(parts) < 2:
        window.status.setText(text.ARRANGE_ONE)
        return None
    if spacing is None:
        spacing, ok = QInputDialog.getDouble(
            window, text.ARRANGE_TITLE, text.ARRANGE_PROMPT, 5.0, 0.0, 100.0, 1
        )
        if not ok:
            return None
    profile = active_profile(window.settings)
    setup = dict(tab.session.document.print_setup or {})
    gap = spacing

    def work() -> Any:
        try:
            face = orientation.down_face(body, setup)
        except orientation.OrientationError:
            face = None
        return arrange(parts, orientation.lay_flat_rotation(face), profile, gap)

    def done(moves: Any) -> None:
        if window.current is not tab:
            return
        if moves is None:
            window.status.setText(text.ARRANGE_NO_FIT.format(x=profile.bed_x, y=profile.bed_y))
            return
        count = _add_moves(window, tab, moves)
        window.status.setText(text.ARRANGE_DONE.format(count=count, spacing=f"{gap:g}"))

    return jobs.start(
        work, done, lambda reason: window.status.setText(text.ARRANGE_FAILED.format(reason=reason))
    )


def _add_moves(window: MainWindow, tab: Any, moves: list[tuple[float, float, float]]) -> int:
    """One Move and Copy Body feature per moved body, as one undo step."""
    from fdcad.core.document.model import Feature, Param
    from fdcad.core.features.solids import solids
    from fdcad.core.naming.names import faces_of
    from fdcad.core.naming.select import reference_for
    from fdcad.ui.body_tools.flow import default_name
    from fdcad.ui.commands.document import AddFeature

    session = tab.session
    body = session.report.body
    parts = solids(body.shape)
    features = []
    for part, (dx, dy, dz) in zip(parts, moves, strict=False):
        if max(abs(dx), abs(dy), abs(dz)) < 1e-6:
            continue
        ref = reference_for(body, faces_of(part)[0])
        if ref is None:
            continue
        params: dict[str, Any] = {"mode": "translate", "translate_by": "delta", "copy": False}
        for key, value in (("dx", dx), ("dy", dy), ("dz", dz)):
            params[key] = Param(f"{value:.4f}mm", value)
        features.append((params, ref))
    if not features:
        return 0
    session.undo.beginMacro(text.ARRANGE_UNDO)
    try:
        for params, ref in features:
            doc = session.document
            feature = Feature(
                doc.new_feature_id(),
                "move_copy_body",
                default_name(doc, "move_copy_body"),
                params=params,
                refs={"bodies": [ref]},
            )
            session.undo.push(AddFeature(session, feature))
    finally:
        session.undo.endMacro()
    return len(features)
