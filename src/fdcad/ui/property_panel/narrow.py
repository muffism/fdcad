"""Keep a panel no wider than the left panel is by default (D2791).

Fillet and Chamfer were laid out by hand to fit (D2790). Every other tool's
panel is fitted here, the same way for all: ``fit`` walks the layouts under a
widget and, only where a row is wider than the room it has,

1. lets a label of several words wrap,
2. turns a row of controls into a column, and a grid into one column,
3. puts a field under its word in a form,
4. lets a drop down be narrower than its longest entry (its list keeps its width,
   and an entry it has no room for ends with an ellipsis, D2800),
5. puts the words of a button or a tick box on two lines of about one length.

The order matters (D2802): a row is stacked before a drop down in it is cut short
or the words of a button in it are broken, since a column of whole controls reads
better than a row of cut ones. A drop down beside a word that cannot show its
longest entry there goes under the word at the full width (D2801).

A row that leads with a field icon or a small button keeps its lead beside its
field (D2692, D2742). Nothing is changed in a row that already fits, so a panel
looks as before wherever there is room. ``Fitter`` runs ``fit`` again whenever
the panel's layout changes: a row shown by a choice is fitted when it shows.
"""

from __future__ import annotations

from collections.abc import Callable
from itertools import combinations, pairwise

import shiboken6
from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractScrollArea,
    QAbstractSpinBox,
    QBoxLayout,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QLabel,
    QLayout,
    QLayoutItem,
    QStackedLayout,
    QToolButton,
    QWidget,
)

from fdcad.ui.property_panel.columns import (
    NARROW_LETTERS,
    UNDER_WORD,
    _forms,
    _lead_of,
    _Rows,
    ask_for_row,
    is_narrow,
    let_narrow,
    settle_under,
    sole_box,
)
from fdcad.ui.property_panel.elide import elide_when_cut

#: The words of a button before they were put on two lines (see ``words_of``).
FULL_TEXT = "full_text"
#: Set on a widget whose least width this module set.
_OURS = "fitted_width"
#: Set on a drop down under its word once it has asked for the whole row.
_ASKED = "row_asked"
#: Set on a button whose accessible name this module gave it.
_NAMED = "fitted_name"
#: Passes over a panel before giving up: each pass can only make rows narrower.
PASSES = 4
_SIDEWAYS = (QBoxLayout.Direction.LeftToRight, QBoxLayout.Direction.RightToLeft)


def _least(item: QLayoutItem) -> int:
    """The least width of a layout item; 0 for one that is hidden."""
    return 0 if item.isEmpty() else int(item.minimumSize().width())


def _items(layout: QLayout) -> list[QLayoutItem]:
    found = [layout.itemAt(i) for i in range(layout.count())]
    return [item for item in found if item is not None]


#: More words than this are broken line by line: the even break tries every place.
_MOST_WORDS = 12


def _wrapped(text: str, width: int, measure: Callable[[str], int]) -> str:
    """``text`` broken into lines of at most ``width`` pixels, at spaces only.

    It takes as few lines as filling each line would, but the lines are about one
    length (D2802): "Keep size when / the type changes", not "Keep size when the
    type / changes" with one word left over. Of the breaks with that many lines,
    the one whose longest line is shortest is taken; of equals, the one whose
    shortest line is longest, then the one that breaks later."""
    words = text.split(" ")
    lines: list[str] = []
    for word in words:
        if lines and measure(f"{lines[-1]} {word}") <= width:
            lines[-1] = f"{lines[-1]} {word}"
        else:
            lines.append(word)
    count = len(lines)
    if count < 2 or count == len(words) or len(words) > _MOST_WORDS:
        return "\n".join(lines)
    best: tuple[tuple[int, int, tuple[int, ...]], list[str]] | None = None
    for breaks in combinations(range(1, len(words)), count - 1):
        edges = (0, *breaks, len(words))
        tried = [" ".join(words[a:b]) for a, b in pairwise(edges)]
        widths = [measure(line) for line in tried]
        if max(widths) > width:
            continue
        score = (max(widths), -min(widths), tuple(-at for at in breaks))
        if best is None or score < best[0]:
            best = (score, tried)
    return "\n".join(best[1] if best is not None else lines)


def words_of(button: QAbstractButton) -> str:
    """The words of a button or a tick box on one line, as its panel wrote them, also
    after ``fit`` put them on two lines (D2806). A test or a tool that finds a control
    by its words asks this, not ``text()``."""
    return str(button.text()).replace("\n", " ")


