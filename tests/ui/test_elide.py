"""A drop down with no room for its entry ends it with an ellipsis (D2800)."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint
from PySide6.QtGui import QHelpEvent
from PySide6.QtWidgets import QApplication, QComboBox, QTabBar, QToolButton
from pytestqt.qtbot import QtBot

from fdcad.ui.property_panel.columns import let_narrow, natural_width
from fdcad.ui.property_panel.elide import elide_when_cut, elided_text, is_cut, shown_text, text_room
from fdcad.ui.themes.style import unit
from tests.ui.test_ui_polish_controls import styled  # noqa: F401  (fixture)

LONG = "An edge picked in the view, or a sketch line"


def _box(qtbot: QtBot, *entries: str) -> QComboBox:
    box = QComboBox()
    qtbot.addWidget(box)
    box.addItems(list(entries))
    return box


def _tip_taken(box: QComboBox) -> bool:
    """True when asking ``box`` for its tooltip was answered."""
    at = QPoint(4, 4)
    event = QHelpEvent(QEvent.Type.ToolTip, at, box.mapToGlobal(at))
    event.ignore()
    QApplication.sendEvent(box, event)
    return bool(event.isAccepted())


def test_an_entry_that_fits_is_shown_whole(qtbot: QtBot) -> None:
    box = _box(qtbot, "Blind", LONG)
    let_narrow(box)
    box.resize(natural_width(box), box.sizeHint().height())
    box.show()
    box.setCurrentIndex(1)
    assert not is_cut(box)
    assert elided_text(box) == LONG
    assert not _tip_taken(box)  # no tooltip of its own, and nothing is cut


def test_an_entry_with_no_room_ends_with_an_ellipsis(qtbot: QtBot) -> None:
    box = _box(qtbot, "Blind", LONG)
    let_narrow(box)  # may be narrower than its entries, so it elides
    box.resize(natural_width(box) // 2, box.sizeHint().height())
    box.show()
    box.setCurrentIndex(1)
    assert is_cut(box)
    drawn = elided_text(box)
    assert drawn != LONG and drawn.endswith("…")
    assert LONG.startswith(drawn[:-1].rstrip())
    assert box.fontMetrics().horizontalAdvance(drawn) <= text_room(box)
    assert box.currentText() == LONG  # the entry itself is not changed
    assert not box.grab().isNull()  # drawn by the filter without an error
    assert _tip_taken(box)  # the whole entry is the tooltip
    box.setCurrentIndex(0)
    assert not is_cut(box) and elided_text(box) == "Blind"


def test_a_placeholder_is_elided_too(qtbot: QtBot) -> None:
    box = _box(qtbot)
    box.setPlaceholderText("Choose a sketch with one circle")
    elide_when_cut(box)
    box.resize(natural_width(box) // 2, box.sizeHint().height())
    box.show()
    assert shown_text(box) == "Choose a sketch with one circle"
    assert is_cut(box) and elided_text(box).endswith("…")
    assert not box.grab().isNull()


def test_an_editable_drop_down_is_left_to_its_field(qtbot: QtBot) -> None:
    box = _box(qtbot, LONG)
    box.setEditable(True)
    elide_when_cut(box)
    box.resize(60, box.sizeHint().height())
    assert not is_cut(box)


def test_natural_width_is_the_width_of_the_longest_entry(qtbot: QtBot) -> None:
    box = _box(qtbot, "Blind", LONG)
    wide = box.sizeHint().width()
    let_narrow(box)
    assert box.sizeHint().width() < wide  # now narrower than its entries
    assert abs(natural_width(box) - wide) <= 2


def test_a_drop_down_gives_its_width_to_its_entry(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
) -> None:
    """D2807: between the entry and the arrow there were 20 px that nothing used, so
    "Square to the sketch" did not fit beside Along in Extrude. Now the entry has the
    same padding on both sides and the arrow has its own 16 px."""
    box = _box(qtbot, "Square to the sketch")
    box.resize(box.sizeHint())
    box.show()
    step = unit(box.font())
    arrow = 4 * step
    assert box.width() - text_room(box) <= arrow + 4 * step  # 30 px at the default font
    words = box.fontMetrics().horizontalAdvance("Square to the sketch")
    assert words < box.sizeHint().width() <= words + arrow + 4 * step
    assert not is_cut(box)


def test_the_arrows_of_a_tab_row_that_scrolls_are_24_px_wide(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
) -> None:
    """U3.3 for the two arrows a tab row shows when its tabs do not fit (D2807). They
    were 12 px wide; the Fillet tabs show them when the left panel is made narrow."""
    bar = QTabBar()
    qtbot.addWidget(bar)
    bar.setUsesScrollButtons(True)
    for name in ("Main", "More", "Favourites", "Another tab", "And one more"):
        bar.addTab(name)
    bar.resize(bar.sizeHint().width() // 2, bar.sizeHint().height())
    bar.show()
    qtbot.wait(20)
    arrows = [b for b in bar.findChildren(QToolButton) if b.isVisible()]
    assert len(arrows) == 2
    assert all(b.width() >= 24 for b in arrows)
