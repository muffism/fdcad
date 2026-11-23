"""One label column for a whole panel (UI review item P6, D2742).

A row of a group leads with a word ("Along", "Size") or with a small icon or
button (the field icons, Reverse Direction). The word rows sat in the label
column of their own group, as wide as that group's longest word, and the icon
rows in a cell as wide as a small button, so the fields of one panel began at
two or more places. ``align`` gives every row of every group under a widget one
column: as wide as the widest lead that shows, up to ``MAX_STEPS`` spacing
steps. ``keep_aligned`` does it again whenever a row shows or hides, so the
column is never wider than the rows on screen need.

A row that leads with a word shows no field icon as well: the word says what
the icon says, and the icon would push that one field out of line.
"""

from __future__ import annotations

import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QObject, QSize, QTimer
from PySide6.QtWidgets import (
    QBoxLayout,
    QComboBox,
    QFormLayout,
    QLabel,
    QSizePolicy,
    QStyle,
    QStyleOptionComboBox,
    QToolButton,
    QWidget,
)

from fdcad.ui.property_panel.elide import elide_when_cut
from fdcad.ui.themes.style import unit

#: The widest the shared column gets, in spacing steps (128 px at the default font). A
#: longer word keeps its own width, and only its own group's fields move right for it.
MAX_STEPS = 32
#: Letters a drop down beside a word always has room for. Its list keeps the width of
#: its longest entry.
MIN_LETTERS = 8
#: The same in a panel that must fit the left panel's default width (D2790).
NARROW_LETTERS = 5
#: The widest the shared column gets in a panel that must fit the default width, in
#: letters of average width (48 px at the default font): what is left is room for a
#: field. A longer word does not widen the column there (D2801). It is counted in
#: letters, not in spacing steps, so the same words fit whatever the font: the font
#: Qt falls back to offscreen on Windows is as wide as it is tall, 13 px a letter.
NARROW_WORD_LETTERS = 8
#: Set on the root of such a panel.
_NARROW_ROOT = "narrow_columns"
#: Name of the label ``groups.icon_label`` makes.
ICON_NAME = "field_icon"
#: Set on a lead row once a spacer follows its lead.
_PADDED = "lead_padded"
#: Set on a drop down once it may be narrower than its longest entry.
_NARROW = "narrow_ok"
#: Set on a drop down that sits under its word at the width of its group (D2801).
UNDER_WORD = "under_word"
#: Set on a label or lead row once the keeper listens to it.
_WATCHED = "column_watched"
#: Events that say a row came or went.
_SHOWS = (
    QEvent.Type.Show,
    QEvent.Type.Hide,
    QEvent.Type.ShowToParent,
    QEvent.Type.HideToParent,
)


def _forms(root: QWidget) -> list[tuple[QWidget, QFormLayout]]:
    """The group and form of every group under ``root`` that is not hidden. A folded
    group counts: folding one must not move the fields of the others."""
    from fdcad.ui.property_panel.groups import Group

    return [(g, g.form) for g in root.findChildren(Group) if g.isVisibleTo(root)]


def _lead_of(row: QWidget | None) -> QWidget | None:
    """The icon or small button a row starts with, when a field follows it."""
    layout = row.layout() if row is not None else None
    if not isinstance(layout, QBoxLayout) or layout.direction() not in (
        QBoxLayout.Direction.LeftToRight,
        QBoxLayout.Direction.RightToLeft,
    ):
        return None
    items = [layout.itemAt(i) for i in range(layout.count())]
    found = [item.widget() for item in items if item is not None]
    widgets = [w for w in found if w is not None]
    if len(widgets) < 2:
        return None
    first, second = widgets[0], widgets[1]
    if isinstance(first, QLabel) and first.objectName() == ICON_NAME:
        return first
    icon_only = isinstance(first, QToolButton) and not isinstance(second, QToolButton)
    return first if icon_only else None


