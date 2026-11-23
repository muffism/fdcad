"""Open in Slicer (PLAN Phase 2, DECISIONS D352).

The part is written as 3MF to a temporary file in the background, then the
slicer of the active printer profile is started with it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fdcad.ui import strings_print as text
from fdcad.ui.preferences import print_settings
from fdcad.ui.print_tools import jobs
from fdcad.ui.themes.theme import LIGHT

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow


def open_in_slicer(window: MainWindow, launch: Any = None) -> jobs.Job | None:
    """Send the active part to the slicer. ``launch`` replaces the real start (tests)."""
    from fdcad.core.io.export import MeshSettings, export_3mf
    from fdcad.core.printing import slicer
    from fdcad.ui.appearance.tool import part_display
    from fdcad.ui.print_tools.orientation import print_transform_work, thumbnail

    tab = window.current
    report = tab.session.report if tab is not None else None
    if tab is None or report is None or report.body is None:
        window.status.setText(text.SLICER_NOTHING)
        return None
    profile = print_settings.active_profile(window.settings)
    doc = tab.session.document
    color = str(doc.appearance.get("part_color", LIGHT.face))
    title = tab.session.title.rstrip("*")
    _color, colored = part_display(tab)
    placed = print_transform_work(tab, profile)  # the orientation as the item transform (TR381)
    picture = thumbnail(tab)
    body_shape = report.body.shape
    # The export quality kept in the part (TR182), always in mm, which slicers expect.
    kept = MeshSettings.from_data((doc.print_setup or {}).get("mesh_export"))
    settings = MeshSettings(kept.deviation, kept.angle, slicer=kept.slicer)
    from fdcad.core.body_titles import report_marks
    from fdcad.core.printing.body_roles import roles_of

    roles = roles_of(doc, report.body, report_marks(report, "body_roles"))  # TR382, TR386
    from fdcad.core.properties import metadata as property_texts

    props = property_texts(doc)  # TR82
    from fdcad.core.body_titles import titles_of
    from fdcad.core.printing.body_settings import settings_of
    from fdcad.core.printing.heights import HEIGHT_CHANGES, clean

    titles = titles_of(doc, report.body, report_marks(report, "body_titles"))  # TR183
    tuned = settings_of(doc, report.body)  # TR383
    heights = clean((doc.print_setup or {}).get(HEIGHT_CHANGES))  # TR384
    from fdcad.core.printing.coating import thickness

    coat = thickness(doc.print_setup)  # TR307
    start = launch or slicer.launch

    def work() -> str:
        from fdcad.core.io.export import transform_of

        trsf, note = placed()
        path = slicer.temp_path(title)
        from fdcad.ui.print_tools.coating_tool import coated

        part, coat_faces, coat_note = coated(body_shape, coat, colored)  # TR307 (D1214)
        note = " ".join(t for t in (note, coat_note) if t)
        export_3mf(
            part,
            path,
            color=color,
            faces=coat_faces,
            name=title,
            settings=settings,
            transform=transform_of(trsf) if trsf is not None else None,
            thumbnail=picture,
            roles=roles,
            metadata=props,
            titles=titles,
            body_settings=tuned,
            heights=heights,
        )
        start(path, profile.slicer)
        name = profile.slicer or text.SLICER_DEFAULT_APP
        done = text.SLICER_STARTED.format(name=path.name, slicer=name)
        return f"{done} {note}" if note else done

    feedback = getattr(window, "feedback", None)
    if feedback is not None:
        feedback.begin("slice")  # status bar, taskbar and Dock progress (TR380, D2506)

    def finished() -> None:
        if feedback is not None:
            feedback.end("slice")

    def done(message: str) -> None:
        finished()
        window.status.setText(message)

    def failed(reason: str) -> None:
        finished()
        window.status.setText(text.SLICER_FAILED.format(reason=reason))

    return jobs.start(work, done, failed)
