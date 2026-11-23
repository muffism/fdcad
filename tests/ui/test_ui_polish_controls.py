"""UI polish U2, U3, U4 and U7: type scale, spacing, control states, focus and motion.

Checks of UI_POLISH_SPEC U11.1 for round 11b (D660 to D667).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QPoint, QSettings, QSize, Qt
from PySide6.QtGui import QAction, QColor, QFont, QFontMetrics, QImage, QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QLineEdit,
    QListWidget,
    QMenu,
    QPushButton,
    QScrollBar,
    QSpinBox,
    QStyle,
    QStyleOptionMenuItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from pytestqt.qtbot import QtBot

from fdcad.core.features.base import FeatureState
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.preferences.dialog import PreferencesDialog
from fdcad.ui.preferences.settings import Settings, Theme
from fdcad.ui.themes import app_style, motion, theme
from fdcad.ui.themes.app_style import menu_row_height, name_widget, tooltip_title
from fdcad.ui.themes.states import FOCUS_RING_TYPES, mix
from fdcad.ui.themes.style import stylesheet, unit
from fdcad.ui.themes.typography import (
    BODY_PX,
    CAPTION_PX,
    DIALOG_TITLE_PX,
    SCALE_PX,
    Role,
    points,
    type_font,
)
from fdcad.ui.tree.row_icons import row_icon
from tests.ui.test_workflow import (  # noqa: F401  (fixtures)
    _folders,
    new_part,
    rectangle_sketch,
    window,
)

SRC = Path(__file__).resolve().parents[2] / "src" / "fdcad" / "ui"
THEMES = [Theme.LIGHT, Theme.BEIGE, Theme.DARK, Theme.STEALTH]


@pytest.fixture
def styled(qapp: QApplication) -> Iterator[QApplication]:
    """FDCAD's style, type scale and Light theme, put back after the test."""
    font = QFont(qapp.font())
    theme.apply_theme(qapp, Theme.LIGHT)
    yield qapp
    app_style._uninstall()
    motion.set_reduce_motion(False)
    motion.set_busy(False)
    qapp.setStyleSheet("")
    qapp.setPalette(qapp.style().standardPalette())
    qapp.setFont(font)
    theme._forced = None


def _settings(tmp_path: Path) -> Settings:
    return Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))


def _px(font: QFont) -> float:
    return font.pointSizeF() * 96.0 / 72.0 if font.pixelSize() <= 0 else font.pixelSize()


# U2.1: one type scale ------------------------------------------------------------------------


def test_type_scale_roles(styled: QApplication) -> None:
    assert SCALE_PX == (11, 13, 13, 15)
    assert type_font(Role.CAPTION).pointSizeF() == pytest.approx(points(CAPTION_PX))
    assert type_font(Role.BODY).pointSizeF() == pytest.approx(points(BODY_PX))
    title = type_font(Role.TITLE)
    assert title.pointSizeF() == pytest.approx(points(BODY_PX))
    assert title.weight() == QFont.Weight.DemiBold
    dialog = type_font(Role.DIALOG_TITLE)
    assert dialog.pointSizeF() == pytest.approx(points(DIALOG_TITLE_PX))
    # The app font is the body size, so every widget without a role is 13 px.
    assert styled.font().pointSizeF() == pytest.approx(points(BODY_PX))
    assert unit(styled.font()) == 4


_SIZE_CALLS = re.compile(
    r"setPointSize(F)?\(|setPixelSize\(|QFont\([^)]*,\s*\d+|font-size:\s*\d|pointSizeF\(\)\s*\*"
)


def test_no_widget_picks_its_own_font_size() -> None:
    """Font sizes come from ``themes.typography`` only (U2.1).

    The command tabs (RIBBON_SPEC, another round) scale their caption to 0.85 of
    the body size, which gives the 11 px caption size.
    """
    allowed = {SRC / "themes" / "typography.py", SRC / "command_tabs" / "ribbon.py"}
    found = []
    for path in SRC.rglob("*.py"):
        if path in allowed:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _SIZE_CALLS.search(line):
                found.append(f"{path.relative_to(SRC)}:{number}: {line.strip()}")
    assert found == []


