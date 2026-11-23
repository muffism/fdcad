"""Scale to Fit Printer (TR185, D828).

Finds the turn about the build direction, and the scale, that fit the part in
the active printer's build volume. They are kept on the open part's tab only
(not saved): print exports and the build volume use them. Save Print Scale as
Feature adds a Scale feature with the factor, so the part itself changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fdcad.ui import strings_print as text

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab, MainWindow


def tab_fit(tab: Any) -> tuple[float, float] | None:
    """The print scale and turn of ``tab``, or None."""
    fit = getattr(tab, "print_fit", None)
    return fit if isinstance(fit, tuple) else None


class FitTool:
    """Scale to Fit Printer, Clear Print Scale, Save Print Scale as Feature."""

    def __init__(self, window: MainWindow) -> None:
        self.window = window
        self.job: Any = None

    def scale_to_fit(self) -> Any:
        """Work out the fit in the background, then keep it on the tab."""
        from fdcad.core.printing import orientation
        from fdcad.ui.preferences import print_settings
        from fdcad.ui.print_tools.jobs import start

        tab = self.window.current
        report = tab.session.report if tab is not None else None
        if tab is None or report is None or report.body is None:
            self.window.status.setText(text.VOLUME_NOTHING)
            return None
        body = report.body
        setup = dict(tab.session.document.print_setup or {})
        profile = print_settings.active_profile(self.window.settings)

        def work() -> tuple[float, float]:
            face = orientation.down_face(body, setup)
            return orientation.fit_to_volume(body.shape, face, profile)

        def done(fit: tuple[float, float]) -> None:
            self.job = None
            self.set_fit(tab, fit)

        def failed(message: str) -> None:
            self.job = None
            self.window.status.setText(text.FIT_FAILED.format(reason=message))

        self.job = start(work, done, failed)
        return self.job

    def set_fit(self, tab: DocumentTab, fit: tuple[float, float] | None) -> None:
        """Keep ``fit`` on the tab and say what it does."""
        if fit is not None and fit[0] >= 1.0 and abs(fit[1]) < 1e-9:
            tab.print_fit = None  # type: ignore[attr-defined]
            self.window.status.setText(text.FIT_ALREADY)
        else:
            tab.print_fit = fit  # type: ignore[attr-defined]
            if fit is None:
                self.window.status.setText(text.FIT_CLEARED)
            else:
                self.window.status.setText(
                    text.FIT_SET.format(percent=f"{fit[0] * 100:.1f}", angle=f"{fit[1]:g}")
                )
        volume = getattr(self.window, "build_volume", None)
        if volume is not None and getattr(volume, "on", False):
            volume.refresh()

    def clear(self) -> None:
        """Print at full size again, turned as modelled."""
        tab = self.window.current
        if tab is not None:
            self.set_fit(tab, None)

    def save_as_feature(self) -> bool:
        """Add a Scale feature with the print scale (one undo step); the turn stays a print
        setting. False when there is no scale to save."""
        from fdcad.core.document.model import Feature, Param
        from fdcad.ui.body_tools.flow import default_name
        from fdcad.ui.commands.document import AddFeature

        tab = self.window.current
        fit = tab_fit(tab)
        if tab is None or fit is None or fit[0] >= 1.0:
            self.window.status.setText(text.FIT_NOTHING_TO_SAVE)
            return False
        doc = tab.session.document
        factor = round(fit[0], 6)
        feature = Feature(
            doc.new_feature_id(),
            "scale",
            default_name(doc, "scale"),
            params={"uniform": True, "factor": Param(f"{factor:g}", factor), "about": "origin"},
        )
        tab.session.undo.push(AddFeature(tab.session, feature))
        tab.print_fit = (1.0, fit[1]) if abs(fit[1]) > 1e-9 else None  # type: ignore[attr-defined]
        self.window.status.setText(text.FIT_SAVED.format(name=feature.name))
        return True
