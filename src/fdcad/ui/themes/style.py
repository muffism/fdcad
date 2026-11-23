"""The application style sheet, built from the theme colours (D111).

Every size is a multiple of ``unit(font)``: a quarter of the UI font's line
height, which is 4 logical pixels at the default font. Qt scales logical
pixels with the Windows display setting, and a bigger UI font scales the unit,
so the layout keeps its proportions from 100 to 200 percent. Corners use two
radii only: ``r1`` for controls and ``r2`` for panels, plates and popups.
"""

from __future__ import annotations

from PySide6.QtCore import QTemporaryDir
from PySide6.QtGui import QFont, QFontMetrics

from fdcad.ui.themes.states import radii, state_rules
from fdcad.ui.themes.theme import Chrome, Palette

#: Small SVG images the style sheet needs (arrows and tick marks). Qt style
#: sheets only take image files, so they are written once per colour into a
#: temporary folder that Qt removes when the app quits.
_IMAGES = {
    "check": '<path d="M5 12.5 L10 17 L19 7.5" fill="none" stroke="{color}" '
    'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>',
    "chevron": '<path d="M6.5 9.5 L12 15 L17.5 9.5" fill="none" stroke="{color}" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    # Tree expand arrows: small, so they sit quietly beside the row icons.
    "branch_closed": '<path d="M10 8 L14 12 L10 16" fill="none" stroke="{color}" '
    'stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"/>',
    "branch_open": '<path d="M8 10 L12 14 L16 10" fill="none" stroke="{color}" '
    'stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"/>',
    # Spin box arrows, the radio button dot and the part ticked check box (U3.1).
    "chevron_up": '<path d="M6.5 14.5 L12 9 L17.5 14.5" fill="none" stroke="{color}" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    "dot": '<circle cx="12" cy="12" r="4.5" fill="{color}"/>',
    "dash": '<path d="M7 12 L17 12" fill="none" stroke="{color}" '
    'stroke-width="2.5" stroke-linecap="round"/>',
}
_folder: QTemporaryDir | None = None


def unit(font: QFont) -> int:
    """The spacing step in logical pixels (4 at the default UI font)."""
    return max(4, round(QFontMetrics(font).height() / 4))


def rgba(color: str, alpha: float) -> str:
    """``#RRGGBB`` with an alpha, as a style sheet ``rgba()`` value."""
    r, g, b = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r}, {g}, {b}, {alpha:.2f})"


def image(name: str, color: str) -> str:
    """Path of a style sheet image in ``color``, with forward slashes, for ``url()``."""
    global _folder
    if _folder is None:
        _folder = QTemporaryDir()
    path = f"{_folder.path()}/{name}_{color.lstrip('#')}.svg"
    try:
        with open(path, "x", encoding="utf-8") as file:
            body = _IMAGES[name].format(color=color)
            file.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">{body}</svg>')
    except FileExistsError:
        pass
    return path


def stylesheet(c: Chrome, p: Palette, font: QFont) -> str:
    """The whole style sheet for one theme."""
    u = unit(font)
    r1, r2 = radii(u)
    chevron, chevron_off = image("chevron", c.text), image("chevron", c.muted)
    tick = image("check", c.on_accent)
    closed, opened = image("branch_closed", c.muted), image("branch_open", c.muted)
    images = {
        "tick": tick,
        "dot": image("dot", c.on_accent),
        "dash": image("dash", c.on_accent),
        "up": image("chevron_up", c.text),
        "down": chevron,
        "up_off": image("chevron_up", c.muted),
        "down_off": chevron_off,
    }
    return _base(c, p, u, r1, r2, chevron, chevron_off, tick, closed, opened) + state_rules(
        c, p, u, images
    )