def sole_box(field: QWidget | None) -> QComboBox | None:
    """The drop down that is all of a row's field: the field itself, or the one
    control in it next to a field icon (which a row that leads with a word hides)."""
    if isinstance(field, QComboBox):
        return field
    layout = field.layout() if field is not None else None
    if not isinstance(layout, QBoxLayout):
        return None
    items = [layout.itemAt(i) for i in range(layout.count())]
    found = [item.widget() for item in items if item is not None]
    inside = [w for w in found if w is not None and w.objectName() != ICON_NAME]
    if len(inside) == 1 and isinstance(inside[0], QComboBox):
        return inside[0]
    return None


def is_under(box: QComboBox | None) -> bool:
    """True for a drop down that sits under its word (D2801)."""
    return box is not None and bool(box.property(UNDER_WORD))


def settle_under(root: QWidget) -> None:
    """In a panel that must fit the default width, say which drop downs sit under
    their word (D2801). It is decided group by group, so the rows of a group look
    alike: when the word of one drop down of a group is wider than the lead column
    may be (``NARROW_WORD_LETTERS``), every drop down of that group that follows a
    word goes under its word, at the width of the group. In a group whose words all
    fit the column (Along, in Extrude) they stay beside their words, in the one
    column of D2742. Once under, a drop down stays there while its panel is open."""
    if not is_narrow(root):
        return
    cap = _cap(root)
    for _group, form in _forms(root):
        rows = [(label, sole_box(field)) for label, field in _Rows(form).words]
        boxes = [(label, box) for label, box in rows if box is not None]
        long_word = any(
            not label.isHidden() and label.sizeHint().width() > cap for label, _box in boxes
        )
        if long_word or any(is_under(box) for _label, box in boxes):
            for _label, box in boxes:
                box.setProperty(UNDER_WORD, True)


class _Rows:
    """The rows of one form: those that lead with a word (the label and its field) and
    those that lead with an icon or a small button."""

    def __init__(self, form: QFormLayout) -> None:
        self.form = form
        self.words: list[tuple[QLabel, QWidget | None]] = []
        self.leads: list[QWidget] = []
        for index in range(form.rowCount()):
            label_item = form.itemAt(index, QFormLayout.ItemRole.LabelRole)
            field_item = form.itemAt(index, QFormLayout.ItemRole.FieldRole)
            span_item = form.itemAt(index, QFormLayout.ItemRole.SpanningRole)
            label = label_item.widget() if label_item is not None else None
            if isinstance(label, QLabel) and label.text():
                field = field_item.widget() if field_item is not None else None
                self.words.append((label, field))
                continue
            row = span_item.widget() if span_item is not None else None
            if row is not None and _lead_of(row) is not None:
                self.leads.append(row)

    def widths(self) -> list[int]:
        """Width of the lead of every row that is not hidden, without the words whose
        drop down sits under them (D2801): those need no column."""
        out = [
            label.sizeHint().width()
            for label, field in self.words
            if not label.isHidden() and not is_under(sole_box(field))
        ]
        for row in self.leads:
            lead = _lead_of(row)
            if lead is not None and not row.isHidden():
                out.append(lead.sizeHint().width())
        return out

    def watched(self) -> list[QWidget]:
        """The widgets whose showing and hiding changes the column."""
        return [label for label, _f in self.words] + self.leads


def _row_spacing(row: QWidget) -> int:
    layout = row.layout()
    spacing = layout.spacing() if layout is not None else -1
    if spacing >= 0:
        return int(spacing)
    return int(row.style().pixelMetric(QStyle.PixelMetric.PM_LayoutHorizontalSpacing))