def test_style_sheet_font_sizes_are_on_the_scale() -> None:
    for chrome, colors in ((theme.LIGHT_CHROME, theme.LIGHT), (theme.DARK_CHROME, theme.DARK)):
        sheet = stylesheet(chrome, colors, QFont())
        sizes = {int(s) for s in re.findall(r"font-size:\s*(\d+)px", sheet)}
        assert sizes <= set(SCALE_PX)
        weights = set(re.findall(r"font-weight:\s*(\d+)", sheet))
        assert weights <= {"600"}  # semibold only


def test_titles_use_the_title_role(styled: QApplication, qtbot: QtBot) -> None:
    from fdcad.ui.help.dialogs import AboutDialog
    from fdcad.ui.property_panel.panel import PropertyPanel

    panel = PropertyPanel()
    qtbot.addWidget(panel)
    assert panel.title.font().weight() == QFont.Weight.DemiBold
    assert panel.title.font().pointSizeF() == pytest.approx(points(BODY_PX))
    about = AboutDialog()
    qtbot.addWidget(about)
    heading = about.findChild(QWidget, "aboutHeading")
    assert heading is not None
    assert heading.font().pointSizeF() == pytest.approx(points(DIALOG_TITLE_PX))


# U2.2 and U2.4: spacing and tabular figures ------------------------------------------------


def test_layout_gaps_are_on_the_4_px_grid(styled: QApplication, qtbot: QtBot) -> None:
    dialog = QDialog()
    qtbot.addWidget(dialog)
    layout = QVBoxLayout(dialog)
    child = QWidget(dialog)
    inner = QVBoxLayout(child)
    layout.addWidget(child)
    assert layout.contentsMargins().left() == 16  # round a window
    assert inner.contentsMargins().left() == 12  # inside a panel
    assert layout.spacing() == 8  # between rows
    metric = styled.style().pixelMetric
    assert metric(QStyle.PixelMetric.PM_LayoutHorizontalSpacing) == 8
    assert metric(QStyle.PixelMetric.PM_LayoutVerticalSpacing) == 8


