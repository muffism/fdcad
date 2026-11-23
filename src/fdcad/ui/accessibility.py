"""Screen readers and target size (TR294 items 2 and 3, DECISIONS D2017).

``describe_part`` writes a plain text summary of the part for Describe Part:
the bodies, the overall size and the features in order. ``apply_large_controls``
makes command tab buttons and tree rows half as large again for Large Controls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fdcad.ui import strings_a11y as text

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow

#: How much larger Large Controls makes targets.
LARGE = 1.5


def describe_part(document: Any, report: Any) -> str:
    """The part as sentences a screen reader can read out."""
    lines = [text.DESCRIBE_NAME.format(name=document_name(document))]
    body = getattr(report, "body", None) if report is not None else None
    if body is None:
        lines.append(text.DESCRIBE_EMPTY)
    else:
        from fdcad.core.features.solids import solids
        from fdcad.samples.make import measure

        count = len(solids(body.shape))
        box = measure(body.shape)["bbox"]
        size = [box[3] - box[0], box[4] - box[1], box[5] - box[2]]
        lines.append(text.DESCRIBE_BODIES.format(count=count))
        lines.append(
            text.DESCRIBE_SIZE.format(x=f"{size[0]:.4g}", y=f"{size[1]:.4g}", z=f"{size[2]:.4g}")
        )
    shown = [f for f in document.features if f.type not in ("origin", "plane")]
    lines.append(text.DESCRIBE_FEATURES.format(count=len(shown)))
    results = getattr(report, "results", {}) if report is not None else {}
    for k, feature in enumerate(shown, start=1):
        state = results.get(feature.id)
        flag = ""
        if feature.suppressed:
            flag = text.DESCRIBE_SUPPRESSED
        elif state is not None and state.state.value != "ok":
            flag = text.DESCRIBE_STATE.format(state=state.state.value)
        lines.append(f"{k}. {feature.name}{flag}")
    return "\n".join(lines)


def document_name(document: Any) -> str:
    """The part's name for the summary."""
    return str(getattr(document, "name", "") or text.DESCRIBE_UNNAMED)


def show_description(window: MainWindow) -> str:
    """Describe Part: show the summary in a box screen readers read."""
    from PySide6.QtWidgets import QMessageBox

    tab = window.current
    if tab is None:
        window.status.setText(text.DESCRIBE_NO_PART)
        return ""
    summary = describe_part(tab.session.document, tab.session.report)
    QMessageBox.information(window, text.DESCRIBE_TITLE, summary)
    return summary


def apply_large_controls(window: MainWindow, on: bool) -> None:
    """Command tab buttons and tree rows at Large Controls size, or back to normal."""
    from PySide6.QtCore import QSize
    from PySide6.QtWidgets import QToolButton, QTreeWidget

    from fdcad.ui.command_tabs import ribbon
    from fdcad.ui.tree.row_icons import ROW_ICON_SIZE

    ribbon.set_scale(LARGE if on else 1.0)
    for button in window.findChildren(QToolButton):
        role = getattr(button, "role", "")
        if role == "large":
            size = ribbon.large_icon_size(button)
        elif role == "compact":
            size = ribbon.small_icon_size(button)
        else:
            continue
        button.setIconSize(QSize(size, size))
    row = round(ROW_ICON_SIZE * (LARGE if on else 1.0))
    for tree in window.findChildren(QTreeWidget):
        if tree.iconSize().width() in (ROW_ICON_SIZE, round(ROW_ICON_SIZE * LARGE)):
            tree.setIconSize(QSize(row, row))