def _name(button: QAbstractButton, words: str) -> None:
    """Remember the whole words of a button whose words are broken, and have them
    read out as one line. A name its panel gave the button is left alone."""
    button.setProperty(FULL_TEXT, words)
    if not button.accessibleName() or button.property(_NAMED):
        button.setAccessibleName(words.replace("&", ""))
        button.setProperty(_NAMED, True)


def _rename(root: QWidget) -> None:
    """Bring the remembered words of every broken button under ``root`` up to date. A
    panel that gives such a button new words (a Fix button, a count) would else have
    the old ones read out (D2806)."""
    for button in root.findChildren(QAbstractButton):
        if button.property(FULL_TEXT) and button.property(FULL_TEXT) != words_of(button):
            _name(button, words_of(button))


def _say_width(widget: QWidget, width: int) -> None:
    """Give ``widget`` a least width of ``width``, and remember that this module did:
    a later, narrower fit may lower it again, unlike a width its own panel set."""
    widget.setMinimumWidth(max(width, 1))
    widget.setProperty(_OURS, True)


def _fit_leaf(widget: QWidget, room: int) -> None:
    """A control with no layout of its own. A drop down may be narrower than its
    entries, a label wraps, the words of a button or tick box go on two lines, and a
    list, a table or a number box, whose contents scroll, may be as narrow as the room."""
    metrics = widget.fontMetrics()
    if isinstance(widget, QComboBox):
        # As wide as the room, and no narrower (D2801): in a form that sends it under
        # its word, where it has the whole width; beside an icon it takes what is left.
        # What it still cannot show ends with an ellipsis (D2800).
        let_narrow(widget, NARROW_LETTERS)
        least = (NARROW_LETTERS + 6) * metrics.averageCharWidth()
        _say_width(widget, max(room, least))
    elif isinstance(widget, QLabel):
        words = widget.text().strip()
        if " " not in words or not widget.pixmap().isNull():
            return
        if not widget.wordWrap():
            widget.setWordWrap(True)
        if (
            widget.minimumSizeHint().width() > room
            and widget.textFormat() != Qt.TextFormat.RichText
        ):
            # A wrapping label still asks for a comfortable width: its longest word is enough.
            longest = max(metrics.horizontalAdvance(word) for word in words.split())
            _say_width(widget, min(room, longest))
    elif isinstance(widget, QAbstractButton):
        # The words on show, not the ones remembered: the panel may have given the
        # button new words since they were last broken (D2806).
        text = words_of(widget)
        if " " not in text.strip():
            return
        around = widget.minimumSizeHint().width() - max(
            metrics.horizontalAdvance(line) for line in widget.text().split("\n")
        )
        broken = _wrapped(text, room - around, metrics.horizontalAdvance)
        if broken != widget.text():
            _name(widget, text)
            widget.setText(broken)
    elif isinstance(widget, (QAbstractScrollArea, QAbstractSpinBox)):
        # A number box asks for room for its longest value (1000000.0000): with a wide
        # font that alone was more than a group has. Its text scrolls, as in any field.
        _say_width(widget, min(room, widget.minimumSizeHint().width()))


def _fit_item(item: QLayoutItem, room: int, every: bool = False) -> None:
    """Fit what ``item`` holds into ``room`` pixels. ``every``: hidden pages too."""
    if item.isEmpty() and not every:
        return
    widget, layout = item.widget(), item.layout()
    if widget is not None:
        _fit_widget(widget, room)
    elif layout is not None and _layout_least(layout) > room:
        _fit_layout(layout, room, None)


def _layout_least(layout: QLayout) -> int:
    layout.invalidate()
    return int(layout.minimumSize().width())


def _fit_widget(widget: QWidget, room: int) -> None:
    if widget.minimumWidth() > room and not widget.property(_OURS):
        return  # a width set on purpose; not ours to change
    if max(widget.minimumSizeHint().width(), widget.minimumWidth()) <= room:
        return
    layout = widget.layout()
    if layout is None:
        _fit_leaf(widget, room)
    else:
        # What the widget adds round its layout: the border a style sheet gives a group.
        frame = max(widget.minimumSizeHint().width() - _layout_least(layout), 0)
        _fit_layout(layout, room - frame, widget)
    widget.updateGeometry()


