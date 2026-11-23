"""Control states, sizes and the keyboard focus ring (UI polish spec U3, U4.1, D660 to D663).

These rules come after the base style sheet in ``themes.style`` so they win
where both set the same property. Every interactive control gets distinct
normal, hover, pressed, focused, disabled and (where it applies) checked looks:

* hover changes the fill a little, pressed changes it more, checked uses the accent
* disabled lowers contrast but keeps the muted text colour (3:1 or more)
* keyboard focus draws a 2 px accent ring inside the control's corner radius;
  the ``keyfocus`` property (set by ``app_style.FocusRing``) limits it to focus
  that came from the keyboard. Text fields show it on any focus, since that is
  where typing goes. Padding drops by 1 px with the ring so nothing moves.

Sizes (U3.2, U3.3): 4 px corners on buttons and fields, 6 px on panels, menus
and popups; buttons, fields and rows 24 px tall or more, main buttons 28 px,
icon buttons at least 24 by 24 px.

``QToolButton#ribbon_*`` rules belong to the command tabs (RIBBON_SPEC) and
are not changed here. Their ID selectors outrank every rule below.
"""

from __future__ import annotations

from fdcad.ui.themes.theme import Chrome, Palette
from fdcad.ui.themes.typography import CAPTION_PX


def mix(a: str, b: str, t: float) -> str:
    """``#RRGGBB`` that is ``t`` of the way from colour ``a`` to colour ``b``."""
    ca = [int(a[i : i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(ca, cb, strict=True))


def radii(u: int) -> tuple[int, int]:
    """The two corner radii of the Datum look (D1034): 6 px for controls and 10 px for
    panels, plates and popups, at the default 4 px spacing step."""
    return round(u * 1.5), round(u * 2.5)


def input_border(c: Chrome) -> str:
    """Outline of text fields, boxes and grooves: ``input_border`` when the theme has it."""
    return str(getattr(c, "input_border", c.border_strong))


#: Control types that show the keyboard focus ring, for the U11.1 check.
FOCUS_RING_TYPES = (
    "QPushButton",
    "QToolButton",
    "QCheckBox",
    "QRadioButton",
    "QSlider",
    "QTabBar",
    "QTreeView",
    "QListView",
    "QTableView",
    "QLineEdit",
    "QComboBox",
    "QAbstractSpinBox",
    "QGraphicsView",
)


def state_rules(c: Chrome, p: Palette, u: int, images: dict[str, str]) -> str:
    """The U3 and U4 rules for one theme. ``u`` is the 4 px spacing step."""
    del p  # the view colours are not needed here
    r1, r2 = radii(u)
    h, main = 6 * u, 7 * u  # 24 and 28 px at the default font
    edge = input_border(c)
    accent_hover = mix(c.accent, c.text, 0.12)
    accent_pressed = mix(c.accent, c.text, 0.24)
    ring = f"border: 2px solid {c.accent}"
    pad_y, pad_x = u // 2, u + u // 2
    return f"""
QToolTip {{ border-radius: {r2}px; }}

QMenu {{ padding: {u}px; border-radius: {r2}px; }}
QMenu::separator {{ height: 1px; background: {c.border}; margin: {u}px {2 * u}px; }}
QComboBox QAbstractItemView {{ border-radius: {r2}px; outline: 0; }}
QComboBox QAbstractItemView::item {{ min-height: {h}px; padding: 0 {2 * u}px; }}

QScrollBar:vertical {{ width: {3 * u}px; }}
QScrollBar:horizontal {{ height: {3 * u}px; }}
QScrollBar::handle {{ background: {c.border_strong}; border-radius: {u // 2}px; }}
QScrollBar::handle:vertical {{ margin: 2px {u}px 2px {u}px; }}
QScrollBar::handle:horizontal {{ margin: {u}px 2px {u}px 2px; }}
QScrollBar[hovered="true"]::handle {{ background: {c.muted}; border-radius: {u - 1}px; }}
QScrollBar[hovered="true"]::handle:vertical {{ margin: 2px 2px 2px 2px; }}
QScrollBar[hovered="true"]::handle:horizontal {{ margin: 2px 2px 2px 2px; }}
QScrollBar::handle:pressed {{ background: {c.text}; }}

QLineEdit, QComboBox, QAbstractSpinBox, QPlainTextEdit, QTextEdit {{
    border: 1px solid {edge}; border-radius: {r1}px;
}}
QLineEdit, QComboBox, QAbstractSpinBox {{
    min-height: {h - 2 - 2 * pad_y}px; padding: {pad_y}px {pad_x}px;
}}
QAbstractSpinBox {{ padding-right: {5 * u}px; }}
QAbstractSpinBox {{
    background: {c.field}; color: {c.text};
    selection-background-color: {c.accent}; selection-color: {c.on_accent};
    padding-top: 1px; padding-bottom: 1px;
}}
QLineEdit:hover, QComboBox:hover, QAbstractSpinBox:hover,
QPlainTextEdit:hover, QTextEdit:hover {{ border-color: {c.muted}; }}
QLineEdit:focus, QAbstractSpinBox:focus, QPlainTextEdit:focus, QTextEdit:focus,
QComboBox:editable:focus, QComboBox[keyfocus="true"] {{
    {ring}; padding: {pad_y - 1}px {pad_x - 1}px;
}}
QPlainTextEdit:focus, QTextEdit:focus {{ padding: 0; }}
QComboBox:editable:focus, QComboBox[keyfocus="true"],
QAbstractSpinBox:focus {{ padding-right: {5 * u - 1}px; }}
QAbstractSpinBox:focus {{ padding-top: 0; padding-bottom: 0; }}
QComboBox:on {{ border-color: {c.accent}; }}
QLineEdit:disabled, QComboBox:disabled, QAbstractSpinBox:disabled,
QPlainTextEdit:disabled, QTextEdit:disabled {{
    color: {c.muted}; background: {c.surface}; border-color: {c.border};
}}
QLineEdit:read-only {{ background: {c.surface}; }}
QLineEdit[invalid="true"], QLineEdit[error="true"] {{ border-color: {c.danger}; }}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
    subcontrol-origin: border; width: {4 * u}px; border: none; background: transparent;
}}
QAbstractSpinBox::up-button {{ subcontrol-position: top right; margin: 1px 1px 0 0; }}
QAbstractSpinBox::down-button {{ subcontrol-position: bottom right; margin: 0 1px 1px 0; }}
QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {{
    background: {c.hover}; border-radius: {r1 - 1}px;
}}
QAbstractSpinBox::up-button:pressed, QAbstractSpinBox::down-button:pressed {{
    background: {c.pressed};
}}
QAbstractSpinBox::up-arrow {{
    image: url({images["up"]}); width: {2 * u + 2}px; height: {2 * u + 2}px;
}}
QAbstractSpinBox::down-arrow {{
    image: url({images["down"]}); width: {2 * u + 2}px; height: {2 * u + 2}px;
}}
QAbstractSpinBox::up-arrow:disabled, QAbstractSpinBox::up-arrow:off {{
    image: url({images["up_off"]});
}}
QAbstractSpinBox::down-arrow:disabled, QAbstractSpinBox::down-arrow:off {{
    image: url({images["down_off"]});
}}

QPushButton {{
    border: 1px solid {edge}; border-radius: {r1}px;
    padding: {u // 2}px {3 * u}px; min-height: {h - 2 - u}px;
}}
QDialogButtonBox QPushButton, QWidget#panel_header QPushButton, QPushButton:default {{
    min-height: {main - 2 - u}px; min-width: {16 * u}px;
}}
QWidget#panel_header QPushButton#panel_pin, QPushButton#message_close {{
    min-width: {h - 2 - u}px; min-height: {h - 2 - u}px; padding: {u // 2}px;
}}
QToolButton#panel_help {{ border: 1px solid {edge}; }}
QPushButton:hover {{ background: {c.hover}; }}
QPushButton:pressed {{ background: {c.pressed}; }}
QPushButton:checked {{ background: {c.selected}; border-color: {c.accent}; }}
QPushButton:default, QPushButton#panel_ok,
QPushButton[main="true"] {{
    background: {c.accent}; color: {c.on_accent}; border-color: {c.accent};
}}
QPushButton:default:hover, QPushButton#panel_ok:hover,
QPushButton[main="true"]:hover {{
    background: {accent_hover}; border-color: {accent_hover};
}}
QPushButton:default:pressed, QPushButton#panel_ok:pressed,
QPushButton[main="true"]:pressed {{
    background: {accent_pressed}; border-color: {accent_pressed};
}}
QPushButton:disabled, QPushButton:default:disabled, QPushButton#panel_ok:disabled,
QPushButton[main="true"]:disabled {{
    color: {c.muted}; background: {c.surface}; border-color: {c.border};
}}
QPushButton:flat {{ background: transparent; border-color: transparent; }}
QPushButton:flat:hover {{ background: {c.hover}; }}
QPushButton:flat:pressed {{ background: {c.pressed}; }}
QPushButton[keyfocus="true"] {{ {ring}; padding: {u // 2 - 1}px {3 * u - 1}px; }}
QPushButton:default[keyfocus="true"], QPushButton#panel_ok[keyfocus="true"],
QPushButton[main="true"][keyfocus="true"] {{
    border-color: {c.text};
}}
QWidget#panel_header QPushButton#panel_pin[keyfocus="true"],
QPushButton#message_close[keyfocus="true"] {{ padding: {u // 2 - 1}px; }}

QToolButton {{ border: 1px solid transparent; border-radius: {r1}px; padding: 2px; }}
QToolButton:hover {{ background: {c.hover}; }}
QToolButton:pressed {{ background: {c.pressed}; }}
QToolButton:checked {{ background: {c.selected}; border-color: {c.accent}; }}
QToolButton:checked:hover {{ background: {c.pressed}; }}
QToolButton:disabled {{ color: {c.muted}; }}
QToolButton[keyfocus="true"] {{ {ring}; padding: 1px; }}

QCheckBox, QRadioButton {{ spacing: {2 * u}px; min-height: {h}px; }}
QCheckBox:disabled, QRadioButton:disabled {{ color: {c.muted}; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: {3 * u + 2}px; height: {3 * u + 2}px; background: {c.field};
    border: 1px solid {edge};
}}
QCheckBox::indicator {{ border-radius: {u}px; }}
QRadioButton::indicator {{ border-radius: {(3 * u + 4) // 2}px; }}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    background: {c.hover}; border-color: {c.accent};
}}
QCheckBox::indicator:pressed, QRadioButton::indicator:pressed {{ background: {c.pressed}; }}
QCheckBox::indicator:checked {{
    background: {c.accent}; border-color: {c.accent}; image: url({images["tick"]});
}}
QCheckBox::indicator:indeterminate {{
    background: {c.accent}; border-color: {c.accent}; image: url({images["dash"]});
}}
QRadioButton::indicator:checked {{
    background: {c.accent}; border-color: {c.accent}; image: url({images["dot"]});
}}
QCheckBox::indicator:checked:hover, QRadioButton::indicator:checked:hover,
QCheckBox::indicator:indeterminate:hover {{
    background: {accent_hover}; border-color: {accent_hover};
}}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
    background: {c.surface}; border-color: {c.border};
}}
QCheckBox::indicator:checked:disabled, QRadioButton::indicator:checked:disabled,
QCheckBox::indicator:indeterminate:disabled {{
    background: {c.border_strong}; border-color: {c.border_strong};
}}
QCheckBox[keyfocus="true"]::indicator, QRadioButton[keyfocus="true"]::indicator {{
    {ring}; width: {3 * u}px; height: {3 * u}px;
}}
QCheckBox[keyfocus="true"]::indicator:checked, QRadioButton[keyfocus="true"]::indicator:checked,
QCheckBox[keyfocus="true"]::indicator:indeterminate {{ border-color: {c.text}; }}

QListView::indicator, QTreeView::indicator, QTableView::indicator {{
    width: {3 * u + 2}px; height: {3 * u + 2}px; background: {c.field};
    border: 1px solid {edge}; border-radius: {u}px;
}}
QListView::indicator:checked, QTreeView::indicator:checked, QTableView::indicator:checked {{
    background: {c.accent}; border-color: {c.accent}; image: url({images["tick"]});
}}
QListView::indicator:indeterminate, QTreeView::indicator:indeterminate,
QTableView::indicator:indeterminate {{
    background: {c.accent}; border-color: {c.accent}; image: url({images["dash"]});
}}
QListView::indicator:disabled, QTreeView::indicator:disabled, QTableView::indicator:disabled {{
    background: {c.surface}; border-color: {c.border};
}}
QListView::indicator:checked:disabled, QTreeView::indicator:checked:disabled,
QTableView::indicator:checked:disabled {{
    background: {c.border_strong}; border-color: {c.border_strong};
}}

QSlider {{ min-height: {h}px; }}
QSlider::groove:horizontal {{
    height: {u}px; background: {edge}; border-radius: {u // 2}px;
}}
QSlider::groove:vertical {{ width: {u}px; background: {edge}; border-radius: {u // 2}px; }}
QSlider::sub-page:horizontal, QSlider::add-page:vertical {{
    background: {c.accent}; border-radius: {u // 2}px;
}}
QSlider::handle:horizontal, QSlider::handle:vertical {{
    background: {c.raised}; border: 1px solid {edge};
    width: {4 * u - 2}px; height: {4 * u - 2}px; border-radius: {2 * u}px;
}}
QSlider::handle:horizontal {{ margin: -{(3 * u) // 2}px 0; }}
QSlider::handle:vertical {{ margin: 0 -{(3 * u) // 2}px; }}
QSlider::handle:hover {{ background: {c.hover}; border-color: {c.accent}; }}
QSlider::handle:pressed {{ background: {c.pressed}; border-color: {c.accent}; }}
QSlider::sub-page:horizontal:disabled, QSlider::add-page:vertical:disabled {{
    background: {c.border_strong};
}}
QSlider::handle:disabled {{ background: {c.surface}; border-color: {c.border}; }}
QSlider[keyfocus="true"]::handle {{
    {ring}; width: {4 * u - 4}px; height: {4 * u - 4}px;
}}

QTabBar::tab:pressed {{ background: {c.pressed}; }}
QTabWidget#left_tabs > QTabBar::tab, QTabWidget#document_tabs > QTabBar::tab {{
    min-height: {h}px;
}}
QTabBar::tab:disabled {{ color: {c.muted}; }}
QTabBar[keyfocus="true"]::tab:selected {{
    border: 2px solid {c.accent}; border-radius: {r1}px;
}}

QTreeView::item, QListView::item {{ min-height: {h}px; }}
QTreeView::item:selected:hover, QListView::item:selected:hover {{ background: {c.pressed}; }}
QTreeView::item:disabled, QListView::item:disabled {{ color: {c.muted}; }}
QTreeView[keyfocus="true"]::item:focus, QListView[keyfocus="true"]::item:focus,
QTableView[keyfocus="true"]::item:focus {{
    border: 2px solid {c.accent}; border-radius: {r1}px;
}}
QTableView[keyfocus="true"], QGraphicsView[keyfocus="true"] {{ {ring}; }}

QAbstractScrollArea::corner {{ background: transparent; border: none; }}

QWidget#dock_title_bar {{ background: {c.window}; }}
QLabel#dock_title {{ color: {c.text}; }}
QToolBar#node_toolbar {{ padding: 0 {2 * u}px {u}px {2 * u}px; }}
QGraphicsView#node_view {{ border: 1px solid {c.border}; }}
QLabel#node_status {{ color: {c.muted}; padding: {u}px {3 * u}px; }}

QGroupBox {{ border-radius: {r2}px; }}
QFrame#panel_group {{ border-radius: {r2}px; }}
QLabel#field_info {{ font-size: {CAPTION_PX}px; }}
QFrame#view_focus {{ border: 2px solid transparent; border-radius: 0; }}
QFrame#view_focus[keyfocus="true"] {{ border-color: {c.accent}; }}
"""