def _base(
    c: Chrome,
    p: Palette,
    u: int,
    r1: int,
    r2: int,
    chevron: str,
    chevron_off: str,
    tick: str,
    closed: str,
    opened: str,
) -> str:
    """The base rules: colours and layout of every widget type."""
    return f"""
QMainWindow, QDialog {{ background: {c.window}; }}
QMainWindow::separator {{ background: {c.window}; width: {u}px; height: {u}px; }}
QMainWindow::separator:hover {{ background: {c.accent}; }}
QSplitter::handle {{ background: {c.border}; }}
QSplitter::handle:hover {{ background: {c.accent}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

QToolTip {{
    background: {c.raised}; color: {c.text}; border: 1px solid {c.border_strong};
    border-radius: {r1}px; padding: {u}px {2 * u}px;
}}

QMenuBar {{ background: {c.window}; color: {c.text}; padding: {u // 2}px {u}px; }}
QMenuBar::item {{ background: transparent; padding: {u}px {2 * u}px; border-radius: {r1}px; }}
QMenuBar::item:selected {{ background: {c.hover}; }}
QMenuBar::item:pressed {{ background: {c.pressed}; }}
QMenu {{
    background: {c.raised}; color: {c.text}; border: 1px solid {c.border_strong};
    border-radius: {r2}px; padding: {u}px;
}}
QMenu::separator {{ height: 1px; background: {c.border}; margin: {u}px {2 * u}px; }}

QToolBar {{ background: {c.window}; border: none; spacing: {u}px; padding: 0; }}
QToolBar#command_tabs {{ background: {c.window}; border: none; }}

QTabWidget::pane {{ border: none; }}
QTabBar {{ qproperty-drawBase: 0; }}
QTabBar::tab {{
    background: transparent; color: {c.muted}; border: none;
    border-bottom: 2px solid transparent; padding: {u + u // 2}px {3 * u}px;
    margin: 0 {u // 2}px;
}}
QTabBar::tab:hover {{ color: {c.text}; background: {c.hover}; }}
QTabBar::tab:selected {{ color: {c.text}; border-bottom-color: {c.accent}; }}
QTabBar::scroller {{ width: {12 * u}px; }}

QTabWidget#command_tab_widget > QTabBar {{ background: {c.window}; }}
QTabWidget#command_tab_widget > QTabBar::tab {{
    border: 1px solid transparent; border-radius: {r1}px;
    margin: {u}px {u // 2}px {u + u // 2}px {u // 2}px; padding: {u}px {3 * u + u // 2}px;
}}
QTabWidget#command_tab_widget > QTabBar::tab:first {{ margin-left: {2 * u}px; }}
QTabWidget#command_tab_widget > QTabBar::tab:selected {{
    background: {c.raised}; color: {c.text}; border-color: {c.border};
}}
QLineEdit#command_search {{ margin: 0 {u + u // 2}px {u + u // 2}px 0; }}
QToolButton#command_tabs_button {{ margin: 0 0 {u + u // 2}px {u // 2}px; }}
QWidget[ribbon="true"] {{ background: {c.window}; }}
QScrollArea#ribbon_scroll {{
    background: {c.raised}; border: 1px solid {c.border}; border-radius: {r2}px;
}}
QWidget#ribbon_content {{ background: transparent; }}
QScrollArea#ribbon_scroll QScrollBar:horizontal {{ height: {u}px; }}
QScrollArea#ribbon_scroll QScrollBar::handle:horizontal {{
    margin: 0 {u // 2}px; border-radius: {u // 2}px;
}}
QLabel#ribbon_caption {{ color: {c.muted}; }}
QFrame#ribbon_separator {{ background: {c.border}; border: none; }}
QToolButton#ribbon_large, QToolButton#ribbon_compact {{
    background: transparent; color: {c.text}; border: 1px solid transparent;
    border-radius: {r1}px; padding: {u // 2}px {u}px;
}}
QToolButton#ribbon_large {{ padding: {u}px {u}px {u // 2}px {u}px; }}
QToolButton#ribbon_large:hover, QToolButton#ribbon_compact:hover {{
    background: {c.hover};
}}
QToolButton#ribbon_large:pressed, QToolButton#ribbon_compact:pressed,
QToolButton#ribbon_large:checked, QToolButton#ribbon_compact:checked {{
    background: {c.pressed};
}}
QToolButton#ribbon_large:disabled, QToolButton#ribbon_compact:disabled {{ color: {c.muted}; }}
QToolButton#ribbon_compact[popupMode="1"] {{ padding-right: {4 * u}px; }}
QToolButton#ribbon_large[popupMode="1"] {{ padding-bottom: {3 * u}px; }}
QToolButton::menu-button {{
    border: none; border-left: 1px solid transparent; width: {3 * u}px;
    border-top-right-radius: {r1}px; border-bottom-right-radius: {r1}px;
}}
QToolButton::menu-button:hover {{ background: {c.pressed}; }}
QToolButton#ribbon_large::menu-button {{
    border: none; width: auto; height: {3 * u}px; border-radius: {r1}px;
}}

QTabWidget#left_tabs > QStackedWidget {{ background: {c.surface}; }}
QLabel#empty_state {{ color: {c.muted}; padding: {6 * u}px {3 * u}px; }}
QLabel#empty_state[compact="true"] {{ padding: {u}px {2 * u}px {2 * u}px {2 * u}px; }}
QTabWidget#left_tabs > QTabBar {{ background: {c.surface}; }}
QTabWidget#left_tabs > QTabBar::tab {{
    border: 1px solid transparent; border-radius: {r1}px;
    margin: {u}px 0 {u}px {u}px; padding: {u // 2 + 1}px {u + u // 2}px; min-height: {5 * u}px;
}}
QTabWidget#left_tabs > QTabBar::tab:selected {{
    background: {c.selected}; border-color: transparent;
}}
QTabWidget#left_tabs::pane {{ border-top: 1px solid {c.border}; background: {c.surface}; }}

QTreeView, QListView {{
    background: {c.surface}; alternate-background-color: {c.surface};
    border: none; outline: 0; color: {c.text};
}}
QTreeView {{ padding-left: {u}px; }}
QTreeView::item, QListView::item {{
    min-height: {6 * u}px; padding: 0 {u}px; border-radius: {r1}px;
}}
QTreeView::item {{ padding-left: {u + u // 2}px; }}
QTreeView::branch {{ background: transparent; border-image: none; }}
QTreeView::branch:has-children:closed {{ image: url({closed}); }}
QTreeView::branch:has-children:open {{ image: url({opened}); }}
QTreeView::item:hover, QListView::item:hover {{ background: {c.hover}; }}
QTreeView::item:selected, QListView::item:selected {{
    background: {c.selected}; color: {c.text};
}}

QTableView {{
    background: {c.field}; alternate-background-color: {c.surface}; color: {c.text};
    gridline-color: {c.border}; border: 1px solid {c.border}; border-radius: {r1}px;
    selection-background-color: {c.selected}; selection-color: {c.text};
}}
QHeaderView {{ background: transparent; border: none; }}
QHeaderView::section {{
    background: {c.surface}; color: {c.muted}; border: none;
    border-bottom: 1px solid {c.border}; border-right: 1px solid {c.border};
    padding: {u}px {2 * u}px;
}}
QHeaderView::section:last {{ border-right: none; }}
QTableCornerButton::section {{
    background: {c.surface}; border: none; border-bottom: 1px solid {c.border};
}}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: {2 * u + 2}px; margin: 0; }}
QScrollBar:horizontal {{ background: transparent; height: {2 * u + 2}px; margin: 0; }}
QScrollBar::handle {{ background: {c.border_strong}; border-radius: {u - 1}px; margin: 2px; }}
QScrollBar::handle:vertical {{ min-height: {6 * u}px; }}
QScrollBar::handle:horizontal {{ min-width: {6 * u}px; }}
QScrollBar::handle:hover {{ background: {c.muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; border: none; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QLineEdit, QComboBox, QPlainTextEdit, QTextEdit, QAbstractSpinBox {{
    background: {c.field}; color: {c.text}; border: 1px solid {c.input_border};
    border-radius: {r1}px; padding: {u // 2}px {u + u // 2}px;
    selection-background-color: {c.accent}; selection-color: {c.on_accent};
}}
QLineEdit:hover, QComboBox:hover, QAbstractSpinBox:hover {{ border-color: {c.muted}; }}
QLineEdit:focus, QComboBox:focus, QComboBox:on, QAbstractSpinBox:focus {{
    border-color: {c.accent};
}}
QLineEdit:disabled, QComboBox:disabled, QAbstractSpinBox:disabled {{
    color: {c.muted}; background: {c.surface}; border-color: {c.border_strong};
}}
QSlider::groove:horizontal {{
    background: {c.field}; border: 1px solid {c.input_border}; height: {u}px;
    border-radius: {u // 2}px;
}}
QSlider::groove:vertical {{
    background: {c.field}; border: 1px solid {c.input_border}; width: {u}px;
    border-radius: {u // 2}px;
}}
QSlider::handle {{
    background: {c.accent}; border: none; width: {3 * u}px; height: {3 * u}px;
    margin: -{u}px; border-radius: {3 * u // 2}px;
}}
QLineEdit[invalid="true"], QLineEdit[error="true"] {{ border-color: {c.danger}; }}
QComboBox::drop-down {{
    subcontrol-origin: padding; subcontrol-position: center right; width: {4 * u}px;
    border: none;
}}
QComboBox::down-arrow {{ image: url({chevron}); width: {3 * u}px; height: {3 * u}px; }}
QComboBox::down-arrow:disabled {{ image: url({chevron_off}); }}
QComboBox QAbstractItemView {{
    background: {c.raised}; border: 1px solid {c.border_strong}; border-radius: {r1}px;
    padding: {u // 2}px; selection-background-color: {c.hover}; selection-color: {c.text};
}}

QPushButton {{
    background: {c.raised}; color: {c.text}; border: 1px solid {c.border_strong};
    border-radius: {r1}px; padding: {u}px {3 * u}px; min-height: {4 * u}px;
}}
QPushButton:hover {{ background: {c.hover}; }}
QPushButton:pressed, QPushButton:checked {{ background: {c.pressed}; }}
QPushButton:default {{ border-color: {c.accent}; }}
QPushButton:disabled {{ color: {c.muted}; background: {c.surface}; border-color: {c.border}; }}
QPushButton:flat {{ background: transparent; border-color: transparent; }}
QPushButton:flat:hover {{ background: {c.hover}; }}
QCheckBox, QRadioButton {{ spacing: {2 * u}px; background: transparent; }}
QCheckBox::indicator {{
    width: {3 * u + 2}px; height: {3 * u + 2}px; background: {c.field};
    border: 1px solid {c.input_border}; border-radius: {r1 - 1}px;
}}
QCheckBox::indicator:hover {{ border-color: {c.accent}; }}
QCheckBox::indicator:checked {{
    background: {c.accent}; border-color: {c.accent}; image: url({tick});
}}
QCheckBox::indicator:disabled {{ background: {c.surface}; border-color: {c.border}; }}
QCheckBox::indicator:checked:disabled {{ background: {c.border_strong}; }}
QGroupBox {{
    background: {c.raised}; border: 1px solid {c.border}; border-radius: {r2}px;
    margin-top: 0; padding: {5 * u}px 0 0 0; font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: padding; subcontrol-position: top left; left: {3 * u}px;
    top: {2 * u}px; padding: 0; color: {c.text};
}}
QToolButton {{ border-radius: {r1}px; }}
QToolButton:hover {{ background: {c.hover}; }}

QWidget#start_page {{ background: {c.surface}; }}
QLabel#start_what {{ color: {c.muted}; }}
QListWidget#start_recent {{
    background: {c.raised}; border: 1px solid {c.border}; border-radius: {r2}px;
    padding: {2 * u}px;
}}
QLabel#start_empty, QLabel#empty_box {{
    color: {c.muted}; border: 1px dashed {c.border_strong}; border-radius: {r2}px;
    padding: {6 * u}px;
}}
QLabel#empty_box {{ padding: {6 * u}px {3 * u}px; }}
QPushButton#start_new_part, QPushButton#start_open {{
    min-height: {7 * u - 2 - u}px; min-width: {20 * u}px;
}}
QListWidget#start_recent::item {{
    border-radius: {r2}px; padding: {u}px; margin: {u // 2}px;
}}

QWidget#property_panel {{ background: {c.surface}; }}
QWidget#panel_header {{ background: {c.surface}; border-bottom: 1px solid {c.border}; }}
QLabel#panel_title {{ color: {c.text}; }}
QLabel#panel_message {{ color: {c.muted}; padding: 0 {3 * u}px; }}
QLabel#panel_hint {{
    background: {c.selected}; color: {c.text}; border-radius: {r1}px;
    padding: {2 * u}px {3 * u}px; margin: 0 {3 * u}px;
}}
QFrame#panel_group {{
    background: {c.raised}; border: 1px solid {c.border}; border-radius: {r2}px;
}}
QFrame#panel_group QLabel, QFrame#panel_group QCheckBox {{ background: transparent; }}
QFrame#panel_group QListView, QGroupBox QListView, QDialog QListView {{
    background: {c.field}; border: 1px solid {c.input_border}; border-radius: {r1}px;
    padding: {u // 2}px;
}}
QFrame#panel_group QComboBox QAbstractItemView, QGroupBox QComboBox QAbstractItemView,
QDialog QComboBox QAbstractItemView {{
    background: {c.raised}; border: 1px solid {c.border_strong}; border-radius: {r2}px;
    padding: {u // 2}px; selection-background-color: {c.hover}; selection-color: {c.text};
}}
QLabel#group_title {{ color: {c.text}; }}
QLabel#field_info {{ color: {c.muted}; }}
QPushButton#panel_ok {{
    background: {c.accent}; color: {c.on_accent}; border-color: {c.accent};
}}
QPushButton#panel_ok:hover {{ background: {rgba(c.accent, 0.85)}; }}
QPushButton#panel_ok:disabled {{
    background: {c.surface}; color: {c.muted}; border-color: {c.border};
}}

QStatusBar {{ background: {c.window}; color: {c.muted}; border-top: 1px solid {c.border}; }}
QStatusBar::item {{ border: none; }}
QStatusBar QLabel {{ color: {c.muted}; padding: 0 {u}px; }}
QStatusBar QLabel#cursor_coordinates {{ color: {c.text}; }}
QToolButton#unit_selector {{
    color: {c.text}; border: 1px solid {c.input_border}; border-radius: {r1}px;
    padding: 0 {4 * u}px 0 {2 * u}px; margin: {u // 2}px {u}px;
}}
QToolButton#unit_selector:hover {{ background: {c.hover}; }}
QToolButton#unit_selector::menu-indicator {{
    image: url({chevron}); width: {2 * u + 2}px; height: {2 * u + 2}px;
    subcontrol-origin: padding; subcontrol-position: center right; right: {u}px;
}}
QProgressBar {{
    background: {c.field}; border: 1px solid {c.border}; border-radius: {r1}px;
    text-align: center; color: {c.text}; max-height: {3 * u}px;
}}
QProgressBar::chunk {{ background: {c.accent}; border-radius: {r1 - 1}px; }}
QStatusBar QProgressBar {{ max-height: {2 * u}px; border-radius: {u}px; }}
QStatusBar QProgressBar::chunk {{ border-radius: {u - 1}px; }}

QTabWidget#document_tabs > QTabBar {{ background: {c.window}; }}
QTabWidget#document_tabs > QTabBar::tab {{
    background: transparent; color: {c.muted}; border: none;
    border-top: 2px solid transparent; border-bottom: 2px solid transparent;
    margin: {u}px 0 0 {u}px; padding: {u}px {u}px {u}px {3 * u}px; min-height: {5 * u}px;
    border-top-left-radius: {r2}px; border-top-right-radius: {r2}px;
}}
QTabWidget#document_tabs > QTabBar::tab:hover {{ background: {c.hover}; color: {c.text}; }}
QTabWidget#document_tabs > QTabBar::tab:selected {{
    background: {p.viewport_top}; color: {c.text}; border-top-color: {c.accent};
}}
QToolButton#tab_close {{ border: none; border-radius: {r1}px; padding: 0; margin: 0; }}
QToolButton#tab_close:hover {{ background: {rgba(c.text, 0.12)}; }}

QFrame#context_bar QToolButton {{ background: transparent; padding: {u // 2}px; }}
QFrame#context_bar QToolButton:hover {{ background: {c.hover}; }}

QFrame#value_box {{
    background: {c.raised}; border: 1px solid {c.accent}; border-radius: {r2}px;
}}
QFrame#value_box QToolButton {{
    background: transparent; color: {c.text}; border-radius: {r1}px;
    min-width: {5 * u}px; min-height: {5 * u}px; font-weight: 600;
}}
QFrame#value_box QToolButton:hover {{ background: {c.hover}; }}
QFrame#value_box QToolButton#value_ok {{ color: {p.state_ok}; }}
QFrame#value_box QToolButton#value_cancel {{ color: {c.danger}; }}
QFrame#value_box QToolButton#value_rebuild {{ color: {c.accent}; }}
"""