def _pad(row: QWidget, extra: int) -> None:
    """Put ``extra`` pixels between the lead of ``row`` and what follows it."""
    layout = row.layout()
    assert isinstance(layout, QBoxLayout)
    item = layout.itemAt(1)
    spacer = item.spacerItem() if item is not None else None
    if row.property(_PADDED) and spacer is not None:
        if spacer.sizeHint().width() == extra:
            return
        spacer.changeSize(extra, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
    else:
        layout.insertSpacing(1, extra)
        row.setProperty(_PADDED, True)
    layout.invalidate()


def let_narrow(box: QComboBox, letters: int = MIN_LETTERS) -> None:
    """Let a drop down be narrower than its longest entry, so a wider column never
    pushes it under its word. The list that drops down keeps its full width (as D2699
    did for Preferences)."""
    was = box.property(_NARROW)
    if was:
        if box.property(UNDER_WORD):
            return  # it asks for its whole row on purpose
        if letters < box.minimumContentsLength():  # a narrow panel asks for less (D2790)
            box.setMinimumContentsLength(letters)
            QCoreApplication.sendEvent(box, QEvent(QEvent.Type.StyleChange))
        return
    box.setProperty(_NARROW, True)
    elide_when_cut(box)  # an entry with no room ends with an ellipsis (D2800)
    box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    box.setMinimumContentsLength(letters)
    # Qt keeps the least size it worked out before, and only a change of style makes
    # it work that size out again, so the box is told its style changed.
    QCoreApplication.sendEvent(box, QEvent(QEvent.Type.StyleChange))

    def widen() -> None:
        # The longest entry, the padding of a row and room for a scroll bar.
        if not shiboken6.isValid(box):
            return  # a model that outlived its box
        metrics = box.fontMetrics()
        entries = (metrics.horizontalAdvance(box.itemText(i)) for i in range(box.count()))
        box.view().setMinimumWidth(max(entries, default=0) + 8 * unit(box.font()))

    widen()
    model = box.model()
    for signal in (model.rowsInserted, model.rowsRemoved, model.modelReset, model.dataChanged):
        signal.connect(lambda *_a: widen())


def ask_for_row(box: QComboBox, width: int) -> None:
    """Have ``box`` ask for ``width`` pixels or more, whatever its entries and its
    least width are, so a form gives it the whole row under its word (D2801).

    A form that puts a field under its word still lines the field up with the fields
    beside their words when the field does not ask for more than that column. With
    no such field in the form, that column starts one gap in, so the drop down under
    "Along" in Extrude stood 8 px to the right of everything else."""
    box.setProperty(UNDER_WORD, True)
    if not box.property(_NARROW):
        let_narrow(box)
    letters = -(-width // max(box.fontMetrics().horizontalAdvance("X"), 1))
    if box.minimumContentsLength() != letters:
        box.setMinimumContentsLength(letters)
        QCoreApplication.sendEvent(box, QEvent(QEvent.Type.StyleChange))


def set_narrow(root: QWidget) -> None:
    """Keep the lead column of ``root`` to ``NARROW_WORD_LETTERS`` (D2791, D2801): for a
    panel that must fit the left panel's default width. A longer word does not widen
    the column, and a drop down that follows it goes under it (``settle_under``)."""
    root.setProperty(_NARROW_ROOT, True)


def _cap(root: QWidget) -> int:
    if root.property(_NARROW_ROOT):
        return NARROW_WORD_LETTERS * int(root.fontMetrics().averageCharWidth())
    return MAX_STEPS * unit(root.font())


def is_narrow(root: QWidget) -> bool:
    """True for a panel that must fit the left panel's default width (``set_narrow``)."""
    return bool(root.property(_NARROW_ROOT))


def natural_width(box: QComboBox) -> int:
    """The width a drop down needs to show its longest entry, or its placeholder, in
    full, whatever width it is allowed to have."""
    metrics = box.fontMetrics()
    words = [box.itemText(i) for i in range(box.count())] + [box.placeholderText()]
    longest = max(metrics.horizontalAdvance(text) for text in words)
    if any(not box.itemIcon(i).isNull() for i in range(box.count())):
        longest += box.iconSize().width() + 4
    option = QStyleOptionComboBox()
    box.initStyleOption(option)
    inside = QSize(longest, max(metrics.height(), 14) + 2)
    size = box.style().sizeFromContents(QStyle.ContentsType.CT_ComboBox, option, inside, box)
    return int(size.width())


def column_width(root: QWidget) -> int:
    """Width of the one lead column of the groups under ``root``: the widest word or
    lead cell on show, and never more than ``MAX_STEPS`` steps.

    In a panel that must fit the default width (D2801) a word wider than
    ``NARROW_WORD_LETTERS`` letters does not count at all, and neither does a word whose
    drop down sits under it (``settle_under``). Before, one long word set the
    column to the most allowed, and every field that follows an icon lost that
    room to line up with it: the drop downs of Sweep had 74 px for their entry."""
    settle_under(root)
    widths = [w for _group, form in _forms(root) for w in _Rows(form).widths()]
    cap = _cap(root)
    if is_narrow(root):
        return max((w for w in widths if w <= cap), default=0)
    return min(max(widths, default=0), cap)


def align(root: QWidget) -> int:
    """Start the field of every row of every group under ``root`` at one x. Returns the
    column's width, 0 when there is no row to line up."""
    width = column_width(root)
    narrow = is_narrow(root)
    if width <= 0 and not narrow:
        return 0
    for _group, form in _forms(root):
        rows = _Rows(form)
        # A word longer than the column keeps its width; its own group follows it.
        own = max([width, *rows.widths()])
        if narrow:
            own = width  # no room to follow a long word: its field goes under it
        for label, field in rows.words:
            label.setMinimumWidth(width)
            icon = _lead_of(field)
            if isinstance(icon, QLabel):
                icon.hide()  # the word leads this row
            if narrow:
                # A drop down beside its word gives way to keep the one column, and
                # ends its entry with an ellipsis (D2800). One that goes under its
                # word (D2801) is given the width of its group by ``narrow.Fitter``.
                box = sole_box(field)
                if box is not None and not is_under(box):
                    let_narrow(box, NARROW_LETTERS)
                continue
            boxes = [field] if isinstance(field, QComboBox) else []
            if field is not None and not boxes:
                boxes = field.findChildren(QComboBox)
            for box in boxes:
                let_narrow(box)
        gap = form.horizontalSpacing()
        for row in rows.leads:
            lead = _lead_of(row)
            assert lead is not None
            _pad(row, max(0, own + gap - lead.sizeHint().width() - _row_spacing(row)))
    return width


class _Keeper(QObject):
    """Lines the rows under ``root`` up again when one of them shows or hides."""

    def __init__(self, root: QWidget) -> None:
        super().__init__(root)
        self.setObjectName("column_keeper")
        self.root = root
        self._waiting = False

    def watch(self) -> None:
        """Listen to every row there is now. The mark is kept on the widget itself: a
        label the form made has no lasting Python object to remember it by."""
        for _group, form in _forms(self.root):
            for widget in _Rows(form).watched():
                if not widget.property(_WATCHED):
                    widget.setProperty(_WATCHED, True)
                    widget.installEventFilter(self)

    def eventFilter(self, _watched: QObject, event: QEvent) -> bool:  # noqa: N802  (Qt override)
        """A row came or went: line up once, after the events of this turn."""
        if event.type() in _SHOWS and not self._waiting:
            self._waiting = True
            QTimer.singleShot(0, self, self.run)
        return False

    def run(self) -> None:
        """Line up now."""
        self._waiting = False
        align(self.root)
        self.watch()


def keep_aligned(root: QWidget) -> int:
    """``align`` now, and again whenever a row under ``root`` shows or hides. Call it
    again after adding groups or rows. Returns the column's width."""
    keeper = root.findChild(_Keeper, "column_keeper")
    if keeper is None:
        keeper = _Keeper(root)
    width = align(root)
    keeper.watch()
    return width


def narrow_boxes(root: QWidget) -> None:
    """Let every drop down under ``root`` be narrower than its longest entry (D2790).
    For a panel that must fit the left panel's default width: its lists keep their
    full width when they drop down."""
    for box in root.findChildren(QComboBox):
        let_narrow(box, NARROW_LETTERS)