def test_property_panel_padding_rows_and_groups(
    styled: QApplication,
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = new_part(qtbot, window)
    sid = rectangle_sketch(qtbot, window, tab)
    assert window.tree is not None and window.panel is not None
    window.tree.select(sid)
    window.insert_feature("extrude", "boss")
    panel = window.panel
    assert panel.groups_layout.spacing() == 16  # groups 16 px apart
    margins = panel.groups_layout.contentsMargins()
    assert (margins.left(), margins.right()) == (12, 12)  # 12 px panel padding
    group = next(iter(panel.groups.values()))
    assert group.form.verticalSpacing() == 8  # rows 8 px apart
    assert group.layout().contentsMargins().left() == 12
    field = panel.values["depth"]
    assert field.edit.font().featureValue(QFont.Tag("tnum")) == 1  # tabular figures (U2.4)
    assert window.coords.font().featureValue(QFont.Tag("tnum")) == 1
    panel.reject()


# U3: control states, radii, sizes, menus, scroll bars ----------------------------------------


@pytest.mark.parametrize("scheme", THEMES, ids=lambda t: t.value)
def test_every_state_has_a_rule(scheme: Theme) -> None:
    colors, chrome, _dark = theme.SCHEMES[scheme]
    sheet = stylesheet(chrome, colors, QFont())
    for control in ("QPushButton", "QToolButton"):
        for state in (":hover", ":pressed", ":checked", ":disabled", '[keyfocus="true"]'):
            assert f"{control}{state}" in sheet, (control, state)
    for state in (":hover", ":pressed", ":checked", ":disabled"):
        assert f"QCheckBox::indicator{state}" in sheet
        assert f"QRadioButton::indicator{state}" in sheet
    for state in (":hover", ":pressed", ":disabled"):
        assert f"QSlider::handle{state}" in sheet
    for state in (":hover", ":focus", ":disabled"):
        assert f"QLineEdit{state}" in sheet and f"QAbstractSpinBox{state}" in sheet


def test_one_radius_for_controls_and_one_for_panels() -> None:
    sheet = stylesheet(theme.LIGHT_CHROME, theme.LIGHT, QFont())
    tail = sheet[sheet.index("QToolTip {", 100) :]  # the U3 rules come last and win
    # The Datum radii (D1034): 6 px for controls, 10 px for panels and popups.
    assert re.search(r"QMenu \{[^}]*border-radius: 10px", tail)
    assert re.search(r"QPushButton \{[^}]*border-radius: 6px", tail)
    assert re.search(
        r"QLineEdit, QComboBox, QAbstractSpinBox, [^{]*\{[^}]*border-radius: 6px", tail
    )
    assert re.search(r"QFrame#panel_group \{[^}]*border-radius: 10px", tail)
    assert "QFrame#view_focus { border: 2px solid transparent; border-radius: 0; }" in sheet


def _ratio(a: str, b: str) -> float:
    """WCAG contrast ratio of two ``#RRGGBB`` colours."""

    def lum(color: str) -> float:
        parts = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in parts]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_accent_hover_keeps_contrast_with_its_text() -> None:
    ratio = _ratio
    for _colors, chrome, _dark in theme.SCHEMES.values():
        base = ratio(chrome.on_accent, chrome.accent)
        for t in (0.12, 0.24):
            assert ratio(chrome.on_accent, mix(chrome.accent, chrome.text, t)) >= base


def test_minimum_sizes(styled: QApplication, qtbot: QtBot) -> None:
    host = QWidget()
    qtbot.addWidget(host)
    layout = QVBoxLayout(host)
    tool = QToolButton()
    tool.setIconSize(QSize(16, 16))
    tool.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    tool.setIcon(row_icon("tree.sketch"))
    widgets: list[QWidget] = [
        QPushButton("Apply"),
        QLineEdit("10 mm"),
        QComboBox(),
        QSpinBox(),
        QCheckBox("Reverse"),
        tool,
    ]
    for widget in widgets:
        layout.addWidget(widget)
    main = QPushButton("OK")
    main.setDefault(True)
    layout.addWidget(main)
    rows = QListWidget()
    rows.addItems(["One", "Two"])
    layout.addWidget(rows)
    host.show()
    for widget in widgets:
        assert widget.sizeHint().height() >= 24, type(widget).__name__
    assert tool.sizeHint().width() >= 24
    assert main.sizeHint().height() >= 28  # main buttons
    assert rows.sizeHintForRow(0) >= 24


@pytest.mark.parametrize("scheme", THEMES, ids=lambda t: t.value)
def test_disabled_text_stays_readable(scheme: Theme) -> None:
    """Disabled controls use the muted text: 3:1 or more on every fill (U3.1)."""
    _colors, chrome, _dark = theme.SCHEMES[scheme]
    for fill in (chrome.window, chrome.surface, chrome.raised, chrome.field):
        assert _ratio(chrome.muted, fill) >= 3.0, fill