def _fit_layout(layout: QLayout, room: int, owner: QWidget | None) -> None:
    margins = layout.contentsMargins()
    inner = room - margins.left() - margins.right()
    if isinstance(layout, QStackedLayout):
        for item in _items(layout):
            _fit_item(item, inner, every=True)  # a hidden page still counts in the width
    elif isinstance(layout, QFormLayout):
        _fit_form(layout, inner, room)
    elif isinstance(layout, QGridLayout):
        _fit_grid(layout, inner, room)
    elif isinstance(layout, QBoxLayout) and layout.direction() in _SIDEWAYS:
        _fit_row(layout, inner, room, owner)
    else:
        for item in _items(layout):
            _fit_item(item, inner)
    layout.invalidate()


def _small(item: QLayoutItem) -> bool:
    """True for an icon or an icon button: it belongs beside its neighbour in a row,
    and would look lost on a line of its own."""
    widget = item.widget()
    if isinstance(widget, QToolButton):
        return widget.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    return isinstance(widget, QLabel) and not widget.pixmap().isNull()


def _fit_row(layout: QBoxLayout, inner: int, room: int, owner: QWidget | None) -> None:
    """A row of controls. Its labels wrap first. If that is not enough the row becomes
    a column of whole controls (D2802); only a row that must stay a row (an icon and
    its field, a control and an icon button) has its controls give way instead."""
    items = _items(layout)

    def over() -> int:
        """Pixels the row is too wide by, as the layout itself counts them."""
        return _layout_least(layout) - room

    by_width = sorted(items, key=_least, reverse=True)
    for item in by_width:
        if over() > 0 and isinstance(item.widget(), QLabel):
            _fit_item(item, _least(item) - over())
    if over() <= 0:
        return
    holders = [item for item in items if not item.isEmpty() and item.spacerItem() is None]
    lead = owner is not None and _lead_of(owner) is not None
    if len(holders) >= 2 and not lead and not any(_small(item) for item in holders):
        layout.setDirection(QBoxLayout.Direction.TopToBottom)
        for item in items:
            _fit_item(item, inner)
        return
    for item in by_width:
        if over() <= 0:
            return
        _fit_item(item, _least(item) - over())
    if over() <= 0 or len(holders) < 2 or lead:
        return  # one control, or an icon and its field: these stay as they are
    layout.setDirection(QBoxLayout.Direction.TopToBottom)
    for item in items:
        _fit_item(item, inner)


def _fit_form(layout: QFormLayout, inner: int, room: int) -> None:
    """Rows of a word and a field: the field goes under its word when both do not fit."""
    wrap = False
    for row in range(layout.rowCount()):
        span = layout.itemAt(row, QFormLayout.ItemRole.SpanningRole)
        if span is not None:
            _fit_item(span, inner)
            continue
        label = layout.itemAt(row, QFormLayout.ItemRole.LabelRole)
        field = layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
        if field is not None:
            _fit_item(field, inner)
        if label is not None:
            _fit_item(label, inner)
        both = sum(_least(item) for item in (label, field) if item is not None)
        if label is not None and field is not None and both + layout.horizontalSpacing() > inner:
            wrap = True
    if wrap and layout.rowWrapPolicy() == QFormLayout.RowWrapPolicy.DontWrapRows:
        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
    # Qt counts a little more than the widest field for a form whose rows wrap (the
    # gap between the columns): take what is still over from the fields.
    for _ in range(2):
        over = _layout_least(layout) - room
        if over <= 0:
            return
        rows = range(layout.rowCount())
        fields = [layout.itemAt(row, QFormLayout.ItemRole.FieldRole) for row in rows]
        widest = max((_least(field) for field in fields if field is not None), default=0)
        for field in fields:
            if field is not None and _least(field) > widest - over:
                _fit_item(field, widest - over)


