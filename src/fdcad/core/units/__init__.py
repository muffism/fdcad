"""Units and expressions: parse what the user types into millimetres, radians or plain numbers.

The rules are in `FDEF_SPEC.md` section 12 and DECISIONS D66.
"""

from fdcad.core.units.errors import CircularReferenceError, ExpressionError
from fdcad.core.units.expressions import Kind, UnitSystem, evaluate
from fdcad.core.units.variables import VariableDef, evaluate_variables

__all__ = [
    "CircularReferenceError",
    "ExpressionError",
    "Kind",
    "UnitSystem",
    "VariableDef",
    "evaluate",
    "evaluate_variables",
]