def test_window_controls_meet_the_minimum_size(
    styled: QApplication,
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """Buttons and fields in the window and the property panel are 24 px or more (U3.3)."""
    from PySide6.QtWidgets import QAbstractSpinBox

    tab = new_part(qtbot, window)
    sid = rectangle_sketch(qtbot, window, tab)
    assert window.tree is not None and window.panel is not None
    window.tree.select(sid)
    window.insert_feature("extrude", "boss")
    qtbot.wait(50)
    small = []
    for widget in window.findChildren(QWidget):
        if not widget.isVisibleTo(window):
            continue
        if not isinstance(widget, (QAbstractButton, QLineEdit, QComboBox, QAbstractSpinBox)):
            continue
        too_narrow = isinstance(widget, QAbstractButton) and widget.width() < 24
        if widget.height() < 24 or too_narrow:
            small.append(f"{type(widget).__name__} {widget.objectName()} {widget.size()}")
    assert small == []
    window.panel.reject()


def test_property_panel_tab_order_follows_reading_order(
    styled: QApplication,
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = new_part(qtbot, window)
    sid = rectangle_sketch(qtbot, window, tab)
    assert window.tree is not None and window.panel is not None
    window.tree.select(sid)
    window.insert_feature("extrude", "boss")
    panel = window.panel
    chain: list[QWidget] = []
    widget = panel.ok_button.nextInFocusChain()
    while widget is not panel.ok_button:
        if (
            panel.isAncestorOf(widget)
            and widget.isVisibleTo(panel)
            and widget.isEnabled()
            and widget.focusPolicy() & Qt.FocusPolicy.TabFocus
        ):
            chain.append(widget)
        widget = widget.nextInFocusChain()
    tops = [w.mapTo(panel, QPoint(0, 0)).y() for w in chain]
    assert len(chain) >= 6
    assert tops == sorted(tops)
    panel.reject()


def test_menu_rows_share_height_icon_column_and_muted_shortcuts(
    styled: QApplication, qtbot: QtBot
) -> None:
    menu = QMenu()
    qtbot.addWidget(menu)
    plain = menu.addAction("Plain")
    with_icon = menu.addAction(row_icon("tree.sketch"), "With Icon")
    shortcut = QAction("Shortcut", menu)
    shortcut.setShortcut(QKeySequence("Ctrl+B"))
    menu.addAction(shortcut)
    menu.addMenu("More").addAction("Inside")
    menu.popup(QPoint(0, 0))
    qtbot.waitExposed(menu)
    u = unit(menu.font())
    heights = {menu.actionGeometry(a).height() for a in menu.actions()}
    assert heights == {menu_row_height(u)}
    assert menu_row_height(u) == 28
    if not QFontMetrics(menu.font()).inFontUcs4(ord("S")):
        pytest.skip(
            "the offscreen platform here has no font with glyphs, so text pixels cannot be read"
        )
    # The label of every row starts at the same place, with or without an icon.
    image = menu.grab().toImage()
    chrome = theme.chrome()

    def first_text_x(action: QAction, color: str) -> int:
        rect = menu.actionGeometry(action)
        for x in range(rect.left(), rect.right()):
            for y in range(rect.top(), rect.bottom()):
                if _close(image, x, y, color) and x > rect.left() + 6 * u:
                    return x
        return -1

    assert first_text_x(plain, chrome.text) == first_text_x(with_icon, chrome.text)
    # The shortcut is right aligned in the muted colour.
    rect = menu.actionGeometry(shortcut)
    right = [
        x
        for x in range(rect.center().x(), rect.right())
        for y in range(rect.top(), rect.bottom())
        if _close(image, x, y, chrome.muted)
    ]
    assert right and max(right) > rect.right() - 12 * u
    menu.hide()


def _close(image: QImage, x: int, y: int, color: str) -> bool:
    got, want = image.pixelColor(x, y), QColor(color)
    return (
        abs(got.red() - want.red()) < 24
        and abs(got.green() - want.green()) < 24
        and abs(got.blue() - want.blue()) < 24
    )


def test_menu_row_size_comes_from_the_style(styled: QApplication, qtbot: QtBot) -> None:
    menu = QMenu()
    qtbot.addWidget(menu)
    option = QStyleOptionMenuItem()
    option.menuItemType = QStyleOptionMenuItem.MenuItemType.Normal
    option.text = "Open\tCtrl+O"
    size = menu.style().sizeFromContents(
        QStyle.ContentsType.CT_MenuItem, option, QSize(40, 10), menu
    )
    assert size.height() == 28


def test_scroll_bar_is_thin_until_hovered(styled: QApplication, qtbot: QtBot) -> None:
    bar = QScrollBar(Qt.Orientation.Vertical)
    qtbot.addWidget(bar)
    bar.setRange(0, 100)
    bar.setPageStep(20)
    bar.resize(12, 200)
    bar.show()
    qtbot.waitExposed(bar)

    def handle_width() -> int:
        image = bar.grab().toImage()
        y = 10
        handle = QColor(
            theme.chrome().border_strong if not bar.property("hovered") else theme.chrome().muted
        )
        return sum(1 for x in range(image.width()) if _close(image, x, y, handle.name()))

    idle = handle_width()
    QApplication.sendEvent(bar, QEvent(QEvent.Type.Enter))
    assert bar.property("hovered") is True
    hovered = handle_width()
    assert 0 < idle < hovered
    QApplication.sendEvent(bar, QEvent(QEvent.Type.Leave))
    assert bar.property("hovered") is False


# U4.1: keyboard focus ring -----------------------------------------------------------------


def test_focus_ring_rule_for_each_control_type() -> None:
    for scheme in THEMES:
        colors, chrome, _dark = theme.SCHEMES[scheme]
        sheet = stylesheet(chrome, colors, QFont())
        for control in FOCUS_RING_TYPES:
            rule = re.search(
                rf"{control}(\[keyfocus=\"true\"\]|:focus|:editable:focus)[^{{]*\{{[^}}]*",
                sheet,
            )
            assert rule is not None, control
        assert f"border: 2px solid {chrome.accent}" in sheet


def test_ring_shows_for_keyboard_focus_not_for_a_click(styled: QApplication, qtbot: QtBot) -> None:
    host = QWidget()
    qtbot.addWidget(host)
    layout = QVBoxLayout(host)
    first, second = QPushButton("First"), QPushButton("Second")
    layout.addWidget(first)
    layout.addWidget(second)
    host.show()
    qtbot.waitExposed(host)
    handle = host.windowHandle()
    assert handle is not None
    handle.requestActivate()
    qtbot.waitUntil(lambda: QApplication.activeWindow() is host)
    first.setFocus(Qt.FocusReason.OtherFocusReason)
    assert not first.property("keyfocus")  # focus from code: no ring
    QTest.keyClick(first, Qt.Key.Key_Tab)
    assert QApplication.focusWidget() is second
    assert second.property("keyfocus") is True  # keyboard: ring
    assert not first.property("keyfocus")
    qtbot.mouseClick(second, Qt.MouseButton.LeftButton)
    assert not second.property("keyfocus")  # a click hides it
    qtbot.mousePress(first, Qt.MouseButton.LeftButton)
    assert QApplication.focusWidget() is first
    assert not first.property("keyfocus")  # mouse focus: no ring
    qtbot.mouseRelease(first, Qt.MouseButton.LeftButton)


def test_ring_draws_on_the_frame_round_the_view(styled: QApplication, qtbot: QtBot) -> None:
    from PySide6.QtWidgets import QFrame

    frame = QFrame()
    frame.setObjectName("view_focus")
    qtbot.addWidget(frame)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    view = QWidget()
    view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    layout.addWidget(view)
    frame.show()
    ring = app_style._ring
    assert ring is not None
    ring.mark(view)
    assert frame.property("keyfocus") is True
    assert frame.contentsRect().left() == 2  # the ring has its own 2 px, nothing moves
    ring._clear()
    assert not frame.property("keyfocus")


# U4.2: tab order, Esc and Enter ------------------------------------------------------------


def test_preferences_tab_order_follows_reading_order(
    styled: QApplication, qtbot: QtBot, tmp_path: Path
) -> None:
    dialog = PreferencesDialog(_settings(tmp_path))
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    page = dialog.tabs.widget(0)
    chain: list[QWidget] = []
    widget = dialog.units_box
    while widget not in chain:
        if page.isAncestorOf(widget) and widget.focusPolicy() & Qt.FocusPolicy.TabFocus:
            chain.append(widget)
        widget = widget.nextInFocusChain()
    tops = [w.mapTo(page, QPoint(0, 0)).y() for w in chain]
    assert len(chain) >= 5
    assert tops == sorted(tops)


def test_dialogs_close_with_esc_and_accept_with_enter(
    styled: QApplication, qtbot: QtBot, tmp_path: Path
) -> None:
    dialog = PreferencesDialog(_settings(tmp_path))
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    with qtbot.waitSignal(dialog.rejected, timeout=2000):
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
    dialog.show()
    dialog.units_box.setFocus()
    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        QTest.keyClick(dialog.units_box, Qt.Key.Key_Return)


# U4.3: accessible names --------------------------------------------------------------------


def test_tooltip_title() -> None:
    assert tooltip_title("<b>Extrude</b><br>Adds material") == "Extrude"
    assert tooltip_title("Fillet\nRounds edges") == "Fillet"
    assert tooltip_title("") == ""


def test_icon_buttons_get_their_tooltip_title(styled: QApplication, qtbot: QtBot) -> None:
    button = QToolButton()
    qtbot.addWidget(button)
    button.setIcon(row_icon("tree.sketch"))
    button.setToolTip("Edit Sketch<br>Opens the sketch")
    button.show()
    assert button.accessibleName() == "Edit Sketch"
    button.setToolTip("Hide")
    assert button.accessibleName() == "Hide"  # follows the tooltip
    named = QToolButton()
    named.setAccessibleName("Chosen")
    named.setToolTip("Other")
    name_widget(named)
    assert named.accessibleName() == "Chosen"  # a name set on purpose stays


def test_tooltips_show_when_the_window_is_not_active(styled: QApplication, qtbot: QtBot) -> None:
    # D1088: Qt shows a tooltip only in the active window, and after using the native
    # 3D view Qt can count no window as active, so every tooltip went quiet.
    from PySide6.QtWidgets import QToolTip

    holder = QWidget()
    qtbot.addWidget(holder)
    button = QToolButton(holder)
    button.setToolTip("Zoom to Fit")
    holder.show()
    other = QWidget()
    qtbot.addWidget(other)
    other.show()
    other.activateWindow()
    qtbot.waitUntil(lambda: QApplication.activeWindow() is not holder, timeout=2000)
    QToolTip.hideText()
    QTest.mouseMove(button, QPoint(5, 5))  # enters the button
    qtbot.wait(30)
    QTest.mouseMove(button, QPoint(6, 6))  # a move inside it starts the tooltip timer
    qtbot.waitUntil(QToolTip.isVisible, timeout=3000)
    assert QToolTip.text() == "Zoom to Fit"
    QToolTip.hideText()


def test_every_icon_button_in_the_window_has_a_name(
    styled: QApplication,
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    from fdcad.ui import strings_a11y as names

    new_part(qtbot, window)
    qtbot.wait(50)
    missing = []
    for button in window.findChildren(QAbstractButton):
        if not button.isVisibleTo(window):
            continue
        has_text = bool(button.text()) and not (
            isinstance(button, QToolButton)
            and button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        if not has_text and not button.accessibleName():
            missing.append(f"{type(button).__name__} {button.objectName()} {button.toolTip()!r}")
    assert missing == []
    assert window.tree is not None and window.tree.accessibleName() == names.NAME_TREE
    assert window.panel is not None and window.panel.accessibleName() == names.NAME_PROPERTY_PANEL
    assert window.current is not None
    assert window.current.viewport.accessibleName() == names.NAME_VIEW
    assert window.command_search.accessibleName() == names.NAME_SEARCH


# U4.4: not by colour alone -----------------------------------------------------------------


def test_warning_and_error_marks_differ_in_shape(qapp: QApplication) -> None:
    same = "#808080"
    warning = row_icon("tree.sketch", same, mark="warning").pixmap(QSize(18, 18)).toImage()
    error = row_icon("tree.sketch", same, mark="error").pixmap(QSize(18, 18)).toImage()
    differ = sum(
        1
        for x in range(9, 18)
        for y in range(9, 18)
        if warning.pixelColor(x, y).alpha() != error.pixelColor(x, y).alpha()
        or warning.pixelColor(x, y) != error.pixelColor(x, y)
    )
    assert differ > 4


def test_errors_list_rows_have_an_icon(qapp: QApplication, qtbot: QtBot) -> None:
    from types import SimpleNamespace

    from fdcad.ui.errors import panel as errors

    shown = errors.ErrorsPanel()
    qtbot.addWidget(shown)
    issue = SimpleNamespace(state=FeatureState.ERROR, message="Fillet 1 failed.")
    entry = SimpleNamespace(feature="Fillet 1", issue=issue)
    original = errors.entries
    errors.entries = lambda _s: [entry]  # type: ignore[assignment]
    try:
        shown.session = object()  # type: ignore[assignment]
        shown.refresh()
    finally:
        errors.entries = original
        shown.session = None
    assert not shown.table.item(0, 0).icon().isNull()


# U4.5 and U7: motion -----------------------------------------------------------------------


def test_reduce_motion_preference(styled: QApplication, qtbot: QtBot, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    assert not settings.reduce_motion  # animations on by default
    dialog = PreferencesDialog(settings)
    qtbot.addWidget(dialog)
    dialog.reduce_motion_box.setChecked(True)
    dialog.accept()
    assert settings.reduce_motion and not settings.animations  # one stored switch
    motion.set_reduce_motion(True)
    assert motion.duration(motion.PANEL_MS) == 0
    assert motion.duration(motion.CAMERA_MS) == 0
    assert not QApplication.isEffectEnabled(Qt.UIEffect.UI_AnimateMenu)
    assert not QApplication.isEffectEnabled(Qt.UIEffect.UI_FadeTooltip)
    motion.set_reduce_motion(False)
    assert motion.duration(motion.PANEL_MS) == motion.PANEL_MS


def test_motion_lengths_and_easing() -> None:
    from PySide6.QtCore import QEasingCurve

    from fdcad.ui.viewport.views import TURN_MS

    assert 120 <= motion.PANEL_MS <= 200 and 120 <= motion.MENU_MS <= 200
    assert motion.CAMERA_MS == TURN_MS == 250
    curve = QEasingCurve(motion.EASING)
    values = [curve.valueForProgress(i / 50) for i in range(51)]
    assert max(values) <= 1.0 and min(values) >= 0.0  # no bounce or overshoot
    assert values == sorted(values)


def test_nothing_animates_during_a_slow_rebuild(qapp: QApplication, qtbot: QtBot) -> None:
    from PySide6.QtCore import QObject

    class Session(QObject):
        running = True

        @property
        def is_rebuilding(self) -> bool:
            return self.running

    session = Session()
    motion.rebuild_started(session)
    assert motion.duration(250) == 250  # a short rebuild doesn't stop anything
    qtbot.wait(motion.SLOW_MS + 100)
    assert motion.duration(250) == 0
    session.running = False
    assert motion.duration(250) == 250  # clears itself when the rebuild ends


def test_sketch_turn_is_instant_with_reduce_motion(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    from tests.ui.test_spec_gaps import _FakeTurn
    from tests.ui.test_workflow import plane_id

    tab = new_part(qtbot, window)
    turn = _FakeTurn()
    tab.viewport.animate_normal_to = turn  # type: ignore[attr-defined]
    motion.set_reduce_motion(True)
    try:
        assert window.sketch_mode is not None
        window.sketch_mode.start(plane_id=plane_id(tab, "Top Plane"))
        [(_normal, ms)] = turn.calls
        assert ms == 0
        assert turn.done is not None
        turn.done()
    finally:
        motion.set_reduce_motion(False)
