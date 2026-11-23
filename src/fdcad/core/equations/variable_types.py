"""Text and yes or no variables, and variable groups (TR417, D2104).

``Variable.type`` is "" for a number (length, angle or plain number, as before),
``"text"`` or ``"yes_no"``. A text variable holds its text in ``expr``; it is not a
name formulas can use, but sketch text fields (TR54) and design table cells show it.
A yes or no variable is a number that is 1 or 0: its value is typed as yes, no,
true or false, or as a formula (a comparison gives 1 or 0), so formulas and tick
box formulas (TR275) can use it. ``Variable.group`` puts variables together in the
equations manager. No Qt.
"""

from __future__ import annotations

from fdcad.core.document.model import Variable

TYPES = ("", "text", "yes_no")
YES = ("yes", "true", "y", "on")
NO = ("no", "false", "n", "off")


def is_text(var: Variable) -> bool:
    """True for a text variable."""
    return var.type == "text"


def is_yes_no(var: Variable) -> bool:
    """True for a yes or no variable."""
    return var.type == "yes_no"


def is_word(expr: str) -> bool:
    """True when ``expr`` is yes, no, true or false (any case)."""
    return expr.strip().lower() in YES + NO


def number_expr(var: Variable) -> str:
    """The expression the equations solve for ``var``: a yes or no word becomes 1 or 0."""
    word = var.expr.strip().lower()
    if is_yes_no(var) and word in YES:
        return "1"
    if is_yes_no(var) and word in NO:
        return "0"
    return var.expr


def shown(var: Variable) -> str:
    """The variable as text fields show it: the text, Yes or No, or None for numbers."""
    if is_text(var):
        return var.expr
    return "Yes" if var.value != 0 else "No"


def guess_type(expr: str, old: Variable | None) -> str:
    """The type a manager row keeps: the old variable's, or yes or no for a new row
    typed as a yes or no word."""
    if old is not None and old.type:
        return old.type
    return "yes_no" if is_word(expr) else ""
