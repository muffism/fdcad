"""Two checks of whatever a tool shows in the left panel (D2841, D2842).

``raw_labels`` finds words on show that are a field's name in the code ("keep",
"angle2") and not a label written for a person. ``blank_rows`` finds a group
with an empty line in it: a note with no words that still takes its row. The
sweep of ``test_panel_widths.py`` runs both on every panel it opens.
"""

from __future__ import annotations

import re
from itertools import pairwise

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QGroupBox,
    QLabel,
    QWidget,
)

from fdcad.ui.property_panel.groups import Group

#: A name as the code writes one: a word all in small letters, with or without
#: underscores and figures ("keep", "rotate_by", "angle2"). No label of FDCAD looks
#: like that: a label starts with a capital.
_NAME = re.compile(r"[a-z]+(_[a-z0-9]+)+|[a-z]{2,}[0-9]*")
#: Words in small letters that are right as they are: units.
PLAIN_WORDS = frozenset({"mm", "cm", "in", "ft", "deg", "rad", "px", "pt"})
#: A drop down with more entries than this lists things of the part, with names the
#: user gave them.
MOST_ENTRIES = 12
#: Empty space of this many pixels or more, past the gap between two rows, is a row
#: with nothing in it.
SLACK = 4
_TAG = re.compile(r"<[^>]+>")


def is_raw(text: str) -> bool:
    """True when ``text`` is a bare name of the code, not a label."""
    word = _TAG.sub("", text).replace("&", "").strip().rstrip(":")
    return bool(_NAME.fullmatch(word)) and word not in PLAIN_WORDS


def _words(widget: QWidget) -> list[str]:
    """What ``widget`` says in words FDCAD wrote: its text, title or entries."""
    if isinstance(widget, QComboBox):
        if widget.isEditable() or widget.count() > MOST_ENTRIES:
            return []
        return [widget.itemText(i) for i in range(widget.count())]
    if isinstance(widget, QGroupBox):
        return [widget.title()]
    if isinstance(widget, QLabel | QAbstractButton):
        return [widget.text()]
    return []


def raw_labels(root: QWidget) -> list[str]:
    """Every bare name on show under ``root``, each once, in the order found."""
    found: list[str] = []
    for widget in root.findChildren(QWidget):
        if not widget.isVisibleTo(root):
            continue
        for text in _words(widget):
            if is_raw(text) and text not in found:
                found.append(text)
    return found


def _has_content(widget: QWidget) -> bool:
    """True for a control that shows something: not a label with no words and no
    picture, and not a bare holder of other widgets."""
    if widget.width() <= 0 or widget.height() <= 0:
        return False
    if isinstance(widget, QLabel):
        return bool(widget.text().strip()) or not widget.pixmap().isNull()
    return type(widget) is not QWidget


def _bands(body: QWidget) -> list[tuple[int, int]]:
    """The stretches of ``body``, top to bottom, that a control with content covers."""
    spans: list[tuple[int, int]] = []
    for widget in body.findChildren(QWidget):
        if not widget.isVisibleTo(body) or not _has_content(widget):
            continue
        top = widget.mapTo(body, QPoint(0, 0)).y()
        spans.append((top, top + widget.height()))
    merged: list[tuple[int, int]] = []
    for top, bottom in sorted(spans):
        if merged and top <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], bottom))
        else:
            merged.append((top, bottom))
    return merged


def blank_rows(root: QWidget) -> list[str]:
    """The groups on show under ``root`` with an empty row, and where it is: at the
    start, between two rows, or at the end. A row is empty when nothing with content
    stands in it, whatever takes its place: a label with no words, or a holder whose
    widgets are all hidden."""
    found: list[str] = []
    for group in root.findChildren(Group):
        if not group.isVisibleTo(root) or not group.is_expanded():
            continue
        body = group.body
        # Rows that showed or hid a moment ago can stay laid out for their old heights
        # until the next change. Lay them out for what shows now.
        group.form.invalidate()
        group.form.activate()
        bands = _bands(body)
        if not bands:
            if body.height() > SLACK:
                found.append(f"{group.title_text}: {body.height()} px with nothing in it")
            continue
        gap = group.form.verticalSpacing()
        if bands[0][0] >= SLACK:
            found.append(f"{group.title_text}: {bands[0][0]} px empty at the start")
        for (_top, bottom), (top, _bottom) in pairwise(bands):
            if top - bottom >= gap + SLACK:
                found.append(f"{group.title_text}: {top - bottom} px empty at y {bottom}")
        if body.height() - bands[-1][1] >= SLACK:
            end = body.height() - bands[-1][1]
            found.append(f"{group.title_text}: {end} px empty at the end")
    return found
