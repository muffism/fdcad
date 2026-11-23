"""``narrow.fit``: a panel's rows give way only where they are too wide (D2791)."""

from __future__ import annotations

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from pytestqt.qtbot import QtBot

from fdcad.ui.property_panel import columns
from fdcad.ui.property_panel.elide import is_cut
from fdcad.ui.property_panel.groups import Group, tool_button, with_icon
from fdcad.ui.property_panel.narrow import FULL_TEXT, Fitter, _wrapped, fit, words_of


def _root(qtbot: QtBot) -> tuple[QWidget, QVBoxLayout]:
    root = QWidget()
    qtbot.addWidget(root)
    layout = QVBoxLayout(root)
    layout.setContentsMargins(0, 0, 0, 0)
    return root, layout


def _row(*widgets: QWidget) -> tuple[QWidget, QHBoxLayout]:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    for widget in widgets:
        layout.addWidget(widget)
    return row, layout


def test_a_row_that_fits_is_left_alone(qtbot: QtBot) -> None:
    root, layout = _root(qtbot)
    row, row_layout = _row(QPushButton("Add"), QPushButton("Remove"))
    layout.addWidget(row)
    wide = root.minimumSizeHint().width()
    assert fit(root, wide)
    assert row_layout.direction() == QBoxLayout.Direction.LeftToRight
    assert root.minimumSizeHint().width() == wide


def test_a_row_of_buttons_becomes_a_column(qtbot: QtBot) -> None:
    root, layout = _root(qtbot)
    first, second = QPushButton("Convex"), QPushButton("Concave")
    row, row_layout = _row(first, second)
    layout.addWidget(row)
    limit = max(first.minimumSizeHint().width(), second.minimumSizeHint().width()) + 4
    assert root.minimumSizeHint().width() > limit
    assert fit(root, limit)
    assert row_layout.direction() == QBoxLayout.Direction.TopToBottom
    assert first.text() == "Convex"  # one word: nothing to break


def test_an_icon_stays_beside_its_field(qtbot: QtBot) -> None:
    """D2692, D2742: a row that leads with a field icon is never stacked; its field gives way."""
    root, layout = _root(qtbot)
    box = QComboBox()
    box.addItems(["Up to the next face of the part", "Blind"])
    row = with_icon("field.depth", "tip", box)
    layout.addWidget(row)
    wide = root.minimumSizeHint().width()
    assert fit(root, wide - 80)
    row_layout = row.layout()
    assert isinstance(row_layout, QBoxLayout)
    assert row_layout.direction() == QBoxLayout.Direction.LeftToRight
    assert root.minimumSizeHint().width() <= wide - 80
    # The list that drops down still shows its longest entry in full.
    longest = box.fontMetrics().horizontalAdvance("Up to the next face of the part")
    assert box.view().minimumWidth() >= longest