def _fit_grid(layout: QGridLayout, inner: int, room: int) -> None:
    """A grid: first let each cell give way; if that is not enough, make it one column."""
    cells: list[tuple[int, int, int, QLayoutItem]] = []
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item is None:
            continue
        place: tuple[int, int, int, int] = layout.getItemPosition(index)  # type: ignore[assignment]
        row, column, columns = place[0], place[1], place[3]
        cells.append((row, column, columns, item))

    def over() -> int:
        return _layout_least(layout) - room

    for _row, _column, columns, item in sorted(cells, key=lambda c: _least(c[3]), reverse=True):
        if over() <= 0:
            return
        _fit_item(item, inner if columns > 1 else _least(item) - over())
    if over() <= 0 or len({column for _row, column, _columns, _item in cells}) < 2:
        return
    # One column, in reading order. What each cell holds is taken before the cell is
    # removed: Qt deletes the cell itself then, and it must not be touched after.
    ordered = sorted(cells, key=lambda cell: (cell[0], cell[1]))
    held: list[tuple[QWidget | None, QLayout | None, Qt.AlignmentFlag]] = [
        (item.widget(), item.layout(), item.alignment()) for _r, _c, _n, item in ordered
    ]
    if any(widget is None and inside is None for widget, inside, _align in held):
        return  # a grid with spacers in its cells is laid out with care: leave it
    for widget, inside, _align in held:
        if widget is not None:
            layout.removeWidget(widget)
        elif inside is not None:
            layout.removeItem(inside)
    for line, (widget, inside, align) in enumerate(held):
        if widget is not None:
            layout.addWidget(widget, line, 0, align)
            _fit_widget(widget, inner)
        elif inside is not None:
            layout.addLayout(inside, line, 0, align)
            if _layout_least(inside) > inner:
                _fit_layout(inside, inner, None)


def boxes_under_words(root: QWidget, limit: int) -> None:
    """In the groups under ``root``, send the drop downs that ``columns.settle_under``
    names under their word, where each is as wide as its group (D2801).

    Beside a long word a drop down had room for a few letters, and which ones stayed
    beside and which went under depended on the length of each one's entries, so a
    group had fields at three left edges. Now the drop downs of such a group all sit
    under their words and show all but the longest entry.

    A form puts a field under its word when the two do not fit side by side, so the
    drop down is given a least width of ``limit``, more than any group has: ``fit``
    then takes it back to the width of its row."""
    settle_under(root)
    for _group, form in _forms(root):
        for _label, field in _Rows(form).words:
            box = sole_box(field)
            if box is None or not box.property(UNDER_WORD) or box.property(_ASKED):
                continue
            box.setProperty(_ASKED, True)
            ask_for_row(box, limit)
            _say_width(box, limit)


def elide_all(root: QWidget) -> None:
    """Every drop down under ``root`` ends an entry it has no room for with an ellipsis
    (D2810), not only the ones the fitter made narrower. A drop down takes the width of
    its row, and an entry chosen later can be wider than that: "Front Plane" in Linear
    Pattern is, in the Mac's font. Nothing changes while the entry fits (D2800)."""
    for box in root.findChildren(QComboBox):
        if not box.isEditable():
            elide_when_cut(box)


def fit(root: QWidget, limit: int) -> bool:
    """Make the least width of ``root`` at most ``limit`` pixels. True when it fits."""
    _rename(root)
    for _ in range(PASSES):
        if root.minimumSizeHint().width() <= limit:
            return True
        layout = root.layout()
        if layout is None:
            return False
        _fit_layout(layout, limit, root)
        layout.activate()
    return bool(root.minimumSizeHint().width() <= limit)


class Fitter(QObject):
    """Fits ``root`` to ``limit()`` now and each time its layout changes."""

    def __init__(self, root: QWidget, limit: Callable[[], int]) -> None:
        super().__init__(root)
        self.setObjectName("width_fitter")
        self.root, self.limit = root, limit
        self._waiting = False
        self._running = False
        root.installEventFilter(self)

    def run(self) -> bool:
        """Fit now. True when ``root`` fits."""
        self._waiting = False
        if self._running or not shiboken6.isValid(self.root):
            return True
        self._running = True
        try:
            limit = self.limit()
            if is_narrow(self.root):
                boxes_under_words(self.root, limit)
            elide_all(self.root)
            return fit(self.root, limit)
        finally:
            self._running = False

    def eventFilter(self, _watched: QObject, event: QEvent) -> bool:  # noqa: N802  (Qt override)
        """The layout changed: fit once, after the events of this turn."""
        if event.type() == QEvent.Type.LayoutRequest and not self._waiting and not self._running:
            self._waiting = True
            QTimer.singleShot(0, self, self.run)
        return False


__all__ = [
    "FULL_TEXT",
    "PASSES",
    "Fitter",
    "boxes_under_words",
    "elide_all",
    "fit",
    "words_of",
]