def test_long_words_of_a_tick_box_go_on_two_lines(qtbot: QtBot) -> None:
    root, layout = _root(qtbot)
    tick = QCheckBox("Other angle below the neutral plane")
    layout.addWidget(tick)
    wide = root.minimumSizeHint().width()
    assert fit(root, wide * 2 // 3)
    assert "\n" in tick.text()
    assert tick.text().replace("\n", " ") == "Other angle below the neutral plane"
    assert tick.property(FULL_TEXT) == "Other angle below the neutral plane"
    assert tick.accessibleName() == "Other angle below the neutral plane"
    # A narrower fit later breaks the full words again, not the broken ones.
    assert fit(root, wide // 2)
    assert tick.text().replace("\n", " ") == "Other angle below the neutral plane"


def test_broken_words_are_lines_of_about_one_length() -> None:
    """D2802: no word left alone on the second line while the first is full."""

    def measure(text: str) -> int:
        return len(text)

    assert _wrapped("Keep size when the type changes", 24, measure) == (
        "Keep size when\nthe type changes"
    )
    assert _wrapped("Pick operation from where it sits", 30, measure) == (
        "Pick operation\nfrom where it sits"
    )
    assert _wrapped("Add Faces That Need Draft", 20, measure) == "Add Faces That\nNeed Draft"
    # As few lines as filling each line takes, and never a line over the width.
    three = _wrapped("Other angle below the neutral plane", 14, measure)
    assert three.count("\n") == 2 and max(len(line) for line in three.split("\n")) <= 14
    assert _wrapped("Reapply fillets", 40, measure) == "Reapply fillets"
    assert _wrapped("Unbreakable", 4, measure) == "Unbreakable"


def test_a_row_is_stacked_before_its_controls_are_cut(qtbot: QtBot) -> None:
    """D2802: a drop down and a button that do not fit side by side go one under the
    other. The button keeps its words on one line and the drop down has the whole row."""
    root, layout = _root(qtbot)
    box, button = QComboBox(), QPushButton("Save Bodies")
    box.addItems(["FDCAD Part", "STEP"])
    row, row_layout = _row(box, button)
    layout.addWidget(row)
    limit = max(box.minimumSizeHint().width(), button.minimumSizeHint().width()) + 8
    assert root.minimumSizeHint().width() > limit
    root.resize(limit, 200)
    root.show()
    assert fit(root, limit)
    qtbot.wait(10)
    assert row_layout.direction() == QBoxLayout.Direction.TopToBottom
    assert button.text() == "Save Bodies"
    assert not is_cut(box) and box.width() == button.width()


def test_a_row_with_an_icon_button_stays_a_row(qtbot: QtBot) -> None:
    """An icon button would look lost on a line of its own: its neighbour gives way."""
    root, layout = _root(qtbot)
    box = QComboBox()
    box.addItems(["Up to the next face of the part", "Blind"])
    row, row_layout = _row(box, tool_button("ui.reverse_direction", "Reverse", "tip"))
    layout.addWidget(row)
    wide = root.minimumSizeHint().width()
    assert fit(root, wide - 60)
    assert row_layout.direction() == QBoxLayout.Direction.LeftToRight


def test_a_number_box_may_be_as_narrow_as_its_room(qtbot: QtBot) -> None:
    root, layout = _root(qtbot)
    spin = QDoubleSpinBox()
    spin.setRange(0.001, 1e6)
    spin.setDecimals(4)
    layout.addWidget(spin)
    wide = root.minimumSizeHint().width()
    assert fit(root, wide - 30)
    assert root.minimumSizeHint().width() <= wide - 30


def _narrow_panel(qtbot: QtBot) -> tuple[QWidget, dict[str, QWidget], int]:
    """A panel as the main window makes them: one group with a short word, one with a
    long word, and rows that lead with an icon in both."""
    root, layout = _root(qtbot)
    first, second = Group("Direction 1", "tip"), Group("Options", "tip")
    layout.addWidget(first)
    layout.addWidget(second)
    fields: dict[str, QWidget] = {}

    def drop(name: str, *entries: str) -> QComboBox:
        box = QComboBox()
        box.addItems(list(entries))
        fields[name] = box
        return box

    def edit(name: str) -> QLineEdit:
        made = QLineEdit()
        fields[name] = made
        return made

    first.form.addRow(with_icon("field.depth", "tip", edit("depth")))
    first.form.addRow("Along", drop("along", "Square to the sketch", "An edge picked in the view"))
    second.form.addRow(with_icon("field.angle", "tip", drop("twist", "None", "Minimum Twist")))
    second.form.addRow("Start tangency", drop("tangency", "None", "Path Tangent"))
    second.form.addRow("Type", drop("type", "Smooth", "Sharp"))
    second.form.addRow("Section values", edit("values"))
    columns.set_narrow(root)
    limit = root.fontMetrics().horizontalAdvance("Start tangency") * 2 + 80
    root.resize(limit, 600)
    root.show()
    columns.keep_aligned(root)
    assert Fitter(root, lambda: limit).run()
    columns.keep_aligned(root)
    qtbot.wait(20)
    return root, fields, limit


def _left(root: QWidget, widget: QWidget) -> int:
    return int(widget.mapTo(root, QPoint(0, 0)).x())


def _label_of(field: QWidget) -> QWidget:
    holder = field.parentWidget()
    assert holder is not None
    form = holder.layout()
    assert isinstance(form, QFormLayout)
    label = form.labelForField(field)
    assert label is not None
    return label


def test_drop_downs_of_a_group_with_a_long_word_sit_under_their_words(qtbot: QtBot) -> None:
    """D2801: one word of the group is wider than the lead column may be, so every drop
    down of the group that follows a word has the whole row under its word."""
    _root_widget, fields, _limit = _narrow_panel(qtbot)
    tangency, kind, values = fields["tangency"], fields["type"], fields["values"]
    label = _label_of(tangency)
    assert tangency.y() > label.y() + label.height() - 2  # under its word
    # Flush with the word and as wide as the rows of the group, not one gap in.
    assert tangency.x() == label.x() == kind.x()
    holder = tangency.parentWidget()
    assert holder is not None
    assert tangency.width() == kind.width() == holder.width() - tangency.x()
    assert not is_cut(tangency)
    # A text field keeps its place beside its word.
    assert values.x() > tangency.x()


def test_a_drop_down_beside_a_short_word_keeps_the_one_column(qtbot: QtBot) -> None:
    """D2742 holds where the words of a group fit the lead column: Along stays beside
    its drop down, which starts where the fields after an icon start."""
    root, fields, limit = _narrow_panel(qtbot)
    along, depth, twist = fields["along"], fields["depth"], fields["twist"]
    label = _label_of(along)
    assert abs(along.y() - label.y()) < along.height()  # beside its word
    assert _left(root, along) == _left(root, depth) == _left(root, twist)
    assert root.minimumSizeHint().width() <= limit


def test_a_long_word_does_not_widen_the_lead_column(qtbot: QtBot) -> None:
    """D2801: the column is as wide as Along, not as wide as the most allowed because
    of "Start tangency", so the fields after an icon keep their room."""
    root, _fields, _limit = _narrow_panel(qtbot)
    metrics = root.fontMetrics()
    assert metrics.horizontalAdvance("Start tangency") > columns._cap(root)
    assert columns.column_width(root) < columns._cap(root)
    assert columns.column_width(root) >= metrics.horizontalAdvance("Along")


def test_a_label_wraps_and_a_field_goes_under_its_word(qtbot: QtBot) -> None:
    root, layout = _root(qtbot)
    holder = QWidget()
    form = QFormLayout(holder)
    form.setContentsMargins(0, 0, 0, 0)
    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
    field = QLineEdit()
    field.setMinimumWidth(120)
    form.addRow(QLabel("Distance"), field)
    note = QLabel("Click edges or faces in the view to add them here.")
    form.addRow(note)
    layout.addWidget(holder)
    assert fit(root, 130)
    assert note.wordWrap()
    assert form.rowWrapPolicy() == QFormLayout.RowWrapPolicy.WrapLongRows
    assert field.minimumWidth() == 120  # a width its panel set is not changed


def test_a_grid_becomes_one_column(qtbot: QtBot) -> None:
    root, layout = _root(qtbot)
    holder = QWidget()
    grid = QGridLayout(holder)
    grid.setContentsMargins(0, 0, 0, 0)
    buttons = [QPushButton(name) for name in ("Save", "Apply", "Update", "Delete")]
    for index, button in enumerate(buttons):
        grid.addWidget(button, index // 2, index % 2)
    layout.addWidget(holder)
    limit = max(b.minimumSizeHint().width() for b in buttons) + 4
    assert fit(root, limit)
    places = [grid.getItemPosition(grid.indexOf(b))[:2] for b in buttons]
    assert places == [(0, 0), (1, 0), (2, 0), (3, 0)]  # in reading order


def test_what_cannot_fit_is_reported(qtbot: QtBot) -> None:
    root, layout = _root(qtbot)
    layout.addWidget(QPushButton("Unbreakable"))
    assert not fit(root, 20)


def test_the_fitter_fits_a_row_that_shows_later(qtbot: QtBot) -> None:
    root, layout = _root(qtbot)
    first, second = QPushButton("Add Convex Edges"), QPushButton("Add Concave Edges")
    row, row_layout = _row(first, second)
    row.hide()
    layout.addWidget(QPushButton("OK"))
    layout.addWidget(row)
    root.show()
    limit = first.minimumSizeHint().width() + 4
    fitter = Fitter(root, lambda: limit)
    assert fitter.run()
    assert row_layout.direction() == QBoxLayout.Direction.LeftToRight  # hidden: left alone
    row.show()
    qtbot.waitUntil(
        lambda: row_layout.direction() == QBoxLayout.Direction.TopToBottom, timeout=2000
    )
    assert root.minimumSizeHint().width() <= limit


def test_words_of_gives_the_words_on_one_line(qtbot: QtBot) -> None:
    """D2806: what finds a control by its words does not see the line break."""
    root, layout = _root(qtbot)
    tick = QCheckBox("Other angle below the neutral plane")
    layout.addWidget(tick)
    assert words_of(tick) == "Other angle below the neutral plane"
    assert fit(root, root.minimumSizeHint().width() * 2 // 3)
    assert tick.text() != "Other angle below the neutral plane"
    assert words_of(tick) == "Other angle below the neutral plane"


def test_new_words_on_a_broken_button_are_kept(qtbot: QtBot) -> None:
    """D2806: a panel gives a button whose words were broken new words. The fit that
    follows breaks the new words; it used to put the old ones back."""
    root, layout = _root(qtbot)
    button = QPushButton("Add Corner Relief Here")
    layout.addWidget(button)
    limit = root.minimumSizeHint().width() * 2 // 3
    assert fit(root, limit)
    assert "\n" in button.text() and button.accessibleName() == "Add Corner Relief Here"
    button.setText("Snap to Stock Size Now")
    assert fit(root, limit)
    assert words_of(button) == "Snap to Stock Size Now"
    assert button.property(FULL_TEXT) == "Snap to Stock Size Now"
    assert button.accessibleName() == "Snap to Stock Size Now"
    # New words that fit on one line: the name read out follows them too.
    button.setText("Fix")
    assert fit(root, limit)
    assert button.text() == "Fix" and button.accessibleName() == "Fix"
    # A name the panel gave is never replaced.
    named = QPushButton("Add Faces That Need Draft")
    named.setAccessibleName("Add steep faces")
    layout.addWidget(named)
    assert fit(root, limit)
    assert "\n" in named.text() and named.accessibleName() == "Add steep faces"


def test_a_drop_down_the_fitter_left_alone_still_elides(qtbot: QtBot) -> None:
    """D2810: a drop down that was never made narrower can still be too narrow for an
    entry chosen later. It ends that entry with an ellipsis too."""
    from fdcad.ui.property_panel.elide import is_cut

    root, layout = _root(qtbot)
    box = QComboBox()
    box.addItems(["Top", "A plane with a much longer name than the box"])
    box.setFixedWidth(90)  # as a row gives it: wide enough for "Top" only
    layout.addWidget(box)
    root.show()
    fitter = Fitter(root, lambda: 400)
    assert fitter.run()  # it fits: the fitter has nothing to make narrower
    assert box.property("elides_entry")
    assert not is_cut(box)
    box.setCurrentIndex(1)
    assert is_cut(box)  # and is drawn with an ellipsis, by ``elide._Elider``
